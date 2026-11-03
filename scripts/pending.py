"""The work list for artifact generation, read from the board.

There is no scoring stage. A card reaches the board already screened, he reads it,
and moving it into the `to apply` column is the judgement that releases it. This
script is the only thing that decides what artifact generation acts on, so the
board column is the trigger and nothing else is.

A card is work when it sits in `to apply` and either its `cv` or its
`coverletter` key is still empty. A card whose keys are both filled is finished
and is reported as such rather than generated again, per the token rule that a
passed document is diffed and never regenerated.

Run:
  .venv/bin/python scripts/pending.py              what needs generating
  .venv/bin/python scripts/pending.py --json       the same, for a dispatcher
  .venv/bin/python scripts/pending.py --column applied
"""

import argparse
import json
import re
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
BOARD = VAULT / "01. job application tracker.md"
TRIGGER_COLUMN = "to apply"


def column_cards(column):
    """The card paths listed under one board column, in board order.

    A missing column is an error rather than an empty list, because an empty
    result and a renamed column are different facts and must not look alike.
    """
    found, cur, out = False, None, []
    for line in BOARD.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
            if cur == column:
                found = True
            continue
        if cur != column:
            continue
        m = re.search(r"\[\[([^\]|]+)", line)
        if m:
            out.append(m.group(1).strip())
    if not found:
        raise SystemExit(f"the board has no '{column}' column, refusing to guess")
    return out


def key(text, name):
    r"""One frontmatter key's value, or the empty string when it is unset.

    The horizontal whitespace class is deliberate. `\s*` matches a newline, so an
    empty `cv:` key read the next line's text and every unfinished card reported
    itself as done.
    """
    m = re.search(rf"^{re.escape(name)}:[ \t]*(.*)$", text, re.M)
    return (m.group(1).strip() if m else "")


def jd_of(text):
    """The archived description, so a stub is caught before an agent is spawned."""
    m = re.search(r"### Job Description\s*(.*?)\n---", text, re.S)
    return (m.group(1).strip() if m else "")


def inspect(rel):
    """One card's state. A card that cannot be read is a stop, never a skip."""
    p = VAULT / f"{rel}.md"
    if not p.exists():
        p = VAULT / rel
    if not p.exists():
        return {"card": rel, "state": "missing", "why": "the board link points at no file"}
    t = p.read_text(encoding="utf-8", errors="replace")
    jd = jd_of(t)
    rec = {
        "card": str(p.relative_to(VAULT)),
        "title": key(t, "Job Title"),
        "company": key(t, "Company"),
        "location": key(t, "Location"),
        "posting": key(t, "Posting"),
        "cv": key(t, "cv"),
        "coverletter": key(t, "coverletter"),
        "jd_chars": len(jd),
    }
    # A card migrated from the old board carries the `old` tag and a different
    # structure, with no archived description. It is history rather than work, so
    # it is never reported as blocked.
    if re.search(r"^\s*-\s*old\s*$", t, re.M) and "### Job Description" not in t:
        rec["state"] = "archived"
    elif len(jd) < 200:
        rec["state"], rec["why"] = "blocked", f"the description is {len(jd)} characters, rule 1"
    elif rec["cv"]:
        rec["state"] = "done"
    else:
        rec["state"] = "work"
        rec["needs"] = ["cv"]
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--column", default=TRIGGER_COLUMN)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--letters", action="store_true",
                    help="list the cards that have no cover letter yet")
    args = ap.parse_args()

    cards = [inspect(c) for c in column_cards(args.column)]
    work = [c for c in cards if c["state"] == "work"]

    if args.letters:
        none_yet = [c for c in cards
                    if c["state"] in ("done", "work") and not c.get("coverletter")]
        print(f"column '{args.column}': {len(none_yet)} card(s) with no cover letter")
        for c in none_yet:
            print(f"  {c['company'][:26]:26s} {c['title'][:42]:42s}"
                  f"{'' if c['cv'] else '  (no CV either)'}")
        return 0

    if args.json:
        json.dump({"column": args.column, "work": work,
                   "done": [c for c in cards if c["state"] == "done"],
                   "blocked": [c for c in cards if c["state"] in ("blocked", "missing")],
                   "archived": sum(1 for c in cards if c["state"] == "archived")},
                  sys.stdout, indent=1)
        print()
        return 0

    print(f"column '{args.column}': {len(cards)} cards")
    for c in cards:
        if c["state"] == "work":
            print(f"  WORK     {c['company'][:26]:26s} {c['title'][:40]:40s} "
                  f"needs {', '.join(c['needs'])}")
    for c in cards:
        if c["state"] == "done":
            print(f"  done     {c['company'][:26]:26s} {c['title'][:40]}")
    for c in cards:
        if c["state"] in ("blocked", "missing"):
            print(f"  BLOCKED  {c.get('company', c['card'])[:26]:26s} {c['why']}")
    n_old = sum(1 for c in cards if c["state"] == "archived")
    if n_old:
        print(f"  ({n_old} migrated from the old board, history rather than work)")
    print(f"\n{len(work)} card(s) to generate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
