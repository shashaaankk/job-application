"""Score the cards in `matched`, one agent process per card, five at a time.

The scorer works for the user. It reads a posting the way an experienced recruiter
and hiring manager in that field would, then scores the card on the axes in
`skills/scoring/references/scorer-prompt.md` and drawn on the "Scoring radar" page of
`job-application.drawio`.

  knockouts      only the user's own hard preferences and facts the posting states
                 outright. Unknown passes.
  quick scan     would a recruiter put the CV in the yes pile in about seven seconds
  must-haves     3 to 5 capabilities the work cannot be done without, read from the
                 work itself, each scored 0 to 3 against the user's record
  nice-to-haves  0 to 4 capabilities that make the work easier
  want           role and domain closeness to the user's preferences
  tailoring      the same axes after honest tailoring, and the edits that get there

The agent returns numbers and reasons. This script computes the tier, so the ranking
does not depend on which agent ran. The tier maps onto the band the rest of the
pipeline already reads, A to 3, B to 2 and C to 1, so `move_card.py`, its caps and
`prune_matched.py` work unchanged.

The agent runs no commands. This script sets the board title and moves the cards,
so any agent that can return JSON can score.

Which agent. Antigravity by default, because it runs on a separate quota and the
Claude budget is spent on the CV and the letter. Set SCORE_CMD to use another one.
The command receives the prompt on stdin and must print the JSON object on stdout,
for example `SCORE_CMD="claude -p --output-format text"`. SCORE_AGENT names it on
the card.

Run:
  .venv/bin/python scripts/score.py                 every unscored card in matched
  .venv/bin/python scripts/score.py --limit 5       a slice, for checking
  .venv/bin/python scripts/score.py --dry-run       what it would score, no calls
"""

import argparse
import datetime as dt
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

print = partial(print, flush=True)

VAULT = Path(__file__).resolve().parent.parent
CARDS = VAULT / "application artifacts" / "job cards"
KNOWLEDGE = VAULT / "knowledge"
# The prompt lives in the skill, so the skill and the scorer cannot drift apart.
PROMPT = VAULT / "skills" / "scoring" / "references" / "scorer-prompt.md"
STATE = VAULT / "scripts" / "data" / "move-counters.json"
BOARD = VAULT / "01. job application tracker.md"
SOURCE_COLUMN = "matched"
TARGET_COLUMN = "to apply"

WORKERS = 5                       # his figure
AGY = "agy"
AGY_TIMEOUT = 900
SCORE_CMD = os.environ.get("SCORE_CMD", "").strip()
AGENT_NAME = os.environ.get("SCORE_AGENT") or (
    shlex.split(SCORE_CMD)[0] if SCORE_CMD else "Antigravity")

# What the scorer is shown. The method lives in the skill's scorer prompt, so the
# skill file itself is not sent, which saves about 13,000 characters per card.
# `06. rules.md` stays because leaving it out once let a naval defence posting reach
# `to apply`. Rule 11 puts European defence out of scope and lives only there.
CONTEXT = ["06. rules.md", "04. preferences.md", "05. profile.md"]
NOTE_CHARS = 900                  # per knowledge note, so the notes cost ~15k chars

TIER_BAND = {"A": 3, "B": 2, "C": 1}

# The CV parts a tailored variant may change. Without the file any edit is allowed.
SLOTS_FILE = VAULT / "scripts" / "data" / "cv-slots.txt"
SLOTS = ([l.strip() for l in SLOTS_FILE.read_text(encoding="utf-8").splitlines()
          if l.strip() and not l.startswith("#")] if SLOTS_FILE.exists() else [])
OTHER = "other"

# The approval block on the card. `pending.py` reads the ticks under this heading.
APPROVAL_HEADING = "#### Tailoring edits for the user to approve"
BASE_AS_IS = "Use the base CV as it is"

ITEM = {
    "type": "object",
    "required": ["capability", "from_duty", "why_needed", "user_evidence", "score",
                 "gap", "time_to_close", "reason", "tailored_score", "tailored_reason"],
    "properties": {
        "capability": {"type": "string"},
        "from_duty": {"type": "string"},
        "activity": {"type": "string"},
        "system": {"type": "string"},
        "constraints": {"type": "string"},
        "user_evidence": {"type": "string"},
        "reason": {"type": "string"},
        "why_needed": {"type": "string"},
        "tailored_reason": {"type": "string"},
        "score": {"type": "integer", "minimum": 0, "maximum": 3},
        "gap": {"type": "string"},
        "time_to_close": {"type": "string", "enum": ["none", "days", "weeks", "months"]},
        "tailored_score": {"type": "integer", "minimum": 0, "maximum": 3},
    },
}

