"""Portal collector - preference-shaped queries, all four portals.

Fetches every posting a portal serves for a query built from the user's
preferences: role keywords + location + freshness + seniority, in each
portal's native form. Onsite, compensation, language,
and domains are NOT query inputs; they are applied downstream.
Keyword-less fetching is deliberately not a mode (removed 2026-09-18 by
Shashank's decision; the boundedness of the role list is an acknowledged
limitation). Postings land in an append-only ledger (data/ledger.tsv);
every run writes per-cell accounting to data/runs.tsv.

Status vocabulary written to the run log:
  ok          cell fetched, per-page invariant held
  PAGE_SHORT  a non-final page read fewer cards than the portal's page
              size: reader bug, treat as failure
  OVERFLOW    claimed count at the portal's enumeration cap; the cell is
              NOT fully reachable through one query
  PARTIAL     stopped by --max-pages (diagnostic runs only)
  BLOCKED     bot-protection page served; stop immediately and never
              retry into a raised flag (retries deepen it; recovery
              takes hours). If the flag persists across a cool-down,
              clear that site's cookies (clear_naukri.py) and re-login
  NETERR      connection reset three times; stop, cool down hours

Proof obligations enforced here:
  1. Exhaustiveness, per page: every page before the last must yield a
     full page of NEW cards, else the run fails as PAGE_SHORT. The
     claimed-count comparison is advisory (claimed is a moving snapshot).
     Claimed >= cap stamps OVERFLOW (never truncate silently).
  2. Containment (subcommand `verify`): keyword queries over the SAME
     bounds must return only postings already in the harvest. A miss
     prints as LEAK with the escaped posting.

Subcommands:
  fetch  --portal {linkedin,stepstone,naukri,indeed} --location L --hours H --query "Q"
  verify --portal ... --location L --hours H --queries "Q1" "Q2" ...
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_DIR = "/home/shashaank/.playwright-profiles/jobs"
DATA_DIR = Path(__file__).resolve().parent / "data"
LEDGER = DATA_DIR / "ledger.tsv"
RUNLOG = DATA_DIR / "runs.tsv"
# posted_at and reposted are exact values the LinkedIn API supplies. The
# DOM-scraping portals leave them empty, and empty means unknown rather than
# false, so nothing downstream may read a blank reposted as "not a repost".
LEDGER_COLS = ["first_seen", "portal", "portal_id", "title", "company",
               "location_text", "age_text", "posted_at", "reposted",
               "experience", "salary", "url", "cell"]
PACING_MS = 3000

INDEED_DOMAINS = {"Germany": "de", "Netherlands": "nl", "India": "in",
                  "Sweden": "se", "Finland": "fi", "Belgium": "be",
                  "Norway": "no", "Denmark": "dk", "France": "fr",
                  "Italy": "it", "Switzerland": "ch"}
INDEED_LOC = {"Germany": "Deutschland"}  # local-language forms where needed


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hyphen(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def ledger_ids(portal):
    if not LEDGER.exists():
        return set()
    with LEDGER.open() as f:
        return {r["portal_id"] for r in csv.DictReader(f, delimiter="\t")
                if r["portal"] == portal}


def ledger_append(rows):
    DATA_DIR.mkdir(exist_ok=True)
    new_file = not LEDGER.exists()
    with LEDGER.open("a", newline="") as f:
        # restval keeps a portal that supplies fewer fields from shifting the
        # columns of every row after it
        w = csv.DictWriter(f, fieldnames=LEDGER_COLS, delimiter="\t",
                           restval="", extrasaction="ignore")
        if new_file:
            w.writeheader()
        w.writerows(rows)


def runlog_append(cell, claimed, collected, status):
    DATA_DIR.mkdir(exist_ok=True)
    new_file = not RUNLOG.exists()
    with RUNLOG.open("a", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        if new_file:
            w.writerow(["ts", "cell", "claimed", "collected", "status"])
        w.writerow([now_iso(), cell, claimed, collected, status])




AGE_RE = re.compile(
    r"(?:vor\s+)?(\d+)\s*(minute|min|stunde|hour|tag|day|woche|week|monat|month)|"
    r"(\d+)\s*(minute|hour|day|week|month)s?\s+ago", re.I)
AGE_HOURS = {"minute": 1/60, "min": 1/60, "stunde": 1, "hour": 1,
             "tag": 24, "day": 24, "woche": 168, "week": 168,
             "monat": 720, "month": 720}


def age_hours(text):
    """Parse 'vor 8 Stunden' / '2 days ago' etc. to hours; None if unknown."""
    m = AGE_RE.search(text or "")
    if not m:
        return None
    n = int(m.group(1) or m.group(3))
    unit = (m.group(2) or m.group(4)).lower().rstrip("ns")
    for k, h in AGE_HOURS.items():
        if unit.startswith(k[:3]):
            return n * h
    return None


def strict_subset(found, loc, hours):
    """Keep keyword results that actually satisfy the cell bounds; portals
    pad sparse queries with relaxed results (older, other locations), which
    belong to other cells or no cell, never to this containment test."""
    city = loc.split(",")[0].strip().lower()
    keep, dropped = {}, 0
    for jid, (t, c, lo, age) in found.items():
        a = age_hours(age)
        age_ok = a is not None and a <= hours + 2
        loc_ok = (not lo) or (city in lo.lower()) or city in ("germany",)
        if age_ok and loc_ok:
            keep[jid] = (t, c, lo, age)
        else:
            dropped += 1
    return keep, dropped


# ---------------- LinkedIn API records ----------------
# The search page fetches voyagerJobsDashJobCards and renders it. Reading that
# response instead of the rendered list removes the whole class of bugs that
# came from racing a virtualized list, where a card's id exists before its
# content does, so a reader could capture an empty card and never revisit it.
# Every field below is a typed value in the payload, not a line of text at a
# guessed position.

def linkedin_csrf(cookies):
    """The csrf token voyager requires is the JSESSIONID cookie, unquoted."""
    for ck in cookies:
        if ck["name"] == "JSESSIONID":
            return ck["value"].strip('"')
    return None


def _li_text(obj, key):
    v = obj.get(key)
    return (v.get("text") or "").strip() if isinstance(v, dict) else ""


def linkedin_records(payload):
    """(rows, total) from one voyagerJobsDashJobCards response.

    Two JobPostingCard objects exist per posting, one for the search list and
    one prefetched for the detail pane, so only the JOBS_SEARCH cards are read.
    """
    inc = payload.get("included") or []
    posts = {o.get("entityUrn"): o for o in inc
             if o.get("$type", "").endswith(".jobs.JobPosting")}
    rows = {}
    for card in inc:
        if not card.get("$type", "").endswith("JobPostingCard"):
            continue
        if "JOBS_SEARCH" not in (card.get("entityUrn") or ""):
            continue
        urn = card.get("jobPostingUrn") or ""
        jid = urn.split(":")[-1]
        if not jid:
            continue
        listed = None
        for item in card.get("footerItems") or []:
            if item.get("type") == "LISTED_DATE" and item.get("timeAt"):
                listed = int(item["timeAt"])
        post = posts.get(urn) or {}
        rows[jid] = {
            "title": card.get("jobPostingTitle") or _li_text(card, "title"),
            "company": _li_text(card, "primaryDescription"),
            # carries the workplace type in parentheses, e.g. "Berlin ... (Hybrid)"
            "location_text": _li_text(card, "secondaryDescription"),
            "posted_at": (datetime.fromtimestamp(listed / 1000, timezone.utc)
                          .strftime("%Y-%m-%dT%H:%M:%SZ") if listed else ""),
            "age_text": "",
            "reposted": ("true" if post.get("repostedJob") else
                         "false" if post.get("repostedJob") is False else ""),
            "url": f"https://www.linkedin.com/jobs/view/{jid}/",
        }
    total = (((payload.get("data") or {}).get("paging") or {}).get("total"))
    return rows, total


def linkedin_incomplete(rows):
    """Records missing any field the API is known to always supply."""
    need = ("title", "company", "location_text", "posted_at")
    return [j for j, r in rows.items() if any(not r[k] for k in need)]


# ---------------- Naukri API records ----------------
# The search page fetches jobapi/v3/search and renders it. A direct call to that
# endpoint is refused with HTTP 406 "recaptcha required", because the page signs
# each request with an nkparam header, so the reader does not call it. It drives
# the site the documented way, by clicking the Next control at human pacing, and
# reads the response the page fetched for itself.
#
# This replaces reading the rendered cards, which dropped the location entirely
# and wrote the experience range into the age column, leaving every Naukri row
# without a posting age. Verified 2026-10-01: 20 typed records per page, no
# missing fields, createdDate as epoch milliseconds.

NAUKRI_API_MATCH = "jobapi/v3/search"


def naukri_records(payload):
    """(rows, total) from one jobapi/v3/search response."""
    rows = {}
    for j in payload.get("jobDetails") or []:
        jid = str(j.get("jobId") or "")
        if not jid:
            continue
        ph = {p.get("type"): p.get("label") for p in (j.get("placeholders") or [])}
        created = j.get("createdDate")
        sal = j.get("salaryDetail") or {}
        # hideSalary means the employer withheld it, which is different from the
        # field being absent, so the label is kept as the portal rendered it
        rows[jid] = {
            "title": (j.get("title") or "").strip(),
            "company": (j.get("companyName") or "").strip(),
            "location_text": (ph.get("location") or "").strip(),
            "age_text": "",
            "posted_at": (datetime.fromtimestamp(int(created) / 1000, timezone.utc)
                          .strftime("%Y-%m-%dT%H:%M:%SZ") if created else ""),
            "reposted": "",
            "experience": (ph.get("experience") or j.get("experienceText") or "").strip(),
            "salary": (ph.get("salary") or "").strip(),
            "url": ("https://www.naukri.com" + j["jdURL"]) if j.get("jdURL") else "",
            # The payload already carries the full description, so a Naukri
            # posting never needs a second page load. The underscore keeps it out
            # of the ledger columns, since the ledger writer ignores extras.
            "_description": (j.get("jobDescription") or "").strip(),
        }
    return rows, payload.get("noOfJobs")


def naukri_incomplete(rows):
    need = ("title", "company", "location_text", "posted_at", "url")
    return [j for j, r in rows.items() if any(not r[k] for k in need)]


# ---------------- Stepstone state records ----------------
# The page embeds its own state as window.__PRELOADED_STATE__ and renders from
# it. Reading that instead of the cards gives datePosted as an exact timestamp,
# which the rendered list only shows as German relative text such as
# "vor 1 Woche". Stepstone has no API in its network responses, so there is
# nothing to call. Verified 2026-10-01 over 4 pages and 135 records: the blob's
# ids and the rendered ids matched exactly both ways, with no empty fields.
# salary is empty on every record and isWorkFromHomePossible appears on about a
# quarter, so neither is read.

STEPSTONE_STATE_JS = ("()=>window.__PRELOADED_STATE__ "
                      "? JSON.stringify(window.__PRELOADED_STATE__) : null")


def _stepstone_walk(node, out):
    if isinstance(node, dict):
        if "datePosted" in node and node.get("id") is not None:
            out[str(node["id"])] = node
        for v in node.values():
            _stepstone_walk(v, out)
    elif isinstance(node, list):
        for v in node:
            _stepstone_walk(v, out)


def stepstone_records(state_json):
    """{id: row} from the page's embedded state.

    The postings are found by shape rather than by path, because the path into
    the state is Stepstone's own and a reshuffle there would silently return
    nothing. A posting is any object carrying both an id and a datePosted.
    """
    rows = {}
    found = {}
    _stepstone_walk(json.loads(state_json), found)
    for jid, o in found.items():
        url = o.get("url") or ""
        if url.startswith("/"):
            url = "https://www.stepstone.de" + url
        rows[jid] = {
            "title": (o.get("title") or "").strip(),
            "company": (o.get("companyName") or "").strip(),
            "location_text": (o.get("location") or "").strip(),
            "age_text": "",
            # the state writes either a bare local timestamp or one with an
            # offset, measured both ways, so it is kept verbatim and whatever
            # reads it downstream has to handle both forms
            "posted_at": (o.get("datePosted") or "").strip(),
            "reposted": "",
            "experience": "",
            "salary": "",
            "url": url.split("?")[0],
        }
    return rows


def stepstone_incomplete(rows):
    need = ("title", "company", "location_text", "posted_at", "url")
    return [j for j, r in rows.items() if any(not r[k] for k in need)]


def blocked(body):
    return ("Access Denied" in body or "Additional Verification Required" in body
            or "verify you are human" in body.lower())


# ================= LinkedIn =================
# Virtualized list: harvest DURING scroll. Pagination via &start=25n. Cap 1000.

class LinkedIn:
    name, cap, page_size = "linkedin", 1000, 25

    def url(self, loc, hours, kw, offset):
        q = {"location": loc, "f_TPR": f"r{hours * 3600}",
             "f_E": "2,3,4",  # Entry/Associate/Mid-Senior, verified 2026-09-19
             "sortBy": "DD", "start": str(offset)}
        if kw:
            q["keywords"] = kw
        return "https://www.linkedin.com/jobs/search/?" + urllib.parse.urlencode(q)

    def claimed(self, page):
        for t in page.locator("small.jobs-search-results-list__text, "
                              "div.jobs-search-results-list__subtitle").all_inner_texts():
            m = re.search(r"([\d.,]+)\+?\s*results?", t)
            if m:
                return int(re.sub(r"[.,]", "", m.group(1)))
        return None

    _EXTRACT_JS = """
    () => Array.from(document.querySelectorAll('li[data-occludable-job-id]')).map(li => {
        const id = li.getAttribute('data-occludable-job-id');
        const lines = li.innerText.split('\\n').map(s => s.trim()).filter(Boolean);
        const title = lines[0] || '';
        const rest = lines.slice(1).filter(l => l !== title);
        const age = lines.find(l => / ago/.test(l)) || '';
        return [id, title, rest[0] || '', rest[1] || '', age];
    })
    """

    def harvest_page(self, page):
        # Virtualized list: cards hydrate as they scroll into view and can be
        # evicted. So ACCUMULATE across scroll steps via a single JS DOM pass
        # each step (proven to read all 25/page), stopping when several steps
        # in a row add nothing new. Fixed, patient scrolling, no early plateau.
        seen, stale = {}, 0
        for _ in range(50):
            added = 0
            for row in page.evaluate(self._EXTRACT_JS):
                jid = row[0]
                if jid and jid not in seen:
                    seen[jid] = (row[1], row[2], row[3], row[4])
                    added += 1
            stale = 0 if added else stale + 1
            if stale >= 5:
                break
            lis = page.locator("li[data-occludable-job-id]")
            if lis.count():
                try:
                    lis.nth(lis.count() - 1).scroll_into_view_if_needed(timeout=3000)
                except Exception:
                    pass
            page.wait_for_timeout(500)
        return seen

    def job_url(self, jid):
        return f"https://www.linkedin.com/jobs/view/{jid}/"


# ================= Stepstone =================
# Server-rendered list, 25/page, page=N param. Ids from job links.

class Stepstone:
    name, cap, page_size = "stepstone", 100 * 25, 25

    def url(self, loc, hours, kw, offset):
        age = "age_1" if hours <= 24 else "age_7"
        place = "deutschland" if loc == "Germany" else hyphen(
            loc.lower().replace("\u00fc", "ue").replace("\u00f6", "oe")
               .replace("\u00e4", "ae").replace("\u00df", "ss"))
        path = (f"/jobs/{hyphen(kw)}/in-{place}" if kw else f"/jobs/in-{place}")
        return (f"https://www.stepstone.de{path}?ag={age}"
                f"&page={offset // self.page_size + 1}")

    def claimed(self, page):
        m = re.search(r"([\d.,]+)\s*(?:Jobs|Stellenangebote|Treffer|Ergebnisse)",
                      page.inner_text("body"))
        return int(re.sub(r"[.,]", "", m.group(1))) if m else None

    _EXTRACT_JS = """()=>Array.from(document.querySelectorAll("[data-at='job-item']"))
     .map(el=>{
       const a=el.querySelector("a[data-at='job-item-title']")||{};
       const g=s=>{const e=el.querySelector(`[data-at='${s}']`);return e?e.innerText.trim():''};
       const href=a.href||''; const m=href.match(/--(\\d+)-inline\\.html|--(\\d+)\\.html/);
       return [m?(m[1]||m[2]):null,(a.innerText||'').trim(),
               g('job-item-company-name'),g('job-item-location'),g('job-item-timeago')];
     })"""

    def harvest_page(self, page):
        out = {}
        for jid, t, c, lo, age in page.evaluate(self._EXTRACT_JS):
            if jid:
                out[jid] = (t, c, lo, age)
        return out

    def job_url(self, jid):
        return f"https://www.stepstone.de/stellenangebote--{jid}-inline.html"


# ================= Naukri =================
# Server-rendered, 20 cards/page, ids on div.srp-jobtuple-wrapper[data-job-id].
# ACCESS PROTOCOL (established empirically 2026-09-18/19): headed only;
# one session, never parallel; jittered 15-35 s pacing; paginate by
# clicking the site's Next control, not fresh URL loads; stop the whole
# cell on the first anomaly. KNOWN PENDING ITEMS (not yet decided or
# not yet aligned - do not treat this class as final):
#   - pagination here is still URL-based (/jobs-in-<city>-<page>); the
#     verified-safe method is CLICKING the site's Next control. Align before
#     production use.
#   - jobAge accepts specific values only; 1 and 7 verified, 2 was silently
#     IGNORED (observed 2026-09-19). Freshness encoding awaits Shashank's
#     decision (jobAge=1 daily vs jobAge=3 + downstream 48 h cut).
#   - seniority (experience=N, semantics verified: job's range contains N)
#     and salary (native bands 15-25/25-50/... Lakhs) encodings also await
#     Shashank's decision.
#   - role slugs degrade for "R&D Engineer" and "C++ Developer"; their
#     portal-native forms are still to be discovered from Naukri's search box.

class Naukri:
    name, cap, page_size = "naukri", 250 * 20, 20
    pacing_ms = 9000

    def url(self, loc, hours, kw, offset):
        days = max(1, round(hours / 24))
        page_no = offset // self.page_size + 1
        base = f"{hyphen(kw)}-jobs-in-{hyphen(loc)}" if kw else f"jobs-in-{hyphen(loc)}"
        if page_no > 1:
            base += f"-{page_no}"
        return f"https://www.naukri.com/{base}?jobAge={days}"

    def claimed(self, page):
        m = re.search(r"of\s+([\d.,]+)", page.inner_text("body"))
        return int(re.sub(r"[.,]", "", m.group(1))) if m else None

    def harvest_page(self, page):
        out = {}
        for div in page.locator("div.srp-jobtuple-wrapper[data-job-id]").all():
            try:
                jid = div.get_attribute("data-job-id")
                lines = [l.strip() for l in div.inner_text().split("\n") if l.strip()]
                link = div.locator("a.title").first.get_attribute("href")
            except Exception:
                continue
            if jid and lines:
                out[jid] = (lines[0], lines[1] if len(lines) > 1 else "",
                            "", link or "")
        return out

    def job_url(self, jid):
        return jid  # real link stored in age_text slot at append time


# ================= Indeed =================
# Fragile (Cloudflare). 15/page via &start=10n. Challenge => abort cell.

class Indeed:
    name, cap, page_size = "indeed", 1000, 15

    def url(self, loc, hours, kw, offset):
        cc = INDEED_DOMAINS.get(loc.split(",")[0].strip())
        if not cc:
            raise SystemExit(f"indeed: no domain for {loc}")
        days = max(1, round(hours / 24))
        q = {"l": INDEED_LOC.get(loc, loc), "fromage": str(days),
             "sort": "date", "start": str(offset)}
        if kw:
            q["q"] = kw
        return f"https://{cc}.indeed.com/jobs?" + urllib.parse.urlencode(q)

    def claimed(self, page):
        m = re.search(r"([\d.,]+)\+?\s*(?:jobs|Jobs|Stellenanzeigen)",
                      page.inner_text("body"))
        return int(re.sub(r"[.,]", "", m.group(1))) if m else None

    def harvest_page(self, page):
        out = {}
        for a in page.locator("a[data-jk]").all():
            try:
                jid = a.get_attribute("data-jk")
                lines = [l.strip() for l in a.inner_text().split("\n") if l.strip()]
            except Exception:
                continue
            if jid:
                out[jid] = (lines[0] if lines else "",
                            lines[1] if len(lines) > 1 else "",
                            lines[2] if len(lines) > 2 else "", "")
        return out

    def job_url(self, jid):
        return f"https://de.indeed.com/viewjob?jk={jid}"


PORTALS = {p.name: p for p in (LinkedIn(), Stepstone(), Naukri(), Indeed())}


# ================= shared driving loop =================

def collect(page, portal, loc, hours, kw=None, label="", max_pages=None):
    """Paginate one query to exhaustion. Returns (claimed, {id: card}, status)."""
    seen, claimed, offset = {}, None, 0
    pages_done = 0
    pacing = getattr(portal, "pacing_ms", PACING_MS)
    while True:
        if max_pages is not None and pages_done >= max_pages:
            return claimed, seen, f"PARTIAL max_pages={max_pages}"
        url = portal.url(loc, hours, kw, offset)
        for attempt in range(3):
            try:
                page.goto(url, wait_until="domcontentloaded")
                break
            except Exception as e:
                print(f"  [{label}] goto failed (attempt {attempt + 1}): "
                      f"{str(e).splitlines()[0][:90]}")
                if attempt == 2:
                    return claimed, seen, "NETERR"
                time.sleep(12 * (attempt + 1))
        page.wait_for_timeout(pacing + 2000)
        body = page.inner_text("body")
        if blocked(body):
            return claimed, seen, "BLOCKED"
        if claimed is None:
            claimed = portal.claimed(page)
        page_cards = portal.harvest_page(page)
        fresh = [j for j in page_cards if j not in seen]
        seen.update(page_cards)
        last_page = (not fresh or (claimed is not None
                     and offset + portal.page_size >= min(claimed, portal.cap)))
        print(f"  [{label}] offset={offset} cards={len(page_cards)} "
              f"new={len(fresh)} total={len(seen)}")
        # Per-page invariant: every page before the last must yield a FULL
        # page of cards read. Checked per page, independent of the claimed
        # snapshot, so a dropped card fails loudly instead of being masked
        # by postings arriving mid-run. Measured on len(page_cards), not on
        # fresh: portals legitimately repeat a promoted card across pages
        # (Stepstone showed 25 cards / 24 new), and a repeat is portal
        # behavior while a missing card is our reader losing data. Only
        # enforced when a claimed count says more pages should exist.
        if (not last_page and claimed is not None
                and len(page_cards) < portal.page_size):
            return claimed, seen, (f"PAGE_SHORT offset={offset} "
                                   f"cards={len(page_cards)}/{portal.page_size}")
        if last_page:
            break
        offset += portal.page_size
        pages_done += 1
        time.sleep(pacing / 1000)
    return claimed, seen, "ok"


def open_profile(p):
    b = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR, channel="chrome", headless=False)
    return b, (b.pages[0] if b.pages else b.new_page())


def cmd_enumerate(args):
    portal = PORTALS[args.portal]
    cell = f"{portal.name}|{args.location}|{args.hours}h|{args.query}"
    known = ledger_ids(portal.name)
    with sync_playwright() as p:
        b, page = open_profile(p)
        claimed, harvest, status = collect(page, portal, args.location,
                                           args.hours, kw=args.query,
                                           label=cell,
                                           max_pages=args.max_pages)
        b.close()

    if status == "ok":
        if claimed is not None and claimed >= 0.9 * portal.cap:
            status = f"OVERFLOW claimed={claimed} cap={portal.cap}: shorten window"
        elif claimed is not None and len(harvest) < 0.95 * claimed:
            # advisory only: claimed is a moving snapshot; the hard
            # completeness guarantee is the per-page invariant in collect()
            status = f"ok (advisory: collected {len(harvest)} vs claimed {claimed})"
    rows = [{"first_seen": now_iso(), "portal": portal.name, "portal_id": jid,
             "title": t, "company": c, "location_text": lo, "age_text": a,
             "url": portal.job_url(jid), "cell": cell}
            for jid, (t, c, lo, a) in harvest.items() if jid not in known]
    ledger_append(rows)
    runlog_append(cell, claimed, len(harvest), status)
    print(f"claimed={claimed} collected={len(harvest)} "
          f"new-to-ledger={len(rows)} status={status}")
    return 0 if status == "ok" else 1


def cmd_verify(args):
    portal = PORTALS[args.portal]
    cell = f"{portal.name}|{args.location}|{args.hours}h"
    harvest_ids = ledger_ids(portal.name)
    if not harvest_ids:
        print(f"Ledger empty for {portal.name}. Run enumerate first.")
        return 2
    failures = 0
    with sync_playwright() as p:
        b, page = open_profile(p)
        for kw in args.queries:
            claimed, found, status = collect(page, portal, args.location,
                                             args.hours, kw=kw,
                                             label=f"verify:{kw}")
            if status == "BLOCKED":
                print(f"VERIFY '{kw}': BLOCKED, no verdict")
                runlog_append(f"verify|{cell}|{kw}", claimed, len(found), "BLOCKED")
                failures += 1
                continue
            strict, dropped = strict_subset(found, args.location, args.hours)
            missing = [jid for jid in strict if jid not in harvest_ids]
            verdict = "CONTAINED" if not missing else f"LEAK {len(missing)} missing"
            print(f"VERIFY '{kw}': raw={len(found)} in-bounds={len(strict)} "
                  f"relaxed-padding={dropped} -> {verdict}")
            for jid in missing[:10]:
                t = strict[jid]
                print(f"   MISSING {jid} | {t[0]} | {t[1]} | {t[2]}")
            runlog_append(f"verify|{cell}|{kw}", claimed, len(strict), verdict)
            if missing:
                failures += 1
            time.sleep(PACING_MS / 1000)
        b.close()
    print("ALL CONTAINED" if failures == 0 else f"{failures} QUERY(S) FAILED")
    return 0 if failures == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("fetch", "verify"):
        s = sub.add_parser(name)
        s.add_argument("--portal", required=True, choices=sorted(PORTALS))
        s.add_argument("--location", required=True)
        s.add_argument("--hours", type=int, default=6)
        s.add_argument("--max-pages", type=int, default=None)
        if name == "fetch":
            s.add_argument("--query", required=True)
        else:
            s.add_argument("--queries", nargs="+", required=True)
    args = ap.parse_args()
    sys.exit(cmd_enumerate(args) if args.cmd == "fetch" else cmd_verify(args))


if __name__ == "__main__":
    main()
