"""Write the review list, so he can see what the screen kept in one place.

Reads the ledger, runs `screen.py` over it, and writes `12. shortlist for review.md`
sorted by how many of his areas each description names. Nothing here grades a
posting or writes a card. The board is where he actually judges, and this file is a
flat read of the same set.

Run:  .venv/bin/python scripts/shortlist.py [--since 2026-10-02T16:0]
"""

import argparse
import collections
import csv
import datetime as dt
import sys
from pathlib import Path

import make_cards as MC
import matrix as MX
import places
import screen

VAULT = Path(__file__).resolve().parent.parent
LEDGER = VAULT / "scripts" / "data" / "ledger.tsv"
DESCRIPTIONS = VAULT / "scripts" / "data" / "descriptions"
OUT = VAULT / "12. shortlist for review.md"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="", help="only rows first seen at or after this timestamp")
    args = ap.parse_args()

    m = MX.load()
    allowed = places.allowed_countries()
    have = MC.existing_ids()
    rows = [r for r in csv.DictReader(LEDGER.open(), delimiter="\t")
            if not args.since or r["first_seen"] >= args.since]
    print(f"ledger rows {len(rows)}, window {m.freshness_hours} h, "
          f"countries {sorted(allowed)}")

    # title stage, then one advert per company and title
    t_drop = collections.Counter()
    seen, uniq = set(), []
    for r in sorted(rows, key=lambda x: x.get("posted_at") or "", reverse=True):
        if r["portal_id"] in have:
            t_drop["already on a card"] += 1
            continue
        if not MC.within_window(r, m.freshness_hours)[0]:
            t_drop["outside the freshness window"] += 1
            continue
        ok, why, flags = screen.screen_title(
            r["title"], r["company"], r["location_text"], r.get("cell"))
        if not ok:
            t_drop[why] += 1
            continue
        r["company"] = screen.clean_company(r["company"])
        r["_flags"] = list(flags)
        k = (screen.norm(r["company"]), screen.norm(r["title"]))
        if k in seen:
            t_drop["the same advert again"] += 1
            continue
        seen.add(k)
        uniq.append(r)

    # description stage
    d_drop = collections.Counter()
    final, unfetched = [], []
    for r in uniq:
        f = DESCRIPTIONS / f"{r['portal']}-{r['portal_id']}.md"
        if not f.exists():
            unfetched.append(r)
            continue
        ok, why, areas, flags = screen.screen_description(
            f.read_text(encoding="utf-8", errors="replace"), r["location_text"],
            allowed, r.get("cell"))
        if not ok:
            d_drop[why.split(" (")[0]] += 1
            continue
        r["_areas"] = areas
        r["_country"] = why
        r["_flags"] += flags
        final.append(r)

    final.sort(key=lambda r: (-len(r["_areas"]), r["company"]))

    out = [
        "---", "type: Reference", "title: Shortlist for review",
        "description: Every posting that survived the sweep and the screen, in one flat "
        "list, as a faster read than the board.",
        "tags:", "  - shortlist", "  - review",
        "generated:", "  by: claude-opus-5", "status: draft", "---", "",
        f"# {len(final)} postings", "",
        f"Freshness window {m.freshness_hours} hours. Countries "
        f"{', '.join(sorted(allowed))}.", "",
        "Sorted by how many of his areas the description names. Nothing here is graded, "
        "and the screen rejects rather than ranks.",
        "A German flag means the posting asks for German at working level, which flags "
        "and never rejects. An agency flag means the lister is a body-leasing firm or "
        "consultancy, which rule 12 treats like a direct employer.", "",
    ]
    cur = None
    for r in final:
        k = len(r["_areas"])
        if k != cur:
            cur = k
            out += ["", f"## {k} areas named", "",
                    "| Company | Role | Country | Place | Areas | Flags |",
                    "|---|---|---|---|---|---|"]
        out.append(f"| {r['company'][:30]} | [{r['title'][:60]}]({r['url']}) | "
                   f"{r['_country']} | {r['location_text'][:26]} | "
                   f"{', '.join(r['_areas'])} | {', '.join(r['_flags'])} |")

    if unfetched:
        out += ["", f"## {len(unfetched)} not yet assessed", "",
                "These passed the title stage and have no description fetched, so the "
                "screen could not read them.", "",
                "| Company | Role | Place |", "|---|---|---|"]
        for r in unfetched:
            out.append(f"| {r['company'][:30]} | [{r['title'][:60]}]({r['url']}) | "
                       f"{r['location_text'][:26]} |")

    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")

    print(f"\ntitle stage dropped {sum(t_drop.values())}:")
    for k, v in t_drop.most_common():
        print(f"   {v:5d}  {k}")
    print(f"title survivors {len(uniq)}")
    print(f"\ndescription stage dropped {sum(d_drop.values())}:")
    for k, v in d_drop.most_common():
        print(f"   {v:5d}  {k}")
    print(f"\nwritten to {OUT.name}: {len(final)} assessed, {len(unfetched)} not yet assessed")
    print(f"  by country: {dict(collections.Counter(r['_country'] for r in final).most_common())}")
    print(f"  by area count: "
          f"{dict(sorted(collections.Counter(len(r['_areas']) for r in final).items(), reverse=True))}")


if __name__ == "__main__":
    main()