SCHEMA = {
    "type": "object",
    "required": ["language", "title_en", "preference_verdict", "preference_detail",
                 "quick_scan", "quick_scan_reason", "must_haves", "want_role",
                 "want_role_reason", "want_domain", "want_domain_reason",
                 "tailored_quick_scan", "tailored_quick_scan_reason",
                 "tailoring_edits", "questions"],
    "properties": {
        "language": {"type": "string"},
        "title_en": {"type": "string"},
        "translation_en": {"type": "string"},
        "preference_verdict": {"type": "string", "enum": ["pass", "reject"]},
        "preference_detail": {"type": "string"},
        "quick_scan": {"type": "integer", "minimum": 0, "maximum": 3},
        "quick_scan_reason": {"type": "string"},
        "must_haves": {"type": "array", "minItems": 1, "maxItems": 5, "items": ITEM},
        "nice_to_haves": {"type": "array", "maxItems": 4, "items": ITEM},
        "want_role": {"type": "integer", "minimum": 0, "maximum": 3},
        "want_role_reason": {"type": "string"},
        "want_domain": {"type": "integer", "minimum": 0, "maximum": 3},
        "want_domain_reason": {"type": "string"},
        "tailored_quick_scan": {"type": "integer", "minimum": 0, "maximum": 3},
        "tailored_quick_scan_reason": {"type": "string"},
        "tailoring_edits": {"type": "array", "items": {
            "type": "object", "required": ["edit", "slot", "why"],
            "properties": {"edit": {"type": "string"}, "why": {"type": "string"},
                           "slot": ({"type": "string", "enum": SLOTS + [OTHER]}
                                    if SLOTS else {"type": "string"})}}},
        "questions": {"type": "array", "items": {
            "type": "object", "required": ["question", "changes", "why"],
            "properties": {"question": {"type": "string"},
                           "changes": {"type": "string"},
                           "why": {"type": "string"}}}},
    },
}


def column_cards(column):
    found, cur, out = False, None, []
    for line in BOARD.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
            found = found or cur == column
            continue
        if cur != column:
            continue
        m = re.search(r"\[\[application artifacts/job cards/([^\]|]+)", line)
        if m:
            out.append(m.group(1).strip())
    if not found:
        raise SystemExit(f"the board has no '{column}' column, refusing to guess")
    return out


def card_parts(path):
    t = path.read_text(encoding="utf-8", errors="replace")
    def key(n):
        m = re.search(rf"^{re.escape(n)}:[ \t]*(.*)$", t, re.M)
        return m.group(1).strip() if m else ""
    jd = ""
    if "### Job Description" in t and "### Evaluation" in t:
        jd = t[t.index("### Job Description"):t.index("### Evaluation")]
        jd = jd.split("\n", 1)[1].strip().rstrip("-").strip()
    return t, {"title": key("Job Title"), "company": key("Company"),
               "location": key("Location"), "posting": key("Posting"),
               "score": key("Score")}, jd


def cv_text():
    """The base CV. One file per market holds the same evidence, so the first will do."""
    cvs = sorted((VAULT / "resume").glob("*.tex"))
    if not cvs:
        raise SystemExit("no CV in resume/, refusing to score without one")
    return cvs[0].name, cvs[0].read_text(encoding="utf-8")


def notes_text():
    """The knowledge notes licensed for a CV, each cut to NOTE_CHARS.

    Only `cv-ready: true` notes may be cited, so only those are shown. The cut keeps
    the evidence line and the opening, which is where each note states its scope.
    """
    out = []
    for p in sorted(KNOWLEDGE.glob("*.md")):
        if p.name.startswith("_"):
            continue
        t = p.read_text(encoding="utf-8")
        if not re.search(r"^cv-ready:\s*true\s*$", t, re.M):
            continue
        ev = re.search(r"^evidence:\s*(.*)$", t, re.M)
        lv = re.search(r"^level:\s*(.*)$", t, re.M)
        body = t.split("---", 2)[-1].strip()
        if len(body) > NOTE_CHARS:
            body = body[:NOTE_CHARS].rsplit(" ", 1)[0] + " …"
        out.append(f"--- {p.stem} (level {lv.group(1) if lv else '?'}; evidence "
                   f"{ev.group(1) if ev else '?'})\n{body}")
    return "\n\n".join(out)


