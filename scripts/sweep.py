"""Portal-parallel sweep driver: one browser, one tab per portal.

Runs the LinkedIn, Stepstone, and Naukri collection workers CONCURRENTLY,
each in its own tab with its own pacing clock, inside the single profile
browser (the profile allows one instance, not one tab). No portal sees a
higher request rate than the serial collector produces; only the waiting
overlaps. Wall-clock becomes max(portal) instead of sum(portals).

Safety rules carried over unchanged, per portal:
  linkedin   ~3 s between pages; PAGE_SHORT invariant on 25-card pages
  stepstone  ~4 s between pages; PAGE_SHORT invariant on 25-card pages
  naukri     one entry navigation per cell, then CLICK-pagination only,
             15-35 s jittered gaps; the first anomaly stops the whole
             Naukri worker (circuit breaker) - other workers continue

Reuses collect.py (untouched) for URL builders, extraction JS, age
parsing, ledger and run-log writers. Results land in the same ledger.

The full production sweep refuses to run while queries.yaml carries
approved: false. The verification slice (--slice) is exempt: it exists
to prove the driver, runs a handful of cells, and is not a production
sweep.

Run:  .venv/bin/python sweep.py --slice     # verification slice
      .venv/bin/python sweep.py             # full matrix (needs approval)
"""

import argparse
import asyncio
import random
import re
import sys
from functools import partial
from pathlib import Path

from playwright.async_api import async_playwright

import collect as C
import matrix as MX

DESCRIPTIONS = Path(__file__).resolve().parent / "data" / "descriptions"

print = partial(print, flush=True)

# The roles, the locations, which portal serves which, the URL shape and each
# portal's native parameter values all live in queries.yaml and are read through
# matrix.py. They used to be Python constants here, which meant editing a
# preference changed nothing in a run while the run still reported success.
MATRIX = MX.load()

# Verification slice: a few cells per portal, enough to prove concurrency. The
# cells are taken from the matrix rather than written out, so a slice can never
# sweep a role or a location the matrix does not carry.
def slice_cells(m):
    def pick(portal, want):
        cells = m.cells(portal)
        chosen = [c for c in cells if c in want]
        return chosen or cells[:len(want)]
    roles = [q for _, q in m.roles]
    return {
        "linkedin": pick("linkedin", [("Norway", roles[0]), ("Denmark", roles[2])]),
        "stepstone": pick("stepstone", [("Germany", roles[2]), ("Germany", roles[0])]),
        "naukri": pick("naukri", [("Bengaluru, India", roles[0])]),
    }

def body_claimed(text, pattern):
    m = re.search(pattern, text or "")
    return int(re.sub(r"[.,]", "", m.group(1))) if m else None


async def body_text(page):
    try:
        return await page.evaluate("()=>document.body.innerText")
    except Exception:
        return ""


def record(portal, cell, claimed, harvest, status, known, extra=""):
    """Append the new rows of one cell to the ledger and log the cell.

    A harvest value is either the DOM readers' positional tuple or the API
    reader's dict. The dict form is preferred, since a named field cannot be
    silently shifted by a change in a portal's markup.
    """
    rows = []
    for jid, v in harvest.items():
        if jid in known:
            continue
        row = {"first_seen": C.now_iso(), "portal": portal, "portal_id": jid,
               "cell": cell}
        if isinstance(v, dict):
            # a reader that already received the description stores it here, so
            # the card stage never fetches it again
            desc = v.pop("_description", "")
            if desc:
                DESCRIPTIONS.mkdir(parents=True, exist_ok=True)
                (DESCRIPTIONS / f"{portal}-{jid}.md").write_text(desc, encoding="utf-8")
            row.update(v)
        else:
            t, c, lo, a, url = v
            row.update({"title": t, "company": c, "location_text": lo,
                        "age_text": a, "url": url})
        rows.append(row)
    C.ledger_append(rows)
    known.update(harvest)
    C.runlog_append(cell, claimed, len(harvest), status)
    print(f"[{portal}] {cell}: claimed={claimed} collected={len(harvest)} "
          f"new={len(rows)} status={status}{extra}")


