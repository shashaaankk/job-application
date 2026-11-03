"""Enforce the screen's rulings. Every posting he has ruled on is a test case.

Adding a rule to `screen.py` proves nothing. A rule is enforced only when a failure
to apply it stops the pipeline, which is what this does.

`scripts/data/screen-cases.tsv` holds one row per posting whose verdict he has
stated, with the ledger fields and the stored description, so every case runs
offline and repeats exactly. Two kinds of case.

  reject   a posting he said should not have reached the board. If the screen lets
           it through, that is the bug he already reported happening again.
  keep     a posting that is his field and must survive. These exist because three
           of my own rules over-rejected on their first version, discarding an
           agency posting over a sector list and a Qt role over the word desktop.
           A keep case is run with its own country allowed, because what it proves
           is about our rules and not about his country list. His preferences are
           his to change and a change must never stop a run.

The screen is also run over every card currently on the board, so a new rule that
would throw away work already accepted is caught before it is committed.

Run:  .venv/bin/python scripts/test_screen.py
Exit: 0 when every case holds, 1 otherwise. `make_cards.py` runs this first and
      refuses to build cards when it fails.
"""

import csv
import glob
import re
import sys
from pathlib import Path

import places
import screen

VAULT = Path(__file__).resolve().parent.parent
CASES = VAULT / "scripts" / "data" / "screen-cases.tsv"
DESCRIPTIONS = VAULT / "scripts" / "data" / "descriptions"
CARDS = VAULT / "application artifacts" / "job cards"


def verdict(row, allowed, keep_case=False):
    """(kept, reason). Both screen stages, exactly as the pipeline runs them.

    `keep_case` neutralises the country check, and that is the whole point of it.

    A keep case exists to prove that a rule of ours does not throw away his field,
    for example that an agency listing defence among its sectors is not a defence
    job, or that a Qt role is not the Microsoft stack. The country the posting sits
    in is irrelevant to what the case proves.

    It is also his to change at any time. He removed France from his preferences and
    two French keep cases began failing, which stopped the whole run at the gate and
    cost a night's cards. A preference edit must never do that, so the country of a
    keep case is resolved and then allowed, whatever his current list says.
    """
    ok, why, flags = screen.screen_title(
        row["title"], row["company"], row["location_text"], row.get("cell"))
    if not ok:
        return False, f"title: {why}"
    f = DESCRIPTIONS / f"{row['portal']}-{row['portal_id']}.md"
    if not f.exists():
        return None, "no stored description, the case cannot be decided"

    if keep_case:
        own = places.country_of(row["location_text"],
                               places.searched_country(row.get("cell")))
        allowed = set(allowed) | ({own} if own else set())

    ok, why, areas, dflags = screen.screen_description(
        f.read_text(encoding="utf-8", errors="replace"),
        row["location_text"], allowed, row.get("cell"))
    if not ok:
        return False, f"description: {why}"
    return True, f"kept, areas {', '.join(areas) or 'none'}"


def run_cases(allowed):
    if not CASES.exists():
        print(f"FAIL  {CASES.name} is missing, so nothing is enforced")
        return 1
    rows = list(csv.DictReader(CASES.open(encoding="utf-8"), delimiter="\t"))
    bad = 0
    for r in rows:
        want = r["expect"]
        kept, why = verdict(r, allowed, keep_case=(want == "keep"))
        if kept is None:
            print(f"SKIP  {r['company'][:24]:24s} {why}")
            bad += 1
            continue
        good = (want == "keep" and kept) or (want == "reject" and not kept)
        tag = "ok  " if good else "FAIL"
        if not good:
            bad += 1
        if not good or want == "reject":
            print(f"{tag}  expect {want:6s} {screen.clean_company(r['company'])[:22]:22s} "
                  f"{r['title'][:38]:38s} -> {why[:58]}")
    print(f"\n{len(rows)} ruled cases, {len(rows) - bad} hold, {bad} fail")
    if bad:
        print("A reject that is kept is a posting he already told us not to send.")
        print("A keep that is rejected is a rule of mine throwing away his field.")
    return 1 if bad else 0


def run_board(allowed):
    """Every card on the board, re-screened. A card that now rejects is a change."""
    changed = []
    for p in sorted(glob.glob(str(CARDS / "*.md"))):
        t = Path(p).read_text(encoding="utf-8", errors="replace")
        if "Description names:" not in t:
            continue                      # migrated from the old board, not screened
        title = re.search(r"^Job Title: (.*)$", t, re.M).group(1)
        comp = re.search(r"^Company: (.*)$", t, re.M).group(1)
        loc = re.search(r"^Location: (.*)$", t, re.M).group(1)
        url = re.search(r"^Posting: (.*)$", t, re.M).group(1)
        pid = (re.findall(r"(\d{6,})", url) or [""])[0]
        portal = next((x for x in ("linkedin", "stepstone", "naukri")
                       if (DESCRIPTIONS / f"{x}-{pid}.md").exists()), None)
        if not portal:
            continue
        # the card does not store the cell, so the country is taken from its location
        cell = f"sweep|{portal}|{loc}|24h|card"
        kept, why = verdict({"title": title, "company": comp, "location_text": loc,
                             "portal": portal, "portal_id": pid, "cell": cell}, allowed)
        if kept is False:
            changed.append((comp, title, why))
    if changed:
        print(f"\n{len(changed)} card(s) already on the board would now be rejected:")
        for c, t, w in changed:
            print(f"      {screen.clean_company(c)[:22]:22s} {t[:38]:38s} {w[:54]}")
        print("      Each one is either a posting that should go or a rule that is too broad.")
    else:
        print("\nno card on the board is affected by the current rules")
    return 0


def main():
    allowed = places.allowed_countries()
    print(f"countries from 04. preferences: {', '.join(sorted(allowed))}\n")
    rc = run_cases(allowed)
    run_board(allowed)
    print("\nPASS" if rc == 0 else "\nFAIL")
    return rc


if __name__ == "__main__":
    sys.exit(main())