def prompt_for(meta, jd):
    ctx = "\n\n".join(f"===== {f} =====\n{(VAULT / f).read_text(encoding='utf-8')}"
                      for f in CONTEXT)
    cv_name, cv = cv_text()
    slots = (", ".join(f'"{s}"' for s in SLOTS) + f', or "{OTHER}"') if SLOTS else \
        "any short name, since the user has not limited the CV"
    fill = {"SLOTS": slots, "CONTEXT": ctx, "CV_NAME": cv_name, "CV": cv, "NOTES": notes_text(),
            "POSTING": meta["posting"], "TITLE": meta["title"],
            "COMPANY": meta["company"], "LOCATION": meta["location"], "JD": jd}
    text = PROMPT.read_text(encoding="utf-8")
    for k, v in fill.items():
        text = text.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{[A-Z_]+\}\}", text)
    if left:
        raise SystemExit(f"the scorer prompt has unfilled slots {left}, refusing to send it")
    return text


def run_agent(prompt):
    """(payload, error). One agent process, JSON out."""
    if SCORE_CMD:
        schema_note = ("\n\nReturn one JSON object matching this schema.\n"
                       + json.dumps(SCHEMA))
        try:
            r = subprocess.run(shlex.split(SCORE_CMD), input=prompt + schema_note,
                               capture_output=True, text=True, timeout=AGY_TIMEOUT,
                               cwd=tempfile.gettempdir())
        except subprocess.TimeoutExpired:
            return None, f"timed out after {AGY_TIMEOUT}s"
        if r.returncode != 0:
            return None, f"exit {r.returncode}: {(r.stderr or '').strip()[:160]}"
        payload = find_payload(r.stdout) or find_payload(
            r.stdout[r.stdout.find("{"):r.stdout.rfind("}") + 1])
        if not payload:
            return None, "no JSON object with the scores in the output"
        payload["_usage"], payload["_seconds"] = {}, 0
        return payload, None

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(SCHEMA, fh)
        schema_path = fh.name
    # An empty working folder. Run from the vault, the agent opened files turn after
    # turn, which cost 1.5 million cached tokens and pushed cards past the timeout.
    # Everything it needs is already in the prompt.
    empty = tempfile.mkdtemp(prefix="score-")
    cmd = [AGY, "--dangerously-skip-permissions", "--output-format", "json",
           "--json-schema", schema_path, f"--print={prompt}"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=AGY_TIMEOUT,
                           cwd=empty)
    except subprocess.TimeoutExpired:
        return None, f"timed out after {AGY_TIMEOUT}s"
    finally:
        Path(schema_path).unlink(missing_ok=True)
        Path(empty).rmdir()
    if r.returncode != 0:
        return None, f"exit {r.returncode}: {(r.stderr or '').strip()[:160]}"
    try:
        out = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None, "the output was not JSON"
    payload = find_payload(out)
    if not payload:
        return None, f"no structured output in the response (status {out.get('status')})"
    payload["_usage"] = out.get("usage", {})
    payload["_seconds"] = out.get("duration_seconds", 0)
    return payload, None


def find_payload(o):
    """The scored object, wherever the wrapper put it."""
    if isinstance(o, dict):
        if "must_haves" in o and "want_role" in o:
            return o
        for v in o.values():
            r = find_payload(v)
            if r:
                return r
    if isinstance(o, list):
        for v in o:
            r = find_payload(v)
            if r:
                return r
    if isinstance(o, str) and o.strip().startswith("{"):
        try:
            return find_payload(json.loads(o))
        except Exception:
            return None
    return None


def flat(v):
    """A field as text, whatever shape the scorer returned it in.

    The schema asks for strings, and one card came back with `preference_detail` as
    an object of per-field verdicts. That crashed the whole run after 92 cards had
    already been evaluated, and the run exited before moving a single card. A schema
    is a request, not a guarantee, so every field is flattened here.
    """
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, float, bool)):
        return str(v)
    if isinstance(v, dict):
        return "\n".join(f"- {k}: {flat(x)}" for k, x in v.items())
    if isinstance(v, list):
        return "\n".join(f"- {flat(x)}" for x in v)
    return str(v)


def num(v, default=0):
    """A 0 to 3 score from whatever came back, so a "2" or a 2.0 does not crash."""
    try:
        return max(0, min(3, int(round(float(v)))))
    except (TypeError, ValueError):
        return default


