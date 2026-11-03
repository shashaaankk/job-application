"""Remove cards from the board. The only sanctioned way, because the ad hoc way lost work.

Why this exists. Asked to clear the `matched` column, I removed that column's board
lines correctly and then ran a second pass over the whole cards folder to catch four
orphans the board had never linked. That pass matched on the screen's reading and did
not look at which column a card sat in, so it deleted the five cards he had moved to
`to apply` as well. Obsidian then created a new empty note for each dangling link,
which is why four of his own selections read as blank files.

Three rules follow from that, and they are the whole point of this file.

  1. A removal names a column, or it names portal ids. It is never "every card".
  2. A card file is moved to `.trash/<date>/`, never unlinked. A mistake stays recoverable.
  3. A removed id is written to `data/retired.tsv`, so the next sweep does not card it
     again. Without that, removing a card means "collect this again tomorrow", which
     is the opposite of what removing it means to him.

A card deleted in Obsidian rather than through this tool is covered too, because
`make_cards.py` reads `data/carded.tsv`, an append only log of every id it has ever
carded. "Carded once" is permanent, so no deletion of any kind brings a posting
back. `--forget` is the single way in, which makes letting one return deliberate.

Run:
  .venv/bin/python scripts/retire_cards.py --column matched
  .venv/bin/python scripts/retire_cards.py --ids 4474760509 4429731907
  .venv/bin/python scripts/retire_cards.py --column matched --dry-run
  .venv/bin/python scripts/retire_cards.py --forget 4474760509
"""

import argparse
import csv
import datetime as dt
import re
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
BOARD = VAULT / "01. job application tracker.md"
CARDS = VAULT / "application artifacts" / "job cards"
TRASH = CARDS / ".trash"
RETIRED = VAULT / "scripts" / "data" / "retired.tsv"
PROTECTED = {"applied", "completed", "user rejection", "rejected"}


def card_ids(text):
    m = re.search(r"^Posting: (.*)$", text, re.M)
    return set(re.findall(r"(\d{6,})", m.group(1))) if m else set()


def board_rows():
    """[(line index, column, card stem)] for every card link on the board."""
    out, cur = [], None
    for i, line in enumerate(BOARD.read_text(encoding="utf-8").splitlines()):
        if line.startswith("## "):
            cur = line[3:].strip()
            continue
        m = re.search(r"\[\[application artifacts/job cards/([^\]|]+)", line)
        if m:
            out.append((i, cur, m.group(1).strip()))
    return out


CARDED = VAULT / "scripts" / "data" / "carded.tsv"


def forget(ids, dry_run):
    """Drop these ids from both memories so the pipeline may card them again.

    This is the deliberate act that undoes a removal. It touches no card file and no
    board line, because the point is only to let the next sweep see the posting.
    """
    ids = set(ids)
    hit = 0
    for f in (RETIRED, CARDED):
        if not f.exists():
            continue
        rows = list(csv.DictReader(f.open(encoding="utf-8"), delimiter="\t"))
        keep = [r for r in rows if r["portal_id"] not in ids]
        gone = len(rows) - len(keep)
        hit += gone
        print(f"{f.name}: {gone} row(s) to drop, {len(keep)} kept")
        if gone and not dry_run:
            cols = list(rows[0].keys())
            with f.open("w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh, delimiter="\t", lineterminator="\n")
                w.writerow(cols)
                for r in keep:
                    w.writerow([r[c] for c in cols])
    if not hit:
        print("neither memory holds those ids, so nothing was blocking them")
    elif dry_run:
        print("\ndry run, nothing written")
    else:
        print("\nthe next sweep may card these again, if they are still fresh enough")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--column", help="remove every card in this column")
    ap.add_argument("--ids", nargs="*", default=[], help="remove these portal ids")
    ap.add_argument("--forget", nargs="*", default=[],
                    help="let these ids be collected and carded again, which is the "
                         "only way a removed posting returns")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.forget:
        return forget(args.forget, args.dry_run)
    if not args.column and not args.ids:
        raise SystemExit("name a --column or some --ids. This tool never removes everything")
    if args.column in PROTECTED:
        raise SystemExit(f"'{args.column}' holds his applications, refusing")

    rows = board_rows()
    cols = sorted({c for _, c, _ in rows if c})
    if args.column and args.column not in cols:
        raise SystemExit(f"the board has no '{args.column}' column, it has {cols}")

    doomed = {}                      # stem -> (column, path or None)
    for _, col, stem in rows:
        p = CARDS / f"{stem}.md"
        if args.column and col == args.column:
            doomed[stem] = (col, p if p.exists() else None)
        elif args.ids:
            ids = card_ids(p.read_text(encoding="utf-8", errors="replace")) if p.exists() else set()
            ids |= set(re.findall(r"(\d{6,})", stem))
            if ids & set(args.ids):
                doomed[stem] = (col, p if p.exists() else None)

    kept_cols = sorted({c for c, _ in doomed.values()})
    print(f"removing {len(doomed)} card(s) from {kept_cols or 'nothing'}")
    for stem, (col, p) in sorted(doomed.items()):
        print(f"   [{col}] {'file' if p else 'board link only'}  {stem[:66]}")
    if not doomed:
        return 0
    if args.dry_run:
        print("\ndry run, nothing written")
        return 0

    # 1. the board, only the lines that belong to these cards
    lines = BOARD.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        m = re.search(r"\[\[application artifacts/job cards/([^\]|]+)", line)
        if m and m.group(1).strip() in doomed:
            continue
        out.append(line)
    BOARD.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"\nboard lines removed: {len(lines) - len(out)}")

    # 2. the files, moved rather than deleted
    day = TRASH / dt.date.today().isoformat()
    day.mkdir(parents=True, exist_ok=True)
    retired = []
    for stem, (col, p) in doomed.items():
        ids = set()
        if p:
            t = p.read_text(encoding="utf-8", errors="replace")
            ids = card_ids(t)
            p.rename(day / p.name)
        ids |= set(re.findall(r"(\d{6,})", stem))
        for i in sorted(ids):
            retired.append((i, col, stem))
    print(f"card files moved to {day.relative_to(VAULT)}: "
          f"{sum(1 for _, (c, q) in doomed.items() if q)}")

    # 3. the memory, so the next sweep does not card them again
    seen = set()
    if RETIRED.exists():
        seen = {r["portal_id"] for r in csv.DictReader(RETIRED.open(encoding="utf-8"),
                                                       delimiter="\t")}
    new = [r for r in retired if r[0] not in seen]
    first = not RETIRED.exists()
    with RETIRED.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        if first:
            w.writerow(["portal_id", "retired_on", "from_column", "card"])
        for i, col, stem in new:
            w.writerow([i, dt.date.today().isoformat(), col, stem])
    print(f"ids written to data/retired.tsv: {len(new)} new, {len(seen)} already there")
    return 0


if __name__ == "__main__":
    sys.exit(main())
