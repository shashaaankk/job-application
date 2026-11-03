"""Clear a portal's bot-protection state without losing the login.

Established empirically 2026-09-18 and again 2026-09-25: a portal's
Akamai deny verdict rides in its own cookies, and deleting them
restores access. The catch is that deleting everything also deletes
the session, which needs a human to log in again. That is fine at a
keyboard and useless at 3am on a scheduled run.

So there are two modes.

  --bot-only  (default)  drop only the bot-protection cookies and keep
                         the session. Safe to run unattended. VERIFIED
                         2026-09-30 against a live Naukri deny verdict:
                         dropping bm_mi, ak_bmsc and bm_sv restored
                         access on the very next navigation, with the
                         session intact and no cool-down.
  --all                  drop every cookie for the domain. Certain to
                         clear the state, costs one manual re-login.

Akamai's cookies are short-lived by design (the Naukri pair expires in
roughly two hours), which is consistent with blocks that fade after a
few hours on their own.

Run:  .venv/bin/python clear_naukri.py [--all] [--domain naukri.com]
"""

import argparse

from playwright.sync_api import sync_playwright

PROFILE = "/home/shashaank/.playwright-profiles/jobs"

# Akamai and other bot-protection cookies. These carry the deny verdict.
BOT_COOKIES = {"ak_bmsc", "bm_sv", "bm_sz", "_abck", "bm_mi", "ak_bmsc_sec"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default="naukri.com")
    ap.add_argument("--all", action="store_true",
                    help="drop every cookie for the domain, not just the "
                         "bot-protection ones. Costs a manual re-login.")
    # `09. lessons` documents the remedy as `--bot-only` and that has always been
    # the default here, but the flag itself did not exist, so following the vault
    # literally exited 2. Accepted explicitly now, because an instruction that
    # cannot be typed is not a procedure.
    ap.add_argument("--bot-only", action="store_true", dest="bot_only",
                    help="drop only the bot-protection cookies, keeping the "
                         "session. This is the default and the flag is accepted "
                         "so the documented command runs as written.")
    args = ap.parse_args()
    if args.all and args.bot_only:
        raise SystemExit("--all and --bot-only ask for opposite things")

    with sync_playwright() as p:
        b = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE, channel="chrome", headless=False)
        cookies = b.cookies()
        mine = [c for c in cookies if args.domain in c["domain"]]
        doomed = mine if args.all else [c for c in mine if c["name"] in BOT_COOKIES]
        keep = [c for c in cookies if c not in doomed]

        print(f"{args.domain}: {len(mine)} cookies, dropping {len(doomed)}")
        for c in doomed:
            print(f"  drop {c['name']}")

        b.clear_cookies()
        if keep:
            b.add_cookies(keep)

        after = [c["name"] for c in b.cookies() if args.domain in c["domain"]]
        others = {c["domain"] for c in b.cookies()
                  if args.domain not in c["domain"]}
        print(f"{args.domain} cookies remaining: {len(after)}")
        print(f"other domains untouched: {len(others)}")
        if args.all:
            print("Session dropped. Log in again before the next run.")
        b.close()


if __name__ == "__main__":
    main()
