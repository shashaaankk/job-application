---
name: searching
description: Drive a job search sweep across the portals. Use whenever the user asks to search for jobs, run a sweep, collect postings, pull new listings, check what is new today, or when a portal is blocking, returning nothing, or throwing connection errors mid-run. Covers what to run, what each run status means, and what to do when a portal refuses, which is the part that goes wrong most often.
---

# Searching

Searching itself is scripts. They live in `~/job-application/scripts` and they already know how to talk to each portal, how to page, and what each portal does that can mislead a reader. This skill is the driver. It covers what to run, how to read what comes back, and what to do when a portal will not cooperate.

The thing worth internalising before anything else. A sweep that returns nothing looks exactly like a quiet day on the job market. Most of the failure modes here are silent, so the work is in checking rather than trusting.

## Before running anything

Three preconditions, each guarding against a specific way a run lies about its results.

**Sessions are alive.** Run `check_session.py` and require exit code 0. An expired session does not error, it just returns an empty or logged-out page, and the sweep records zero postings for a portal that had plenty. If a portal fails, log in again before sweeping, per 03. playwright setup.

**The matrix is approved.** `queries.yaml` carries an `approved` flag that the user flips by hand after reading the matrix. The sweep refuses to run while it is false. That refusal is the design working, not a bug to route around.

**Nothing else holds the browser profile.** The profile allows one browser instance at a time. A leftover instance, or a stale `SingletonLock` from a crashed run, makes the next launch fail. Close what is open before starting.

## Running the sweep

`sweep.py` is the normal path. It opens one browser and gives each portal its own tab, so the portals work at the same time while each keeps its own pacing. The wall-clock cost is then the slowest portal rather than the sum of all of them.

```bash
cd ~/job-application && .venv/bin/python scripts/sweep.py
```

For one portal or one cell, `collect.py fetch` takes a portal, a location and a query. One caveat that matters. `collect.py`'s Naukri class still pages by changing the URL, which is the pattern that raised Naukri's bot-protection flag in the first place. Use `sweep.py` for anything touching Naukri until that is fixed.

## Reading what comes back

Every cell writes a status to the run log. The status is the whole point of the log, so read it rather than the posting count.

| Status | What it means | What to do |
|---|---|---|
| `ok` | the cell paged to the end with full pages throughout | nothing |
| `PAGE_SHORT` | a page before the last returned fewer cards than the portal serves per page | a reader bug on our side, not a portal limit. Fix the extraction, do not accept the partial harvest |
| `OVERFLOW` | the portal claims more results than one query can page through | the cell is not fully reachable. Say so plainly rather than treating it as complete |
| `PARTIAL` | stopped early by a page cap, which only diagnostic runs set | rerun without the cap if the cell matters |
| `BLOCKED` | a bot-protection page was served instead of results | see below. Do not retry |
| `NETERR` | the connection was reset repeatedly | see below. Do not retry |

## When a portal refuses

This is where runs go wrong, so the rule is short and it is absolute in one direction only. Stop touching that portal.

Retrying into a raised flag deepens it. This is not caution, it is what happened. A few rapid retries turned a transient Naukri reset into a block that survived for hours and then survived a browser restart, because the deny state had been written into the profile's cookies. Recovery took a cookie clear and a fresh login.

So, on the first anomaly from a portal:

1. That portal's run ends. Not that cell, the portal.
2. The other portals keep going. One portal refusing is not a reason to lose the rest of the sweep.
3. The run log records what did not run. A cell that was never attempted must never read as a cell that found nothing.
4. Wait hours, not minutes, before trying that portal again.

If the block survives a cool-down, the deny state is in the profile's cookies for that site. `clear_naukri.py` removes only that one portal's cookies, which costs a single re-login and leaves every other session untouched. The same pattern adapts to another portal by changing the domain.

Indeed is a separate case. It challenges automated page loads, and a human verification does not carry over to later automated ones. Challenges are never worked around. Indeed either runs with the user present or stays out of the sweep.

## What a run must never do

- Report a portal as covered when its cells did not come back `ok`.
- Drop a cell quietly. An unattempted cell and an empty cell are different facts and the difference is what makes degradation visible.
- Run two browser instances against the profile to go faster.

## After collection

Collected listings are cheap. Job descriptions are mostly cheap now, because LinkedIn serves its description to a logged-out visitor over the anonymous path and Naukri's arrives with the search itself. Only Stepstone still costs a browser page load. The title stage of `scripts/screen.py` runs first regardless, so nothing is fetched for a posting the rules already reject.

From there `scripts/make_cards.py` takes over. It screens the description, and a posting that survives both screen stages becomes a card written from the job entry template and linked into the board's `matched` column. `refetch_cards.py` reformats existing cards in place when extraction improves or when a card was fetched while its portal was unreachable.

A card in `matched` is where a run stops. He reads it and moves it to `to apply`, which is what releases it to [artifact generation](../artifact-generation/SKILL.md). No run moves a card and no run grades one.

## Reporting back to the user

Report per portal, and lead with what did not work rather than the total. A useful report names the cells attempted, the postings collected, every status that was not `ok`, and anything skipped with the reason. The total on its own hides the only thing worth knowing, which is whether the sweep actually covered what it claims to have covered.
