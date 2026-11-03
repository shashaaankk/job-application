"""Log a posting he has already applied to. No screening, no questions.

His instruction, and it is absolute. When he says he has applied to a job, the
pipeline records it. The screen does not run, no rule is consulted and no verdict is
written onto the card, because his judgement outweighs every rule in the vault. The
rules exist to decide what to put in front of him, and this posting is past that.

What this does.
  1. fetches the title, company, location and description over the anonymous
     endpoint, which uses no account and risks nothing
  2. writes a card from templates/job entry.md
  3. adds one line to the `applied` column and touches no other column
  4. records the id in carded.tsv, so no sweep ever cards it again

Run:
  .venv/bin/python scripts/log_applied.py <linkedin url or job id> [more ids]
  .venv/bin/python scripts/log_applied.py 4479575686 --column applied
"""

import argparse
import datetime as dt
import html
import re
import sys
import time
import urllib.request
from pathlib import Path

import make_cards as MC

VAULT = Path(__file__).resolve().parent.parent
BOARD = VAULT / "01. job application tracker.md"
DESCRIPTIONS = VAULT / "scripts" / "data" / "descriptions"

FIELDS = (("title", r'<h2[^>]*top-card-layout__title[^>]*>(.*?)</h2>'),
          ("company", r'topcard__org-name-link[^>]*>(.*?)</a>'),
          ("location", r'topcard__flavor--bullet[^>]*>(.*?)</span>'))


def job_id(s):
    m = re.search(r"currentJobId=(\d{6,})", s) or re.search(r"jobs/view/(\d{6,})", s) \
        or re.fullmatch(r"\s*(\d{6,})\s*", s)
    return m.group(1) if m else None


def head(jid):
    """Title, company and location from the public posting page."""
    req = urllib.request.Request(MC.GUEST_EP.format(jid=jid),
                                 headers={"User-Agent": MC.GUEST_UA})
    body = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
    out = {}
    for name, pat in FIELDS:
        m = re.search(pat, body, re.S)
        out[name] = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""
    return out


def description(jid):
    """The description, with a back-off because the endpoint rate limits."""
    for wait in (0, 8, 16, 30):
        if wait:
            time.sleep(wait)
        txt, err = MC.guest_description(jid)
        if txt:
            return txt, None
    return None, err


def add_line(column, line):
    lines = BOARD.read_text(encoding="utf-8").splitlines()
    out, placed = [], False
    for l in lines:
        out.append(l)
        if l.strip() == f"## {column}" and not placed:
            out.append("")
            out.append(line)
            placed = True
    if not placed:
        raise SystemExit(f"the board has no '{column}' column, refusing to guess")
    BOARD.write_text("\n".join(out) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="+", help="LinkedIn urls or bare job ids")
    ap.add_argument("--column", default="applied")
    args = ap.parse_args()
    today = dt.date.today().isoformat()
    rc = 0

    for t in args.targets:
        jid = job_id(t)
        if not jid:
            print(f"FAIL no job id in {t[:60]}")
            rc = 1
            continue
        if any(p.name.endswith(f"- {jid}.md") for p in MC.CARDS.glob("*.md")):
            print(f"{jid} already has a card, nothing done")
            continue
        try:
            h = head(jid)
        except Exception as e:
            print(f"FAIL {jid}, could not read the posting: {type(e).__name__}")
            rc = 1
            continue
        jd, err = description(jid)
        if not jd:
            print(f"FAIL {jid}, no description: {err}")
            rc = 1
            continue
        DESCRIPTIONS.mkdir(parents=True, exist_ok=True)
        (DESCRIPTIONS / f"linkedin-{jid}.md").write_text(jd, encoding="utf-8")

        row = {"portal": "linkedin", "portal_id": jid, "title": h["title"],
               "company": h["company"], "location_text": h["location"],
               "url": f"https://www.linkedin.com/jobs/view/{jid}/",
               "posted_at": "", "age_text": "", "cell": "manual"}
        text = MC.card_text(row, jd, today, today, "", "", [], [])
        # the Evaluation section carries no verdict, because none was formed
        text = re.sub(
            r"(### Evaluation\n\n).*?(\n\n### Questions)",
            r"\1He applied to this posting himself and told the pipeline to log it. "
            r"No screening ran and no rule was consulted, per rule 88. The description "
            r"was fetched over the anonymous endpoint on the day he logged it.\2",
            text, flags=re.S)
        fname = MC.safe_name(f"{h['company']} - {h['title']} - {jid}") + ".md"
        (MC.CARDS / fname).write_text(text, encoding="utf-8")
        add_line(args.column,
                 f"- [ ] [[application artifacts/job cards/{fname[:-3]}"
                 f"|{today} - {h['company']} - {h['title']}]]")
        MC.log_carded([(jid, "linkedin", fname)])
        print(f"logged into '{args.column}': {h['company']} - {h['title']} ({jid})")
    return rc


if __name__ == "__main__":
    sys.exit(main())
