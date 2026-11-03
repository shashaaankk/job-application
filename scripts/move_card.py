"""Move one card between board columns. Called by the scorer, not by a human.

Antigravity scores each card and moves the ones that fire the document trigger. This
is the command it calls to do it, and it exists for two reasons that have nothing to
do with who decides.

First, five scorers run at once and they would all be rewriting the same board file.
An unlocked edit loses whichever write lands second, which is how board lines
vanished before. This takes an exclusive lock for the duration of the edit.

Second, his three caps are counted across the whole run and no single scorer can see
the others' cards. The counters live in `data/move-counters.json`, keyed by run, and
this refuses the move once a cap is reached. The card then keeps its evaluation and
stays where it is, which is what rule 62 requires.

The screen also runs here, because a card that the rules reject must not reach
document generation even if it was carded before the rule existed.

At most two cards per poster reach `to apply` in one run, his instruction. One
consultancy listed 28 postings in a single night, and without this they would have
taken most of the 35 slots and crowded out every other employer. The two that stay
are the two best, by band. A third card with a higher band than one already admitted
displaces it, and the displaced card goes back to `matched` with its evaluation, so
arrival order does not decide which two survive.

Exit 0 means moved. Exit 3 means refused, either at a cap, by the per-poster limit,
or by the screen, and none is an error. Anything else is a failure.

Run:
  .venv/bin/python scripts/move_card.py --card "<card file stem>" --band 3 --run <id>
"""

import argparse
import fcntl
import json
import re
import sys
from pathlib import Path

import places
import screen

VAULT = Path(__file__).resolve().parent.parent
BOARD = VAULT / "01. job application tracker.md"
CARDS = VAULT / "application artifacts" / "job cards"
STATE = VAULT / "scripts" / "data" / "move-counters.json"
LOCK = VAULT / "scripts" / "data" / ".board.lock"
FROM_COLUMN = "matched"
TO_COLUMN = "to apply"
CAPS = {3: 20, 2: 30, "total": 35}
PER_COMPANY = 2        # his instruction, so one poster cannot take the run


LEDGER = VAULT / "scripts" / "data" / "ledger.tsv"


def ledger_cell(card_text):
    """The sweep cell for this card's posting, or None.

    Read by portal id from the ledger, never by company or title. Matching a card to
    a row by name has been wrong three times in this pipeline, each time quietly.
    """
    m = re.search(r"^Posting:[ \t]*(.*)$", card_text, re.M)
    if not m:
        return None
    ids = set(re.findall(r"(\d{6,})", m.group(1)))
    if not ids or not LEDGER.exists():
        return None
    import csv as _csv
    with LEDGER.open(encoding="utf-8") as fh:
        for row in _csv.DictReader(fh, delimiter="\t"):
            if row.get("portal_id") in ids:
                return row.get("cell")
    return None


def screen_says(stem):
    """(ok, reason). The screen, re-applied at the gate.

    A naval defence posting reached `to apply` at band 3 because the card predates
    the description-stage defence check, scoring does not re-apply the screen, and
    the move did not check it either. Three stages each assumed another had done it.

    So the screen runs here too. It is the same rule set that decides whether a card
    is written at all, and running it twice costs milliseconds. Rule 81 already says
    a ruling is enforced by a check rather than by being written down.
    """
    p = CARDS / f"{stem}.md"
    if not p.exists():
        return True, "no card file to screen"
    t = p.read_text(encoding="utf-8", errors="replace")

    def key(n):
        m = re.search(rf"^{re.escape(n)}:[ \t]*(.*)$", t, re.M)
        return m.group(1).strip() if m else ""

    title, company, loc = key("Job Title"), key("Company"), key("Location")
    if not title:
        return True, "the card has no title to screen"

    # The sweep cell comes from the ledger, by portal id. Without it a town name held
    # by several countries resolves to the most populous one, which read "Gera" as
    # Hungarian and would have pulled a Thuringian posting out of the column. The
    # cell records the country the query actually asked for, which settles it.
    cell = ledger_cell(t) or f"sweep|card|{loc}|24h|gate"
    ok, why, flags = screen.screen_title(title, company, loc, cell)
    if not ok:
        return False, f"the screen rejects the title, {why}"
    jd = ""
    if "### Job Description" in t and "### Evaluation" in t:
        jd = t[t.index("### Job Description"):t.index("### Evaluation")]
    if len(jd) < 200:
        return True, "no readable description on the card to screen"
    ok, why, areas, dflags = screen.screen_description(
        jd, loc, places.allowed_countries(), cell)
    if not ok:
        # a location the gazetteer cannot resolve from a card is not a verdict on the
        # posting, since the card carries no sweep cell to fall back on
        if "does not resolve to a country" in why:
            return True, "the location could not be resolved from the card alone"
        return False, f"the screen rejects the description, {why}"
    return True, ""


