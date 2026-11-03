"""Resolve a posting's location text to a country, and test it against the preferences.

A portal writes the place as a city and a region and often omits the country, so
"Gauting, Bavaria" is Germany and nothing in the string says so. A plain country
match therefore failed on a third of the rows.

Two sources, in order.

  REGIONS below, a hand written list of countries, states and provinces. It stays
  because a region name is not a city and no city dump carries it.

  scripts/data/gazetteer.tsv, 565000 place names built from the GeoNames dump by
  `build_gazetteer.py`. This replaced the hand written city list, which could never
  be complete. One run dropped 88 postings as unresolvable and every one was a
  German town, including Freiburg, Darmstadt, Erlangen, Koblenz and Trier.

When neither resolves the string, the country the sweep actually searched is used,
because a portal omits the country exactly when it is the local default. That
inference is reported rather than hidden, so a card says the country was taken from
the query rather than read from the posting.
"""
import re
import unicodedata
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
PREFS = VAULT / "04. preferences.md"
GAZETTEER = VAULT / "scripts" / "data" / "gazetteer.tsv"

# Countries, states and provinces. Cities are NOT maintained here any more, they come
# from the gazetteer. The city names that remain are the ones a posting writes as a
# metropolitan area rather than as a municipality, so they stay.
REGIONS = {
    "Germany": [
        "germany", "deutschland", "bavaria", "bayern", "baden.?wurttemberg",
        "baden.?w.rttemberg", "north rhine.?westphalia", "nordrhein.?westfalen",
        "hesse", "hessen", "lower saxony", "niedersachsen", "saxony", "sachsen",
        "berlin", "hamburg", "bremen", "schleswig.?holstein", "rhineland.?palatinate",
        "rheinland.?pfalz", "thuringia", "thuringen", "brandenburg", "saarland",
        "mecklenburg", "stuttgart", "munich", "munchen", "frankfurt", "cologne",
        "koln", "dusseldorf", "dortmund", "essen", "leipzig", "dresden", "hannover",
        "nuremberg", "nurnberg", "karlsruhe", "mannheim", "augsburg", "ulm",
        "regensburg", "ingolstadt", "wolfsburg", "aachen", "braunschweig", "kiel",
    ],
    "Netherlands": [
        "netherlands", "nederland", "holland", "north brabant", "noord.?brabant",
        "south holland", "zuid.?holland", "north holland", "noord.?holland",
        "utrecht", "gelderland", "overijssel", "friesland", "zeeland", "drenthe",
        "flevoland", "groningen", "amsterdam", "rotterdam", "the hague", "den haag",
        "eindhoven", "veghel", "delft", "enschede", "nijmegen", "tilburg", "breda",
        "arnhem", "apeldoorn", "almere", "oegstgeest", "helmond", "wageningen",
    ],
    "Sweden": [
        "sweden", "sverige", "stockholm", "vastra gotaland", "v.stra g.taland",
        "skane", "sk.ne", "uppsala", "ostergotland", ".sterg.tland", "vastmanland",
        "v.stmanland", "gothenburg", "goteborg", "g.teborg", "malmo", "malm.",
        "linkoping", "link.ping", "lund", "vasteras", "v.ster.s", "sodertalje",
        "s.dert.lje", "jonkoping", "j.nk.ping", "orebro", ".rebro", "helsingborg",
    ],
    "France": [
        "france", "ile.?de.?france", ".le.?de.?france", "auvergne", "rhone.?alpes",
        "occitanie", "nouvelle.?aquitaine", "provence", "grand est", "hauts.?de.?france",
        "bretagne", "brittany", "normandy", "normandie", "pays de la loire",
        "centre.?val de loire", "bourgogne", "corsica", "paris", "toulouse", "lyon",
        "marseille", "bordeaux", "nantes", "lille", "rennes", "grenoble", "nice",
        "strasbourg", "montpellier", "sophia antipolis", "ismaning",
    ],
    "India": [
        "india", "karnataka", "telangana", "maharashtra", "bengaluru", "bangalore",
        "hyderabad", "pune", "secunderabad", "mumbai", "chennai", "delhi", "noida",
        "gurgaon", "gurugram", "ahmedabad", "kolkata", "mysuru", "mysore",
    ],
    # countries he has searched before and may drop, kept so a location still
    # resolves to a name rather than to unknown
    "Italy": ["italy", "italia", "piedmont", "piemonte", "lombardy", "lombardia",
              "veneto", "lazio", "apulia", "puglia", "tuscany", "toscana", "emilia",
              "turin", "torino", "milan", "milano", "rome", "roma", "bologna",
              "naples", "napoli", "bergamo", "modena", "padova", "soleto"],
    "Switzerland": ["switzerland", "schweiz", "suisse", "zurich", "z.rich", "geneva",
                    "geneve", "gen.ve", "basel", "bern", "lausanne", "lucerne",
                    "zug", "lachen", "mechelen zwitserland", "vaud", "ticino"],
    "Belgium": ["belgium", "belgique", "belgie", "belgi.", "brussels", "bruxelles",
                "flanders", "wallonia", "antwerp", "antwerpen", "ghent", "gent",
                "leuven", "mechelen", "liege", "li.ge", "lokeren", "hasselt"],
    "Denmark": ["denmark", "danmark", "copenhagen", "kobenhavn", "k.benhavn", "aarhus",
                "odense", "aalborg", "herlev", "capital region of denmark",
                "central denmark", "jutland"],
    "Finland": ["finland", "suomi", "helsinki", "espoo", "tampere", "oulu", "turku",
                "vantaa", "uusimaa", "pirkanmaa"],
    "Norway": ["norway", "norge", "oslo", "bergen", "trondheim", "stavanger",
               "rogaland", "viken", "trondelag", "tr.ndelag"],
    "Spain": ["spain", "espana", "espa.a", "madrid", "barcelona", "valencia",
              "catalonia", "cataluna", "sevilla", "bilbao", "zaragoza", "malaga"],
    "Poland": ["poland", "polska", "warsaw", "warszawa", "krakow", "krak.w",
               "wroclaw", "gdansk", "poznan", "lodz", "katowice"],
    "Austria": ["austria", "osterreich", ".sterreich", "vienna", "wien", "graz",
                "linz", "salzburg", "innsbruck", "tyrol", "tirol"],
    "Portugal": ["portugal", "lisbon", "lisboa", "porto", "braga", "coimbra"],
    "Ireland": ["ireland", "eire", "dublin", "cork", "galway", "limerick"],
    "Czechia": ["czech", "czechia", "prague", "praha", "brno", "ostrava"],
    "Romania": ["romania", "bucharest", "bucuresti", "cluj", "timisoara", "iasi"],
    "United Kingdom": ["united kingdom", "england", "scotland", "wales", "london",
                       "manchester", "cambridge", "oxford", "bristol", "edinburgh",
                       "glasgow", "birmingham", "leeds", "\\buk\\b"],
    "Israel": ["israel", "tel aviv", "haifa", "jerusalem", "herzliya"],
    "Turkey": ["turkey", "turkiye", "t.rkiye", "istanbul", "ankara", "izmir"],
}

