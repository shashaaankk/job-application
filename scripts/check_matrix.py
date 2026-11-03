"""Check queries.yaml against 04. preferences.md.

The preferences file is prose written by a human, so nothing here tries to
compile it. This script reports coverage and staleness, and the reading of a
loose entry stays a human judgement. It exits non-zero when a preference has
no plausible counterpart in the matrix, when the matrix carries an entry the
preferences no longer list, or when the matrix is older than the preferences.

Run:  .venv/bin/python check_matrix.py [--vault PATH]
"""

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

STOP = {"and", "or", "the", "of", "a", "an", "for", "in", "context", "developer",
        "engineer", "mwd", "m", "w", "d"}


def tokens(s):
    s = s.lower()
    s = s.replace("c++", "cpp").replace("&", " and ")
    # A portal is written either as a brand or as a domain, so the TLD is
    # dropped before comparison. Naukri and Naukri.com are the same portal.
    s = re.sub(r"\.(com|de|nl|in|co\.uk|io|net|org)\b", " ", s)
    return {t for t in re.split(r"[^a-z0-9+]+", s) if t and t not in STOP}


def section(text, heading):
    """Lines of the numbered list under an exact '### heading' line."""
    out, depth_ok = [], False
    for line in text.splitlines():
        if line.strip().startswith("###"):
            depth_ok = line.strip() == heading
            continue
        if not depth_ok:
            continue
        m = re.match(r"^(\s*)\d+\.\s+(.*\S)\s*$", line)
        if m:
            out.append((len(m.group(1)), m.group(2).strip()))
    return out


def flat(items):
    return [t for _, t in items]


def nested(items):
    """Top-level entries, each with the deeper-indented entries beneath it."""
    result, current = [], None
    base = min((i for i, _ in items), default=0)
    for indent, txt in items:
        if indent == base:
            current = (txt, [])
            result.append(current)
        elif current is not None:
            current[1].append(txt)
    return result


def yaml_block(text, key):
    """Raw lines of a top-level YAML block, without parsing it."""
    out, inside = [], False
    for line in text.splitlines():
        if re.match(rf"^{key}:", line):
            inside = True
            continue
        if inside:
            if line and not line[0].isspace():
                break
            out.append(line)
    return out


def variants(item):
    """Spellings of one preference entry.

    The preferences file writes a role as several names for the same thing,
    such as "Firmware Engineer / Developer", and qualifies some with a
    parenthetical. Each spelling is offered separately so a match on any one
    of them counts, and a genuinely new entry still matches nothing.
    """
    base = re.sub(r"\([^)]*\)", " ", item).strip()
    out = [base.replace("/", " ")]
    out += [part.strip() for part in base.split("/") if part.strip()]
    return [v for v in out if tokens(v)]


def matches(item, candidates):
    """Candidates that name the same thing as item, and the closest miss.

    A candidate matches when one spelling of the item and the candidate are
    token subsets in either direction. Both directions are needed because the
    preferences file is sometimes broader than the matrix, as in "Embedded /
    Physical AI Engineer" against "Physical AI Engineer", and sometimes
    narrower, as in "AI/ML Engineer" against "AI ML Engineer Embedded". A
    genuinely new entry is a subset of nothing and matches nothing.
    """
    hits, closest, best_score = [], None, 0.0
    for v in variants(item):
        tv = tokens(v)
        for c in candidates:
            tc = tokens(c)
            if tv <= tc or tc <= tv:
                if c not in hits:
                    hits.append(c)
            score = len(tv & tc) / len(tv | tc)
            if score > best_score:
                closest, best_score = c, score
    return hits, closest, best_score


def report(label, wanted, have):
    print(f"\n== {label} ==")
    missing, matched = [], set()
    for w in wanted:
        hits, closest, score = matches(w, have)
        if hits:
            matched.update(hits)
            print(f"  ok      {w}  ->  {', '.join(hits)}")
        else:
            missing.append(w)
            hint = (f"closest {closest!r} at {score:.0%}" if closest
                    else "no entry in the matrix shares a word with it")
            print(f"  MISSING {w}  ({hint})")
    extra = [h for h in have if h not in matched]
    for e in extra:
        print(f"  EXTRA   {e}  (matrix carries it, preferences do not list it)")
    return missing, extra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=str(Path(__file__).resolve().parent))
    args = ap.parse_args()
    vault = Path(args.vault)
    prefs_path = vault / "04. preferences.md"
    matrix_path = vault / "scripts" / "queries.yaml"
    for p in (prefs_path, matrix_path):
        if not p.is_file():
            print(f"FAIL missing {p}")
            return 2

    prefs = prefs_path.read_text()
    matrix = matrix_path.read_text()
    problems = 0

    # --- roles ---
    want_roles = flat(section(prefs, "### 2.1 Roles"))
    have_roles = re.findall(r"query:\s*([^}\n]+?)\s*}", matrix)
    m, e = report("Roles", want_roles, have_roles)
    problems += len(m) + len(e)

    # --- locations ---
    want_loc = []
    for top, kids in nested(section(prefs, "### 1.1 Location ")
                            or section(prefs, "### 1.1 Location")):
        want_loc.extend(kids if kids else [top])
    loc_block = "\n".join(yaml_block(matrix, "locations"))
    have_loc = [x.strip().strip('"') for x in re.findall(r"^\s*-\s*(.+)$", loc_block, re.M)]
    m, e = report("Locations", want_loc, have_loc)
    problems += len(m) + len(e)

    # --- portals ---
    want_portals = flat(section(prefs, "### 1.2 Portals"))
    have_portals = re.findall(r"^  (\w+):$", "\n".join(yaml_block(matrix, "portals")), re.M)
    m, e = report("Portals", want_portals, have_portals)
    problems += len(m) + len(e)

    # --- staleness ---
    print("\n== Freshness ==")
    compiled = re.search(r"^compiled_on:\s*([\d-]+)", matrix, re.M)
    approved = bool(re.search(r"^approved:\s*true", matrix, re.M))
    pref_mtime = dt.date.fromtimestamp(prefs_path.stat().st_mtime)
    if compiled:
        cdate = dt.date.fromisoformat(compiled.group(1))
        print(f"  matrix compiled_on {cdate}, preferences last modified {pref_mtime}")
        if pref_mtime > cdate:
            print("  STALE preferences were edited after the matrix was compiled")
            problems += 1
    else:
        print("  FAIL matrix carries no compiled_on date")
        problems += 1
    print(f"  approved: {approved}")

    print()
    if problems:
        print(f"FAIL {problems} problem(s). The matrix does not match the preferences.")
        return 1
    print("PASS matrix covers the preferences and is not stale.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
