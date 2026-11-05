"""Run every test case in this skill's evals folder through the real scorer.

Each case's first grader states the expected tier ("scored tier A") or a knockout
("receives no tier"). This checks that part mechanically, so a prompt edit or a new
agent that shifts a tier is caught before a run reaches the board. The other graders
are judgements and are printed for a person to check against the saved answer.

Run from the vault root:
  .venv/bin/python skills/scoring/scripts/check_cases.py            every case
  .venv/bin/python skills/scoring/scripts/check_cases.py robotics   cases whose name matches

Each answer is saved next to its case as `last-answer.json`, ignored by git.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_posting as P  # noqa: E402

EVALS = Path(__file__).resolve().parent.parent / "evals"


def expected(case):
    text = " ".join(g.read_text(encoding="utf-8").split("---", 2)[-1]
                    for g in sorted((case / "graders").glob("*.md")))
    if re.search(r"no tier", text):
        return None
    m = re.search(r"tier ([ABC])\b", text)
    return m.group(1) if m else "unknown"


def main():
    pick = sys.argv[1] if len(sys.argv) > 1 else ""
    cases = [c for c in sorted(EVALS.iterdir()) if c.is_dir() and pick in c.name]
    failed = 0
    for case in cases:
        want = expected(case)
        payload, g = P.score(case / "files" / "posting.md")
        (case / "last-answer.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        ok = g["tier"] == want
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {case.name:32s} expected {want or 'none'}, "
              f"got {g['tier'] or 'none'}  ({g['why']})")
        for gr in sorted((case / "graders").glob("*.md"))[1:]:
            print(f"      check by hand: {gr.read_text(encoding='utf-8').split('---', 2)[-1].strip()}")
    print(f"\n{len(cases) - failed} of {len(cases)} cases on the expected tier")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
