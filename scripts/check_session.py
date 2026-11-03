"""Verify the saved portal sessions work.

Uses the pipeline profile at ~/.playwright-profiles/jobs (created and
logged in via `playwright-cli open <url> --profile=... --headed`).

Runs ONE headed browser instance for all portals, matching how the
pipeline scrapes (everything headed for uniformity; Naukri blocks
headless anyway). A visible window opens briefly.

A portal counts as logged in only on positive evidence: its session
cookie exists AND the logged-in page loads without bouncing to a login
or block page. URL alone is never trusted.

Run:  .venv/bin/python check_session.py
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_DIR = Path.home() / ".playwright-profiles" / "jobs"

# (name, logged-in page, session cookie, URL substring proving arrival)
PORTALS = [
    ("LinkedIn", "https://www.linkedin.com/feed/", "li_at", "/feed"),
    ("Naukri", "https://www.naukri.com/mnjuser/homepage", "nauk_at", "mnjuser"),
    # logged-in visits to the login page redirect to /profile
    ("Stepstone", "https://www.stepstone.de/candidate/login", "AuthCA", "/profile"),
    # URL is the same logged in or out; the PPID cookie is the evidence
    ("Indeed", "https://de.indeed.com/", "PPID", "indeed.com"),
]


def main() -> int:
    if not PROFILE_DIR.is_dir():
        print(f"Profile folder {PROFILE_DIR} does not exist.")
        print("Create it by logging in:  playwright-cli open <login-url> "
              f"--profile={PROFILE_DIR} --headed")
        return 2

    failures = 0
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            channel="chrome",
            headless=False,
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        for name, url, cookie, ok_marker in PORTALS:
            problems = []
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)  # allow client-side login redirects to run
            # cookies are read AFTER the visit: short-lived access tokens
            # (e.g. Stepstone's AuthCA) only get re-minted on contact
            cookie_names = {c["name"] for c in browser.cookies()}
            if cookie not in cookie_names:
                problems.append(f"session cookie {cookie} missing")
            if ok_marker not in page.url:
                problems.append(f"bounced to {page.url}")
            body = page.inner_text("body")[:2000]
            if "Access Denied" in body:
                problems.append("blocked (Access Denied page)")
            if problems:
                print(f"{name}: NOT logged in ({'; '.join(problems)})")
                failures += 1
            else:
                print(f"{name}: logged in ({page.url})")
        browser.close()

    if failures:
        print(f"{failures} portal(s) need attention. Log in with: "
              f"playwright-cli open <login-url> --profile={PROFILE_DIR} --headed")
        return 1
    print("All sessions valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