def do_move(stem):
    """(moved, note). The board edit itself, under the caller's lock."""
    lines = BOARD.read_text(encoding="utf-8").splitlines()
    line, cur, kept = None, None, []
    for l in lines:
        if l.startswith("## "):
            cur = l[3:].strip()
            kept.append(l)
            continue
        m = re.search(r"\[\[application artifacts/job cards/([^\]|]+)", l)
        if m and m.group(1).strip() == stem:
            if cur == TO_COLUMN:
                return False, f"already in '{TO_COLUMN}'"
            if cur != FROM_COLUMN:
                return False, f"in '{cur}', which this never moves out of"
            line = l
            continue
        kept.append(l)
    if line is None:
        return False, "no board line for that card"

    out, cur, placed = [], None, False
    for l in kept:
        if l.startswith("## "):
            if cur == TO_COLUMN and not placed:
                out.append(line); placed = True
            cur = l[3:].strip()
        out.append(l)
    if cur == TO_COLUMN and not placed:
        out.append(line); placed = True
    if not placed:
        return False, f"the board has no '{TO_COLUMN}' column"
    BOARD.write_text("\n".join(out) + "\n", encoding="utf-8")
    return True, ""


def set_board_title(stem, title_en):
    """Rewrite one board link's display text to the English title. 1 if changed.

    The text is rebuilt from fields rather than parsed, namely the leading date on
    the line if it has one, the card's Company field, and the English title. Two
    earlier versions tried to split the old text on " - " and replace the last
    segment, and both were wrong, because a link can show the whole filename and a
    job title can itself contain a dash, as in "Embedded SW engineer - EPT2 at
    BoschGroup". Parsing a display string is guesswork. Rebuilding it is not.

    The link target is untouched, because the target is the filename and renaming a
    target orphans the card.

    Takes the same lock as a move, since a scoring run rewrites many of these.
    """
    card = CARDS / f"{stem}.md"
    company = ""
    if card.exists():
        m = re.search(r"^Company:[ \t]*(.*)$", card.read_text(encoding="utf-8",
                                                              errors="replace"), re.M)
        company = (m.group(1).strip() if m else "")

    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        lines = BOARD.read_text(encoding="utf-8").splitlines()
        for i, l in enumerate(lines):
            m = re.search(r"\[\[application artifacts/job cards/([^\]|]+)\|([^\]]*)\]\]", l)
            if not m or m.group(1).strip() != stem:
                continue
            shown = m.group(2)
            d = re.match(r"\s*(\d{4}-\d{2}-\d{2}|\d{2}\.\d{2})\s*-\s*", shown)
            bits = ([d.group(1)] if d else []) + ([company] if company else []) + [title_en]
            new_shown = " - ".join(bits)
            if new_shown == shown:
                return 0
            lines[i] = l.replace(f"|{shown}]]", f"|{new_shown}]]")
            BOARD.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return 1
        return 0


def move_back(stem):
    """Return one card from `to apply` to `matched`. For a displaced card only."""
    lines = BOARD.read_text(encoding="utf-8").splitlines()
    line, cur, kept = None, None, []
    for l in lines:
        if l.startswith("## "):
            cur = l[3:].strip()
            kept.append(l)
            continue
        m = re.search(r"\[\[application artifacts/job cards/([^\]|]+)", l)
        if m and cur == TO_COLUMN and m.group(1).strip() == stem:
            line = l
            continue
        kept.append(l)
    if line is None:
        return False
    out, cur, placed = [], None, False
    for l in kept:
        if l.startswith("## "):
            if cur == FROM_COLUMN and not placed:
                out.append(line); placed = True
            cur = l[3:].strip()
        out.append(l)
    if cur == FROM_COLUMN and not placed:
        out.append(line); placed = True
    if not placed:
        return False
    BOARD.write_text("\n".join(out) + "\n", encoding="utf-8")
    return True


def has_documents(stem):
    """Whether a card already carries a built CV or letter."""
    p = CARDS / f"{stem}.md"
    if not p.exists():
        return False
    t = p.read_text(encoding="utf-8", errors="replace")
    return bool(re.search(r"^(cv|coverletter):[ \t]*\S+", t, re.M))