def items(p, key):
    out = []
    for it in p.get(key) or []:
        if not isinstance(it, dict):
            continue
        s = num(it.get("score"))
        out.append({**it, "score": s,
                    "tailored_score": max(s, num(it.get("tailored_score"), s))})
    return out


def grade(p):
    """The tier and the numbers behind it, computed here and never by the agent.

    Must-haves carry three quarters of Can, because they decide whether the user can
    start. A must-have still at 0 after tailoring is a months gap in the core work,
    which is tier C whatever else holds. Want is the mean of role and domain.
    """
    mh, nh = items(p, "must_haves"), items(p, "nice_to_haves")
    if not mh:
        raise ValueError("the agent named no must-haves")
    mean = lambda xs: sum(xs) / len(xs)
    def can(key):
        m = mean([i[key] for i in mh])
        n = mean([i[key] for i in nh]) if nh else m
        return 0.75 * m + 0.25 * n
    # Tailoring counts only through edits in an allowed CV slot. When none is left,
    # the tailored scores fall back to the base, because the CV generator would
    # refuse every edit that produced them.
    edits, dropped = [], []
    for e in p.get("tailoring_edits") or []:
        text = flat(e.get("edit")) if isinstance(e, dict) else flat(e)
        slot = flat(e.get("slot")).lower() if isinstance(e, dict) else ""
        why = flat(e.get("why")) if isinstance(e, dict) else ""
        if text:
            text += f" Why: {why_or(why)}"
            (edits if not SLOTS or slot in SLOTS else dropped).append((slot, text))
    if not edits:
        for i in mh + nh:
            i["tailored_score"] = i["score"]
    scan_b = num(p.get("quick_scan"))
    scan_t = max(scan_b, num(p.get("tailored_quick_scan"), scan_b)) if edits else scan_b
    role, dom = num(p.get("want_role")), num(p.get("want_domain"), 2)
    g = {"mh": mh, "nh": nh, "scan_b": scan_b, "scan_t": scan_t,
         "edits": edits, "dropped": dropped,
         "can_b": can("score"), "can_t": can("tailored_score"),
         "role": role, "domain": dom, "want": (role + dom) / 2}

    if flat(p.get("preference_verdict")) == "reject":
        g["tier"], g["why"] = None, "a knockout applies"
    elif min(i["tailored_score"] for i in mh) == 0:
        g["tier"], g["why"] = "C", "a must-have is a months gap even after tailoring"
    elif g["want"] < 1.5:
        g["tier"], g["why"] = "C", f"want is {g['want']:.1f}, below 1.5"
    elif g["can_t"] < 1.5:
        g["tier"], g["why"] = "C", f"can after tailoring is {g['can_t']:.2f}, below 1.5"
    elif g["want"] >= 2.5 and g["can_t"] >= 2.25 and scan_t >= 2:
        g["tier"], g["why"] = "A", (f"want {g['want']:.1f}, can {g['can_t']:.2f} and "
                                    f"quick scan {scan_t} after tailoring all clear the A line")
    else:
        g["tier"], g["why"] = "B", (f"want {g['want']:.1f}, can {g['can_t']:.2f}, quick "
                                    f"scan {scan_t} after tailoring, below the A line")
    g["band"] = TIER_BAND.get(g["tier"], 0)
    return g


UNEXPLAINED = "UNEXPLAINED, the scorer gave no reason (rule 90)"


def why_or(v):
    """The reason, or a visible mark that there was none. Rule 90."""
    return flat(v) or UNEXPLAINED


def cell(v):
    return flat(v).replace("|", "/").replace("\n", " ")


