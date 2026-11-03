"""Hand Naukri recovery to Antigravity when the in-sweep remedy was not enough.

`worker_naukri` already applies the documented remedy by itself. It drops the Akamai
cookies, opens a fresh page and retries once, which is what `09. lessons` prescribes
and what was proved on six consecutive cells. The circuit breaker now trips only
when that retry also fails.

When it does trip, the run used to stop there and wait for him. It no longer does.
This reads the run log, and if Naukri's last cells show a breaker trip it gives
Antigravity the job of getting the portal back, with the vault's own rules as its
boundary. It costs no Claude tokens.

What Antigravity may do, and nothing else.
  read     09. lessons, 03. playwright setup, 07. searching
  run      scripts/check_session.py
           scripts/clear_naukri.py --bot-only
           scripts/sweep.py --portal naukri
It may not log in, because a password is typed by him in a visible window and never
handled by a script. It may not work around a block, try another route to the
portal, change the pacing, or touch any other portal. A portal that stays blocked
is recorded and left alone, which is the vault's rule and not a limitation of this
script.

Run:
  .venv/bin/python scripts/recover_naukri.py            recover if the log says to
  .venv/bin/python scripts/recover_naukri.py --check    report only, call nothing
  .venv/bin/python scripts/recover_naukri.py --force    recover regardless
"""

import argparse
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
RUNS = VAULT / "scripts" / "data" / "runs.tsv"
AGY = "agy"
AGY_TIMEOUT = 2400
BAD = ("NETERR", "BLOCKED", "PARSE")

SCHEMA = {
    "type": "object",
    "required": ["diagnosis", "actions_taken", "recovered", "report"],
    "properties": {
        "diagnosis": {"type": "string"},
        "actions_taken": {"type": "array", "items": {"type": "string"}},
        "recovered": {"type": "boolean"},
        "cells_ok": {"type": "integer"},
        "needs_him": {"type": "string"},
        "report": {"type": "string"},
    },
}

PROMPT = """Naukri's worker tripped its circuit breaker in the last sweep of Shashank's
job pipeline. Your job is to get the portal collecting again, inside the vault's own
rules. Return only JSON matching the schema.

The vault is /home/shashaank/job-application. Read these first and follow them:
  09. lessons.md        the Naukri section, which holds the access procedure, the
                        failure signatures and the verified remedy
  03. playwright setup.md
  07. searching.md

What the last run recorded for Naukri:
{evidence}

The remedy the vault prescribes, already automatic inside the sweep and evidently
not enough this time: drop the Akamai bot cookies, which carry the deny verdict,
open a fresh page so the poisoned HTTP/2 connection is not reused, and retry once.

You may run exactly these commands, from /home/shashaank/job-application:
  .venv/bin/python scripts/check_session.py
  .venv/bin/python scripts/clear_naukri.py --bot-only
  .venv/bin/python scripts/sweep.py --portal naukri --cells 3
  .venv/bin/python scripts/sweep.py --portal naukri

Nothing else. In particular:
- Do not log in, and do not type or read any credential. He types passwords himself
  in a visible window, and no script handles them. If a session has expired, say so
  in needs_him and stop.
- Do not run `clear_naukri.py --all`. It drops the session and costs him a manual
  re-login, so it is his decision and not yours.
- Do not work around a block. No alternative route to the portal, no proxy, no user
  agent change, no faster pacing, no third-party mirror. A portal that stays blocked
  after the documented remedy is recorded and left alone.
- Do not touch LinkedIn, Stepstone or Indeed.
- Do not edit any file in the vault. Report what you found and let Claude write it.
- Only one browser may hold the profile at a time, so never run two of these at once.

Set recovered to true only if a `scripts/sweep.py --portal naukri` run you executed
reported `status=ok` for at least one cell. Put the cell count in cells_ok. If the
portal is still refusing, set recovered to false, say what you observed, and put in
needs_him the one thing he would have to do.
"""


def naukri_trouble(limit=40):
    """The recent Naukri cells, and whether the last of them failed."""
    if not RUNS.exists():
        return [], False
    rows = [r for r in csv.DictReader(RUNS.open(encoding="utf-8"), delimiter="\t")
            if "|naukri|" in (r.get("cell") or "")]
    recent = rows[-limit:]
    if not recent:
        return [], False
    bad = any(any(recent[-1]["status"].startswith(b) for b in BAD) for _ in (0,))
    return recent, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report only")
    ap.add_argument("--force", action="store_true", help="recover regardless")
    args = ap.parse_args()

    recent, bad = naukri_trouble()
    tail = recent[-8:]
    print(f"recent Naukri cells: {len(recent)}, last status "
          f"{recent[-1]['status'] if recent else 'none recorded'}")
    for r in tail:
        print(f"   {r['ts']}  {r['status']:<10s} {r['cell'][:58]}")

    if not bad and not args.force:
        print("\nNaukri's last cell was fine, nothing to recover")
        return 0
    if args.check:
        print("\nrecovery is warranted, and --check calls nothing")
        return 0

    evidence = "\n".join(f"  {r['ts']}  {r['status']}  {r['cell']}" for r in tail) \
        or "  no Naukri cells in the run log"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(SCHEMA, fh)
        schema = fh.name
    print("\nhanding recovery to Antigravity")
    try:
        r = subprocess.run(
            [AGY, "--dangerously-skip-permissions", "--output-format", "json",
             "--json-schema", schema,
             f"--print={PROMPT.format(evidence=evidence)}"],
            cwd=str(VAULT), capture_output=True, text=True, timeout=AGY_TIMEOUT)
    except subprocess.TimeoutExpired:
        print(f"FAIL Antigravity did not finish within {AGY_TIMEOUT}s")
        return 1
    finally:
        Path(schema).unlink(missing_ok=True)

    if r.returncode != 0:
        print(f"FAIL agy exited {r.returncode}: {(r.stderr or '').strip()[:200]}")
        return 1
    try:
        out = json.loads(r.stdout)
    except json.JSONDecodeError:
        print("FAIL the output was not JSON")
        return 1

    def find(o):
        if isinstance(o, dict):
            if "recovered" in o and "diagnosis" in o:
                return o
            for v in o.values():
                f = find(v)
                if f:
                    return f
        if isinstance(o, list):
            for v in o:
                f = find(v)
                if f:
                    return f
        if isinstance(o, str) and o.strip().startswith("{"):
            try:
                return find(json.loads(o))
            except Exception:
                return None
        return None

    p = find(out)
    if not p:
        print(f"FAIL no structured output (status {out.get('status')})")
        return 1

    print(f"\ndiagnosis: {p['diagnosis']}")
    for a in p.get("actions_taken", []):
        print(f"   did: {a}")
    print(f"recovered: {p['recovered']}, cells ok: {p.get('cells_ok', 0)}")
    if p.get("needs_him"):
        print(f"NEEDS HIM: {p['needs_him']}")
    print(f"\n{p['report']}")
    return 0 if p["recovered"] else 2


if __name__ == "__main__":
    sys.exit(main())
