"""Mechanical enforcement of the cover letter rules.

A direct port of letter-gate.mjs, which was written after a batch shipped ten
letters that each broke the same rules while a six-agent critic fleet passed all
ten, because every sentence in them was true. Truth is necessary and not
sufficient. These checks are the part a language model keeps talking itself out
of, so they are a script instead.

The port is deliberately literal. Check order, severities and detail wording all
match the original, because the two were diffed over 396 letters to prove they
agree. Improving a check here means changing behaviour, so it is done knowingly
and not while translating.

Run:
  .venv/bin/python scripts/letter_gate.py <letter.tex ...>
  .venv/bin/python scripts/letter_gate.py --all      every *-coverletter.tex in the letters folder
  .venv/bin/python scripts/letter_gate.py --json     machine readable

Exit code 1 if any letter FAILS. A FAIL blocks delivery, per 06. rules.

Revised 2026-10-15 after the MOTOR Ai letter, the first letter he accepted.
The port is no longer literal. The Q-A-W checks are retired, the paragraph
count is three to five, the company must be named, the work authorisation line
is required on German letters, and every phrase he flagged as an AI pattern in
that session is a FAIL. See the Letters rules in 06. rules and the 2026-10-15
section of 10. lessons learnt.
"""

import json
import re
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
LETTERS = VAULT / "application artifacts" / "coverletters"

I = re.I

# Phrases that disclose a gap. The ban is absolute, since gaps are interview material.
GAP_PATTERNS = [
    r"\bI have not\b", r"\bI ha[sv]e no record\b", r"\bthe gap\b", r"\btwo gaps\b",
    r"\bone gap\b", r"\bI lack\b", r"\bnew ground\b", r"\bI would be learning\b",
    r"\bwould have to learn\b", r"\bI am willing to learn\b", r"\bgrow into\b",
    r"\bnot aspiration\b", r"\bI should say\b", r"\bI should state\b",
    r"\bhave never\b", r"\brather than arrive with\b", r"\bI did not want that to reach you\b",
    r"\boutside (its|the|my) scope\b", r"\bstopped (just )?short\b", r"\bcame close\b",
]

# Openings that are a bare position line or a verdict on his own fit.
WEAK_OPENING = [
    r"^I am applying for the .{0,90}position[^.]*\.\s*(Your|The)\b",
    r"\bI will be direct about the shape of my fit\b",
    r"\breads very close to how I actually\b",
    r"\bI want to lead with it and be straight\b",
]

# Resume-fact fingerprints. The limit is two distinct items.
RESUME_ITEMS = [
    ("continental/aspice", r"\bASPICE\b|\bMC/DC\b|vehicle dynamics"),
    ("imu project", r"nRF52840|Allan deviation|Madgwick|magnetometer"),
    ("ball-balancing", r"ball balancing|ESP32"),
    ("thesis", r"Jetson|TensorRT|BoT-SORT|YOLO-E|RGB-D"),
    ("hiwi segmentation", r"(?<![a-z])liver(?![a-z])|phantom fabrication|MONAI|liver vasculature"),
    ("chess arms", r"MuJoCo|inverse kinematics"),
    ("maze/sim", r"TurtleBot|Gazebo|slam.?toolbox|Nav2"),
    ("sofdcar", r"SofDCar|\bHough\b"),
]

BANNED_PUNCT = r"[:\u2014]|(?<!\\)[()]"   # colons, em-dashes, brackets

AI_PROSE = [
    r"\bnot only\b[^.]*\bbut also\b", r"\bit is ?n[o']?t (just )?[^.]*, it(?:'s| is)\b",
    r"\bdelve\b|\btapestry\b|\btestament\b|\bpivotal\b|\bunderscore\b|\brobust\b|\bseamless\b",
    r"\bleverag(e|ing)\b|\bfoster\b|\bcomprehensive\b|\bmyriad\b|\bshowcase\b|\bspearhead",
    r"\bpassionate\b|\bpassion for\b|\bresonate\b",
    r"\bstops being\b[^.]*\bbecomes\b",
    r"\brather than\b", r"\bless (on|about|from)\b[^.]*\bthan (on|about|from)\b",
]

# Manufactured conviction with no measurement in the same sentence.
EPIPHANY = (r"\b(taught me|showed me|convinced me|made me realis?ze|made me realise|"
            r"I came to (see|believe|understand)|I have come to|I learned that|"
            r"I realis?zed|I believe that|I am convinced|it struck me)\b")

BOILERPLATE_P1 = (r"^\s*(I am writing to|I would like to (apply|express)|Please (accept|find)|"
                  r"It is with (great )?(enthusiasm|interest|excitement)|I am excited to apply|"
                  r"With (great )?interest)")