# ---------------- LinkedIn worker ----------------
# Reads the endpoint the search page itself calls. The previous reader scraped
# the rendered list, which is virtualized: a card's id is in the DOM before its
# content is, so it captured empty cards and, because it never revisited an id
# it had already seen, kept them. On 2026-09-30 that produced 145 of 203 rows
# with no company, no location and no posting age, which left freshness, a hard
# filter, unenforceable on three quarters of the harvest. The endpoint returns
# the same 25 records as typed fields with an exact posting timestamp, so there
# is no render to race and no line position to guess.


async def worker_linkedin(page, cells, known):
    lp = C.PORTALS["linkedin"]
    hours = MATRIX.freshness_hours
    count = MATRIX.api_count("linkedin")

    # One real page load first. It establishes the voyager context the endpoint
    # is served under, and it is where the csrf token comes from.
    await page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    csrf = C.linkedin_csrf(await page.context.cookies())
    if not csrf:
        for loc, role in cells:
            record("linkedin", f"sweep|linkedin|{loc}|{hours}h|{role}",
                   None, {}, "BLOCKED no JSESSIONID", known)
        return

    headers = {"csrf-token": csrf, "x-restli-protocol-version": "2.0.0",
               "accept": "application/vnd.linkedin.normalized+json+2.1"}

    for loc, role in cells:
        cell = f"sweep|linkedin|{loc}|{hours}h|{role}"
        seen, claimed, start, status = {}, None, 0, "ok"
        incomplete = 0
        while True:
            url = MATRIX.api_url("linkedin", loc, role, start)
            try:
                resp = await page.request.get(url, headers=headers)
            except Exception as e:
                status = f"NETERR {str(e).splitlines()[0][:50]}"
                break
            if resp.status != 200:
                # 401 and 403 mean the session is gone, which is a portal-level
                # failure rather than a thin cell, so it is never read as ok
                status = f"BLOCKED http={resp.status}"
                break
            try:
                rows, total = C.linkedin_records(await resp.json())
            except Exception as e:
                status = f"PARSE {str(e).splitlines()[0][:50]}"
                break
            if claimed is None:
                claimed = total
            incomplete += len(C.linkedin_incomplete(rows))
            fresh = [j for j in rows if j not in seen]
            seen.update(rows)
            reachable = min(claimed, lp.cap) if claimed is not None else None
            last = (not rows or not fresh
                    or (reachable is not None and start + count >= reachable))
            # A short page before the end means records were lost, which the API
            # reader should never do, so it fails the cell rather than quietly
            # returning a partial harvest.
            if not last and len(rows) < count:
                status = f"PAGE_SHORT start={start} got={len(rows)}"
                break
            if last:
                if claimed is not None and claimed > lp.cap:
                    status = f"OVERFLOW claimed={claimed} cap={lp.cap}"
                break
            start += count
            await asyncio.sleep(3)
        extra = f" incomplete={incomplete}" if incomplete else ""
        record("linkedin", cell, claimed, seen, status, known, extra)


# ---------------- Stepstone worker ----------------
# Reads the page's own embedded state rather than the rendered cards, so the
# posting date arrives as an exact timestamp instead of German relative text.
# Stepstone has no 48 h facet, so the run sends age_7 and over-collects on
# purpose. The surplus is dropped after the fetch, which is only exact because
# of the timestamp.


async def worker_stepstone(page, cells, known):
    sp = C.PORTALS["stepstone"]
    facet = MATRIX.age_facet("stepstone")
    for loc, role in cells:
        cell = f"sweep|stepstone|{loc}|{facet}|{role}"
        seen, claimed, offset, status = {}, None, 0, "ok"
        incomplete = 0
        while True:
            await page.goto(MATRIX.url("stepstone", loc, role, offset, sp.page_size),
                            wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)
            text = await body_text(page)
            if C.blocked(text):
                status = "BLOCKED"
                break
            if claimed is None:
                claimed = body_claimed(
                    text, r"([\d.,]+)\s*(?:Jobs|Stellenangebote|Treffer|Ergebnisse)")
            state = await page.evaluate(C.STEPSTONE_STATE_JS)
            if not state:
                # The page rendered without its own state, which is a reader
                # fault rather than an empty cell.
                status = "PARSE no embedded state"
                break
            page_cards = C.stepstone_records(state)
            incomplete += len(C.stepstone_incomplete(page_cards))
            fresh = [j for j in page_cards if j not in seen]
            seen.update(page_cards)
            last = (not fresh or (claimed is not None
                    and offset + sp.page_size >= min(claimed, sp.cap)))
            if last:
                break
            offset += sp.page_size
            await asyncio.sleep(4)
        extra = f" incomplete={incomplete}" if incomplete else ""
        record("stepstone", cell, claimed, seen, status, known, extra)


