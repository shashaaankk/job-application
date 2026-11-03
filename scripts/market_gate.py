"""Mechanical check that every application packet carries its market's contact block.

A direct port of market-gate.mjs. Origin, a nightly batch built all sixteen
packets from the EU base and shipped German contact data on seven India-market
documents, which a truthfulness review cannot catch because a German phone number
is true. The rule is in 06. rules, and this is the enforcement.

Market is read from the card's Location frontmatter. An India packet must carry
the Indian number and Mysuru, must not carry the German number or Stuttgart, and
must render the B.E. as a CGPA on the ten point scale with the M.Sc. as 1.8/5
beside a link that explains the German grading scheme, which is either the Wikipedia page or the degree programme's own regulations page. An EU packet must carry the German
number and must not carry the Indian one.

The port is literal, so the checks, the wording and the exit code match the
original, which was diffed against it over the archived cards.

Run:
  .venv/bin/python scripts/market_gate.py              every card in the vault
  .venv/bin/python scripts/market_gate.py <card.md>... specific cards
"""

import re
import sys
import urllib.parse
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
CARDS_DIR = VAULT / "application artifacts" / "job cards"

PHONE_IN = "+91 9986093799"
PHONE_EU = "+49 17685648702"
# The M.Sc. grade is on a German scale, so an Indian reader needs a link that
# explains it. Either link does that job. The Wikipedia page was the original, and
# the India base now links the degree programme's own regulations page instead,
# which is the better source. The gate checked for the Wikipedia string alone and so
# failed a CV that was byte-identical to the frozen base above the projects.
GRADE_LINKS = ("Academic_grading_in_Germany",
               "infotech.uni-stuttgart.de/program")


def file_url_to_tex(url):
    """A frontmatter file:// value as the path of its LaTeX source."""
    if not url:
        return None
    p = urllib.parse.unquote(re.sub(r"^file://", "", url).strip())
    return re.sub(r"\.pdf$", ".tex", p)


def check(card):
    try:
        src = Path(card).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    loc = (re.search(r"^Location:\s*(.+)$", src, re.M) or [None, ""])[1] if re.search(
        r"^Location:\s*(.+)$", src, re.M) else ""
    market = "IN" if re.search(r"india", loc, re.I) else "EU"

    cv_m = re.search(r"^cv:[^\S\n]*(\S+)", src, re.M)
    cl_m = re.search(r"^coverletter:[^\S\n]*(\S+)", src, re.M)
    cv_tex = file_url_to_tex(cv_m.group(1) if cv_m else None)
    cl_tex = file_url_to_tex(cl_m.group(1) if cl_m else None)

    problems = []
    # An empty cv key on a live card means the packet is missing or unlinked, which
    # is a failure rather than a skip. Nine cards once slipped through exactly this
    # way.
    #
    # A missing letter is NOT a failure any more. He ruled that every card in
    # `to apply` carries a CV and that letters are produced on request only, so a
    # card with no letter is the normal state. A letter that exists is still checked
    # for the right market, which is the error this gate was built for.
    if not cv_tex:
        problems.append("card has no cv: link")

    for label, tex in (("CV", cv_tex), ("letter", cl_tex)):
        if not tex:
            continue
        if not Path(tex).exists():
            problems.append(f"{label} tex missing: {tex}")
            continue
        t = Path(tex).read_text(encoding="utf-8", errors="replace")
        if market == "IN":
            if PHONE_IN not in t:
                problems.append(f"{label} lacks Indian phone")
            if PHONE_EU in t:
                problems.append(f"{label} carries German phone")
            if label == "CV":
                if not re.search(r"Mysuru", t):
                    problems.append("CV lacks Mysuru location")
                if re.search(r"Stuttgart,\s*DE", t):
                    problems.append("CV carries Stuttgart location")
                if not re.search(r"CGPA:\s*8\.9/10", t):
                    problems.append("CV lacks 10 point B.E. CGPA")
                if not re.search(r"1\.8/5", t):
                    problems.append("CV M.Sc. grade not rendered as 1.8/5")
                if not any(x in t for x in GRADE_LINKS):
                    problems.append("CV lacks a grading scheme link")
        else:
            if PHONE_EU not in t:
                problems.append(f"{label} lacks German phone")
            if PHONE_IN in t:
                problems.append(f"{label} carries Indian phone")

    return market, problems


def main():
    args = sys.argv[1:]
    cards = args if args else sorted(str(p) for p in CARDS_DIR.glob("*.md"))

    fail = passed = skipped = 0
    for card in cards:
        result = check(card)
        if result is None:
            skipped += 1
            continue
        market, problems = result
        name = Path(card).name
        if problems:
            fail += 1
            print(f"FAIL [{market}] {name}")
            for p in problems:
                print(f"     {p}")
        else:
            passed += 1
            print(f"PASS [{market}] {name}")

    tail = f", {skipped} unreadable" if skipped else ""
    print(f"\n{passed + fail} packets, {fail} FAIL, {passed} PASS{tail}")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
