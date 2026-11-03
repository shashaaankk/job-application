"""Set one board link's display title. Called by the scorer, not by a human.

The board is where he decides, so the title shown there has to be English. The
scorer produces the translation and runs this to put it on the board, in the same
way it runs `move_card.py` to move a card.

Only the text after the pipe changes. The link target is the filename and renaming
a target orphans the card, which has happened before.

The edit takes the board lock, because five scorers run at once and an unlocked
write loses whichever lands second.

Run:
  .venv/bin/python scripts/board_title.py --card "<card file stem>" --title "<English title>"
"""

import argparse
import sys

import move_card as MC


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", required=True, help="the card file stem, without .md")
    ap.add_argument("--title", required=True, help="the job title in English")
    args = ap.parse_args()

    title = " ".join(args.title.split()).strip()
    if not title:
        print("no title given, nothing changed")
        return 0
    if MC.set_board_title(args.card, title):
        print(f"board title set to {title!r}")
        return 0
    print("nothing changed, either the title already read that way or the card has "
          "no board link")
    return 0


if __name__ == "__main__":
    sys.exit(main())
