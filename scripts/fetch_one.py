"""Prototype of the fetch stage: pull ONE job end to end.

Picks a random role and location from the preference lists, runs the
verified LinkedIn query, takes the newest in-window posting, opens its
job page, extracts the full description, and writes a job entry card
into the vault from the job entry template. Prints the card path and
the board line for the Kanban update.

Run:  .venv/bin/python fetch_one.py
"""

import random
import re
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

from playwright.sync_api import sync_playwright

import collect as C
import jd_extract

print = partial(print, flush=True)

VAULT = Path(__file__).resolve().parent.parent
CARDS_DIR = VAULT / "application artifacts" / "job cards"

ROLES = ["Robotics Engineer", "Embedded Software Engineer", "Firmware Engineer",
         "Physical AI Engineer", "ADAS Software Engineer", "R&D Engineer",
         "Autonomous Systems Engineer", "C++ Developer",
         "Automation and Controls Engineer", "AI ML Engineer Embedded"]
LOCATIONS = ["Germany", "Netherlands", "Sweden", "Finland", "Belgium",
             "Norway", "Denmark", "France", "Italy", "Switzerland",
             "Bengaluru, India", "Hyderabad, India", "Pune, India"]

CARD_TEMPLATE = """---
Job Title: {title}
Company: {company}
Location: {location}
Posting: {url}
Posting date: {posting_date}
Discovery date: {discovery_date}
Cover letter:
Resume:
Score:
---
---
### Job Description

{jd}

---
### Evaluation

Evaluation results after the job entry's fit is evaluated

### Questions

- [ ] Insert any open questions that need addressing as a check box


---
### User Comments

Answers to the questions and any comments
"""


def safe_name(s):
    return re.sub(r"[^\w &+.-]+", "", s).strip()[:80]


def main() -> None:
    portal = C.PORTALS["linkedin"]
    today = datetime.now(timezone.utc).date().isoformat()

    with sync_playwright() as p:
        b, page = C.open_profile(p)
        job = None
        for _ in range(3):  # re-roll empty cells up to 3 times
            role = random.choice(ROLES)
            loc = random.choice(LOCATIONS)
            print(f"cell: {role} x {loc}, 48 h")
            page.goto(portal.url(loc, 48, role, 0), wait_until="domcontentloaded")
            page.wait_for_timeout(6000)
            cards = portal.harvest_page(page)
            print(f"  cards on page 1: {len(cards)}")
            if cards:
                jid, (title, company, location, age) = next(iter(cards.items()))
                job = dict(jid=jid, title=title, company=company,
                           location=location, age=age, role=role, cell_loc=loc)
                break
        if job is None:
            print("三 empty cells in a row; stopping")
            b.close()
            return

        url = portal.job_url(job["jid"])
        print(f"newest posting: {job['title']} | {job['company']} | {url}")
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        jd = jd_extract.extract(page, url)
        # posting age on the detail page is more precise than the card's
        body = page.inner_text("body")
        m = re.search(r"(\d+\s+(?:minute|hour|day|week)s?\s+ago)", body)
        age_text = m.group(1) if m else job["age"]
        b.close()

    if not jd:
        print("JD EXTRACTION FAILED (jd_extract returned empty)")
        return
    print(f"JD extracted: {len(jd)} characters")

    a = C.age_hours(age_text)
    posting_date = "unknown"
    if a is not None:
        from datetime import timedelta
        posting_date = (datetime.now(timezone.utc) - timedelta(hours=a)).date().isoformat()

    company = job["company"].split("\n")[0].strip()
    title = job["title"].strip()
    location = job["location"].split("(")[0].strip()
    fname = safe_name(f"{company} - {title} - {job['jid']}") + ".md"
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    card_path = CARDS_DIR / fname
    card_path.write_text(CARD_TEMPLATE.format(
        title=title, company=company, location=location, url=url,
        posting_date=posting_date, discovery_date=today, jd=jd))
    print(f"CARD WRITTEN: {card_path}")
    print("BOARD LINE: - [ ] [[application artifacts/job cards/"
          f"{fname[:-3]}|{today} - {company} - {title}]]")


if __name__ == "__main__":
    main()