# ---------------- Naukri worker (protocol) ----------------
# Reads the response the search page fetches for itself, rather than the
# rendered cards. The card reader dropped the location on every row and wrote
# the experience range into the age column, so no Naukri row carried a posting
# age and freshness was unenforceable on all of them.
#
# The access protocol is unchanged and is the part that keeps Naukri from
# blocking. One entry navigation per cell, then the site's own Next control with
# a 15 to 35 second jittered gap, and the first anomaly ends the whole worker.
# The endpoint is never called directly, because it is signed per request and a
# direct call is refused as a captcha challenge.


# The documented remedy, from 09. lessons, Naukri, verified 2026-09-30. An
# ERR_HTTP2_PROTOCOL_ERROR or an Access Denied page is the Akamai deny verdict, and
# that verdict rides in three cookies alone, not in the session and not in the IP.
# Dropping them restores access within minutes and needs no re-login, so an
# unattended run can continue. A bare retry into a raised flag deepens it, which is
# why the clear always comes first.
#
# `clear_naukri.py` is the same remedy for a human at a terminal. It cannot be used
# here, because it opens its own browser on the profile and the profile allows one
# instance. So the clear runs through the live context instead.
BOT_COOKIES = ("ak_bmsc", "bm_sv", "bm_mi", "bm_sz", "_abck", "ak_bmsc_sec")


async def clear_bot_state(page, domain="naukri.com"):
    """Drop the bot-protection cookies for one domain. Returns how many went.

    The login cookie, `nauk_at`, is never named here, so the session survives.
    """
    ctx = page.context
    before = {c["name"] for c in await ctx.cookies()
              if domain in (c.get("domain") or "")}
    for name in BOT_COOKIES:
        await ctx.clear_cookies(name=name, domain=re.compile(re.escape(domain)))
    after = {c["name"] for c in await ctx.cookies()
             if domain in (c.get("domain") or "")}
    dropped = sorted(before - after)
    print(f"[naukri] bot state cleared, dropped {dropped or 'nothing'}, "
          f"session cookie present: {'nauk_at' in after}")
    return len(dropped)