def cards_of_poster(poster):
    """[{stem, band}] for that poster's cards already in `to apply`, from the board."""
    out = []
    cur = None
    for l in BOARD.read_text(encoding="utf-8").splitlines():
        if l.startswith("## "):
            cur = l[3:].strip()
            continue
        if cur != TO_COLUMN:
            continue
        m = re.search(r"\[\[application artifacts/job cards/([^\]|]+)", l)
        if not m:
            continue
        stem = m.group(1).strip()
        if poster_of(stem) != poster:
            continue
        p = CARDS / f"{stem}.md"
        b = 0
        if p.exists():
            bm = re.search(r"^Score:[ \t]*band (\d)",
                           p.read_text(encoding="utf-8", errors="replace"), re.M)
            # a card he placed himself carries no band; it is never displaced
            b = int(bm.group(1)) if bm else 99
        out.append({"stem": stem, "band": b})
    return out


def poster_of(stem):
    """The employer, cleaned and normalised, so one poster is one identity.

    A portal's company field carries marketing, so FERCHAU reads as
    "FERCHAU - Connecting People and Technologies". Counting those as different
    posters would defeat the limit entirely.
    """
    p = CARDS / f"{stem}.md"
    if not p.exists():
        return ""
    m = re.search(r"^Company:[ \t]*(.*)$", p.read_text(encoding="utf-8",
                                                       errors="replace"), re.M)
    return screen.norm(screen.clean_company(m.group(1))) if m else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", required=True, help="the card file stem, without .md")
    ap.add_argument("--band", required=True, type=int, choices=[0, 1, 2, 3])
    ap.add_argument("--run", default="manual", help="the run id, which scopes the caps")
    args = ap.parse_args()

    if args.band not in (2, 3):
        print(f"band {args.band} does not fire the document trigger, nothing moved")
        return 3

    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)          # waits, never fails
        state = {}
        if STATE.exists():
            try:
                state = json.loads(STATE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                state = {}
        c = state.get(args.run) or {"3": 0, "2": 0, "total": 0}
        c.setdefault("posters", {})

        poster = poster_of(args.card)
        # Counted from the board, not from this run's own tally. A per-run count let
        # a poster that already held two cards from an earlier night take two more.
        admitted = cards_of_poster(poster) if poster else []
        displaced = None
        if poster and len(admitted) >= PER_COMPANY:
            # a card whose documents are already built is never displaced, since the
            # tokens are spent and he may be about to apply with them
            movable = [a for a in admitted if not has_documents(a["stem"])]
            if not movable:
                print(f"refused, this poster already has {len(admitted)} cards in "
                      f"'{TO_COLUMN}' and all of them carry documents. This card "
                      f"keeps its evaluation in '{FROM_COLUMN}'")
                return 3
            weakest = min(movable, key=lambda a: a["band"])
            if args.band <= weakest["band"]:
                print(f"refused, this poster already has {PER_COMPANY} cards in "
                      f"'{TO_COLUMN}' at band {sorted(a['band'] for a in admitted)} "
                      f"and this one is band {args.band}. It keeps its evaluation in "
                      f"'{FROM_COLUMN}'")
                return 3
            displaced = weakest          # a better card takes the weaker one's place

        if displaced is None and c["total"] >= CAPS["total"]:
            print(f"refused, the run cap of {CAPS['total']} is reached. "
                  f"The card keeps its evaluation in '{FROM_COLUMN}'")
            return 3
        if displaced is None and c[str(args.band)] >= CAPS[args.band]:
            print(f"refused, the band {args.band} cap of {CAPS[args.band]} is reached. "
                  f"The card keeps its evaluation in '{FROM_COLUMN}'")
            return 3

        ok, why = screen_says(args.card)
        if not ok:
            print(f"refused, {why}. The card keeps its evaluation in "
                  f"'{FROM_COLUMN}' and no documents are generated for it")
            return 3

        moved, note = do_move(args.card)
        if not moved:
            print(f"not moved, {note}")
            return 0 if "already" in note else 1

        note = ""
        if displaced is not None:
            if move_back(displaced["stem"]):
                admitted = [a for a in admitted if a["stem"] != displaced["stem"]]
                c[str(displaced["band"])] -= 1
                c["total"] -= 1
                note = (f" It displaced a band {displaced['band']} card from the same "
                        f"poster, which went back to '{FROM_COLUMN}' with its evaluation.")
            else:
                note = (" The weaker card from the same poster could not be moved back, "
                        "so this poster now holds one more than the limit.")
        c[str(args.band)] += 1
        c["total"] += 1
        if poster:
            admitted.append({"stem": args.card, "band": args.band})
            c["posters"][poster] = admitted
        state[args.run] = c
        STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
        print(f"moved to '{TO_COLUMN}'. This run has moved {c['total']} of "
              f"{CAPS['total']}, band 3 {c['3']} of {CAPS[3]}, band 2 {c['2']} of "
              f"{CAPS[2]}.{note}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