# a place that is not a place, so it can never satisfy a location preference
NON_PLACE = r"european union|\bemea\b|\beu\b wide|worldwide|global|anywhere|bundesweit|remote"


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s)


_GAZ = None


def gazetteer():
    """{folded place name: (best country, other countries, {country: state})}.

    Loaded once per process. The state travels per country, because a name can sit
    in two countries and the state has to follow whichever one the caller resolves
    to. "Gera" is in Hungary and in Thuringia.

    565000 rows read in under half a second, so this is cheaper than any lookup
    service and it can never fail mid-run or rate limit.
    """
    global _GAZ
    if _GAZ is None:
        if not GAZETTEER.exists():
            raise SystemExit(
                f"{GAZETTEER.name} is missing. Build it with "
                "'.venv/bin/python scripts/build_gazetteer.py'")
        import csv
        _GAZ = {}
        with GAZETTEER.open(encoding="utf-8") as fh:
            rd = csv.reader(fh, delimiter="\t")
            next(rd, None)
            for row in rd:
                if len(row) >= 3:
                    states = {}
                    if len(row) > 3 and row[3]:
                        for pair in row[3].split("|"):
                            if "=" in pair:
                                k, v = pair.split("=", 1)
                                states[k] = v
                    _GAZ[row[0]] = (row[1],
                                    frozenset(row[2].split("|")) if row[2] else frozenset(),
                                    states)
    return _GAZ


# A location string is a list of places and qualifiers, so it is split before any
# lookup. LinkedIn writes "Leipzig, Saxony, Germany (On-site)" and Stepstone writes
# a bare "Stockach".
_SPLIT = re.compile(r"[,;/()|]|\bund\b|\bor\b|\band\b|\+")


def _region_match(s):
    """The country a region, state or country name in the string gives, or None.

    Checked longest pattern first, so "mechelen zwitserland" resolves to Switzerland
    rather than to Belgium's Mechelen.
    """
    best = None
    for country, pats in REGIONS.items():
        for p in sorted(pats, key=len, reverse=True):
            if re.search(rf"\b{p}\b", s):
                if best is None or len(p) > best[1]:
                    best = (country, len(p))
    return best[0] if best else None