async def worker_naukri(page, cells, known):
    days = MATRIX.job_age_days("naukri")
    match = MATRIX.portal("naukri").get("api_response_match", C.NAUKRI_API_MATCH)
    payloads = []

    async def on_response(resp):
        if match in resp.url:
            try:
                payloads.append(await resp.json())
            except Exception:
                pass

    page.on("response", lambda r: asyncio.create_task(on_response(r)))

    for loc, role in cells:
        cell = f"sweep|naukri|{loc}|{days}d|{role}"
        url = MATRIX.url("naukri", loc, role)
        seen, claimed, status, incomplete = {}, None, "ok", 0
        payloads.clear()
        # One attempt, then the documented remedy, then one retry. The breaker trips
        # only when the retry fails too, because a protocol error on its own is the
        # Akamai deny verdict rather than evidence that the account is in trouble.
        failure = None
        for attempt in (1, 2):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            except Exception as e:
                failure = ("NETERR", str(e).splitlines()[0][:70])
            else:
                await page.wait_for_timeout(6000)
                text = await body_text(page)
                failure = ("BLOCKED", "block page") if C.blocked(text) else None
            if failure is None:
                break
            if attempt == 1:
                print(f"[naukri] {failure[0]} on {loc}, {failure[1]}")
                await clear_bot_state(page)
                # The documented remedy was verified with a separate browser launch,
                # so the retry got a new connection. ERR_HTTP2_PROTOCOL_ERROR is a
                # connection-level fault and a reused HTTP/2 connection stays
                # poisoned, so the retry runs on a fresh page.
                try:
                    fresh = await page.context.new_page()
                    fresh.on("response",
                             lambda r: asyncio.create_task(on_response(r)))
                    await page.close()
                    page = fresh
                    print("[naukri] retrying on a fresh page")
                except Exception as e:
                    print(f"[naukri] could not open a fresh page: "
                          f"{str(e).splitlines()[0][:60]}")
                await page.wait_for_timeout(5000)
        if failure is not None:
            record("naukri", cell, None, {}, failure[0], known)
            print(f"[naukri] circuit breaker after the bot-state clear: {failure[1]}")
            return

        def drain():
            """Fold every payload captured so far into the cell's harvest."""
            nonlocal claimed, incomplete
            while payloads:
                rows, total = C.naukri_records(payloads.pop(0))
                if total is not None and claimed is None:
                    claimed = total
                incomplete += len(C.naukri_incomplete(rows))
                for jid, row in rows.items():
                    seen.setdefault(jid, row)

        drain()
        if not seen:
            # The page rendered but its own request produced nothing readable,
            # which is a reader fault rather than an empty cell.
            record("naukri", cell, claimed, {}, "PARSE no payload captured", known)
            print("[naukri] circuit breaker: no payload on the entry page")
            return

        for page_no in range(1, 4):        # page cap, unchanged
            if page_no == 3:
                break
            await asyncio.sleep(random.uniform(15, 35))
            try:
                clicked = await page.evaluate(
                    """()=>{const b=[...document.querySelectorAll('a')]
                        .find(e=>/^next$/i.test((e.innerText||'').trim()));
                        if(b){b.click();return true;} return false;}""")
                if not clicked:
                    break
                await page.wait_for_timeout(6000)
                drain()
            except Exception as e:
                record("naukri", cell, claimed, seen, "NETERR", known)
                print(f"[naukri] circuit breaker: {str(e).splitlines()[0][:70]}")
                return
        extra = f" incomplete={incomplete}" if incomplete else ""
        record("naukri", cell, claimed, seen, status, known, extra)


# ---------------- driver ----------------

async def run(cells_by_portal):
    known = {p: C.ledger_ids(p) for p in ("linkedin", "stepstone", "naukri")}
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=C.PROFILE_DIR, channel="chrome", headless=False)
        pages = {}
        for name in cells_by_portal:
            pages[name] = await browser.new_page()
        # only the portals this run was asked for, so --portal can prove one access
        # path without opening tabs for the others
        workers = {"linkedin": worker_linkedin, "stepstone": worker_stepstone,
                   "naukri": worker_naukri}
        names = [n for n in workers if n in cells_by_portal]
        results = await asyncio.gather(
            *(workers[n](pages[n], cells_by_portal[n], known[n]) for n in names),
            return_exceptions=True)
        for name, r in zip(names, results):
            if isinstance(r, Exception):
                print(f"[{name}] worker crashed: {str(r).splitlines()[0][:80]}")
        await browser.close()


def full_matrix():
    return {p: MATRIX.cells(p) for p in ("linkedin", "stepstone", "naukri")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", action="store_true",
                    help="verification slice: a few cells per portal")
    ap.add_argument("--portal", action="append", default=[],
                    help="run only this portal, repeatable. For proving one "
                         "portal's access path without a full sweep")
    ap.add_argument("--cells", type=int, default=0,
                    help="take at most this many cells per portal")
    args = ap.parse_args()
    if args.slice:
        cells = slice_cells(MATRIX)
    else:
        if not MATRIX.approved:
            print("REFUSED: queries.yaml is not approved (approved: false). "
                  "Full sweeps run only on an approved matrix; use --slice "
                  "for the verification slice.")
            sys.exit(2)
        cells = full_matrix()
    if args.portal:
        cells = {p: c for p, c in cells.items() if p in args.portal}
        if not cells:
            raise SystemExit(f"no such portal in the matrix: {args.portal}")
    if args.cells:
        cells = {p: c[:args.cells] for p, c in cells.items()}
    total = sum(len(v) for v in cells.values())
    print(f"matrix v{MATRIX.version}, freshness {MATRIX.freshness_hours}h, "
          f"{total} cells: "
          + ", ".join(f"{p}={len(c)}" for p, c in cells.items()))
    asyncio.run(run(cells))


if __name__ == "__main__":
    main()
