"""Read queries.yaml, the executed form of 04. preferences.md.

This module is the only place the matrix is read. Before it existed, sweep.py
carried the roles and locations as Python constants and greped the file for
nothing but the approved flag, so editing a preference changed nothing in a run
and the run still reported success.

The split is deliberate. The file owns the SHAPE, meaning the roles, the
locations, which portals serve which locations, the URL layout and each
portal's native parameter values. Python owns the TRANSFORMS, meaning hours to
seconds, hours to a native age facet, and text to a slug, because those encode
portal quirks a template string cannot express.

Nothing here falls back to a default. A missing or malformed key raises, since a
silent fallback to built-in values is exactly the failure this replaces.
"""

import re
import urllib.parse
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).resolve().parent / "queries.yaml"


class MatrixError(Exception):
    """queries.yaml is missing a key the run needs, or it is malformed."""


UMLAUT = str.maketrans({"\u00fc": "ue", "\u00f6": "oe", "\u00e4": "ae",
                        "\u00df": "ss", "\u00e9": "e", "\u00e5": "a"})


def hyphen(s):
    """Slug a value for a URL path, transliterating rather than dropping.

    German place names reach the portals with umlauts, and Stepstone spells
    them out, so Muenchen has to survive as muenchen rather than as m-nchen.
    """
    return re.sub(r"[^a-z0-9]+", "-", s.lower().translate(UMLAUT)).strip("-")


UNIT_HOURS = {"h": 1, "hour": 1, "d": 24, "day": 24, "w": 168, "week": 168,
              "m": 720, "month": 720}


def _duration_hours(label):
    """'24h', '7d', '1w', 'week' and 'day' all read as a number of hours."""
    s = str(label).strip().lower()
    m = re.fullmatch(r"(\d*)\s*([a-z]+)", s)
    if not m:
        return None
    n = int(m.group(1)) if m.group(1) else 1
    unit = m.group(2).rstrip("s")
    if unit in UNIT_HOURS:
        return n * UNIT_HOURS[unit]
    for k, h in UNIT_HOURS.items():
        if len(k) > 1 and unit.startswith(k[:3]):
            return n * h
    return None


def _need(d, key, where):
    if not isinstance(d, dict) or key not in d:
        raise MatrixError(f"queries.yaml: {where} has no {key!r}")
    return d[key]