def country_of(location_text, searched=None):
    """The country a posting's location names, or None.

    `searched` is the country the sweep asked for, taken from the ledger's cell. It
    only ever breaks a tie between two countries holding a place of the same name,
    such as Freiburg in Germany and in Switzerland. It never invents a country for an
    unresolvable string, which `in_preferences` handles separately and reports.
    """
    s = norm(location_text)
    if not s:
        return None

    # a region or a country name is decisive and is checked first
    c = _region_match(s)
    if c:
        return c

    g = gazetteer()
    parts = [p.strip() for p in _SPLIT.split(s) if p.strip()]

    # whole parts first, longest first, since "bad hersfeld" must beat "bad"
    for p in sorted(parts, key=len, reverse=True):
        hit = g.get(p)
        if hit:
            return _resolve(p, hit, searched, g)

    # then single words, for a string the dump spells differently, such as
    # "Burgkirchen a.d. Alz" against the dump's "Burgkirchen an der Alz". Short
    # words are excluded because they collide with ordinary language.
    for w in sorted({w for p in parts for w in p.split()}, key=len, reverse=True):
        if len(w) < 5:
            continue
        hit = g.get(w)
        if hit:
            return _resolve(w, hit, searched, g)
    return None


def _resolve(name, hit, searched, g):
    """One gazetteer hit, with an ambiguous name settled by what was searched.

    An ambiguous name defaults to the most populous place carrying it, which is what
    a reader would assume. The searched country overrides that only when a place of
    that name genuinely exists there, which the third column records exactly, so no
    guessing is involved.
    """
    country, also = hit[0], hit[1]
    if also and searched:
        want = searched if searched in REGIONS else _region_match(norm(searched))
        if want and want != country and want in also:
            return want
    return country


def state_of(location_text, searched=None):
    """The state or province a posting's location names, or None.

    Reads the string first, since a posting that writes "Leipzig, Saxony, Germany"
    says it outright. Falls back to the gazetteer, which is what answers a bare
    "Gera", and takes the state belonging to the country the location resolves to.
    """
    s = norm(location_text)
    if not s:
        return None
    g = gazetteer()
    country = country_of(location_text, searched)

    # the string itself, checked against every state the gazetteer knows for that
    # country, so a spelled-out state wins over a town lookup
    if country:
        known = {st for hit in g.values() for c, st in hit[2].items() if c == country}
        for st in sorted(known, key=len, reverse=True):
            if re.search(rf"\b{re.escape(norm(st))}\b", s):
                return st

    parts = [x.strip() for x in _SPLIT.split(s) if x.strip()]
    for p in sorted(parts, key=len, reverse=True):
        hit = g.get(p)
        if hit and hit[2]:
            return hit[2].get(country) or hit[2].get(hit[0])
    for w in sorted({w for p in parts for w in p.split()}, key=len, reverse=True):
        if len(w) < 5:
            continue
        hit = g.get(w)
        if hit and hit[2]:
            return hit[2].get(country) or hit[2].get(hit[0])
    return None


def allowed_countries():
    """The countries his preferences list, read fresh from the file."""
    txt = PREFS.read_text(encoding="utf-8")
    block = re.search(r"### 1\.1 Location.*?(?=###)", txt, re.S)
    if not block:
        raise SystemExit("04. preferences has no '### 1.1 Location' block")
    names = set()
    for line in block.group(0).splitlines():
        m = re.match(r"^\s*\d+\.\s+(.*\S)\s*$", line)
        if not m:
            continue
        name = m.group(1).strip()
        if name in REGIONS:
            names.add(name)
        else:
            c = country_of(name)        # a city such as Bengaluru resolves to India
            if c:
                names.add(c)
    return names


def searched_country(cell):
    """The country a sweep cell asked for, or None.

    The ledger's cell reads `sweep|portal|place|age|role`, so the third field is the
    place the query named. It is a country or a city, and a city resolves through the
    region list.
    """
    parts = (cell or "").split("|")
    if len(parts) < 3:
        return None
    place = parts[2].strip()
    if place in REGIONS:
        return place
    return _region_match(norm(place))


def in_preferences(location_text, allowed=None, cell=None):
    """(ok, reason). An unresolvable or non-place location is not a pass.

    `cell` is the ledger's cell for this row. It does two things. It settles a place
    name held by more than one country, and it supplies the country when the posting
    names a town the gazetteer does not hold at all. The second case is an inference
    and the reason string says so, because a portal omitting the country is not the
    same fact as a posting stating it.
    """
    allowed = allowed or allowed_countries()
    s = norm(location_text)

    # A non place is rejected before any lookup. The gazetteer holds a Honduran
    # town called Union, so "European Union" resolved to Honduras when this test
    # ran second.
    if re.search(NON_PLACE, s):
        return False, "not a place, such as European Union or remote"

    searched = searched_country(cell)
    c = country_of(location_text, searched)

    if c is None:
        if searched:
            # The query asked for one country and the portal answered without naming
            # one. That is how a portal writes a local result, so the searched
            # country is the reading, marked as taken from the query.
            if searched not in allowed:
                return False, f"{searched} is not in his preferences"
            return True, f"{searched} (from the query)"
        return False, f"location does not resolve to a country ({location_text!r})"

    if c not in allowed:
        return False, f"{c} is not in his preferences"
    return True, c
