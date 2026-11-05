"""Score one posting file without touching a card or the board.

The posting file is a few header lines, a line of three dashes, then the job
description, which is the layout of the files in this skill's evals folders.

    Title: Robotics Technology Center Engineer
    Company: Eindhoven University of Technology
    Location: Eindhoven, Netherlands
    Posting: linkedin 4487504844
    ---
    <the job description>

It uses the same prompt, agent and tier logic as `scripts/score.py`, so a result here
is what a card would get.

Run from the vault root:
  .venv/bin/python skills/scoring/scripts/score_posting.py posting.md
  .venv/bin/python skills/scoring/scripts/score_posting.py posting.md --json out.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(VAULT / "scripts"))
import score as S  # noqa: E402


def read_posting(path):
    head, _, jd = Path(path).read_text(encoding="utf-8").partition("\n---\n")
    def key(n):
        m = re.search(rf"^{n}:[ \t]*(.*)$", head, re.M)
        return m.group(1).strip() if m else ""
    meta = {"title": key("Title"), "company": key("Company"),
            "location": key("Location"), "posting": key("Posting")}
    if not jd.strip():
        raise SystemExit(f"{path} has no job description after the --- line")
    return meta, jd.strip()


def score(path):
    """(payload, grade). Raises SystemExit when the agent fails."""
    meta, jd = read_posting(path)
    payload, err = S.run_agent(S.prompt_for(meta, jd))
    if err:
        raise SystemExit(f"the agent failed: {err}")
    return payload, S.grade(payload)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("posting")
    ap.add_argument("--json", help="also write the agent's raw answer here")
    args = ap.parse_args()
    payload, g = score(args.posting)
    if args.json:
        Path(args.json).write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(S.evaluation_text(payload, g))
    qs = [q for q in payload.get("questions") or [] if isinstance(q, dict) and q.get("changes")]
    print("\nQuestions:" + "".join(f"\n- {q['question']} (changes: {q['changes']})"
                                   for q in qs) if qs else "\nQuestions: none")
    print(f"\nTIER {g['tier'] or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