ORIGIN_HOOK = (r"\b(ever since|for as long as I can remember|from a young age|"
               r"since childhood|my fascination with)\b")

RESEARCH_TELL = (r"\b(I read|I learned that your|while researching|"
                 r"according to (your|the) (website|site|posting)|"
                 r"your (website|site) (says|states))\b")

PSEUDO_PROFOUND = [
    r"\bat the end of the day\b",
    r"\bmore than (that|anything)\b",
    r"\bthat is (exactly )?(what|why|where) .{0,40}\bmatters?\b",
    r"\bis not (just|merely|simply|only) (a|an|about)\b",
    r"\bthe (real|true) (question|challenge|problem) is\b",
    r"\bthis is (precisely|exactly) (the|why|what)\b",
]

# Sentence shapes a model reaches for when it has no real content, or when it
# clones a formula from the exemplar.
FORMULA = [
    ("DECLARED-WANT", [
        r"\bdedicate myself\b",
        r"\bthe (kind of )?work I (want|am looking)\b",
        r"\bI want (more of|to continue)\b",
    ]),
    ("TOTALITY", [
        r"\bend[- ]to[- ]end\b",
        r"\bentire(ly)?\b",
        r"\bsingle[- ]?handed",
        r"\bmyself as\b",
    ]),
    ("DURATION", [
        r"\b(\d+|one|two|three|four|five|six|several)\s+(years?|months?)\b",
    ]),
    ("SELF-PORTRAIT", [
        r"\bthrough ?line\b",
        r"\bI recogni[sz]ed my own\b",
        r"\bgenuine (respect|interest|curiosity)\b",
    ]),
    ("FIT-MAPPING", [
        r"\bthe experience closest to\b",
        r"\bmatches your\b",
        r"\bexactly what you need\b",
    ]),
    ("SESSION-FLAGGED", [
        # Every phrase below was struck by him as an AI pattern on 2026-10-15.
        r"\beasy to state\b", r"\bstayed with me\b", r"\bpart of the stack\b",
        r"\bhas to work that way\b", r"\bso I applied here\b",
        r"\brelease by release\b", r"\bfinally decided\b", r"\bthe cost of that choice\b",
        r"\bsettles? the question\b", r"\banswers to the same question\b",
        r"\bin the other direction\b", r"\bV[- ]model\b", r"\bside of the V\b",
        r"\bthis role interests me\b", r"\bThis is why I am applying\b",
        r"\bwork on that decision\b", r"\bI am an? (embedded|software)",
        # Struck with the Agile Robots letter, 2026-10-15.
        r"\bfor a different reason\b", r"\bsat between\b", r"\bIn each of (them|these)\b",
        r"\bthat fits how I think\b", r"\bshould be spent\b",
    ]),
    ("FORMULA-CLOSER", [
        r"\bwelcome the opportunity\b", r"\bhow I (can|could) contribute\b",
        r"\blook forward to discussing\b",
        r"\bin further detail\b",
        r"\bThank you for (your consideration|considering)\b",
        r"\bThank you for the opportunity to apply\b",
    ]),
]

STOPWORDS_7 = {
    "because", "between", "through", "without", "against", "further",
    "another", "already", "instead", "working", "engineering", "systems",
    "position", "software", "project", "available", "relocate", "stuttgart",
}


def sentences(s):
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", s) if x.strip()]


def body(tex):
    """The letter's prose, with the preamble, comments and LaTeX commands removed."""
    doc = tex.find("\\begin{document}")
    frm = 0 if doc == -1 else doc
    i = tex.find("\\letterhead", frm)
    s = tex[frm:] if i == -1 else tex[i + 11:]
    s = re.sub(r"\\end\{document\}[\s\S]*$", "", s)
    s = re.sub(r"^\s*%.*$", "", s, flags=re.M)        # full-line LaTeX comments
    s = re.sub(r"([^\\])%.*$", r"\1", s, flags=re.M)  # trailing comments
    s = s.replace("\\\\", "\n")
    s = re.sub(r"\\[a-zA-Z]+\s?", "", s)
    return s.strip()


def company_of(path):
    name = Path(path).name
    name = re.sub(r"^sbm_", "", name)
    name = re.sub(r"_\d\d_\d\d-coverletter\.tex$", "", name)
    name = re.sub(r"-coverletter\.tex$", "", name)
    return name.split("-")[0]