class Matrix:
    def __init__(self, data, path):
        self.path = path
        self.version = _need(data, "version", "top level")
        self.approved = _need(data, "approved", "top level") is True
        self.freshness_hours = _need(_need(data, "defaults", "top level"),
                                     "freshness_hours", "defaults")
        self.locations = _need(data, "locations", "top level")
        self.portals = _need(data, "portals", "top level")
        roles = _need(data, "roles", "top level")
        self.roles = []
        for r in roles:
            self.roles.append((_need(r, "id", "a roles entry"),
                               str(_need(r, "query", "a roles entry"))))
        if not self.roles:
            raise MatrixError("queries.yaml: roles is empty")

    # ---- lookups ----

    def portal(self, name):
        if name not in self.portals:
            raise MatrixError(f"queries.yaml: no portal {name!r}")
        return self.portals[name] or {}

    def template(self, name):
        return str(_need(self.portal(name), "url_template", f"portal {name}"))

    def serves(self, name):
        """The location units a portal covers.

        `serves` names either a group under `locations`, such as `europe`, or a
        single location spelled as it appears there, such as `Germany`.
        """
        out = []
        for entry in _need(self.portal(name), "serves", f"portal {name}"):
            if entry in self.locations:
                out.extend(str(x) for x in self.locations[entry])
            else:
                known = [str(x) for g in self.locations.values() for x in g]
                if entry not in known:
                    raise MatrixError(
                        f"queries.yaml: portal {name} serves {entry!r}, "
                        "which is neither a location group nor a location")
                out.append(str(entry))
        return out

    def cells(self, name):
        """Every (location, role query) pair this portal is asked to sweep."""
        return [(loc, q) for loc in self.serves(name) for _, q in self.roles]

    # ---- transforms ----

    def freshness_seconds(self):
        return int(self.freshness_hours) * 3600

    def age_facet(self, name):
        """Hours mapped onto a portal's own age values.

        Stepstone offers 24 hours and 7 days and nothing between, so a 48 hour
        preference has no native form. The smallest native window that still
        contains the request is used, and the surplus is dropped after the
        fetch. Choosing the smaller window instead would lose postings the
        preference asks for, and a lost posting cannot be recovered downstream.
        """
        facets = _need(self.portal(name), "age_facets", f"portal {name}")
        pairs = []
        for label, value in facets.items():
            hours = _duration_hours(label)
            if hours is None:
                raise MatrixError(
                    f"queries.yaml: portal {name} age facet {label!r} is not "
                    "a duration such as 24h, 48h, 7d, 1w, day or week")
            pairs.append((hours, value))
        pairs.sort()
        for hours, value in pairs:
            if hours >= self.freshness_hours:
                return value
        return pairs[-1][1]

    def job_age_days(self, name):
        """Hours as one of a portal's accepted day values.

        Naukri accepts 1 and 7 and silently ignores anything else, so a value
        it does not accept reads as a working filter and applies none. The
        accepted values are declared in the file and the smallest one that
        still contains the request wins.
        """
        allowed = sorted(int(v) for v in
                         _need(self.portal(name), "job_age_values", f"portal {name}"))
        want = max(1, round(self.freshness_hours / 24))
        for v in allowed:
            if v >= want:
                return v
        return allowed[-1]

    def api_count(self, name):
        return int(self.portal(name).get("api_count", 25))

    def api_url(self, name, loc, role, start=0):
        """The endpoint the portal's own page calls for one page of a cell."""
        tpl = str(_need(self.portal(name), "api_template", f"portal {name}"))
        q = urllib.parse.quote
        fields = {
            "kw": q(role),
            "loc": q(loc),
            "start": start,
            "count": self.api_count(name),
            "freshness_hours": self.freshness_hours,
            "freshness_seconds": self.freshness_seconds(),
        }
        try:
            return tpl.format(**fields)
        except KeyError as e:
            raise MatrixError(
                f"queries.yaml: portal {name} api_template uses {e}, which this "
                f"loader does not supply. Known fields are {', '.join(sorted(fields))}")

    def url(self, name, loc, role, offset=0, page_size=25):
        """The portal's URL for one cell, formatted from the file's template."""
        city = loc.split(",")[0].strip()
        # A portal may spell a place its own way, as Stepstone does with
        # Germany, so the file's map wins over the slug.
        place = self.portal(name).get("place_names", {}) or {}
        q = urllib.parse.quote_plus
        fields = {
            "kw": q(role),
            "kw_hyphen": hyphen(role),
            "loc": q(loc),
            "place": place.get(city, hyphen(city)),
            "city_hyphen": hyphen(city),
            "offset": offset,
            "page": offset // page_size + 1,
            "freshness_hours": self.freshness_hours,
            "freshness_seconds": self.freshness_seconds(),
        }
        tpl = self.template(name)
        if "{age_facet}" in tpl:
            fields["age_facet"] = self.age_facet(name)
        if "{job_age}" in tpl:
            fields["job_age"] = self.job_age_days(name)
        try:
            return tpl.format(**fields)
        except KeyError as e:
            raise MatrixError(
                f"queries.yaml: portal {name} url_template uses {e}, "
                f"which this loader does not supply. Known fields are "
                f"{', '.join(sorted(fields))}")


def load(path=None):
    p = Path(path) if path else DEFAULT_PATH
    if not p.is_file():
        raise MatrixError(f"queries.yaml not found at {p}")
    data = yaml.safe_load(p.read_text())
    if not isinstance(data, dict):
        raise MatrixError(f"{p} did not parse as a mapping")
    return Matrix(data, p)
