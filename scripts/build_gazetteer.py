"""Build the offline gazetteer that resolves a bare town name to a country.

Why this exists. `places.py` carried a hand written list of regions and larger
cities, and a hand written list can never be complete. One run dropped 88 postings
for an unresolvable location and every one of them was a German town, including
Freiburg, Darmstadt, Erlangen, Koblenz and Trier. The screen was discarding good
matches silently, which is worse than letting them through.

So the city list is no longer maintained by hand. It comes from GeoNames, which
publishes every populated place with its country, and this script reduces that dump
to the two columns the screen needs.

Source:  https://download.geonames.org/export/dump/cities500.zip
         every populated place with a population of 500 or more, about 236000 rows
         https://download.geonames.org/export/dump/countryInfo.txt
         the ISO country code to country name mapping
         https://download.geonames.org/export/dump/admin1CodesASCII.txt
         the state or province name for each admin1 code

Output:  scripts/data/gazetteer.tsv, one row per place name, holding the name, the
         country holding the most populous place of that name, and every other
         country holding one. The second column is what a reader would assume and
         the third is what lets a caller override it, because Freiburg is in both
         Germany and Switzerland and only the query knows which was searched. The
         fourth holds the state or province per country, because the state has to
         follow whichever country the caller settles on. "Gera" is a town in both
         Hungary and Thuringia, and only the query says which.

The output is committed, so a run never downloads anything and the screen stays
deterministic. Rebuild it only when a place is genuinely missing.

Run:  .venv/bin/python scripts/build_gazetteer.py [--keep-downloads]
"""

import argparse
import collections
import csv
import io
import sys
import re
import unicodedata
import urllib.request
import zipfile
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
OUT = VAULT / "scripts" / "data" / "gazetteer.tsv"
CITIES = "https://download.geonames.org/export/dump/cities500.zip"
COUNTRIES = "https://download.geonames.org/export/dump/countryInfo.txt"
ADMIN1 = "https://download.geonames.org/export/dump/admin1CodesASCII.txt"

# A place below this population is left out. 500 is the dump's own floor, and a
# German industrial village hosting a plant is usually above 1000, so this keeps
# the file small without losing the towns the postings actually name.
MIN_POP = 500

# Names that are also ordinary words or company names, which would resolve a
# location column holding something other than a place. Each one is a real place,
# so the exclusion is of the name alone and not of the place.
STOPWORDS = {"of", "as", "do", "is", "it", "and", "or", "the", "a", "an", "same",
             "best", "general", "major", "central", "industry", "same", "most",
             "sale", "sales", "may", "june", "august", "march", "mobile", "union",
             "international", "national", "global", "remote", "home", "both",
             "group", "team", "nice", "split", "why", "how", "we", "me", "sum"}


LATIN = re.compile(r"^[a-z0-9 .\-\'()/]+$")


def fold(name):
    """The lookup key, lower case and without diacritics, matching places.norm."""
    s = unicodedata.normalize("NFKD", (name or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def latin(name):
    """True when the name is writable in the Latin script.

    GeoNames carries every alternate spelling, including Cyrillic, Greek, Arabic,
    Hebrew, Chinese, Japanese and Korean. A job posting never writes a European
    town in those scripts, and including them made the file ten times larger and
    added false matches, so they are dropped at build time.
    """
    s = unicodedata.normalize("NFKD", name.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return bool(LATIN.match(s))


def fetch(url):
    with urllib.request.urlopen(url, timeout=180) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-downloads", action="store_true")
    args = ap.parse_args()

    print(f"fetching {COUNTRIES}")
    code_to_name = {}
    for line in fetch(COUNTRIES).decode("utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        f = line.split("\t")
        if len(f) > 4:
            code_to_name[f[0]] = f[4]
    print(f"  {len(code_to_name)} countries")

    print(f"fetching {ADMIN1}")
    admin1 = {}
    for line in fetch(ADMIN1).decode("utf-8").splitlines():
        f = line.split("\t")
        if len(f) > 1:
            admin1[f[0]] = f[1]
    print(f"  {len(admin1)} states and provinces")

    print(f"fetching {CITIES}")
    z = zipfile.ZipFile(io.BytesIO(fetch(CITIES)))
    raw = z.read("cities500.txt").decode("utf-8")
    print(f"  {raw.count(chr(10))} places")

    # name -> {country: (population, state)}, so the most populous wins a tie, the
    # number of distinct countries tells us whether the name is ambiguous, and the
    # state travels with the winning entry
    places = collections.defaultdict(dict)
    rows = 0
    for line in raw.splitlines():
        f = line.split("\t")
        if len(f) < 15:
            continue
        name, asciiname, alt, cc, pop = f[1], f[2], f[3], f[8], f[14]
        state = admin1.get(f"{cc}.{f[10]}", "") if len(f) > 10 else ""
        country = code_to_name.get(cc)
        if not country:
            continue
        try:
            pop = int(pop or 0)
        except ValueError:
            pop = 0
        if pop < MIN_POP:
            continue
        rows += 1
        # the official name, the ASCII form, and the alternate spellings, since a
        # posting writes Munich, München or Muenchen for the same place
        for n in [name, asciiname] + alt.split(","):
            n = n.strip()
            # the stopword test runs on the folded form, because "Unión" lower
            # cases to a string that is not in the list while folding to one that is
            if len(n) < 3 or fold(n) in STOPWORDS or not latin(n):
                continue
            cur = places[fold(n)]
            if pop >= cur.get(country, (0, ""))[0]:
                cur[country] = (pop, state)

    print(f"  {rows} places above population {MIN_POP}, {len(places)} distinct names")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["name", "country", "also", "states"])
        for n in sorted(places):
            by = places[n]
            best = max(by.items(), key=lambda kv: kv[1][0])[0]
            also = "|".join(sorted(c for c in by if c != best))
            # one state per country holding the name, so the state follows the
            # country the caller resolves to rather than the most populous one
            states = "|".join(f"{c}={st}" for c, (_, st) in sorted(by.items()) if st)
            w.writerow([n, best, also, states])
    size = OUT.stat().st_size / 1e6
    amb = sum(1 for by in places.values() if len(by) > 1)
    print(f"written {OUT.relative_to(VAULT)}: {len(places)} names, {amb} ambiguous, "
          f"{size:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
