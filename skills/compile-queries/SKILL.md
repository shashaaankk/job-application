---
name: compile-queries
description: Recompile queries.yaml from 04. preferences.md after a preference changes, then check it mechanically. Use when a preference is edited, before a sweep on an unchecked matrix, or when the user asks whether the matrix still matches the preferences.
---

# Compile queries

`04. preferences.md` holds the wants. `scripts/queries.yaml` is its executed form. They drift silently, because a sweep on a stale matrix succeeds on the wrong cells.

Reading the preferences is judgement, since the file is prose. Only the final check is mechanical.

## Preconditions

Read `04. preferences.md` in full this session. Read the current `queries.yaml`, because the output is a diff against it.

## Steps

1. Read the coverage table in `08. scoring.md`. A field enters the matrix only if its row says it is enforced at the query. Roles, locations, freshness, seniority and portals do. Workplace type, domains and compensation do not.
2. One `roles` entry per role, `query` being the exact keyword string sent and `id` its slug. Where a preference names several spellings of one role, pick the spelling the portals index and note the others. Never emit two cells for one role.
3. Country-level units go under `locations.europe`. Cities go under `locations.india` as `"City, Country"`. A country whose preference lists cities beneath it is not itself a unit.
4. Each portal carries `serves` and `url_template`. An unverified portal keeps `verified: false` and an empty `serves`, which holds it in the file and out of the run.
5. Carry `verified:` dates, portal `notes` and every `PENDING` or `DECISION pending` line forward unchanged. Drop one only when its parameter leaves the file.
6. Raise `version` by one, set `compiled_on` to today, set `approved: false`.
7. Show the diff, the cell count before and after, and every entry added, removed or renamed. Then stop.
8. Run the check and fix any `FAIL` in the matrix.

```bash
cd ~/job-application && .venv/bin/python scripts/check_matrix.py --vault .
```

`MISSING` is a preference the matrix would never search. `EXTRA` is a cell swept for a dropped preference. `STALE` means the preferences were modified after `compiled_on`, read from the filesystem, so an editor touching the file without changing it can raise it alone.

## Never

Flip `approved` to true. That is the user's, by hand, after reading the diff.

Run a sweep in the same turn as a recompile.

Write a field whose coverage row says it is checked after the fetch.

Overwrite `queries.yaml` before showing the diff.

Drop a `verified:` date or a pending decision.
