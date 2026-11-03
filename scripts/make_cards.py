"""Turn collected ledger rows into job cards, screening first.

This is the stage between the sweep and the board. The sweep writes every row a
portal served, which is deliberately more than the preferences allow, because a
portal pads a sparse query and its own age facet is coarse. Screening therefore
happens here rather than at collection.

Every rejecting rule lives in `screen.py` and none lives in this file, so there is
one definition of what is out of scope.

The run begins by checking `screen.py` against every posting he has ruled on, held
in `scripts/data/screen-cases.tsv`. A broken ruling stops the run, because a rule
that is written down and not enforced is how the same posting reached the board
twice.

Order, cheapest first.
  1. drop rows already on a card, by portal id
  2. drop rows outside the freshness window
  3. screen_title, which reads the title and the lister only and costs nothing
  4. one advert per company and title
  5. fetch the description for what survives
  6. screen_description, which is where the real screening happens
  7. write a card from templates/job entry.md and a line for the matched column

A card that reaches the board has passed both screen stages. Nothing scores it.
He reads the card, and moving it to the `to apply` column is the judgement that
releases it to artifact generation.

The template is read from disk and never copied into this file, so the card format
has exactly one definition.

Run:
  .venv/bin/python scripts/make_cards.py --dry-run     report what would be built
  .venv/bin/python scripts/make_cards.py --limit 20    build at most 20 cards
"""

import argparse
import csv
import datetime as dt
import re
import sys
import unicodedata
from functools import partial
from pathlib import Path

from playwright.sync_api import sync_playwright

import collect as C
import jd_extract
import matrix as MX
import places
import screen
import test_screen

print = partial(print, flush=True)

VAULT = Path(__file__).resolve().parent.parent
CARDS = VAULT / "application artifacts" / "job cards"
TEMPLATE = VAULT / "templates" / "job entry.md"
BOARD = VAULT / "01. job application tracker.md"
LEDGER = VAULT / "scripts" / "data" / "ledger.tsv"
DESCRIPTIONS = VAULT / "scripts" / "data" / "descriptions"

# A new card always enters this column. He weighs the description himself and
# moves it onward, so nothing downstream of scoring places a card anywhere else.
NEW_CARD_COLUMN = "matched"


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def safe_name(s):
    """A filename the board link can carry. Generated, never hand written."""
    return re.sub(r"[^\w &+.-]+", " ", s).strip()[:120]


def posted_at_of(row):
    """The row's posting time, exact where the portal gave one."""
    raw = (row.get("posted_at") or "").strip()
    if raw:
        try:
            # Stepstone writes a bare local timestamp, the others write UTC with Z
            return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    hours = C.age_hours(row.get("age_text"))
    if hours is None:
        return None
    return dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)


