#!/usr/bin/env python3
"""census_demand.py — free demographic signal for Location Scout phase 2.

WHY THESE FIVE NUMBERS
----------------------
Phase 1 ranked candidate offices on geometry alone: distance from the pin and
how many target towns one office would cover. Geometry says nothing about
whether the towns are worth serving. Santino: "Does it also take into account
the population size and potential for water damage jobs based on affluency of
the neighborhood as well as maybe residential size?"

  population            market size — how many properties exist at all
  median_household_income
                        affluence. Higher-income owners pay out of pocket and
                        approve full scopes; lower-income owners defer, or the
                        claim stalls on the deductible.
  owner_occupied_pct    owners call restoration companies. RENTERS CALL THEIR
                        LANDLORD, so a town of renters has a far smaller
                        addressable market than its population suggests.
  median_home_value     job size — restoration scope tracks property value.
  median_year_built     the sleeper metric, and probably the best free proxy
                        for water-damage FREQUENCY there is. Older stock means
                        older supply lines, older water heaters, cast-iron
                        drains and galvanised pipe. A 1955 town generates far
                        more emergency water work per household than a 2015 one.

DATA SOURCES
------------
  Census Geocoder  (KEYLESS)  lat/lng -> state + place FIPS.
  ACS 5-year API   (KEY)      the five variables above, per place.

The geocoder needs nothing. The ACS endpoint DOES require a free key — I
originally said it was keyless and that was wrong; it returns a "Missing Key"
page. Get one in about a minute at
https://api.census.gov/data/key_signup.html and set CENSUS_API_KEY.

Without the key this module degrades cleanly: every lookup returns None and
Location Scout falls back to pure geometry rather than failing.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

GEOCODER = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
ACS = "https://api.census.gov/data/2023/acs/acs5"

VARS = {
    "B01003_001E": "population",
    "B19013_001E": "median_household_income",
    "B25003_001E": "occupied_units",
    "B25003_002E": "owner_occupied_units",
    "B25035_001E": "median_year_built",
    "B25077_001E": "median_home_value",
}

# Census uses large negative sentinels for "no data" (-666666666 and friends).
def _num(v):
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return None if n < -1e6 else n


def place_for(lat: float, lng: float) -> dict | None:
    """lat/lng -> {'state': '06', 'place': '69196', 'name': 'Santa Maria city'}.

    Keyless. Returns None when the point falls outside any incorporated place
    (unincorporated communities are common in service areas — Orcutt and Los
    Berros both are), in which case the caller simply has no demographics.
    """
    q = urllib.parse.urlencode({
        "x": lng, "y": lat, "benchmark": "Public_AR_Current",
        "vintage": "Current_Current", "layers": "Places", "format": "json",
    })
    try:
        with urllib.request.urlopen(f"{GEOCODER}?{q}", timeout=25) as r:
            geo = json.load(r).get("result", {}).get("geographies", {})
    except Exception:
        return None
    places = geo.get("Incorporated Places") or geo.get("Census Designated Places") or []
    if not places:
        return None
    p = places[0]
    if not p.get("STATE") or not p.get("PLACE"):
        return None
    return {"state": p["STATE"], "place": p["PLACE"], "name": p.get("NAME")}


def key_status() -> tuple:
    """('ok'|'missing'|'invalid'|'unreachable', human explanation).

    A key that is present but REJECTED must not look the same as no key at all.
    Census emails a key and it stays inert until the activation link in that
    email is clicked, so "I pasted the key and nothing happened" is the normal
    first experience — worth naming rather than silently showing blank columns.
    """
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        return ("missing", "CENSUS_API_KEY is not set — get one free at "
                           "api.census.gov/data/key_signup.html")
    probe = f"{ACS}?get=NAME&for=state:06&key={urllib.parse.quote(key)}"
    try:
        with urllib.request.urlopen(probe, timeout=20) as r:
            body = r.read(400).decode("utf-8", "replace")
    except Exception as e:
        return ("unreachable", f"could not reach the Census API ({str(e)[:80]})")
    if body.lstrip().startswith("["):
        return ("ok", "Census key is live")
    if "Invalid Key" in body:
        return ("invalid", "Census rejected the key. A new key stays INACTIVE "
                           "until you click the activation link Census emails "
                           "you — check the inbox you signed up with.")
    return ("invalid", "Census did not return data for this key")


def demographics(lat: float, lng: float) -> dict | None:
    """The five signals for the place containing this point, or None."""
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        return None
    pl = place_for(lat, lng)
    if not pl:
        return None
    q = urllib.parse.urlencode({
        "get": "NAME," + ",".join(VARS),
        "for": f"place:{pl['place']}",
        "in": f"state:{pl['state']}",
        "key": key,
    })
    try:
        with urllib.request.urlopen(f"{ACS}?{q}", timeout=30) as r:
            rows = json.load(r)
    except Exception:
        return None
    if not rows or len(rows) < 2:
        return None
    head, vals = rows[0], rows[1]
    rec = dict(zip(head, vals))
    out = {"census_place": rec.get("NAME") or pl["name"]}
    for code, label in VARS.items():
        out[label] = _num(rec.get(code))
    occ, own = out.pop("occupied_units", None), out.pop("owner_occupied_units", None)
    out["owner_occupied_pct"] = round(100 * own / occ, 1) if occ and own else None
    return out


def demand_score(d: dict | None) -> dict:
    """Blend the five signals into one 0-100 score with its reasoning kept.

    Deliberately transparent rather than clever: each component is scored
    independently against a plain restoration-market yardstick and averaged over
    whatever is actually present, so a missing variable weakens confidence
    instead of silently scoring zero. The point is a defensible ranking a client
    can be walked through, not a black box.
    """
    if not d:
        return {"score": None, "parts": {}, "note": "no census match"}
    parts: dict = {}

    pop = d.get("population")
    if pop is not None:                      # 5k -> 0, 100k+ -> 100
        parts["population"] = max(0.0, min(100.0, (pop - 5000) / 95000 * 100))

    inc = d.get("median_household_income")
    if inc is not None:                      # $45k -> 0, $150k+ -> 100
        parts["income"] = max(0.0, min(100.0, (inc - 45000) / 105000 * 100))

    own = d.get("owner_occupied_pct")
    if own is not None:                      # 35% -> 0, 80%+ -> 100
        parts["owner_occupancy"] = max(0.0, min(100.0, (own - 35) / 45 * 100))

    val = d.get("median_home_value")
    if val is not None:                      # $200k -> 0, $1.2M+ -> 100
        parts["home_value"] = max(0.0, min(100.0, (val - 200000) / 1000000 * 100))

    yr = d.get("median_year_built")
    if yr is not None:                       # 2005+ -> 0, 1950 or older -> 100
        parts["housing_age"] = max(0.0, min(100.0, (2005 - yr) / 55 * 100))

    if not parts:
        return {"score": None, "parts": {}, "note": "no usable census values"}
    return {"score": round(sum(parts.values()) / len(parts), 1),
            "parts": {k: round(v, 1) for k, v in parts.items()},
            "note": f"{len(parts)}/5 signals present"}


if __name__ == "__main__":
    import sys
    lat, lng = float(sys.argv[1]), float(sys.argv[2])
    print("place:", json.dumps(place_for(lat, lng)))
    d = demographics(lat, lng)
    print("demographics:", json.dumps(d, indent=2))
    print("demand:", json.dumps(demand_score(d), indent=2))
