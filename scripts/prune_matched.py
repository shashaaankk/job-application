"""Clear the `matched` column of cards that are done with, after scoring has run.

Two kinds go, on his instruction.

  below the threshold   band 0 or 1, or a preference match that rejected. These will
                        never generate documents, so they are not waiting for
                        anything.
  older than the window matched.freshness_hours from the matrix. A card that has
                        aged out is no longer a live posting, whatever its band.

Nothing else is touched. Other columns are never read, an unscored card is left
alone because scoring has not had its say, and a band 2 or 3 card inside the window
stays, since it is either on its way to `to apply` or held at one of his caps.

Removal goes through `retire_cards.py`, so a pruned card is moved to `.trash/<date>/`
rather than deleted and its id is written to `retired.tsv`, which stops the next
sweep carding it again.

Run:
  .venv/bin/python scripts/prune_matched.py --dry-run
  .venv/bin/python scripts/prune_matched.py
"""

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

import make_cards as MC
import matrix as MX
import score as S

VAULT = Path(__file__).resolve().parent.parent
CARDS = VAULT / "application artifacts" / "job cards"
COLUMN = "matched"
KEEP_BANDS = (2, 3)


def card_band(text):
    """(band, preference verdict) from the Score field, or (None, None)."""
    m = re.search(r"^Score:[ \t]*band (\d), preference (\w+)", text, re.M)
    return (int(m.group(1)), m.group(2)) if m else (None, None)


def posting_age_hours(text):
    """Hours since the posting date on the card, or None when it has none."""
    m = re.search(r"^Posting date:[ \t]*(\d{4}-\d{2}-\d{2})", text, re.M)
    if not m:
        return None
    d = dt.date.fromisoformat(m.group(1))
    return (dt.datetime.now(dt.timezone.utc)
            - dt.datetime.combine(d, dt.time(), dt.timezone.utc)).total_seconds() / 3600


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    hours = MX.load().freshness_hours
    print(f"pruning '{COLUMN}', freshness window {hours} h")

    go, keep, ids = [], 0, []
    for stem in S.column_cards(COLUMN):
        p = CARDS / f"{stem}.md"
        if not p.exists():
            print(f"  board link with no file, leaving it: {stem[:56]}")
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        band, pref = card_band(t)
        age = posting_age_hours(t)

        if band is None:
            keep += 1                      # unscored, scoring has not had its say
            continue
        if band not in KEEP_BANDS or pref != "pass":
            why = (f"band {band}" if band not in KEEP_BANDS
                   else f"preference {pref}") + ", below the threshold"
        elif age is not None and age > hours + 2:
            why = f"{age/24:.1f} days old, outside the {hours} h window"
        else:
            keep += 1
            continue

        m = re.search(r"^Posting:[ \t]*(.*)$", t, re.M)
        pid = (re.findall(r"(\d{6,})", m.group(1)) if m else []) or \
              re.findall(r"(\d{6,})", stem)
        if not pid:
            print(f"  no portal id, leaving it: {stem[:56]}")
            continue
        go.append((stem, why))
        ids.append(pid[0])

    print(f"  keeping {keep}, pruning {len(go)}")
    for stem, why in go[:40]:
        print(f"     {why:44s} {stem[:52]}")
    if len(go) > 40:
        print(f"     ... and {len(go) - 40} more")
    if not go:
        return 0
    if args.dry_run:
        print("\ndry run, nothing written")
        return 0

    r = subprocess.run([sys.executable, str(Path(__file__).with_name("retire_cards.py")),
                        "--ids", *ids], cwd=str(VAULT), capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr.strip()[:400])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