def check(path):
    txt = body(Path(path).read_text(encoding="utf-8", errors="replace"))
    findings = []

    def add(name, severity, detail):
        findings.append({"check": name, "severity": severity, "detail": detail})

    company = company_of(path)
    # The slug drops spaces, so "motorai" must still find "MOTOR Ai" in the prose.
    escaped = r"\s?".join(re.escape(c) for c in company)
    raw = Path(path).read_text(encoding="utf-8", errors="replace")

    paras = [s.strip() for s in txt.split("\n") if s.strip()]
    body_paras = [p for p in paras if len(re.split(r"\s+", p)) >= 25]
    p1 = body_paras[0] if body_paras else ""
    p2 = body_paras[1] if len(body_paras) > 1 else ""
    p3 = body_paras[-1] if body_paras else ""

    # A. STRUCTURE
    if not 3 <= len(body_paras) <= 5:
        add("STRUCTURE", "FAIL", f"{len(body_paras)} body paragraphs, 3 to 5 required")

    # OPENING. First name, the degree as he names it, and no job-title label
    # that can conflict with the advertised role.
    if p1 and not re.match(r"I am Shashank\b", p1):
        add("OPENING", "FAIL", "paragraph 1 must open with \"I am Shashank\"")
    if re.search(r"Information Technology", txt):
        add("OPENING", "FAIL", "degree must read Embedded Systems Engineering, never Information Technology")
    first = sentences(p1)[0] if p1 and sentences(p1) else ""
    if re.search(r"\b(engineer|developer|specialist|programmer)\b", first, I):
        add("OPENING", "FAIL", f'first sentence labels him with a job title: "{first}"')

    # TAGLINE. The letterhead is name and contact line only, his ruling 2026-10-15.
    if re.search(r"\\fontsize\{12\}\{14\.4\}|^\s*\{[^%\n]*\b(Engineer|Developer)\}\\\\", raw, re.M):
        add("TAGLINE", "FAIL", "letterhead carries a tagline under the name, remove it")

    # WORK-AUTH. German letters carry the residence permit line.
    if "+91" not in raw and not re.search(r"AufenthG", txt):
        add("WORK-AUTH", "FAIL", "German letter is missing the \u00a7 20 AufenthG work authorisation sentence")

    # B. EPIPHANY, flagged only when the sentence carries no measurement
    for s in sentences(txt):
        if re.search(EPIPHANY, s, I) and not re.search(r"\d", s):
            add("EPIPHANY", "FAIL", f'unmeasured conviction aphorism: "{s}"')

    # C. BOILERPLATE-HOOK
    if p1 and re.search(BOILERPLATE_P1, p1, I):
        first = sentences(p1)[0] if sentences(p1) else p1
        add("BOILERPLATE-HOOK", "FAIL", f'canned opening in paragraph 1: "{first}"')
    for s in sentences(txt):
        if re.search(ORIGIN_HOOK, s, I):
            add("BOILERPLATE-HOOK", "FAIL", f'origin-story hook: "{s}"')

    # D. LECTURE
    lecture = (rf"\b{escaped}(?:'s)?\b[^.]{{0,40}}\b(builds?|develops?|offers?|provides?|"
               r"deploys?|operates?|delivers?|pioneers?|specialis?zes?|"
               r"is (building|developing)|has (built|developed|deployed))\b")
    for s in sentences(txt):
        if re.search(lecture, s, I):
            add("LECTURE", "FAIL", f'company as subject of technical verb: "{s}"')
        if re.search(RESEARCH_TELL, s, I):
            add("LECTURE", "FAIL", f'explicit research tell: "{s}"')

    # E. SKILL-DUMP, paragraph 3 only
    if p3:
        for s in sentences(p3):
            if re.search(r"\bI bring\b", s, I):
                add("SKILL-DUMP", "FAIL", f'"I bring" in P3: "{s}"')
            if re.search(r"\b(experience|background|skills?|expertise|proficien\w+|hands-on)\b"
                         r"[^.]*,[^.]*,[^.]*\b(and|as well as)\b", s, I):
                add("SKILL-DUMP", "FAIL", f'skills noun with 3-part list in P3: "{s}"')

    # F. PSEUDO-PROFOUND
    for s in sentences(txt):
        for r in PSEUDO_PROFOUND:
            if re.search(r, s, I):
                add("PSEUDO-PROFOUND", "FAIL", f'pseudo-profound transition: "{s}"')
                break

    # GAP-DISCLOSURE
    for s in sentences(txt):
        if any(re.search(r, s, I) for r in GAP_PATTERNS):
            add("GAP-DISCLOSURE", "FAIL", f'gap phrase in: "{s}"')

    # RESUME-RECITAL
    items = [k for k, r in RESUME_ITEMS if re.search(r, txt, I)]
    if len(items) > 2:
        add("RESUME-RECITAL", "FAIL",
            f"{len(items)} resume items, limit is 2: {', '.join(items)}. "
            "Breadth is recital; the letter goes deep on at most two.")
    elif len(items) == 2:
        add("RESUME-RECITAL", "REVIEW",
            f"2 resume items: {', '.join(items)}. "
            "Confirm by hand both are explained in depth, not recited.")

    # WEAK-OPENING
    if p1 and any(re.search(r, p1, I) for r in WEAK_OPENING):
        add("WEAK-OPENING", "FAIL",
            "opens on a bare position line or a self-assessment, not the layer-two tie")

    # PUNCTUATION
    for s in sentences(txt):
        m = re.search(BANNED_PUNCT, s)
        if m:
            add("PUNCTUATION", "FAIL", f'found {m.group(0)} in: "{s}"')

    # AI-PROSE
    for s in sentences(txt):
        if any(re.search(r, s, I) for r in AI_PROSE):
            add("AI-PROSE", "FAIL", f'AI prose pattern in: "{s}"')

    # FORMULA categories
    for name, regexes in FORMULA:
        for s in sentences(txt):
            if any(re.search(r, s, I) for r in regexes):
                if name == "DURATION":
                    add(name, "REVIEW", f'duration stated, confirm it matches the CV dates exactly and is never a sum: "{s}"')
                else:
                    add(name, "FAIL", f'formula pattern in: "{s}"')

    # PUNCHLINE
    for idx, p in enumerate(body_paras):
        sents = sentences(p)
        last = sents[-1] if sents else None
        if last and re.search(r"\bI (want|hope|enjoy(ed)?|love)\b|\blooking for\b|\bexcit", last, I):
            add("PUNCHLINE", "FAIL", f'paragraph {idx + 1} ends on a sentiment: "{last}"')

    # NUMBER-DENSITY, whole letter. The permit paragraph and a Level N
    # automation grade are not measurements and do not count.
    measured = re.sub(r"~?\s?\d+\s+AufenthG|\bLevel \d\b|\bL\d\b", "", txt)
    nums = re.findall(r"(?<![a-zA-Z0-9_.])\d+(?:\.\d+)?(?![a-zA-Z0-9_])", measured)
    if len(nums) > 4:
        add("NUMBER-DENSITY", "FAIL",
            f"{len(nums)} figures in the letter ({', '.join(nums)}), limit is 4. "
            "Narrative over benchmark datasheet.")

    # H. ECHO
    freq7 = {}
    for w in re.findall(r"\b[a-z]{7,}\b", txt.lower()):
        if w != company.lower() and w not in STOPWORDS_7:
            freq7[w] = freq7.get(w, 0) + 1
    echoes = [f"{w} ({n}x)" for w, n in freq7.items() if n >= 3]
    if echoes:
        add("ECHO", "REVIEW", f"tokens appearing 3+ times: {', '.join(echoes)}")

    # DRUMBEAT
    counts = {}
    for w in re.findall(r"\b[a-z]{5,}\b", txt.lower()):
        if w != company.lower():
            counts[w] = counts.get(w, 0) + 1
    drum = [f"{w} {n}x" for w, n in counts.items() if n >= 5]
    if drum:
        add("DRUMBEAT", "REVIEW", ", ".join(drum))

    # LENGTH
    words = len([w for w in re.split(r"\s+", txt) if w])
    if words < 300:
        add("LENGTH", "FAIL", f"{words} words, minimum 300")
    elif words > 500:
        add("LENGTH", "FAIL", f"{words} words, maximum 500. One page is the bound.")

    # NO-PRODUCT-TIE
    after_greeting = " ".join(txt.split("\n")[1:])
    name_hits = len(re.findall(escaped, after_greeting, I))
    if name_hits == 0:
        add("WHY-COMPANY", "FAIL",
            "company never named. The letter must say why this company, in his own reason")

    verdict = "FAIL" if any(f["severity"] == "FAIL" for f in findings) else "PASS"
    return {"file": str(path), "verdict": verdict, "words": words, "findings": findings}


def main():
    args = sys.argv[1:]
    as_json = "--json" in args
    files = [a for a in args if a.endswith(".tex")]
    if "--all" in args:
        files = sorted(str(p) for p in LETTERS.glob("*-coverletter.tex"))
    if not files:
        print("usage: letter_gate.py <letter.tex ...> | --all [--json]", file=sys.stderr)
        sys.exit(2)

    results = [check(f) for f in files]

    if as_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for r in results:
            mark = "FAIL" if r["verdict"] == "FAIL" else "PASS"
            print(f"\n{mark} {r['file']}  ({r['words']}w)")
            for x in r["findings"]:
                print(f"   {x['severity']:<6} {x['check']:<16} {x['detail']}")
        failed = sum(1 for r in results if r["verdict"] == "FAIL")
        print(f"\n{len(results)} letters, {failed} FAIL, {len(results) - failed} PASS")

    sys.exit(1 if any(r["verdict"] == "FAIL" for r in results) else 0)


if __name__ == "__main__":
    main()