def within_window(row, hours):
    """Freshness is a hard preference, and an unknown age is not a pass."""
    t = posted_at_of(row)
    if t is None:
        return False, "no posting date"
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    age = (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 3600
    if age > hours + 2:          # two hours of slack for the run's own duration
        return False, f"{age/24:.1f} days old"
    return True, ""


# LinkedIn serves the description as plain HTML to a logged-out visitor, because it
# wants the posting indexed. So a description is an ordinary HTTP fetch rather than a
# browser page load, and it sends no cookies, which is the point. Volume on this path
# throttles an anonymous address and can never cost him his LinkedIn account.
#
# Measured 2026-10-02. Five concurrent ran 20 requests in 1.5 s with no refusals.
# Ten concurrent reached 23 requests a second and LinkedIn returned 9 rate limits out
# of 40, so five is the setting and ten is the ceiling.
GUEST_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/154.0.0.0 Safari/537.36")
GUEST_EP = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{jid}"
GUEST_WORKERS = 5


def guest_description(jid):
    """(text, error) for one posting, over the anonymous path. No cookies."""
    import urllib.error, urllib.request
    req = urllib.request.Request(GUEST_EP.format(jid=jid), headers={"User-Agent": GUEST_UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, type(e).__name__
    m = re.search(r'show-more-less-html__markup[^>]*>(.*?)</div>', body, re.S)
    if not m:
        return None, "no description block"
    import html as _html
    txt = re.sub(r"<br\s*/?>", "\n", m.group(1))
    txt = re.sub(r"</(p|li|ul|ol|div)>", "\n", txt)
    txt = re.sub(r"<[^>]+>", "", txt)
    txt = _html.unescape(txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
    return (txt, None) if len(txt) >= 200 else (None, f"too short ({len(txt)})")


def fetch_guest_descriptions(rows):
    """Descriptions for LinkedIn rows, five at a time, backing off on a rate limit.

    A sustained rate limit stops this path rather than retrying into it, which is the
    rule the vault already applies to a refusing portal.
    """
    from concurrent.futures import ThreadPoolExecutor
    import time
    out, errors, limited = {}, {}, 0
    batch = list(rows)
    for i in range(0, len(batch), GUEST_WORKERS):
        chunk = batch[i:i + GUEST_WORKERS]
        with ThreadPoolExecutor(max_workers=GUEST_WORKERS) as ex:
            got = list(ex.map(lambda r: (r, guest_description(r["portal_id"])), chunk))
        for r, (txt, err) in got:
            if txt:
                out[r["portal_id"]] = txt
            else:
                errors[r["portal_id"]] = err
                if err == "HTTP 429":
                    limited += 1
        if limited >= 3:
            print(f"  anonymous path rate limited {limited} times, stopping it at "
                  f"{len(out)} of {len(batch)}")
            break
        if limited:
            time.sleep(10)        # back off once rather than pressing on
        else:
            time.sleep(0.4)
        if (i // GUEST_WORKERS) % 10 == 0 and i:
            print(f"  descriptions {len(out)}/{len(batch)}")
    return out, errors


CARDED = VAULT / "scripts" / "data" / "carded.tsv"


def carded_ids():
    """Every id this pipeline has ever written a card for.

    The cards folder used to be the memory, which made the memory as fragile as the
    files. A card deleted in Obsidian, or lost to a mistake of mine, erased the fact
    that the posting had ever been seen, and the next run wrote it again.

    This log is append only and is never pruned, so "carded once" is permanent and a
    deleted card cannot return by itself. `retire_cards.py --forget <id>` is the only
    way back in, which makes letting a posting return a deliberate act.
    """
    if not CARDED.exists():
        return set()
    import csv as _csv
    return {r["portal_id"] for r in _csv.DictReader(CARDED.open(encoding="utf-8"),
                                                    delimiter="\t")}


def log_carded(rows):
    """Append the ids of the cards this run wrote. Called once, after the run."""
    if not rows:
        return
    import csv as _csv
    first = not CARDED.exists()
    with CARDED.open("a", newline="", encoding="utf-8") as fh:
        w = _csv.writer(fh, delimiter="\t", lineterminator="\n")
        if first:
            w.writerow(["portal_id", "portal", "carded_on", "card"])
        for pid, portal, card in rows:
            w.writerow([pid, portal, dt.date.today().isoformat(), card])


def retired_ids():
    """Ids he has already removed from the board, so they are never carded again.

    The cards folder used to be the only memory of a posting, which made deleting a
    card mean "collect this again tomorrow". `retire_cards.py` writes the id here so
    the removal sticks.
    """
    f = VAULT / "scripts" / "data" / "retired.tsv"
    if not f.exists():
        return set()
    import csv as _csv
    return {r["portal_id"] for r in _csv.DictReader(f.open(encoding="utf-8"), delimiter="\t")}


def existing_ids():
    """Portal ids already on a card, so a card is never written twice."""
    ids = set()
    for p in CARDS.glob("*.md"):
        t = p.read_text(encoding="utf-8", errors="replace")
        for m in re.findall(r"(?:jobs/view/|stellenangebote--|job-listings-\S*?-)(\d{6,})", t):
            ids.add(m)
        m = re.search(r"^Posting:\s*(\S+)", t, re.M)
        if m:
            for n in re.findall(r"(\d{6,})", m.group(1)):
                ids.add(n)
    return ids


def card_text(row, jd, posting_date, today, country, title_match, areas, flags):
    """The template, filled. The template file is the only definition."""
    t = TEMPLATE.read_text(encoding="utf-8")
    fields = {
        "Job Title": row["title"].strip(),
        "Company": row["company"].strip(),
        "Location": row["location_text"].strip(),
        "Posting": row["url"].strip(),
        "Posting date": posting_date,
        "Discovery date": today,
    }
    for key, val in fields.items():
        t, n = re.subn(rf"^{re.escape(key)}:\s*$", f"{key}: {val}", t, count=1, flags=re.M)
        if n != 1:
            raise SystemExit(f"template has no empty '{key}:' field, refusing to guess")
    # the description replaces the placeholder line under its own heading
    placeholder = "Raw text from the posting goes here - before evaluation "
    if placeholder not in t:
        raise SystemExit("template placeholder for the job description has changed, refusing to guess")
    t = t.replace(placeholder, jd)

    # The screen's own reading, in the Evaluation section. Nothing scores the card,
    # so this records why the posting is on the board and leaves the judgement to
    # him. A flag is a thing to check rather than a verdict.
    ev = "Evaluation results after the job entry's fit is evaluated "
    if ev not in t:
        raise SystemExit("template placeholder for the evaluation has changed, refusing to guess")
    lines = [f"Screened in from {row['portal']}. Country {country}.",
             "",
             f"Title names: {', '.join(title_match.split(',')) or 'nothing recorded'}",
             f"Description names: {', '.join(areas) or 'nothing recorded'}",
             f"Flags: {', '.join(flags) or 'none'}",
             "",
             "The screen rejects, it does not rank. His own reading is the score, and "
             "moving this card to the `to apply` column is what releases it to "
             "artifact generation."]
    return t.replace(ev, "\n".join(lines))


def board_line(fname, row, today):
    return (f"- [ ] [[application artifacts/job cards/{fname[:-3]}"
            f"|{today} - {row['company'].strip()} - {row['title'].strip()}]]")


def add_to_board(lines):
    """Append the new entries under the matched column, leaving the rest alone."""
    out, placed, cur = [], False, None
    for line in BOARD.read_text().splitlines():
        if line.startswith("## "):
            if cur == NEW_CARD_COLUMN and not placed:
                out.extend(lines); placed = True
            cur = line[3:].strip()
        out.append(line)
    if cur == NEW_CARD_COLUMN and not placed:
        out.extend(lines); placed = True
    if not placed:
        raise SystemExit(f"the board has no '{NEW_CARD_COLUMN}' column, refusing to guess")
    BOARD.write_text("\n".join(out) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many cards")
    ap.add_argument("--portal", help="one portal only")
    ap.add_argument("--no-test", action="store_true",
                    help="skip the ruling check. Only for debugging the screen itself")
    args = ap.parse_args()

    # Enforcement. Every posting he has ruled on is a case in
    # scripts/data/screen-cases.tsv, and a broken ruling stops the run rather than
    # producing cards he has already said he does not want. A rule that is only
    # written down is not enforced, which is why this is a gate and not a report.
    if not args.no_test:
        print("checking the screen against his rulings")
        if test_screen.run_cases(places.allowed_countries()):
            raise SystemExit("the screen no longer honours a ruling, refusing to build cards")
        print()

    m = MX.load()
    hours = m.freshness_hours
    rows = list(csv.DictReader(LEDGER.open(), delimiter="\t"))
    print(f"ledger rows {len(rows)}, freshness window {hours} h")

    on_disk = existing_ids()
    ever = carded_ids()
    gone = retired_ids()
    have = on_disk | ever | gone
    print(f"ids on a card file: {len(on_disk)}, carded before: {len(ever)}, "
          f"retired by him: {len(gone)}, skipped in total: {len(have)}")

    allowed = places.allowed_countries()
    print(f"countries from 04. preferences: {', '.join(sorted(allowed))}")

    # ---- title stage. screen.py owns every rule; this loop only counts. ----
    kept, drops, title_rejects = [], {}, []
    for r in rows:
        if args.portal and r["portal"] != args.portal:
            continue
        if r["portal_id"] in have:
            drops["already carded or retired"] = drops.get("already carded or retired", 0) + 1
            continue
        if not within_window(r, hours)[0]:
            drops["stale"] = drops.get("stale", 0) + 1
            continue
        if not r.get("url"):
            drops["no url"] = drops.get("no url", 0) + 1
            continue
        ok, why, flags = screen.screen_title(
            r["title"], r["company"], r["location_text"], r.get("cell"))
        if not ok:
            drops[why] = drops.get(why, 0) + 1
            title_rejects.append((r["title"], r["company"], why))
            continue
        r["company"] = screen.clean_company(r["company"])
        r["_flags"] = list(flags)
        r["_match"] = why
        kept.append(r)

    # newest first, so a capped run takes the freshest
    kept.sort(key=lambda r: posted_at_of(r) or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
              reverse=True)
    # one advert per portal id, then one per company and title, since the same
    # position is listed repeatedly and each copy would otherwise become a card
    seen_id, seen_ad, uniq = set(), set(), []
    for r in kept:
        if r["portal_id"] in seen_id:
            drops["the same posting again"] = drops.get("the same posting again", 0) + 1
            continue
        k = (screen.norm(r["company"]), screen.norm(r["title"]))
        if k in seen_ad:
            drops["the same advert again"] = drops.get("the same advert again", 0) + 1
            continue
        seen_id.add(r["portal_id"]); seen_ad.add(k); uniq.append(r)
    kept = uniq

    print(f"dropped {sum(drops.values())} at the title stage:")
    for k, v in sorted(drops.items(), key=lambda kv: -kv[1]):
        print(f"   {v:5d}  {k}")
    if title_rejects:
        # what the screen removed is written out rather than hidden, so a wrong
        # rejection is visible without rerunning anything
        Path(LEDGER.parent / "title-rejects.txt").write_text(
            "\n".join(f"{t}\t{c}\t{w}" for t, c, w in title_rejects), encoding="utf-8")
        print(f"   written to data/title-rejects.txt")
    by_portal = {}
    for r in kept:
        by_portal[r["portal"]] = by_portal.get(r["portal"], 0) + 1
    print(f"survivors {len(kept)} -> {by_portal}")

    if args.limit:
        kept = kept[:args.limit]
        print(f"capped to {len(kept)}")

    if args.dry_run:
        # the description stage, on what is already stored. A posting with no stored
        # description is reported separately rather than counted either way, because
        # unknown and rejected are different facts.
        pass_, drop, nodesc = 0, {}, 0
        for r in kept:
            f = DESCRIPTIONS / f"{r['portal']}-{r['portal_id']}.md"
            if not f.exists():
                nodesc += 1
                continue
            ok, why, areas, _ = screen.screen_description(
                f.read_text(encoding="utf-8", errors="replace"), r["location_text"],
                allowed, r.get("cell"))
            if ok:
                pass_ += 1
            else:
                k = why.split(" (")[0]
                drop[k] = drop.get(k, 0) + 1
        print(f"\ndescription stage on {len(kept) - nodesc} stored descriptions:")
        for k, v in sorted(drop.items(), key=lambda kv: -kv[1]):
            print(f"   {v:5d}  {k}")
        print(f"would write {pass_} cards into '{NEW_CARD_COLUMN}'")
        print(f"{nodesc} title survivors have no stored description and would be fetched")
        return 0

    CARDS.mkdir(parents=True, exist_ok=True)
    DESCRIPTIONS.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    written, failed, new_lines = 0, [], []
    carded, d_drop = [], {}

    def commit(row, jd):
        """Screen the description, then write the card. The only path to the board.

        A card is written only when the description survives screen.py, so the
        board holds no posting the rules reject. The screen's reading goes onto
        the card, because he reads the card and his reading is the score.
        """
        nonlocal written
        ok, why, areas, dflags = screen.screen_description(
            jd, row["location_text"], allowed, row.get("cell"))
        if not ok:
            d_drop[why.split(" (")[0]] = d_drop.get(why.split(" (")[0], 0) + 1
            return False
        t_posted = posted_at_of(row)
        posting_date = t_posted.date().isoformat() if t_posted else "unknown"
        fname = safe_name(
            f"{row['company'].strip()} - {row['title'].strip()} - {row['portal_id']}") + ".md"
        (CARDS / fname).write_text(
            card_text(row, jd, posting_date, today, why, row.get("_match", ""),
                      areas, row["_flags"] + dflags), encoding="utf-8")
        new_lines.append(board_line(fname, row, today))
        carded.append((row["portal_id"], row["portal"], fname))
        written += 1
        return True

    # stage one, descriptions that cost nothing. Naukri's arrived with the search and
    # LinkedIn's come over the anonymous path, so only Stepstone needs the browser.
    have_desc = {}
    for r in kept:
        f = DESCRIPTIONS / f"{r['portal']}-{r['portal_id']}.md"
        if f.exists() and len(f.read_text(encoding="utf-8", errors="replace")) >= 200:
            have_desc[(r["portal"], r["portal_id"])] = f.read_text(encoding="utf-8")
    print(f"descriptions already stored by the sweep: {len(have_desc)}")

    li_needed = [r for r in kept
                 if r["portal"] == "linkedin" and (r["portal"], r["portal_id"]) not in have_desc]
    if li_needed:
        print(f"fetching {len(li_needed)} LinkedIn descriptions over the anonymous path, "
              f"{GUEST_WORKERS} at a time")
        got, errs = fetch_guest_descriptions(li_needed)
        for jid, txt in got.items():
            (DESCRIPTIONS / f"linkedin-{jid}.md").write_text(txt, encoding="utf-8")
            have_desc[("linkedin", jid)] = txt
        print(f"  got {len(got)}, failed {len(errs)}")
        if errs:
            kinds = {}
            for e in errs.values():
                kinds[e] = kinds.get(e, 0) + 1
            print(f"  failures by kind: {kinds}")

    browser_needed = [r for r in kept if (r["portal"], r["portal_id"]) not in have_desc]
    print(f"needing a browser page load: {len(browser_needed)} "
          f"({', '.join(sorted({r['portal'] for r in browser_needed})) or 'none'})")

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=C.PROFILE_DIR, channel="chrome", headless=False)
        page = browser.pages[0] if browser.pages else browser.new_page()
        naukri_stopped = False

        for i, r in enumerate(kept, 1):
            portal = r["portal"]
            cached = have_desc.get((portal, r["portal_id"]))
            if cached:
                commit(r, cached)
                if i % 25 == 0:
                    print(f"  [{i}/{len(kept)}] cards written {written}")
                continue
            if portal == "naukri" and naukri_stopped:
                failed.append((r, "naukri worker stopped earlier in this run"))
                continue
            try:
                page.goto(r["url"], wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(5000)
                body = page.inner_text("body")
                if C.blocked(body):
                    # one anomaly ends that portal for the whole run
                    if portal == "naukri":
                        naukri_stopped = True
                    failed.append((r, "BLOCKED"))
                    print(f"[{portal}] blocked on {r['portal_id']}, stopping that portal")
                    continue
                jd = jd_extract.extract(page, r["url"])
            except Exception as e:
                if portal == "naukri":
                    naukri_stopped = True
                failed.append((r, f"NETERR {str(e).splitlines()[0][:50]}"))
                continue

            if not jd or len(jd) < 200:
                failed.append((r, f"description too short ({len(jd or '')} chars)"))
                continue

            (DESCRIPTIONS / f"{portal}-{r['portal_id']}.md").write_text(jd, encoding="utf-8")
            if commit(r, jd):
                print(f"  [{i}/{len(kept)}] {portal:10s} card written")

            # per portal pacing, Naukri at human speed
            import random
            page.wait_for_timeout(int(random.uniform(15, 35) * 1000) if portal == "naukri" else 3000)

        browser.close()

    if new_lines:
        add_to_board(new_lines)
    # written after the board, so a crash leaves a card without a log row rather than
    # a log row without a card. The first is recoverable and the second is a posting
    # silently lost for good.
    log_carded(carded)

    if d_drop:
        print(f"\ndescription stage dropped {sum(d_drop.values())}:")
        for k, v in sorted(d_drop.items(), key=lambda kv: -kv[1]):
            print(f"   {v:5d}  {k}")
    print(f"\ncards written {written}, into the '{NEW_CARD_COLUMN}' column")
    print(f"failed to read a description {len(failed)}")
    for r, why in failed[:12]:
        print(f"   {r['portal']:10s} {r['portal_id']:14s} {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