def evaluation_text(p, g):
    """The Evaluation section. Numbers first, so the user can overturn it in seconds."""
    L = []
    t_en = flat(p.get("title_en"))
    if t_en:
        L += [f"**Title in English.** {t_en}", ""]
    tier = f"Tier {g['tier']} (band {g['band']})" if g["tier"] else "No tier"
    L += [f"**Scored by {AGENT_NAME}.** {tier}, preference match "
          f"{flat(p.get('preference_verdict'))}. Why: {g['why']}.", ""]
    L += ["**Job gives the user what the user wants.**",
          why_or(p.get("preference_detail")), ""]
    L += ["| Axis | Base CV | Tailored CV |", "| --- | --- | --- |",
          f"| Quick scan | {g['scan_b']} | {g['scan_t']} |",
          f"| Can (must-haves and nice-to-haves) | {g['can_b']:.2f} | {g['can_t']:.2f} |",
          f"| Want, role | {g['role']} | {g['role']} |",
          f"| Want, domain | {g['domain']} | {g['domain']} |", ""]
    L += [f"**Quick scan {g['scan_b']}.** {why_or(p.get('quick_scan_reason'))}", ""]
    if g["scan_t"] != g["scan_b"]:
        L += [f"**Quick scan after tailoring {g['scan_t']}.** "
              f"{why_or(p.get('tailored_quick_scan_reason'))}", ""]
    L += [f"**Want, role {g['role']}.** {why_or(p.get('want_role_reason'))}", "",
          f"**Want, domain {g['domain']}.** {why_or(p.get('want_domain_reason'))}", ""]
    for key, name in (("mh", "Must-haves"), ("nh", "Nice-to-haves")):
        if not g[key]:
            continue
        L += [f"**{name}.**", "",
              "| Capability | Why it is needed | The user's record | Score | Gap | "
              "Time to close | Why this score |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
        for i in g[key]:
            sc = (f"{i['score']}" if i["tailored_score"] == i["score"]
                  else f"{i['score']} → {i['tailored_score']}")
            why = cell(why_or(i.get("reason")))
            if i["tailored_score"] != i["score"]:
                why += f" Tailored: {cell(why_or(i.get('tailored_reason')))}"
            L.append(f"| {cell(i.get('capability'))} | {cell(why_or(i.get('why_needed')))} "
                     f"Posting: {cell(i.get('from_duty'))} | {cell(i.get('user_evidence'))} | "
                     f"{sc} | {cell(i.get('gap')) or 'none'} | "
                     f"{cell(i.get('time_to_close')) or '-'} | {why} |")
        L.append("")
    # Proposals only. Nothing reaches a CV until the user ticks it, and the CV is not
    # built until at least one box here is ticked, per rule 83.
    L += [f"{APPROVAL_HEADING}", "",
          "Tick what goes into this posting's CV. Nothing is built until one box is ticked.",
          ""] + [f"- [ ] {s + ': ' if s else ''}{x}" for s, x in g["edits"]] + \
         [f"- [ ] {BASE_AS_IS}", ""]
    if g["dropped"]:
        L += [f"**Dropped.** {len(g['dropped'])} proposed edit(s) fall outside the CV parts "
              f"a variant may change ({', '.join(SLOTS)}) and count for nothing:"] + \
             [f"- {x}" for _, x in g["dropped"]] + [""]
    if flat(p.get("language")).lower() not in ("english", "en", ""):
        L += [f"**Language.** The posting is in {flat(p['language'])}. An English rendering "
              f"is under its own heading below. The original above is the evidence, "
              f"and the translation is a reading aid.", ""]
    L += ["The user's correction in User Comments re-scores this card, and that is not "
          "a negotiation."]
    return "\n".join(L)


def write_card(path, raw, p, g):
    """Fill the Evaluation, the Score and the questions. The original text is kept."""
    ev_start = raw.index("### Evaluation")
    q_start = raw.index("### Questions / Comments")
    head, tail = raw[:ev_start], raw[q_start:]

    body = f"### Evaluation\n\n{evaluation_text(p, g)}\n\n"
    # the translation goes after the original, never over it
    tr = flat(p.get("translation_en"))
    if tr and flat(p.get("language")).lower() not in ("english", "en"):
        body += ("### Job Description in English\n\nMachine assisted translation for "
                 "reading only. The original above is the evidence that documents are "
                 f"written from.\n\n{tr}\n\n")

    # a question that names no decision it changes is dropped, per the skill
    qs = []
    for q in p.get("questions") or []:
        text = flat(q.get("question")) if isinstance(q, dict) else flat(q)
        changes = flat(q.get("changes")) if isinstance(q, dict) else ""
        why = flat(q.get("why")) if isinstance(q, dict) else ""
        if text and changes:
            qs.append(f"{text} (changes: {changes}. Why asked: {why_or(why)})")
    qtail = "### Questions / Comments\n\n" + (
        "\n".join(f"- [ ] {q}" for q in qs) if qs else
        "- [ ] Nothing the posting raises changes a decision.") + "\n"
    rest = tail[tail.index("\n", tail.index("### Questions / Comments")):]
    rest = rest.split("---", 1)
    after = ("\n\n---" + rest[1]) if len(rest) > 1 else "\n"

    out = head + body + qtail + after
    tier = f", tier {g['tier']}" if g["tier"] else ""
    out = re.sub(r"^Score:[ \t]*.*$",
                 f"Score: band {g['band']}, preference {p['preference_verdict']}{tier}",
                 out, count=1, flags=re.M)
    path.write_text(out, encoding="utf-8")


def helper(script, *args):
    """Run a board helper. Both hold the board lock, so they are safe beside a run."""
    r = subprocess.run([sys.executable, str(VAULT / "scripts" / script), *args],
                       capture_output=True, text=True, cwd=str(VAULT))
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=WORKERS)
    args = ap.parse_args()

    todo = []
    for stem in column_cards(SOURCE_COLUMN):
        p = CARDS / f"{stem}.md"
        if not p.exists():
            print(f"  skipped, the board link points at no file: {stem[:60]}")
            continue
        raw, meta, jd = card_parts(p)
        if meta["score"]:
            continue                       # already scored
        if len(jd) < 200:
            print(f"  skipped, the description is {len(jd)} characters: {stem[:50]}")
            continue
        todo.append((stem, p, raw, meta, jd))

    print(f"'{SOURCE_COLUMN}' holds {len(column_cards(SOURCE_COLUMN))} cards, "
          f"{len(todo)} unscored")
    if args.limit:
        todo = todo[:args.limit]
        print(f"limited to {len(todo)}")
    if args.dry_run:
        for stem, *_ in todo[:12]:
            print(f"   would score {stem[:70]}")
        if todo:
            print(f"prompt for the first card: {len(prompt_for(todo[0][3], todo[0][4])):,} characters")
        return 0
    if not todo:
        return 0

    print(f"scoring with {AGENT_NAME}, {args.workers} at a time")
    run_id = dt.datetime.now().strftime("%Y-%m-%dT%H%M")
    print(f"run id {run_id}, which scopes his caps")

    def one(item):
        stem, p, raw, meta, jd = item
        payload, err = run_agent(prompt_for(meta, jd))
        return stem, p, raw, meta, payload, err

    done, failed, untitled = [], [], []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, (stem, p, raw, meta, payload, err) in enumerate(ex.map(one, todo), 1):
            if not err:
                try:
                    g = grade(payload)
                    write_card(p, raw, payload, g)
                except Exception as e:
                    err = f"grading or writing failed: {type(e).__name__} {e}"
            if err:
                failed.append((stem, err))
                print(f"  [{i}/{len(todo)}] FAILED {meta['company'][:20]:20s} {err[:60]}")
                continue
            t_en = flat(payload.get("title_en"))
            if t_en and helper("board_title.py", "--card", stem, "--title", t_en)[0] != 0:
                untitled.append(stem)
            done.append((stem, payload, g))
            u = payload.get("_usage", {})
            print(f"  [{i}/{len(todo)}] tier {g['tier'] or '-'} want {g['want']:.1f} "
                  f"can {g['can_b']:.2f}→{g['can_t']:.2f} scan {g['scan_b']}→{g['scan_t']} "
                  f"{meta['company'][:22]:22s} {payload['_seconds']:.0f}s  "
                  f"in {u.get('input_tokens', 0):,}")

    # Moves happen here, after scoring, so tier A always claims the caps before B.
    order = {"A": 0, "B": 1}
    eligible = sorted(((s, g) for s, _, g in done if g["tier"] in order),
                      key=lambda x: (order[x[1]["tier"]], -x[1]["can_t"], -x[1]["want"]))
    moved, refused = [], []
    for stem, g in eligible:
        code, out = helper("move_card.py", "--card", stem, "--band", str(g["band"]),
                           "--run", run_id)
        (moved if code == 0 else refused).append((stem, g["tier"], out.splitlines()[-1:]))

    tiers = {}
    for _, _, g in done:
        tiers[g["tier"] or "knockout"] = tiers.get(g["tier"] or "knockout", 0) + 1
    print(f"\nscored {len(done)}, failed {len(failed)}")
    print(f"tiers: {dict(sorted(tiers.items()))}")
    print(f"moved to '{TARGET_COLUMN}': {len(moved)}")
    if refused:
        print(f"eligible but kept in '{SOURCE_COLUMN}': {len(refused)}, a cap or a "
              f"same-poster rule refused them:")
        for s, t, why in refused[:8]:
            print(f"   tier {t}  {s[:55]}  {' '.join(why)[:60]}")
    if untitled:
        print(f"board title not set for {len(untitled)}")
    tin = sum(d.get("_usage", {}).get("input_tokens", 0) for _, d, _ in done)
    print(f"agent input tokens {tin:,} across {len(done)} cards")
    for stem, err in failed[:8]:
        print(f"   {stem[:60]}  {err[:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
