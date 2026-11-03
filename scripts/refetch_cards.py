"""Re-fetch and reformat the Job Description on existing vault cards.

Walks every card in the vault's job cards folder, opens its Posting URL,
re-extracts the JD through jd_extract (structured markdown, chrome
stripped), and rewrites ONLY the Job Description section in place.
Frontmatter, Evaluation, Questions, and User Comments are untouched.

Use when extraction improves, or when a card was fetched while its
portal was unreachable. Naukri cards are processed last and a failed
navigation leaves the card unchanged (never retry into a raised flag).

Run:  .venv/bin/python refetch_cards.py
"""

import re
import time
from functools import partial
from pathlib import Path

from playwright.sync_api import sync_playwright

import collect as C
import jd_extract

print = partial(print, flush=True)

CARDS = Path(__file__).resolve().parent.parent / "application artifacts" / "job cards"


def main() -> None:
    def naukri_last(f):
        return 2 if "naukri.com" in f.read_text() else 1

    with sync_playwright() as p:
        b, page = C.open_profile(p)
        for f in sorted(CARDS.glob("*.md"), key=naukri_last):
            s = f.read_text()
            m = re.search(r"^Posting: (.+)$", s, re.M)
            if not m:
                print(f"{f.name}: no Posting URL, skipped")
                continue
            url = m.group(1).strip()
            if "naukri.com" in url:
                time.sleep(20)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
            except Exception as e:
                print(f"{f.name}: goto failed ({str(e).splitlines()[0][:60]}), unchanged")
                continue
            page.wait_for_timeout(6000)
            if "Access Denied" in page.inner_text("body"):
                print(f"{f.name}: blocked, unchanged")
                continue
            jd = jd_extract.extract(page, url)
            if not jd:
                print(f"{f.name}: extraction failed, unchanged")
                continue
            head, _, _ = s.partition("### Job Description")
            _, _, tail = s.partition("### Evaluation")
            f.write_text(head + "### Job Description\n\n" + jd
                         + "\n\n---\n### Evaluation" + tail)
            print(f"{f.name}: JD rewritten, {len(jd)} chars")
        b.close()


if __name__ == "__main__":
    main()
