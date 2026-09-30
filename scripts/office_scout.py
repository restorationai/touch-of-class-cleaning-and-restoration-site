#!/usr/bin/env python3
"""office_scout.py — location_scout phase 3: WHICH BUILDING in the town.

location_scout.py answers "which towns are worth a second Google Business
Profile". This answers the next question (queue item 21, Santino 2026-09-27):
for each of those towns, what can the client actually RENT to put that second
pin at, and how likely is it to survive Google's verification?

Why it matters: Power Dry (Kansas City) runs a second GBP at a Regus office and
ChatGPT's #1 KC answer cites that listing; Alert Restoration (Bakersfield) has
real satellite offices in Hanford and Tehachapi. Google now leans on VIDEO
verification (signage, equipment, proof you control the space), so the tier of
space decides whether the profile survives:

  flex / industrial / warehouse suite  HIGH    signage + equipment on camera
  small office you lease (own door)    HIGH    same, less room for equipment
  exec suite / Regus PRIVATE office    MEDIUM  sometimes passes; never the
                                               "virtual office" product
  self-storage business unit           MEDIUM  equipment yes, signage/staffing
                                               usually no; ask for a business bay
  open coworking desk                  LOW     nothing lockable to film
  UPS Store / mailbox / virtual-only   NEVER   filtered out, never shown

Gray-area options stay in the report as the client's informed choice; the
rating is the honest part.

WHERE THE TOWNS COME FROM (single source of truth)
  * marketing_location_scout (the shortlist the app's Locations tab shows,
    written by `location_scout.py --save`) — top N seats by rank, default 3.
  * --fresh-scout runs location_scout.scout() live instead (slow: Nominatim).
  * --towns "Delano, CA; Tehachapi, CA" adds towns by hand (or is the only
    input when there is no shortlist).

DataForSEO: Google Maps live/advanced, ~$0.002 per query, 6 queries per town
(coworking, exec suites, office for rent, warehouse, flex industrial, self
storage). PLUS LoopNet + Crexi, where small-town flex/office suites actually
list: both are bot-protected, so they are never fetched; Google organic SERP
(`site:loopnet.com` / `site:crexi.com`, ~$0.01 each, + one plain "flex space
for lease" query at ~$0.002) is parsed for address, sq ft, $/SF or $/mo.
Those listings rate HIGH (a real suite with signage) and outrank storage.

MORE SOURCES (2026-09-27, same rule: Google's index via DataForSEO organic
SERP, NEVER a direct fetch of the site): CityFeet + Showcase (CoStar), and
CommercialCafe + OfficeSpace.com go through the same address parser as
LoopNet/Crexi; Craigslist "office & commercial" posts (monthly rent + sq ft
from the snippet, address when the post gives one); LiquidSpace + Coworker.com
PRIVATE offices (tier coworking); SpareFoot facilities (tier storage). Paired
sites share one `site:a OR site:b` query (billed once). Facebook Marketplace
is login-walled and not indexed: a future Mac Mini browser lane, not here.
~$0.084/town (6 Maps + 7 site: + 1 plain organic). Every run is capped at
MAX_RUN_COST ($0.30, ~3 towns; pass --cap for more) and stops querying past
it; spend is printed.

Store (only with --apply; default is a dry-run print):
  * marketing_office_scout: one row per option (the app's Locations tab reads
    it under RLS). A run inserts the fresh ranked set, then deletes that
    company's older rows, so the table is always the current set.
  * ops_kv `office-scout:{company_id}`, the full run blob:
  {"slug", "company_id", "generated_at", "pin", "reach_mi", "spend_usd",
   "towns": [{"town", "state", "lat", "lng", "source", "would_cover",
              "distance_from_pin_mi", "options": [...], "excluded": [...]}]}

CONTACTS (2026-09-28, --contacts, default ON with --apply): who to call per
option (listing broker / facility office): name, role, company, phone (E.164
+ Twilio line type mobile|landline|voip), email, and the page it was found on.
See the "contacts" section below for how each source is handled; capped by
--contacts-cap ($0.40, SERP + Twilio); fail-open per option; never invented.

Usage:
  python3 scripts/office_scout.py --slug prorestoration
  python3 scripts/office_scout.py --slug prorestoration --towns "Delano, CA; Tehachapi, CA" --apply
  python3 scripts/office_scout.py --towns "Hanford, CA"            # no client: no pin distances
  python3 scripts/office_scout.py --slug X --json
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from client_concierge import kv_get, kv_set, load_env  # noqa: E402

load_env()
import location_scout as ls  # noqa: E402  haversine, geocode, load_client, scout

DFS_MAPS = "https://api.dataforseo.com/v3/serp/google/maps/live/advanced"
DFS_ORGANIC = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
COST_PER_QUERY = 0.002
COST_PER_SITE_QUERY = 0.01   # DataForSEO bills search operators (site:) ~5x
# ~$0.084/town (6 Maps + 7 site: + 1 plain organic), so the cap covers ~3 towns.
MAX_RUN_COST = 0.30
DEFAULT_TOP_TOWNS = 3
PER_TOWN = 8            # options shown per town
MAX_LISTINGS = 4        # CRE/Craigslist listings per town, so Maps options still show
PER_TIER_CAP = 2        # keep a spread of tiers, not five storage units
# An office further than this from the town it is meant to serve is serving a
# different town. The seat's own reach is used when larger.
MAX_FROM_CENTER_MI = 6.0
# A second office this far from the first one is a different business, and far
# more often a bad geocode (Nominatim put ProRestoration's "East Niles", an
# east-Bakersfield neighbourhood, 108mi away near Fresno).
MAX_FROM_PIN_MI = 75.0
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) RankAI-OfficeScout/1.0"

# (tier hint, query). The tier is decided from the RESULT's category, not the
# query: "office space for rent" returns storage units and apartments too.
QUERIES = [
    ("coworking", "coworking space"),
    ("coworking", "executive office suites"),
    ("office", "office space for rent"),
    ("flex", "warehouse space for rent"),
    ("flex", "flex industrial space for lease"),
    ("storage", "self storage"),
]

# ------------------------------------------------------------- classification
# Addresses that can never pass verification. Checked against title + main
# category + domain, and the result is dropped (listed as excluded, not shown).
NEVER_PASS = re.compile(
    r"ups store|\bthe ups\b|mailbox|mail box|mail center|mail boxes|postal|post office|"
    r"\bp\.?\s?o\.?\s?box|pak mail|postnet|pack\s*(?:&|and|n)\s*ship|shipping and mailing|"
    r"anytime ?mailbox|ipostal|davinci|opus virtual|alliance virtual|earth ?class ?mail|"
    r"virtual (?:office|mailbox|address)", re.I)
# Big-brand flex operators whose PRIVATE OFFICE (never the membership/virtual
# product) can pass video verification. WeWork added 2026-09-30 (Santino: others
# have used it to get verified): private office with your name on the door only.
IWG = re.compile(r"\bregus\b|\bspaces\b|\bhq\b|signature by regus|\biwg\b|\bbasepoint\b|"
                 r"\bwework\b", re.I)
STORAGE_BAD = re.compile(r"cold storage|records|document|\brv\b|boat|freezer|shred|parking|"
                         r"moving|portable|pods\b|container", re.I)
RENTAL_WORDS = re.compile(r"rent|lease|space|suite|\bpark\b|flex|business|center|centre|"
                          r"storage|units?\b|industrial|commercial", re.I)
BIZ_UNITS = re.compile(r"business|commercial|warehouse|workspace|office|flex|industrial", re.I)

CAT_TIER = {
    "coworking space": "coworking",
    "executive suite rental agency": "coworking",
    "business center": "coworking",
    "office space rental agency": "office",
    "office building": "office",
    "business park": "flex",
    "industrial real estate agency": "broker",
    "commercial real estate agency": "broker",
    "real estate rental agency": "broker",
    "property management company": "broker",
    "warehouse": "flex",
    "self-storage facility": "storage",
    "storage facility": "storage",
    "mini warehouse": "storage",
}

COST_BAND = {        # small-market California defaults, per month
    "flex": "$800-2,500",
    "office": "$400-1,200",
    "coworking": "$300-900",
    "storage": "$120-350",
    "broker": "varies (unit)",
    "virtual": "$50-150",
}
RETAIL_CATS = {"office supply store", "shipping service", "print shop", "hotel", "motel",
               "apartment building", "apartment complex", "shopping mall", "parking lot",
               "truck parking area", "employment agency", "event venue"}
FALLBACK_CATS = {"coworking space", "executive suite rental agency", "office space rental agency",
                 "self-storage facility"}
V_WEIGHT = {"high": 3, "medium": 2, "low": 1}


def classify(it: dict) -> tuple[str | None, str | None]:
    """-> (tier, None) or (None, exclusion reason) or (None, None) = irrelevant."""
    title = it.get("title") or ""
    cat = (it.get("category") or "").lower()
    extra = [c.lower() for c in (it.get("additional_categories") or []) if c]
    blob = f"{title} {cat} {it.get('domain') or ''}"
    if NEVER_PASS.search(blob) or cat in ("shipping and mailing service", "mailbox rental service",
                                         "post office"):
        return None, "mailbox/UPS/virtual-address service (never passes)"
    if cat == "virtual office rental" and not IWG.search(title):
        return None, "virtual-office-only provider (never passes)"
    if IWG.search(title) and (cat in CAT_TIER or "office" in cat or "coworking" in cat):
        return "coworking", None
    # Cold storage / records / RV lots are somebody's operation, not a unit for
    # a restoration company, whatever tier the category suggests.
    if STORAGE_BAD.search(f"{title} {cat}"):
        return None, None
    if cat in RETAIL_CATS or re.search(r"\bwalmart\b|staples|office ?depot|fedex|\bhotel\b|\bmotel\b|"
                                       r"\binn\b|\bihg\b|marriott|hilton|hyatt", title, re.I):
        return None, None
    # Property managers file under "Office space rental agency" but mostly
    # rent apartments: they are a lead to a unit, not a unit.
    if "property management" in title.lower() or "apartment rental agency" in extra:
        return "broker", None
    if "coworking space" in extra and cat == "office space rental agency":
        return "coworking", None
    tier = CAT_TIER.get(cat)
    # Residential agents are noise; COMMERCIAL agents are how you find a flex
    # suite in a town too small to list one on Maps.
    if not tier and cat == "real estate agency" and (
            "commercial real estate agency" in extra or re.search(r"commercial", title, re.I)):
        tier = "broker"
    if not tier:
        # Additional categories only for unambiguous space types; "Warehouse"
        # or "Business center" as a side category marked truck lots and a
        # Walmart B2B counter as flex/coworking in the first run.
        for c in extra:
            if c in FALLBACK_CATS:
                tier = CAT_TIER[c]
                break
    if not tier:
        return None, None
    if tier == "flex" and cat == "warehouse" and not RENTAL_WORDS.search(title):
        return None, None          # somebody's own warehouse, not a unit for lease
    return tier, None


def rate(tier: str, it: dict) -> tuple[str, str, str]:
    """-> (verification_likelihood, one-line reason, note)."""
    title = it.get("title") or ""
    cat = (it.get("category") or "").lower()
    if tier == "flex":
        return ("high", "Own roll-up/suite with exterior signage and equipment on camera is "
                "exactly what video verification checks.",
                "Ask for the smallest flex/warehouse suite (500-1,500 sq ft); confirm exterior "
                "sign allowed and business-use lease.")
    if tier == "office":
        if cat == "office space rental agency":
            return ("medium", "Leased office suites pass when lockable with door/building "
                    "signage; shared-suite setups get rejected.",
                    "Ask for a private lockable office with your name on the door and lobby "
                    "directory; confirm staffed-hours access.")
        return ("high", "A small office you lease with your own entrance and sign is a "
                "legitimate location if filmed with signage, equipment and keys.",
                "Ask the landlord for a small suite with exterior or door signage; month-to-month "
                "if possible.")
    if tier == "coworking":
        if IWG.search(title):
            return ("medium", "IWG/WeWork private offices sometimes pass (Power Dry KC "
                    "precedent); the virtual-office, All Access and hot-desk products fail.",
                    "Regus/IWG/WeWork: ask for a PRIVATE OFFICE on a monthly term, not a "
                    "membership or virtual office; confirm your name on the door and lobby "
                    "signage are allowed, and staffed-hours access.")
        if cat == "coworking space":
            return ("low", "Open desks have nothing lockable or signed to film; only a private "
                    "office here could pass.",
                    "Only worth it if they rent a lockable private office with signage; skip "
                    "hot-desk / dedicated-desk plans.")
        return ("medium", "Executive suites pass sometimes with a private office and door "
                "signage; mail-only plans fail.",
                "Ask for a private office (not mail/virtual plan); confirm signage and "
                "staffed hours.")
    if tier == "storage":
        if BIZ_UNITS.search(title):
            return ("medium", "Facility markets business/commercial units; equipment films well "
                    "but signage and staffing are the weak points.",
                    "Ask for a business/warehouse bay with signage allowed and daytime access; "
                    "a standard unit behind a gate usually fails.")
        return ("medium", "Drive-up unit can show equipment on video, but most facilities ban "
                "signage and the gate reads as storage.",
                "Ask whether they allow business use + a sign on a drive-up unit; if not, "
                "treat as last resort.")
    if tier == "broker":
        return ("medium", "Depends on the unit they lease you; a flex suite or small office "
                "from them rates HIGH.",
                "Commercial broker/landlord: ask for small flex or office listings in town "
                "with signage allowed.")
    return ("low", "Unknown space type.", "")


def cost_rank(tier: str) -> float:
    return {"storage": 0.6, "coworking": 0.4, "office": 0.3, "flex": 0.0, "broker": 0.0}.get(tier, 0)


# ------------------------------------------------------------- DataForSEO
class DFS:
    def __init__(self, cap: float = MAX_RUN_COST):
        import geogrid_scan as gs
        u, p = gs.load_dfs_creds()
        self.auth = base64.b64encode(f"{u}:{p}".encode()).decode()
        self.cost = 0.0
        self.cost_maps = 0.0
        self.cost_serp = 0.0
        self.calls = 0
        self.cap = cap
        self.skipped = 0
        self.lock = threading.Lock()   # contact enrichment calls organic() from threads
        self.reserve = 0.0             # other spend (Twilio) counted against the same cap

    def organic(self, keyword: str) -> list[dict]:
        """Google organic top 10. `site:` queries bill ~5x (~$0.01)."""
        est = COST_PER_SITE_QUERY if "site:" in keyword else COST_PER_QUERY
        with self.lock:
            if self.cost + self.reserve + est > self.cap + 1e-9:
                self.skipped += 1
                return []
            self.reserve += est        # held until the real cost is known
        try:
            r = requests.post(DFS_ORGANIC, timeout=120, headers={
                "Authorization": "Basic " + self.auth, "Content-Type": "application/json"},
                json=[{"keyword": keyword, "language_code": "en", "location_code": 2840,
                       "depth": 10}])
            task = (r.json().get("tasks") or [{}])[0]
        except Exception as e:  # noqa: BLE001
            print(f"  [dfs] error on '{keyword}': {str(e)[:80]}")
            with self.lock:
                self.reserve -= est
            return []
        with self.lock:
            self.reserve -= est
            self.calls += 1
            c = float(task.get("cost") or 0)
            self.cost += c
            self.cost_serp += c
        items = (((task.get("result") or [{}])[0] or {}).get("items")) or []
        return [{"title": it.get("title") or "", "url": it.get("url") or "",
                 "snippet": it.get("description") or ""}
                for it in items if it.get("type") == "organic"]

    def maps(self, keyword: str, lat: float, lng: float) -> list[dict]:
        if self.cost + COST_PER_QUERY > self.cap + 1e-9:
            self.skipped += 1
            return []
        try:
            r = requests.post(DFS_MAPS, timeout=120, headers={
                "Authorization": "Basic " + self.auth, "Content-Type": "application/json"},
                json=[{"keyword": keyword, "location_coordinate": f"{lat:.5f},{lng:.5f},12z",
                       "language_code": "en", "depth": 20}])
            task = (r.json().get("tasks") or [{}])[0]
        except Exception as e:  # noqa: BLE001
            print(f"  [dfs] error on '{keyword}': {str(e)[:80]}")
            return []
        with self.lock:
            self.calls += 1
            c = float(task.get("cost") or 0)
            self.cost += c
            self.cost_maps += c
        return (((task.get("result") or [{}])[0] or {}).get("items")) or []


# ------------------------------------------------------------- inputs
def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def client_ctx(slug: str) -> dict:
    data = ls.load_client(slug)
    brand = data["plan"].get("brand") or {}
    cid = data["rec"].get("company_id") or brand.get("company_id")
    if not cid:
        cmap = ls.CLIENTS_DIR / "company_map.json"
        if cmap.exists():
            try:
                cid = json.loads(cmap.read_text()).get(slug)
            except Exception:  # noqa: BLE001
                pass
    return {"slug": slug, "company_id": cid,
            "name": brand.get("name") or data["rec"].get("name") or slug,
            "pin": (_f(brand.get("lat")), _f(brand.get("lng")))}


def saved_shortlist(cid: str) -> list[dict]:
    return ls._sb(f"/rest/v1/marketing_location_scout?company_id=eq.{cid}&order=rank.asc&limit=50") or []


def parse_towns(s: str) -> list[tuple[str, str]]:
    out = []
    for part in (s or "").split(";"):
        part = part.strip()
        if not part:
            continue
        city, _, state = part.partition(",")
        out.append((city.strip(), state.strip() or "CA"))
    return out


def gather_towns(ctx: dict | None, towns_arg: str, top: int, fresh: bool) -> tuple[list[dict], float]:
    """-> (towns, reach_mi). Shortlist seats first (by rank), then --towns."""
    towns: list[dict] = []
    reach = ls.DEFAULT_REACH_MI
    if ctx:
        if fresh:
            res = ls.scout(ctx["slug"])
            reach = res.get("effective_reach_mi") or reach
            seats = [{"seat_city": s["seat_city"], "state": s["state"], "lat": s["lat"],
                      "lng": s["lng"], "distance_from_pin_mi": s["distance_from_pin_mi"],
                      "would_cover": s["would_cover"]} for s in res["recommended_offices"]]
            src = "location_scout (live run)"
        else:
            seats = saved_shortlist(ctx["company_id"]) if ctx.get("company_id") else []
            if seats:
                reach = _f(seats[0].get("effective_reach_mi")) or reach
            src = "location_scout shortlist (marketing_location_scout)"
        taken = 0
        for s in seats:
            if taken >= top:
                break
            d = _f(s.get("distance_from_pin_mi"))
            if d is not None and d > MAX_FROM_PIN_MI:
                print(f"  skipping seat {s['seat_city']}: {d}mi from the pin — almost certainly a "
                      f"bad geocode in location_scout, verify by hand")
                continue
            towns.append({"town": s["seat_city"], "state": s.get("state") or "", "lat": _f(s["lat"]),
                          "lng": _f(s["lng"]), "source": f"{src} #{s.get('rank', taken + 1)}",
                          "town_rank": s.get("rank", taken + 1),
                          "would_cover": s.get("would_cover") or [s["seat_city"]]})
            taken += 1
    have = {t["town"].lower() for t in towns}
    pin = (ctx or {}).get("pin") or (None, None)
    county = pin_state = None
    if pin[0] is not None and towns_arg.strip():
        county, pin_state = ls.county_of(pin[0], pin[1])
    for city, state in parse_towns(towns_arg):
        if city.lower() in have:
            continue
        # Same plausibility guard as location_scout: in-state, near the pin,
        # "Town, County, ST" retry. Nominatim pacing lives inside the helper.
        ll = ls.geocode(city, state, near=pin if pin[0] is not None else None,
                        county=county if pin_state and state.upper() == pin_state else None)
        if not ll:
            print(f"  could not geocode {city}, {state} plausibly; skipped")
            continue
        towns.append({"town": city, "state": state, "lat": ll[0], "lng": ll[1],
                      "source": "--towns", "town_rank": None, "would_cover": [city]})
        have.add(city.lower())
    for t in towns:
        t["distance_from_pin_mi"] = (round(ls.haversine_mi(pin[0], pin[1], t["lat"], t["lng"]), 1)
                                     if pin[0] is not None else None)
    return towns, reach


# ------------------------------------------------------------- price peek
PRICE_RE = re.compile(r"\$\s?(\d{1,2},\d{3}|\d{2,5})(?:\.\d{2})?\s*(?:/\s*mo\b|/\s*month|"
                      r"per month|a month|monthly|/mth)", re.I)


def price_peek(url: str) -> int | None:
    """Cheapest '$N/mo' on the landing page. One GET, 6s, first 400KB. Most
    storage/IWG pages render prices in JS, so a miss is normal and harmless."""
    if not url or not url.startswith("http"):
        return None
    try:
        r = requests.get(url, timeout=6, headers={"User-Agent": UA}, stream=True)
        if r.status_code >= 400:
            return None
        raw = r.raw.read(400_000, decode_content=True).decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return None
    vals = []
    for m in PRICE_RE.finditer(raw):
        v = int(m.group(1).replace(",", ""))
        if 20 <= v <= 20000:
            vals.append(v)
    return min(vals) if vals else None


# ------------------------------------------------------------- LoopNet / Crexi
# Small towns rarely put a flex suite on Google Maps; the real inventory is on
# LoopNet and Crexi. Both are bot-protected, so they are NEVER fetched: we read
# what Google already indexed (title / snippet / URL) through DataForSEO's
# organic SERP and parse options out of that. Queries per town:
# Path-scoped on purpose (tested 2026-09-27): bare site:loopnet.com returns
# assessor parcel pages, bare site:crexi.com returns for-sale search pages.
LISTING_QUERIES = [
    ("loopnet", 'site:loopnet.com/Listing "{town}, {st}" (flex OR office OR industrial OR warehouse) for lease'),
    ("crexi", 'site:crexi.com/lease "{town}, {st}" office OR flex OR industrial OR warehouse'),
    ("web", "{town} {st} flex space for lease"),
    # CoStar's consumer sites: /cont/listing/{addr}/ and /{addr}/{id}/ pages
    # (Showcase is mostly "no longer advertised" + FOR SALE; filters drop those).
    ("cityfeet", 'site:cityfeet.com OR site:showcase.com "{town}, {st}" for lease'),
    ("commercialcafe", 'site:commercialcafe.com OR site:officespace.com "{town}, {st}" office OR warehouse OR flex'),
]
# Sources parsed by their own handlers (extra_options), not the address flow.
EXTRA_QUERIES = [
    # Plain form on purpose: quoting the town or OR-ing terms returned 0 (tested).
    ("craigslist", "site:craigslist.org {town} office for rent"),
    ("coworking", 'site:liquidspace.com OR site:coworker.com "{town}, {st}" private office'),
    # WeWork (2026-09-30): building pages list the city; private offices only.
    ("coworking", 'site:wework.com "{town}" private office'),
    ("storage", 'site:sparefoot.com "{town}, {st}" self storage'),
]
# Hosts we recognise, host fragment -> source label shown in the app.
SOURCES = {"loopnet": "loopnet", "crexi": "crexi", "cityfeet": "cityfeet", "showcase": "showcase",
           "commercialcafe": "commercialcafe", "officespace": "officespace",
           "craigslist": "craigslist", "liquidspace": "liquidspace", "coworker": "coworker",
           "wework": "wework",
           "sparefoot": "sparefoot"}
# CRE listing sites whose own listing page is a unit for lease even when it
# never names the type ("listing: space").
CRE_SITES = ("loopnet", "crexi", "cityfeet", "showcase", "commercialcafe", "officespace")
LISTING_TIERS = ("listing: flex", "listing: industrial", "listing: office", "listing: retail",
                 "listing: space")
COST_BAND.update({"listing: flex": "$800-2,500", "listing: industrial": "$900-3,000",
                  "listing: office": "$500-1,500", "listing: retail": "$1,000-3,000",
                  "listing: space": "$600-2,000"})
SF_RE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d{3,6})\s*(?:-\s*(\d{1,3}(?:,\d{3})+|\d{3,6})\s*)?"
                   r"(?:\+/-\s*)?(?:sf\b|sq\.?\s?ft|sqft|square f(?:ee|oo)t|ft\s?(?:2|²)(?!\d))", re.I)
# An address needs a street word, or "1 Warehouse For Rent in Delano, CA" and
# "10 Shared Office Spaces near Tehachapi, CA" read as addresses.
STREET_RE = re.compile(r"\b(?:st|street|ave|avenue|rd|road|blvd|boulevard|dr|drive|ln|lane|way|"
                       r"hwy|highway|pkwy|pky|parkway|ct|court|pl|place|cir|circle|ter|terrace|"
                       r"trl|trail|loop|plaza|expy|fwy|freeway|route|rte)\b", re.I)
NOT_LISTINGS = re.compile(r"facebook\.com|instagram\.com|yelp\.com|reddit\.com|nextdoor\.com|"
                          r"tiktok\.com|youtube\.com|linkedin\.com|craigslist|"
                          # residential portals: parcel/home records, not units for lease
                          r"zillow\.com|redfin\.com|trulia\.com|realtor\.com|homes\.com|"
                          r"apartments\.com|movoto\.com", re.I)
MAX_LISTING_SF = 20_000   # a satellite needs 500-1,500 SF; 60,000 SF is not an option
RATE_RE = re.compile(r"\$\s?(\d+(?:\.\d{1,2})?)\s*(?:-\s*\$?\s?\d+(?:\.\d{1,2})?\s*)?/?\s*"
                     r"(?:per\s+)?(?:sf|sq\.?\s?ft|sqft)\s*/?\s*(yr|year|mo|month)\b", re.I)
MONTHLY_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d{3,6})(?:\.\d{2})?\s*(?:/\s*mo\b|/\s*month|"
                        r"per month|a month|monthly)", re.I)
SALE_RE = re.compile(r"\bfor sale\b|available for sale|\bsold\b", re.I)
LEASE_RE = re.compile(r"\blease\b|\bfor rent\b|\brent\b", re.I)
STALE_RE = re.compile(r"no longer (?:being )?advertised|off market", re.I)
SALE_PRICE_RE = re.compile(r"\$\s?\d{1,3},\d{3},\d{3}|\$\s?[1-9]\d{2},\d{3}(?!\s*(?:/|per))")
LAND_RE = re.compile(r"\bland (?:for lease|property)|\bground lease\b|/acre|\bacres?\b|\blot\b", re.I)
# Parcels that never have a building: "Capital Hills Commercial Land", "Two
# Highway Commercial / Light Industrial lots" (CommercialCafe, 2026-09-27).
# Only a real building word rescues these, not "industrial".
LAND_STRONG = re.compile(r"(?:commercial|vacant|industrial) land\b|\blots\b|\bparcels?\b|shovel.ready|"
                         r"\bapn\b|[-/]lot-[a-z0-9]|[-/]acres?\b|\d-acres", re.I)
BUILDING_RE = re.compile(r"building|suite|warehouse|\bunit\b|office space|sq\.?\s?ft|\bsf\b", re.I)


def _src(url: str) -> str:
    host = re.sub(r"^https?://(www\.)?", "", url or "").split("/")[0].lower()
    for k, label in SOURCES.items():
        if k in host:
            return label
    return host.rsplit(".", 1)[0] if host else "web"


def _tier_from(text: str) -> str | None:
    t = text.lower()
    if re.search(r"\bflex\b", t):
        return "listing: flex"
    if re.search(r"industrial|warehouse|\bshop\b|manufactur|distribution", t):
        return "listing: industrial"
    if re.search(r"office|medical", t):
        return "listing: office"
    if re.search(r"retail|storefront|restaurant|\bqsr\b", t):
        return "listing: retail"
    return None


def _money(text: str) -> dict:
    """sq ft / $-per-sf / $-per-month out of a snippet window."""
    out: dict = {}
    m = SF_RE.search(text)
    if m:
        lo = int(m.group(1).replace(",", ""))
        hi = int(m.group(2).replace(",", "")) if m.group(2) else None
        if 100 <= lo <= 500_000:
            out["sq_ft_min"], out["sq_ft_max"] = lo, hi
    m = RATE_RE.search(text)
    if m:
        out["rate"] = float(m.group(1))
        out["rate_unit"] = "yr" if m.group(2).lower().startswith("y") else "mo"
    m = MONTHLY_RE.search(text)
    if m:
        v = int(m.group(1).replace(",", ""))
        if 100 <= v <= 100_000:
            out["monthly"] = v
    return out


def _cost_band(tier: str, money: dict) -> tuple[str, str]:
    sf, rate, unit = money.get("sq_ft_min"), money.get("rate"), money.get("rate_unit")
    if money.get("monthly") and sf and money["monthly"] / sf < 0.20:
        money.pop("monthly")          # "$550/mo" beside "6,798 SF" is two different units
    if money.get("monthly"):
        return f"${money['monthly']:,}/mo", "listing snippet"
    if rate and sf:
        mo = sf * rate / (12 if unit == "yr" else 1)
        return f"~${mo:,.0f}/mo ({sf:,} SF @ ${rate:.2f}/SF/{unit})", "listing snippet"
    if rate:
        return f"${rate:.2f}/SF/{unit} (size unknown)", "listing snippet"
    return COST_BAND[tier], "tier default"


def _addr_re(town: str, st: str):
    # "1700 Schuster Rd, Delano, CA 93215" / "701 Bailey Ave, Tehachapi CA - Warehouse"
    # optional ", Unit A400" / ", Suite 5" inside the street part
    return re.compile(r"(\d{1,6}(?:\s*-\s*\d{1,6})?\s+[A-Za-z0-9][A-Za-z0-9 .'#&-]{1,50}?"
                      r"(?:,?\s*(?:unit|suite|ste\.?|bldg\.?|#)\s*[A-Za-z0-9-]{1,8})?)"
                      r",?\s+(" + re.escape(town) + r"),?\s+" + re.escape(st) + r"\b(?:\s+(\d{5}))?",
                      re.I)


def rate_listing(tier: str, money: dict) -> tuple[str, str, str]:
    big = (money.get("sq_ft_min") or 0) > 5000
    ask_size = (f" It is listed at {money['sq_ft_min']:,}+ SF, far more than a satellite needs: ask "
                "whether it is divisible or if the landlord has a smaller suite." if big else "")
    if tier in ("listing: flex", "listing: industrial"):
        return ("high", "A flex/industrial suite you lease has its own door, exterior signage and "
                "room for equipment, which is exactly what video verification checks.",
                "Call the listing broker: smallest divisible suite (500-1,500 SF), business-use lease "
                "with exterior signage, shortest term they allow." + ask_size)
    if tier == "listing: office":
        return ("high", "A leased office with its own entrance and signage passes when filmed with "
                "the sign, equipment and keys.",
                "Call the listing broker: smallest private suite with door/building signage; "
                "avoid shared-reception setups." + ask_size)
    if tier == "listing: space":
        return ("medium", "Listing does not say what kind of space it is; rates HIGH if it is a "
                "suite with its own door and signage.",
                "Ask the broker what the unit is (office, flex, retail) and whether exterior "
                "signage and contractor use are allowed." + ask_size)
    return ("medium", "A storefront with its own signage can pass, but retail rents are high and "
            "the landlord may resist a service business.",
            "Ask whether a service/contractor use is allowed and the smallest space available."
            + ask_size)


def listing_options(dfs: DFS, town: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """-> (options, browse links, excluded) for one town from LoopNet/Crexi SERPs."""
    name, st = town["town"], (town.get("state") or "").upper()
    towns_ok = {t.lower() for t in (town.get("would_cover") or [])} | {name.lower()}
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    options: dict[str, dict] = {}
    browse: dict[str, dict] = {}
    excluded: list[dict] = []
    # The seat's covered towns also count as "in town" for address matching.
    rx = [_addr_re(t, st) for t in sorted(towns_ok, key=len, reverse=True)]
    canon = {t.lower(): t for t in (town.get("would_cover") or [])} | {name.lower(): name}
    hits: dict[str, list] = {}
    dead: set = set()

    def add(addr: str, city: str, zip5: str | None, text: str, url: str, title: str, src: str,
            page_title: str = ""):
        # The lazy street match can start early ("1 unit. 2234 Girard St",
        # "93561 1170 E Tehachapi Blvd"): keep the last sentence, drop a zip.
        addr = re.split(r"\.\s+|\s+[•·;|]\s+", re.sub(r"\s+", " ", addr))[-1]
        addr = re.sub(r"^\d{5}\s+(?=\d)", "", addr)
        addr = re.sub(r"^[\d,]*\d\s*(?:sq\.?\s?ft|sqft|sf)\b\.?\s*", "", addr, flags=re.I).strip(" ,-·.")
        if not re.match(r"\d", addr) or not STREET_RE.search(addr):
            return
        city = canon.get(city.lower(), city)
        # "31992 Highway 46" on LoopNet is "31992 Hwy 46" on Crexi: one key.
        norm = re.sub(r"\bhighway\b", "hwy", addr.lower())
        norm = re.sub(r"\b(street|avenue|road|drive|boulevard|parkway|pky)\b",
                      lambda m: {"street": "st", "avenue": "ave", "road": "rd", "drive": "dr",
                                 "boulevard": "blvd", "parkway": "pkwy", "pky": "pkwy"}[m.group(1)], norm)
        key = re.sub(r"[^a-z0-9]", "", norm) + city.lower()
        name_ = f"{addr}, {city}"
        own = f"{title} {text}"            # this listing's own words
        if STALE_RE.search(own):
            drop(key, name_, addr, f"{src}: listing no longer advertised")
            return
        if title and SALE_RE.search(title) and not LEASE_RE.search(title):
            return                                       # for sale, not for lease
        if not title and SALE_RE.search(text) and not LEASE_RE.search(text):
            return
        has_rate = bool(RATE_RE.search(text) or MONTHLY_RE.search(text))
        if SALE_PRICE_RE.search(text) and not has_rate:
            return                                       # "$595,000" is a sale price
        # Embedded in a for-sale results page ("Commercial Property For Sale",
        # crexi.com/properties?..., ...-for-sale): a NNN investment, not a unit.
        if not title and not has_rate and (
                (SALE_RE.search(page_title) and not LEASE_RE.search(page_title))
                or "for-sale" in url.lower()
                or re.search(r"crexi\.com/properties(?:\?|/\d)", url)):
            return
        if src == "crexi" and re.search(r"crexi\.com/properties/\d", url) and not LEASE_RE.search(title):
            return                                       # Crexi sale listing
        # Land: judged on the listing's own words plus a /...-Land results page,
        # and only a building word in the listing's own words rescues it.
        if (LAND_STRONG.search(own) or (title and LAND_STRONG.search(url))) and not BUILDING_RE.search(own):
            drop(key, name_, addr, f"{src}: land / parcel, no building")
            return
        landish = LAND_RE.search(own) or (not title and re.search(r"[-/]land\b", url, re.I))
        if landish and not re.search(r"office|industrial|flex|warehouse|retail|building|suite",
                                     own, re.I):
            drop(key, name_, addr, f"{src}: land / ground lease, no building")
            return
        tier = _tier_from(title) or _tier_from(text) or _tier_from(url)
        if not tier:
            # A LoopNet/Crexi listing page that never names the type ("Amazing
            # 1226 square foot unit on Mill St") is still a unit for lease.
            if not (title and src in CRE_SITES):
                return
            tier = "listing: space"
        hits.setdefault(key, []).append({"addr": addr, "city": city, "zip": zip5, "tier": tier,
                                         "money": _money(text), "url": url, "src": src,
                                         "from_title": bool(title)})

    def drop(key: str, name_: str, addr: str, reason: str):
        dead.add(key)
        if not any(e["name"] == name_ and e["reason"] == reason for e in excluded):
            excluded.append({"name": name_, "address": addr, "reason": reason})

    def finalize():
        """One option per address: the listing's own page wins for URL/tier,
        size and price are pooled from every page that mentioned it."""
        for key, hs in hits.items():
            if key in dead:
                continue
            hs.sort(key=lambda h: (not h["from_title"], h["src"] not in CRE_SITES))
            best = hs[0]
            money: dict = {}
            for h in hs:
                for k, v in h["money"].items():
                    money.setdefault(k, v)
            name_ = f"{best['addr']}, {best['city']}"
            if (money.get("sq_ft_min") or 0) > MAX_LISTING_SF:
                excluded.append({"name": name_, "address": best["addr"],
                                 "reason": f"{best['src']}: {money['sq_ft_min']:,} SF, far too large "
                                           f"for a satellite"})
                continue
            tier = best["tier"]
            v, reason, note = rate_listing(tier, money)
            band, band_src = _cost_band(tier, money)
            zip5 = next((h["zip"] for h in hs if h["zip"]), None)
            full = f"{best['addr']}, {best['city']}, {st}" + (f" {zip5}" if zip5 else "")
            options[key] = {
                "name": full, "tier": tier, "category": f"{best['src']} listing",
                "source": best["src"], "address": full, "city": best["city"], "phone": None,
                "website": best["url"],
                # False = the address was only MENTIONED on that page (a search
                # page or a "nearby listings" strip), not that listing's own page.
                "listing_page": best["from_title"], "rating": None, "reviews": None, "lat": None, "lng": None,
                "cid": None, "place_id": None, "distance_from_town_mi": None,
                "distance_from_pin_mi": None,
                "sq_ft_min": money.get("sq_ft_min"), "sq_ft_max": money.get("sq_ft_max"),
                "rate": money.get("rate"), "rate_unit": money.get("rate_unit"),
                "verification_likelihood": v, "verification_reason": reason,
                "cost_band": band, "cost_source": band_src, "notes": note,
                "found_by": f"organic SERP ({best['src']} via Google, not scraped)",
            }

    for src_hint, tmpl in LISTING_QUERIES:
        q = tmpl.format(town=name, st=st)
        for r in dfs.organic(q):
            url, title, snip = r["url"], r["title"], r["snippet"]
            src = _src(url)
            low = url.lower()
            if NOT_LISTINGS.search(low):
                continue                          # social posts / reviews, not listings
            if src == "loopnet" and "/property/" in low:
                continue                          # assessor parcel record, not a listing
            if src == "loopnet" and "/commercial-real-estate-brokers/" in low:
                continue
            if low.endswith(".pdf") or "images1.showcase.com" in low:
                continue                          # marketing brochures: often stale
            is_search = (src == "loopnet" and "/search/" in low) or \
                (src == "crexi" and ("/search" in low or re.search(r"/properties/[a-z]{2}/", low))) or \
                (src == "cityfeet" and "/cont/" in low and "/cont/listing/" not in low) or \
                (src == "commercialcafe" and "/commercial-real-estate/" in low) or \
                (src == "officespace" and not re.search(r"/\d+[-/]", low))
            # 1) The page itself is one listing: address in the title.
            hit = None
            if not is_search:
                for x in rx:
                    hit = x.search(title)
                    if hit:
                        add(hit.group(1), hit.group(2), hit.group(3), f"{title}. {snip}", url, title, src)
                        break
            # 2) Listings embedded in the snippet of a search/aggregator page
            #    ("... 701 Bailey Ave, Tehachapi CA - Warehouse. 7,394 SF; $24.24 SF/YR").
            if is_search or not hit:
                ms = sorted((m for x in rx for m in x.finditer(snip)), key=lambda m: m.start())
                for i, m in enumerate(ms):
                    # a little lead-in ("Flex Space With Fenced Yard. 827 High St...")
                    # plus the text up to the next listing (separator or next
                    # address), so one listing never borrows another's price
                    prev_end = ms[i - 1].end() if i else 0
                    pre = snip[max(prev_end, m.start() - 60): m.start()].split(" · ")[-1]
                    stop = min(ms[i + 1].start() if i + 1 < len(ms) else len(snip), m.start() + 180)
                    seg = pre + snip[m.start(): stop].split(" · ")[0]
                    add(m.group(1), m.group(2), m.group(3), seg, url, "", src, page_title=title)
            # 3) Town-level search pages on LoopNet/Crexi are worth a link.
            if is_search and src in CRE_SITES and slug in low and "sale" not in low \
                    and not re.search(r"[-/]land\b", low):
                cnt = re.match(r"\s*(\d{1,3})\s", title) or re.search(r"there (?:is|are) (\d+)", snip, re.I)
                browse.setdefault(url, {"source": src, "title": title[:90], "url": url,
                                        "count": int(cnt.group(1)) if cnt else None})

    finalize()

    def lscore(o):
        s = V_WEIGHT[o["verification_likelihood"]] * 10 + 1.5 + 1.0   # in town, real listing
        if o["cost_source"] == "listing snippet":
            s += 0.5
        if (o.get("sq_ft_min") or 0) > 5000:
            s -= 3.0                                                  # oversized for a satellite
        if o["source"] in CRE_SITES:
            s += 0.3
        return round(s, 2)
    for o in options.values():
        o["score"] = lscore(o)
    ranked = sorted(options.values(), key=lambda o: o["score"], reverse=True)
    links = [b for b in browse.values() if b["count"] != 0][:3]
    return ranked, links, excluded


# ------------------------------------------------------------- Craigslist / coworking / storage
# Same rule as LoopNet/Crexi: Google's index only (DataForSEO organic SERP),
# never a direct fetch. These sources are not "one address = one listing"
# pages, so they get their own handler:
#   craigslist   individual posts (/view/d/{town}-... or {area}.craigslist.org
#                /off/d/...). Office & commercial prices are monthly rent. The
#                post may not give a street address; it is kept (the post link
#                is the lead) when it is clearly in this town.
#   liquidspace/coworker  a PRIVATE OFFICE at a named centre (tier coworking).
#                Hourly day-offices, meeting rooms, desks and virtual plans are
#                not the product and are skipped.
#   sparefoot    a storage facility page (tier storage).
CL_POST = re.compile(r"craigslist\.org/(?:view/d/|[a-z]{3}/d/|.*/d/)", re.I)
CL_HOUSING = re.compile(r"bedroom|\bbd\b|\bbath\b|apartment|\bapt\b|studio|roommate|\broom for rent\b|"
                        r"house for rent|home for rent|mobile home|\bduplex\b|\bcondo\b|furnished|"
                        r"\bhousing\b|parking space|\brv\b", re.I)
CL_COMMERCIAL = re.compile(r"office|commercial|warehouse|\bshop\b|industrial|retail|suite|business|flex|"
                           r"medical|storefront", re.I)
CL_PRICE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d{3,5})(?!\s*(?:/|per)\s*(?:hr|hour|day|sf|sq))", re.I)
COWORK_SKIP = re.compile(r"meeting room|conference|event space|virtual|mailbox|hourly|day office|"
                         r"day-office|hot desk|coworking desk|dedicated desk|\bdesk\b|podcast|studio", re.I)
HOURLY_RE = re.compile(r"\$\s?\d+(?:\.\d{2})?\+?\s*/\s*(?:hr|hour)|per hour|/hour", re.I)


def extra_options(dfs: DFS, town: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """-> (options, browse links, excluded) from Craigslist, LiquidSpace/Coworker, SpareFoot."""
    name, st = town["town"], (town.get("state") or "").upper()
    towns_ok = {t.lower() for t in (town.get("would_cover") or [])} | {name.lower()}
    canon = {t.lower(): t for t in (town.get("would_cover") or [])} | {name.lower(): name}
    rx = [_addr_re(t, st) for t in sorted(towns_ok, key=len, reverse=True)]
    slugs = {re.sub(r"[^a-z0-9]+", "-", t).strip("-") for t in towns_ok}
    opts: dict[str, dict] = {}
    browse: dict[str, dict] = {}
    excluded: list[dict] = []

    def find_addr(text: str):
        for x in rx:
            m = x.search(text)
            if m:
                addr = re.split(r"\.\s+|\s+[•·;|]\s+", re.sub(r"\s+", " ", m.group(1)))[-1]
                addr = re.sub(r"^[\d,]*\d\s*(?:sq\.?\s?ft|sqft|sf|ft\s?2)\b\.?\s*", "", addr, flags=re.I)
                addr = re.sub(r"^\d{5}\s+(?=\d)", "", addr).strip(" ,-·.")
                if re.match(r"\d", addr) and STREET_RE.search(addr):
                    city = canon.get(m.group(2).lower(), m.group(2))
                    return f"{addr}, {city}, {st}" + (f" {m.group(3)}" if m.group(3) else ""), city
        return None, None

    def base(nm, tier, src, url, addr, city, v, reason, note, band, band_src, money, price_text):
        return {"name": nm, "tier": tier, "category": f"{src} listing", "source": src,
                "address": addr, "city": city, "phone": None, "website": url, "listing_page": True,
                "rating": None, "reviews": None, "lat": None, "lng": None, "cid": None,
                "place_id": None, "distance_from_town_mi": None, "distance_from_pin_mi": None,
                "sq_ft_min": money.get("sq_ft_min"), "sq_ft_max": money.get("sq_ft_max"),
                "rate": money.get("rate"), "rate_unit": money.get("rate_unit"),
                "verification_likelihood": v, "verification_reason": reason,
                "cost_band": band, "cost_source": band_src, "price_text": price_text, "notes": note,
                "found_by": f"organic SERP ({src} via Google, not scraped)"}

    for kind, tmpl in EXTRA_QUERIES:
        for r in dfs.organic(tmpl.format(town=name, st=st)):
            url, title, snip = r["url"], r["title"], r["snippet"]
            low, src, text = url.lower(), _src(url), f"{title}. {snip}"
            if kind == "craigslist":
                if src != "craigslist":
                    continue
                if "/search/" in low:
                    # Town-level "office & commercial" search page: a browse link.
                    if "cat=off" in low and any(f"/{sl}-" in low for sl in slugs) and "query=" not in low:
                        browse.setdefault(url, {"source": "craigslist", "title": title[:90], "url": url,
                                                "count": None})
                    continue
                if not CL_POST.search(url):
                    continue
                path = low.split("/d/", 1)[-1]
                addr, city = find_addr(snip)
                in_town = bool(addr) or any(path.startswith(f"{sl}-") for sl in slugs) or \
                    any(f"({t})" in text.lower() for t in towns_ok)
                if not in_town:
                    continue
                if CL_HOUSING.search(title) or not CL_COMMERCIAL.search(title):
                    continue
                if SALE_RE.search(title) and not LEASE_RE.search(title):
                    continue
                if NEVER_PASS.search(text):
                    excluded.append({"name": title[:80], "address": addr, "reason":
                                     "craigslist: mailbox/virtual office (never passes)"})
                    continue
                money = _money(text)
                pm = CL_PRICE.search(snip) or CL_PRICE.search(title)
                if pm and "monthly" not in money:
                    v_ = int(pm.group(1).replace(",", ""))
                    if 100 <= v_ <= 20000:
                        money["monthly"] = v_
                if (money.get("sq_ft_min") or 0) > MAX_LISTING_SF:
                    excluded.append({"name": title[:80], "address": addr,
                                     "reason": f"craigslist: {money['sq_ft_min']:,} SF, far too large"})
                    continue
                tier = _tier_from(title) or _tier_from(snip) or "listing: space"
                v, reason, note = rate_listing(tier, money)
                note += " Craigslist post: confirm it is still available and that the poster is " \
                        "the landlord or listing broker before sharing details."
                band, band_src = _cost_band(tier, dict(money))
                city = city or name
                key = re.sub(r"[^a-z0-9]", "", (addr or url).lower())
                opts.setdefault(key, base(
                    title.strip()[:120], tier, "craigslist", url,
                    addr or f"{city}, {st} (street address on the post)", city, v, reason, note, band,
                    "craigslist post" if band_src == "listing snippet" else band_src, money,
                    f"${money['monthly']:,}/mo" if money.get("monthly") else None))
            elif kind == "coworking":
                if src not in ("liquidspace", "coworker", "wework"):
                    continue
                path = re.sub(r"^https?://[^/]+", "", low)
                depth = len([x for x in path.split("?")[0].split("/") if x])
                if depth <= 3 or "/s/" in path or "search" in path:
                    # /us/ca/{town} (LiquidSpace) or /united-states/ca/{town} index page
                    if any(f"/{sl}" in path for sl in slugs) and "?" not in path:
                        browse.setdefault(url, {"source": src, "title": title[:90], "url": url,
                                                "count": None})
                    continue
                if COWORK_SKIP.search(title) or COWORK_SKIP.search(path):
                    continue
                addr, city = find_addr(snip)
                if not addr:
                    continue                           # no in-town address: some other city's centre
                if NEVER_PASS.search(text):
                    continue
                money = {}
                mm = MONTHLY_RE.search(snip)
                if mm:
                    money["monthly"] = int(mm.group(1).replace(",", ""))
                iwg = bool(IWG.search(text))
                v = "medium"
                reason = ("IWG/WeWork private offices sometimes pass (Power Dry KC precedent); "
                          "the virtual-office, All Access and hot-desk products fail." if iwg else
                          "A lockable private office in an executive/coworking centre passes "
                          "sometimes with door or lobby signage; desks and mail plans fail.")
                note = ("Ask for a PRIVATE OFFICE on a monthly term (not hourly, not a virtual "
                        "office or membership); confirm your name on the door and lobby "
                        "directory, and staffed-hours access.")
                band = f"${money['monthly']:,}/mo" if money.get("monthly") else COST_BAND["coworking"]
                key = re.sub(r"[^a-z0-9]", "", addr.lower()) + re.sub(r"[^a-z0-9]", "", title.lower())[:20]
                opts.setdefault(key, base(
                    title.split("|")[0].strip()[:120], "coworking", src, url, addr, city, v, reason,
                    note, band, "listing snippet" if money else "tier default", money,
                    band if money else None))
            else:  # storage
                if src != "sparefoot":
                    continue
                path = re.sub(r"^https?://[^/]+", "", low)
                url_town = re.match(r"/([a-z0-9-]+)-[a-z]{2}-self-storage/", path)
                addr, city = find_addr(snip)
                if not addr and not (url_town and url_town.group(1) in slugs):
                    continue
                # Facility pages end in "-{id}.html"; "5x10-storage-units.html"
                # and "rv-storage.html" are size/feature category pages.
                if not re.search(r"-\d{4,}\.html$", path):
                    continue
                if STORAGE_BAD.search(title):
                    continue
                pm = re.search(r"\$\s?(\d{2,4})(?:\s?\.\d{2})?\s*(?:/\s*mo|per month)", snip, re.I)
                money = {"monthly": int(pm.group(1))} if pm else {}
                fake = {"title": title}
                v, reason, note = rate("storage", fake)
                band = f"from ${money['monthly']:,}/mo" if money else COST_BAND["storage"]
                city = city or canon.get((url_town.group(1).replace("-", " ") if url_town else ""), name)
                nm = re.sub(r"\s*[|-]\s*SpareFoot.*$", "", title).strip()[:120]
                key = "sf" + re.sub(r"[^a-z0-9]", "", nm.lower())
                opts.setdefault(key, base(
                    nm, "storage", "sparefoot", url, addr or f"{city}, {st} (see listing)", city, v,
                    reason, note, band, "listing snippet" if money else "tier default", money,
                    band if money else None))

    def xscore(o):
        s = V_WEIGHT[o["verification_likelihood"]] * 10 + 1.5          # in town by construction
        if o["cost_source"] != "tier default":
            s += 0.5
        if (o.get("sq_ft_min") or 0) > 5000:
            s -= 3.0
        if o["source"] == "craigslist" and not re.match(r"\d", o["address"] or ""):
            s -= 1.0                                                   # no street address yet
        return round(s + cost_rank(o["tier"]), 2)
    for o in opts.values():
        o["score"] = xscore(o)
    return sorted(opts.values(), key=lambda o: o["score"], reverse=True), list(browse.values())[:3], excluded


# ------------------------------------------------------------- core
def scout_town(dfs: DFS, town: dict, pin, reach: float) -> dict:
    lat, lng = town["lat"], town["lng"]
    radius = max(MAX_FROM_CENTER_MI, reach or 0)
    seen: dict[str, dict] = {}
    excluded: list[dict] = []
    for _hint, q in QUERIES:
        for it in dfs.maps(f"{q} {town['town']} {town['state']}", lat, lng):
            if it.get("type") != "maps_search":
                continue
            key = it.get("cid") or it.get("place_id") or \
                f"{(it.get('title') or '').lower()}|{(it.get('address') or '').lower()}"
            if key in seen or any(e["key"] == key for e in excluded):
                continue
            tier, why = classify(it)
            if why:
                excluded.append({"key": key, "name": it.get("title"), "address": it.get("address"),
                                 "reason": why})
                continue
            if not tier:
                continue
            ilat, ilng = _f(it.get("latitude")), _f(it.get("longitude"))
            if ilat is None or ilng is None:
                continue
            d_center = ls.haversine_mi(lat, lng, ilat, ilng)
            if d_center > radius:
                continue
            d_pin = ls.haversine_mi(pin[0], pin[1], ilat, ilng) if pin[0] is not None else None
            if d_pin is not None and reach and d_pin < reach:
                excluded.append({"key": key, "name": it.get("title"), "address": it.get("address"),
                                 "reason": f"inside the existing pin's {reach}mi reach "
                                           f"({d_pin:.1f}mi) — would cannibalise it"})
                continue
            v, reason, note = rate(tier, it)
            rating = it.get("rating") or {}
            ai = it.get("address_info") or {}
            seen[key] = {
                "name": it.get("title"), "tier": tier, "category": it.get("category"),
                "address": it.get("address"), "city": ai.get("city"),
                "phone": it.get("phone"), "website": it.get("url") or it.get("domain"),
                "rating": rating.get("value"), "reviews": rating.get("votes_count"),
                "lat": ilat, "lng": ilng, "cid": it.get("cid"), "place_id": it.get("place_id"),
                "distance_from_town_mi": round(d_center, 1),
                "distance_from_pin_mi": round(d_pin, 1) if d_pin is not None else None,
                "verification_likelihood": v, "verification_reason": reason,
                "cost_band": COST_BAND.get(tier), "cost_source": "tier default",
                "notes": note, "found_by": q, "source": "google maps",
            }

    def score(o):
        in_town = 1.5 if (o.get("city") or "").lower() == town["town"].lower() else 0.0
        social = min(math.log10((o.get("reviews") or 0) + 1), 2.5) * 0.4
        return (V_WEIGHT[o["verification_likelihood"]] * 10 - o["distance_from_town_mi"] * 0.8
                + in_town + social + cost_rank(o["tier"]))

    for o in seen.values():
        o["score"] = round(score(o), 2)
    # LoopNet/Crexi listings (scored in listing_options: a HIGH-rated real
    # suite in town lands at ~32, above any storage unit at ~20-23).
    listings, browse, l_excluded = listing_options(dfs, town)
    # Craigslist posts, LiquidSpace/Coworker private offices, SpareFoot.
    extras, x_browse, x_excluded = extra_options(dfs, town)
    browse = browse + [b for b in x_browse if b["url"] not in {x["url"] for x in browse}]
    ranked = sorted(list(seen.values()) + listings + extras, key=lambda o: o["score"], reverse=True)
    picks, per_tier, n_list, addr_seen = [], {}, 0, set()
    for o in ranked:
        if per_tier.get(o["tier"], 0) >= PER_TIER_CAP:
            continue
        # The same building found twice (Regus on Maps AND on LiquidSpace,
        # one suite on LoopNet AND CityFeet): keep the higher-scored one.
        ak = addr_key(o.get("address"))
        if ak and ak in addr_seen:
            continue
        is_listing = o["tier"] in LISTING_TIERS
        if is_listing and n_list >= MAX_LISTINGS:
            continue
        per_tier[o["tier"]] = per_tier.get(o["tier"], 0) + 1
        n_list += is_listing
        if ak:
            addr_seen.add(ak)
        picks.append(o)
        if len(picks) >= PER_TOWN:
            break

    # One cheap GET per Maps pick for a posted monthly price. Never scrapes
    # deeper, and never touches a listing site (LoopNet, Crexi, Craigslist,
    # CityFeet, LiquidSpace, SpareFoot...): the SERP snippet is all we use.
    maps_picks = [o for o in picks if o.get("source") == "google maps"]
    with ThreadPoolExecutor(max_workers=5) as ex:
        prices = list(ex.map(lambda o: price_peek(o.get("website") or ""), maps_picks))
    for o, p in zip(maps_picks, prices):
        if p:
            o["cost_band"] = f"from ${p:,}/mo"
            o["cost_source"] = "website"
    return {**town, "options": picks, "candidates_seen": len(seen),
            "listings_seen": len(listings) + len(extras), "listing_searches": browse,
            "excluded": [{k: v for k, v in e.items() if k != "key"}
                         for e in excluded + l_excluded + x_excluded]}


def addr_key(addr: str | None) -> str | None:
    """'4900 California Avenue, Tower B' -> '4900california'. None without a number."""
    m = re.match(r"\s*(\d{1,6})\s+(?:[NSEW]\.?\s+)?([A-Za-z0-9]+)", addr or "")
    return f"{m.group(1)}{m.group(2).lower()}" if m else None


def render(out: dict) -> None:
    print(f"\nOFFICE SCOUT — {out.get('slug') or '(no client)'}"
          + (f"  [{out['company_id']}]" if out.get("company_id") else ""))
    if out.get("reach_mi"):
        print(f"  existing pin reach in use: {out['reach_mi']}mi (options inside it are dropped)")
    for t in out["towns"]:
        dp = f", {t['distance_from_pin_mi']}mi from the pin" if t.get("distance_from_pin_mi") else ""
        print(f"\n  {t['town'].upper()}, {t['state']}{dp}  —  source: {t['source']}")
        if len(t.get("would_cover") or []) > 1:
            print(f"    would cover: {', '.join(t['would_cover'])}")
        if not t["options"]:
            print(f"    no rentable space found on Google Maps ({t['candidates_seen']} candidates) "
                  f"or listing sites ({t.get('listings_seen', 0)}); try a commercial broker or the "
                  f"nearest bigger town")
        for i, o in enumerate(t["options"], 1):
            print(f"    {i}. {o['name']}  [{o['tier']}]  verify: {o['verification_likelihood'].upper()}"
                  f"  cost: {o['cost_band']}  ({o.get('source') or 'google maps'})")
            if o.get("source") != "google maps":
                sf = (f"{o['sq_ft_min']:,}" + (f"-{o['sq_ft_max']:,}" if o.get("sq_ft_max") else "")
                      + " SF") if o.get("sq_ft_min") else "size n/a"
                print(f"       {o.get('address') or ''}  |  {sf}  |  cost from {o['cost_source']}")
            else:
                rv = f"{o['rating']}* ({o['reviews']})" if o.get("rating") else "no reviews"
                print(f"       {o['address']}  |  {o.get('phone') or 'no phone'}  |  {rv}  |  "
                      f"{o['distance_from_town_mi']}mi from center"
                      + (f", {o['distance_from_pin_mi']}mi from pin" if o.get("distance_from_pin_mi") else ""))
            c = o.get("contact")
            if c is not None:
                bits = [x for x in (c.get("contact_name"), c.get("contact_role"), c.get("company"),
                                    (f"{c['phone_display']} [{c.get('phone_type') or '?'}]"
                                     if c.get("phone") else None), c.get("email")) if x]
                print(f"       contact: {' | '.join(bits) if bits and (c.get('phone') or c.get('email') or c.get('contact_name')) else 'none found'}"
                      + (f"  (via {c['contact_source']})" if c.get("contact_source") else ""))
            print(f"       why: {o['verification_reason']}")
            print(f"       ask: {o['notes']}")
            if o.get("website"):
                lbl = "seen on" if o.get("listing_page") is False else "web"
                print(f"       {lbl}: {o['website'][:100]}")
        for b in t.get("listing_searches") or []:
            n = f"{b['count']} listed" if b.get("count") is not None else "browse"
            print(f"    browse ({b['source']}, {n}): {b['url'][:110]}")
        if t["excluded"]:
            print("    filtered: " + "; ".join(f"{e['name']} ({e['reason'].split(' (')[0]})"
                                              for e in t["excluded"][:6]))
    print(f"\n  DataForSEO: {out['dfs_calls']} queries, ${out['spend_usd']:.3f} spent "
          f"(cap ${out['cap_usd']:.2f})"
          + (f"; {out['dfs_skipped']} queries SKIPPED at the cap" if out.get("dfs_skipped") else ""))
    cs = out.get("contacts")
    if cs:
        print(f"  Contacts: {cs['with_phone']}/{cs['options']} phone, {cs['with_email']}/{cs['options']} email, "
              f"{cs['with_name']}/{cs['options']} named person; SERP {cs['serp_calls']} queries "
              f"${cs['serp_usd']:.3f}, Twilio {cs['twilio_lookups']} lookups ${cs['twilio_usd']:.3f} "
              f"({cs['twilio_reused']} reused), {cs['fetches']} page GETs")
    sp = out.get("spend_breakdown") or {}
    if sp:
        print(f"  SPEND: Maps ${sp['maps']:.3f} + SERP ${sp['serp']:.3f} + contacts SERP "
              f"${sp['contacts_serp']:.3f} + OnPage ${sp['onpage']:.3f} + Twilio ${sp['twilio']:.3f} "
              f"= ${sp['total']:.3f}")


# ------------------------------------------------------------- contacts
# WHO TO CALL about each option (--contacts, default on with --apply). Every
# lookup is fail-open per option and nothing is ever invented: a field we did
# not see on a real page or SERP snippet stays null.
#
#   google maps options  phone from the Maps result; email from the business's
#                        own website (homepage, /contact, /contact-us, /about;
#                        10s timeout each, stops at the first usable email).
#   CRE listings         LoopNet / Crexi / CityFeet / Showcase / CommercialCafe
#                        403 every fetcher we tried, DataForSEO's OnPage crawler
#                        included (tested 2026-09-28: content_parsing "empty",
#                        instant_pages 403 even with browser rendering). So:
#                        one plain SERP for '"{street}" {city} {st} for lease'
#                        reads the broker out of Google's snippets ("Contact
#                        Colliers for more information", CityFeet's "Oscar
#                        Baltazar; Marco Petrini. 701 Bailey Ave") and finds the
#                        brokerage's OWN property page (daumcommercial.com...),
#                        which is fetched directly (vCard, agent block, Cloudflare-
#                        protected emails decoded). If a broker is named but no
#                        phone/email turned up, one more SERP on the broker's
#                        name reads phone/email from snippets that name them.
#   sparefoot/liquidspace/coworker  the facility's own site via one SERP.
#   craigslist           contact sits behind Craigslist's relay: the post URL
#                        is recorded as contact_url, nothing is fetched.
#   phone line type      Twilio Lookup v2 line_type_intelligence ($0.008 each,
#                        cached per number and reused from the previous run).
COST_TWILIO_LOOKUP = 0.008
US_STATES = {"CA": "California", "AZ": "Arizona", "NV": "Nevada", "OR": "Oregon", "WA": "Washington",
             "TX": "Texas", "FL": "Florida", "CO": "Colorado", "UT": "Utah", "ID": "Idaho",
             "NM": "New Mexico", "GA": "Georgia", "NC": "North Carolina", "NY": "New York"}
CONTACTS_CAP = 0.40          # SERP + Twilio spend cap for the contacts pass
FETCH_TIMEOUT = 10
CONTACT_PATHS = ("", "/contact", "/contact-us", "/about")
TWILIO_TYPES = {"mobile": "mobile", "landline": "landline", "fixedVoip": "voip",
                "nonFixedVoip": "voip", "tollFree": "voip", "voicemail": "voip",
                "personal": "mobile", "pager": "unknown", "sharedCost": "unknown",
                "uan": "unknown", "unknown": "unknown"}
# Never fetched: bot-protected listing portals, residential portals, social,
# people-search / data brokers, documents. Their SERP snippets are still read.
NO_FETCH = re.compile(
    r"loopnet\.|crexi\.|showcase\.com|cityfeet\.|commercialcafe\.|officespace\.com|commercialsearch\.|"
    r"realmo\.|propertyshark\.|craigslist\.|zillow\.|redfin\.|trulia\.|realtor\.com|homes\.com|movoto\.|"
    r"highrises\.|apartments\.com|yelp\.|facebook\.|instagram\.|linkedin\.|youtube\.|tiktok\.|x\.com|"
    r"twitter\.|nextdoor\.|rocketreach\.|zoominfo\.|signalhire\.|contactout\.|apollo\.io|experience\.com|"
    r"mapquest\.|bizapedia\.|opencorporates\.|manta\.com|bbb\.org|yellowpages\.|google\.|bing\.|"
    r"cloudinary\.|blob\.core\.|amazonaws\.|\.gov\b|wikipedia\.|sparefoot\.|liquidspace\.|coworker\.com|"
    r"warehousespaces\.|storageunits\.|storagearea\.|storagecafe\.|storageseeker\.|selfstorage\.com|storagefront\.|\.pdf(?:$|\?)", re.I)
PHONE_RE = re.compile(r"(?<![\d-])(?:\+?1[\s.-]?)?\(?([2-9]\d{2})\)?[\s.-]?([2-9]\d{2})[\s.-]?(\d{4})(?![\d-])")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+\s?@\s?[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,10}")
EMAIL_JUNK = re.compile(
    r"\.(?:png|jpe?g|gif|webp|svg|css|js|ico)$|noreply|no-reply|donotreply|example\.|@example|wix|sentry|"
    r"godaddy|domain\.com|email\.com|yourname|your-?email|@yoursite|test@|user@|name@|placeholder|"
    r"schema\.org|cloudflare|u00|@2x|@3x|ingest|jquery|bootstrap|@sentry|privacy@|abuse@|webmaster@|"
    r"support@(?:squarespace|shopify)|@mysite|@company\.com", re.I)
EMAIL_PREFER = ("leasing", "info", "office", "manager", "rentals", "rent", "contact", "hello",
                "admin", "storage", "sales", "frontdesk")
NAME_RE = re.compile(r"^[A-Z][a-z]+(?:\s[A-Z]\.?)?\s(?:(?:Mc|Mac|O')?[A-Z][a-zA-Z'’-]+)(?:\s(?:Jr|Sr|II|III)\.?)?$")
NAME_STOP = re.compile(
    r"\b(?:street|st|ave|avenue|road|rd|blvd|drive|suite|ste|real|estate|commercial|property|properties|"
    r"group|company|partners|realty|office|lease|sale|california|los|san|santa|new|north|south|east|west|"
    r"county|center|centre|storage|self|mini|home|homes|privacy|policy|terms|contact|about|services|"
    r"management|investments?|capital|markets|industrial|retail|view|listing|listings|search|more|"
    r"learn|read|click|call|email|phone|fax|main|menu|back|results|download|brochure|share|print|"
    r"inland|empire|valley|beach|hills|city|bakersfield|delano|wasco|tehachapi|lamont|mcfarland|"
    r"arvin|shafter|fresno|angeles|diego|francisco|orange|ventura|woodland|phoenix|headquarters|parcel|"
    r"id|request|info|square|world|rent|truck|official|website|saved|searches|opportunity|zone|tires?|"
    r"wheels|market|plaza|mall|shopping|professional|medical|dental|building|land|lot|acres?|free|"
    r"now|today|open|hours|map|directions|photos|details|price|reduced|new|sold|available|for|"
    r"vice|president|principal|senior|associate|leasing|central|sales|team|work|mobile|direct)\b", re.I)
BROKER_TITLE = re.compile(r"licen[cs]e|\bdre\b|\blic\b|vice president|\bsvp\b|\bevp\b|principal|associate|"
                          r"broker|agent|director|managing|senior|advisor|realtor", re.I)
CONTACT_CO_RE = re.compile(r"Contact ([A-Z][\w&.,'’ -]{2,60}?) for more\b")
LISTED_BY_RE = re.compile(r"(?:Listed by|Listing (?:courtesy of|provided by|agent|broker|office)|"
                          r"Presented by|Courtesy of)[:\s]+([A-Z][^.|•·\n<>]{2,80})")


def _e164(raw: str | None) -> str | None:
    m = PHONE_RE.search(raw or "")
    return f"+1{m.group(1)}{m.group(2)}{m.group(3)}" if m else None


def _display(e164: str | None) -> str | None:
    if not e164 or len(e164) != 12:
        return e164
    return f"({e164[2:5]}) {e164[5:8]}-{e164[8:]}"


def _host(url: str) -> str:
    return re.sub(r"^https?://", "", url or "").split("/")[0].split(":")[0].lower().removeprefix("www.")


def _root(host: str) -> str:
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


class Contacts:
    """Shared state for one contacts pass: page cache, Twilio cache, spend."""

    def __init__(self, dfs: DFS, prev_types: dict | None = None):
        self.dfs = dfs                          # a DFS with its own (contacts) cap
        self.pages: dict[str, str | None] = {}
        self.memo: dict[str, tuple[threading.Event, dict]] = {}
        self.inflight: dict[str, threading.Event] = {}
        self.types: dict[str, dict] = dict(prev_types or {})
        self.twilio_calls = 0
        self.twilio_reused = 0
        self.lock = threading.Lock()
        self.fetches = 0
        sid, tok = os.environ.get("TWILIO_MASTER_ACCOUNT_SID"), os.environ.get("TWILIO_MASTER_AUTH_TOKEN")
        self.twilio = (sid, tok) if sid and tok else None

    @property
    def twilio_cost(self) -> float:
        return round(self.twilio_calls * COST_TWILIO_LOOKUP, 4)

    # ---- fetch
    def get(self, url: str) -> str | None:
        """One polite GET (10s, first 1.5MB). Cached; None on any failure."""
        if not url or not url.startswith("http") or NO_FETCH.search(url):
            return None
        with self.lock:
            ev = self.inflight.get(url)
            mine = ev is None
            if mine:
                ev = self.inflight[url] = threading.Event()
        if not mine:                             # another thread is fetching it: wait
            ev.wait(FETCH_TIMEOUT + 5)
            return self.pages.get(url)
        html = None
        try:
            r = requests.get(url, timeout=FETCH_TIMEOUT, stream=True, headers={
                "User-Agent": UA, "Accept": "text/html,application/xhtml+xml,text/vcard;q=0.9,*/*;q=0.5",
                "Accept-Language": "en-US,en;q=0.8"})
            ct = r.headers.get("content-type", "")
            if r.status_code < 400 and ("html" in ct or "vcard" in ct or "text" in ct):
                html = r.raw.read(1_500_000, decode_content=True).decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            html = None
        with self.lock:
            self.fetches += 1
            self.pages[url] = html
        ev.set()
        return html

    # ---- Twilio
    def line_type(self, e164: str | None) -> str | None:
        if not e164:
            return None
        with self.lock:
            hit = self.types.get(e164)
        if hit:
            return hit.get("phone_type")
        if not self.twilio:
            return "unknown"
        with self.dfs.lock:
            if self.dfs.cost + self.dfs.reserve + COST_TWILIO_LOOKUP > self.dfs.cap + 1e-9:
                return "unknown"
            self.dfs.reserve += COST_TWILIO_LOOKUP
        t = "unknown"
        carrier = None
        try:
            r = requests.get(f"https://lookups.twilio.com/v2/PhoneNumbers/{e164}",
                             params={"Fields": "line_type_intelligence"}, auth=self.twilio, timeout=15)
            if r.status_code == 200:
                lti = r.json().get("line_type_intelligence") or {}
                t = TWILIO_TYPES.get(lti.get("type") or "unknown", "unknown")
                carrier = lti.get("carrier_name")
                with self.lock:
                    self.twilio_calls += 1
        except Exception:  # noqa: BLE001
            pass
        with self.dfs.lock:
            self.dfs.reserve -= COST_TWILIO_LOOKUP
        with self.lock:
            self.types[e164] = {"phone_type": t, "carrier": carrier}
        return t


def _cf_decode(hexstr: str) -> str:
    try:
        key = int(hexstr[:2], 16)
        return "".join(chr(int(hexstr[i:i + 2], 16) ^ key) for i in range(2, len(hexstr), 2))
    except ValueError:
        return ""


def _page_text(html: str) -> str:
    """HTML -> ' | '-separated text, Cloudflare-protected emails decoded."""
    html = re.sub(r'<a[^>]*data-cfemail="([0-9a-fA-F]+)"[^>]*>.*?</a>',
                  lambda m: " " + _cf_decode(m.group(1)) + " ", html, flags=re.S)
    html = re.sub(r'<span[^>]*data-cfemail="([0-9a-fA-F]+)"[^>]*>.*?</span>',
                  lambda m: " " + _cf_decode(m.group(1)) + " ", html, flags=re.S)
    html = re.sub(r"/cdn-cgi/l/email-protection#([0-9a-fA-F]+)", lambda m: "mailto:" + _cf_decode(m.group(1)), html)
    t = re.sub(r"<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>|<!--.*?-->", " ", html,
               flags=re.S | re.I)
    t = re.sub(r"<(?:br|/p|/div|/li|/h\d|/td|/tr|/span|/a)[^>]*>", " | ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = (t.replace("&nbsp;", " ").replace("&#160;", " ").replace("&amp;", "&").replace("&#8211;", "-")
         .replace("&#39;", "'").replace("&#x27;", "'"))
    t = re.sub(r"\s+", " ", t)
    return re.sub(r"(?:\s*\|\s*)+", " | ", t)


def _emails(html: str, text: str) -> list[str]:
    raw = re.findall(r'mailto:([^"\'?<>\s]+)', html, re.I) + EMAIL_RE.findall(text)
    out = []
    for e in raw:
        e = _clean_email(requests.utils.unquote(e))
        if not e or len(e) > 80:
            continue
        if e not in out:
            out.append(e)
    return out


def _best_email(emails: list[str], site_host: str | None) -> str | None:
    if not emails:
        return None
    root = _root(site_host) if site_host else None

    def key(e):
        local, _, dom = e.partition("@")
        same = bool(root) and _root(dom) == root
        pref = next((i for i, p in enumerate(EMAIL_PREFER) if local.startswith(p)), len(EMAIL_PREFER))
        return (not same, pref)
    return sorted(emails, key=key)[0]


def _tel_links(html: str) -> list[str]:
    out = []
    for t in re.findall(r'href=["\']tel:([^"\']+)', html, re.I):
        e = _e164(requests.utils.unquote(t))
        if e and e not in out:
            out.append(e)
    return out


def _vcard(ctx: Contacts, html: str, base: str) -> dict | None:
    m = re.search(r'href=["\']([^"\']+\.vcf(?:\?[^"\']*)?|[^"\']*vcard[^"\']*)["\']', html, re.I)
    if not m:
        return None
    href = requests.compat.urljoin(base, m.group(1).replace("&amp;", "&"))
    if _root(_host(href)) != _root(_host(base)):
        return None
    raw = ctx.get(href)
    if not raw or "BEGIN:VCARD" not in raw.upper():
        return None
    out: dict = {}
    tels = []
    for line in raw.splitlines():
        k, _, v = line.partition(":")
        ku, v = k.upper(), v.strip()
        if ku == "FN" and v:
            out["contact_name"] = v
        elif ku.startswith("N") and ku[:2] in ("N", "N;") and v and "contact_name" not in out:
            last, first = (v.split(";") + [""])[:2]
            if first and last:
                out["contact_name"] = f"{first} {last}"
        elif ku.startswith("ORG") and v:
            out["company"] = v.split(";")[0]
        elif ku.startswith("TITLE") and v:
            out["title"] = v
        elif ku.startswith("TEL") and _e164(v):
            tels.append((0 if "CELL" in ku else 1 if "WORK" in ku else 2, _e164(v)))
        elif ku.startswith("EMAIL") and "@" in v:
            out.setdefault("email", v.lower())
    if tels:
        out["phone"] = sorted(tels)[0][1]
    if not (out.get("phone") or out.get("email")):
        return None
    out["contact_url"] = href
    return out


def _is_name(seg: str) -> bool:
    seg = seg.strip(" ,.-")
    return bool(NAME_RE.match(seg)) and not NAME_STOP.search(seg)


def _split_camel(s: str) -> str:
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", s)


def _agent_block(html: str, text: str, site_host: str) -> dict:
    """Name + phone + email of the agent on a brokerage's own property page.
    The name is kept only when the page backs it (email local part carries
    the name, or a licence/title line sits beside it)."""
    emails = [e for e in _emails(html, text)]
    tels = _tel_links(html)
    out: dict = {}
    person_emails = [e for e in emails if not e.split("@")[0].startswith(EMAIL_PREFER)]
    segs = [s.strip() for s in text.split(" | ")]
    anchor = None
    for i, sg in enumerate(segs):
        low = sg.lower()
        if any(e in low for e in person_emails) or (tels and _e164(sg) in tels) or \
                re.search(r"licen[cs]e|\bdre\b", sg, re.I):
            anchor = i
            break
    if anchor is not None:
        window = segs[max(0, anchor - 8): anchor + 6]
        for sg in window:
            for part in re.split(r"\s{2,}|,\s(?=[A-Z])", sg):
                if not _is_name(part):
                    continue
                first, last = part.split()[0].lower(), part.split()[-1].lower()
                backed = any(last in e.split("@")[0] or (first in e.split("@")[0] and len(first) > 3)
                             for e in person_emails) or any(BROKER_TITLE.search(w) for w in window)
                if backed:
                    out["contact_name"] = part.strip(" ,.-")
                    break
            if out.get("contact_name"):
                break
    nm = out.get("contact_name")
    if nm:
        first, last = nm.split()[0].lower(), nm.split()[-1].lower()
        mine = [e for e in person_emails if last in e.split("@")[0] or first in e.split("@")[0]]
        out["email"] = (mine or [None])[0] or _best_email(emails, site_host)
        # the phone printed next to the agent's name ("P (310) 883-8476")
        i = text.find(nm)
        near = PHONE_RE.search(text[i: i + 400]) if i >= 0 else None
        out["phone"] = _e164(near.group(0)) if near else (tels[0] if tels else None)
    else:
        out["email"] = _best_email(emails, site_host)
        out["phone"] = tels[0] if tels else None
    return out


def _site_contacts(ctx: Contacts, website: str) -> dict:
    """Email (+ a tel: link when there is one) from a business's own site."""
    if not website:
        return {}
    if not website.startswith("http"):
        website = "https://" + website
    host = _host(website)
    origin = re.match(r"https?://[^/]+", website).group(0)
    found: dict = {}
    urls = [website] + [origin + p for p in CONTACT_PATHS if origin + p != website.rstrip("/")]
    for u in urls[:5]:
        html = ctx.get(u)
        if not html:
            continue
        text = _page_text(html)
        em = _best_email(_emails(html, text), host)
        if not found.get("phone"):
            tl = _tel_links(html)
            if tl:
                found["phone"], found["phone_url"] = tl[0], u
        if em:
            local = em.split("@")[0]
            same = _root(em.split("@")[1]) == _root(host)
            if same or not found.get("email"):
                found["email"], found["contact_url"] = em, u
            if same and local.startswith(EMAIL_PREFER):
                break
            if same:
                break
    return found


def _street(addr: str) -> str:
    return (addr or "").split(",")[0].strip()


# People-search / directory sites: their "Name | Phone Number" pages are about
# whoever shares the name, never read for a broker.
PEOPLE_SITES = re.compile(r"whitepages|spokeo|fastpeoplesearch|truepeoplesearch|radaris|peoplefinder|"
                          r"beenverified|intelius|mylife|thatsthem|clustrmaps|nuwber|411\.com|"
                          r"yellowpages|yelp\.|mapquest|rocketreach|zoominfo|signalhire|contactout|"
                          r"apollo\.io|lusha|bizapedia|opencorporates|manta\.com", re.I)
RE_CONTEXT = re.compile(r"real estate|realty|broker|leasing|commercial|\bdre\b|lic(?:ense)?\b|colliers|cbre|"
                        r"cushman|marcus|svn|kw commercial|nai\b|lee & associates|associate|vice president", re.I)
IDX_HINT = re.compile(r"\bIDX\b|brivity|MLS ?#|listing courtesy|multiple listing|mls data", re.I)
BROKER_NAME_RE = re.compile(r"([A-Z][a-z]+(?: [A-Z]\.)? [A-Z][A-Za-z'’-]+),? (?:Commercial )?(?:Real Estate )?"
                            r"(?:Broker|Agent|Associate|Realtor|Salesperson)\b|"
                            r"([A-Z][a-z]+(?: [A-Z]\.)? [A-Z][A-Za-z'’-]+),? (?:CA )?DRE\b")
CO_STOP = re.compile(r"^(?:the|us|our|customer|support|zillow|loopnet|crexi|a|an)\b", re.I)


def _about(r: dict, street: str) -> bool:
    """Is this SERP result about this address (its own URL or title names it)?"""
    num, *rest = street.lower().split()
    word = next((w for w in rest if len(w) > 1 and w not in ("n", "s", "e", "w")), "")
    blob = (r["title"] + " " + re.sub(r"%20|[-_/+]", " ", r["url"])).lower()
    return bool(re.search(r"(?<!\d)" + re.escape(num) + r"(?!\d)", blob)) and word in blob


def _phone_after(blob: str, anchor: str, span: int = 200) -> str | None:
    """First phone within `span` chars after `anchor`, unless another person's
    name sits in between (team pages list several brokers in a row)."""
    i = blob.lower().find(anchor.lower())
    if i < 0:
        return None
    seg = blob[i + len(anchor): i + len(anchor) + span]
    m = PHONE_RE.search(seg)
    if not m:
        return None
    between = seg[: m.start()]
    for nm in re.findall(r"[A-Z][a-z]+(?: [A-Z]\.)? [A-Z][A-Za-z'’-]+", between):
        if _is_name(nm) and nm.lower() != anchor.lower():
            return None
    return _e164(m.group(0))


def _clean_email(e: str) -> str | None:
    e = re.sub(r"\s", "", e).strip(".,;:\\\"'").lower()
    if re.fullmatch(r"[a-z0-9._%+-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,10}", e) and not EMAIL_JUNK.search(e):
        return e
    return None


def _serp_broker(results: list[dict], street: str) -> dict:
    """Broker name / brokerage from the SERP snippets of THIS listing's pages
    (LoopNet's "Contact Colliers for more information", CityFeet's "Oscar
    Baltazar; Marco Petrini. 701 Bailey Ave", a post signed "Gary Mittin,
    Commercial Real Estate Broker")."""
    out: dict = {"names": [], "company": None, "url": None, "src": None}
    num = street.split()[0]
    for r in results:
        if PEOPLE_SITES.search(r["url"]):
            continue
        blob = f"{r['title']}. {r['snippet']}"
        own = _about(r, street)
        src = _src(r["url"])
        if own:
            m = CONTACT_CO_RE.search(blob)
            if m and not out["company"] and not CO_STOP.search(m.group(1)):
                out["company"] = m.group(1).strip(" ,.")
                out["url"], out["src"] = r["url"], f"{src} via Google"
        if src in ("cityfeet", "showcase", "commercialcafe") and street.lower() in blob.lower():
            for m in re.finditer(r"((?:[A-Z][a-z]+(?: [A-Z]\.)? [A-Z][A-Za-z'’-]+)(?:;\s*[A-Z][a-z]+(?: [A-Z]\.)? "
                                 r"[A-Z][A-Za-z'’-]+)*)\.\s*" + re.escape(num) + r"\s", blob):
                names = [n.strip() for n in m.group(1).split(";") if _is_name(n)]
                if names and not out["names"]:
                    out["names"] = names
                    out["url"] = out["url"] or r["url"]
                    out["src"] = out["src"] or f"{src} via Google"
        if own or street.lower() in blob.lower():
            m = BROKER_NAME_RE.search(blob)
            nm = m and (m.group(1) or m.group(2))
            if nm and _is_name(nm) and not out["names"]:
                out["names"] = [nm]
                out["url"], out["src"] = out["url"] or r["url"], out["src"] or f"{src} via Google"
    return out


def listing_contact(ctx: Contacts, o: dict, town: dict) -> dict:
    st = (town.get("state") or "").upper()
    street = _street(o.get("address") or o.get("name"))
    city = o.get("city") or town["town"]
    if not re.match(r"\d", street) or len(street.split()) < 2:
        return {}
    res = ctx.dfs.organic(f'"{street}" {city} {st} lease contact broker')
    sb = _serp_broker(res, street)
    if not sb["names"]:
        # Google words the snippets per query: the plain "for lease" form is
        # the one that surfaces CityFeet's broker-name strip.
        res2 = ctx.dfs.organic(f'"{street}" {city} {st} for lease')
        sb2 = _serp_broker(res2, street)
        sb = {"names": sb2["names"], "company": sb["company"] or sb2["company"],
              "url": sb["url"] or sb2["url"], "src": sb["src"] or sb2["src"]}
        res = res + [r for r in res2 if r["url"] not in {x["url"] for x in res}]
    c: dict = {"contact_role": "listing broker"}
    if sb["names"]:
        c["contact_name"] = sb["names"][0]
    if sb["company"]:
        c["company"] = sb["company"]
    if sb["url"]:
        c["contact_url"], c["contact_source"] = sb["url"], sb["src"]
    # The brokerage's own page for this property (not a portal): fetch it.
    for r in res:
        if NO_FETCH.search(r["url"]) or not _about(r, street):
            continue
        html = ctx.get(r["url"])
        if not html:
            continue
        text = _page_text(html)
        if street.split()[0] not in text or not re.search(r"lease|for rent", text, re.I):
            continue
        host = _host(r["url"])
        if IDX_HINT.search(text) or LISTED_BY_RE.search(text):
            # MLS/IDX syndication page ("Listed by Compass, Edgar Torossian"):
            # the page's own phone/email belong to the IDX host, not the broker.
            lb = LISTED_BY_RE.search(text)
            if lb:
                for part in [p.strip() for p in _split_camel(lb.group(1)).split(",")]:
                    if _is_name(part) and not c.get("contact_name"):
                        c["contact_name"] = part
                    elif not _is_name(part) and 2 < len(part) < 60 and not c.get("company") \
                            and not CO_STOP.search(part):
                        c["company"] = part
                c["contact_url"], c["contact_source"] = r["url"], f"{host} (MLS listing attribution)"
            continue
        vc = _vcard(ctx, html, r["url"])
        if vc:
            c.update({k: v for k, v in vc.items() if k != "title" and v})
            c.setdefault("company", host)
            c["contact_url"] = r["url"]          # the property page, not the .vcf download
            c["contact_source"] = f"{host} (brokerage page, vCard)"
            break
        ab = _agent_block(html, text, host)
        # A property page without a named agent is a franchise/IDX template
        # (eXp's 833 line + info@): not the listing broker.
        if ab.get("contact_name") and (ab.get("phone") or ab.get("email")):
            if ab.get("contact_name"):
                c["contact_name"] = ab["contact_name"]
            c["phone"], c["email"] = ab.get("phone"), ab.get("email")
            og = re.search(r'property=["\']og:site_name["\']\s+content=["\']([^"\']{2,60})', html)
            c["company"] = c.get("company") or (og.group(1) if og else host)
            c["contact_url"], c["contact_source"] = r["url"], f"{host} (brokerage page)"
            break
    # A named broker but no way to reach them yet: one SERP on the name.
    if c.get("contact_name") and not (c.get("phone") or c.get("email")):
        nm = c["contact_name"]
        first, last = nm.split()[0].lower(), nm.split()[-1].lower()
        for r in ctx.dfs.organic(f'"{nm}" {c.get("company") or st} commercial real estate broker'):
            blob = f"{r['title']}. {r['snippet']}"
            if nm.lower() not in blob.lower() or PEOPLE_SITES.search(r["url"]) or not RE_CONTEXT.search(blob):
                continue
            prof = re.match(re.escape(nm) + r"\s*\|\s*([^|]{2,50}?)\s*\|", r["title"])
            if prof and not c.get("company"):
                c["company"] = prof.group(1).strip()
            ph = _phone_after(blob, nm, 160)
            if ph and not c.get("phone"):
                c["phone"] = ph
                c["contact_url"], c["contact_source"] = r["url"], f"{_host(r['url'])} via Google"
            for e in EMAIL_RE.findall(blob):
                e = _clean_email(e)
                if e and not c.get("email") and (last in e.split("@")[0] or first in e.split("@")[0]):
                    c["email"] = e
                    if not c.get("phone"):
                        c["contact_url"], c["contact_source"] = r["url"], f"{_host(r['url'])} via Google"
            if c.get("phone") and c.get("email"):
                break
    # Only the brokerage is known: its office line / email (the broker's desk
    # is one transfer away).
    if c.get("company") and not (c.get("phone") or c.get("email")):
        co = c["company"]
        toks = [w for w in re.findall(r"[a-z]{3,}", co.lower()) if w not in ("the", "and", "inc", "llc", "group")]
        for r in ctx.dfs.organic(f'"{co}" {city} {st} commercial real estate phone'):
            blob = f"{r['title']}. {r['snippet']}"
            if co.lower() not in blob.lower() or PEOPLE_SITES.search(r["url"]):
                continue
            ph = _phone_after(blob, co, 200)
            # National brands (Cushman & Wakefield, Colliers) have hundreds of
            # offices: only a local area code or a snippet naming the town counts.
            if ph and not (ph[2:5] in (town.get("_area_codes") or ()) or city.lower() in blob.lower()):
                ph = None
            if ph and not c.get("phone"):
                c["phone"] = ph
                c["contact_url"], c["contact_source"] = r["url"], f"{_host(r['url'])} via Google"
                if not c.get("contact_name"):
                    c["contact_role"] = "listing brokerage (office line)"
            host = _host(r["url"])
            ini = "".join(w[0] for w in toks)
            if not c.get("email") and not NO_FETCH.search(r["url"]) and toks and \
                    (any(len(t) > 3 and t in host for t in toks) or (len(ini) >= 3 and host.startswith(ini))):
                sc = _site_contacts(ctx, r["url"])
                page = ctx.pages.get(sc.get("contact_url") or "") or ""
                if sc.get("email") and not re.search(r",\s?" + st + r"\b|" + US_STATES.get(st, "@@"), page):
                    sc = {}          # same initials, different country/state (cwedm.com = Edmonton)
                if sc.get("email"):
                    c["email"] = sc["email"]
                    if not c.get("phone") and sc.get("phone"):
                        c["phone"] = sc["phone"]
                        c["contact_role"] = "listing brokerage (office line)"
                    c["contact_url"], c["contact_source"] = sc["contact_url"], f"{host} (brokerage website)"
            if c.get("phone") and c.get("email"):
                break
    if not any(c.get(k) for k in ("contact_name", "company", "phone", "email")):
        return {}
    return c


def facility_contact(ctx: Contacts, o: dict, town: dict) -> dict:
    """SpareFoot / LiquidSpace / Coworker option: the facility's own website."""
    st = (town.get("state") or "").upper()
    nm = re.split(r"\s+[|-]\s+|,", o.get("name") or "")[0].strip()
    if not nm:
        return {}
    city = o.get("city") or town["town"]
    res = ctx.dfs.organic(f'"{nm}" {city} {st}')
    generic = {"storage", "self", "mini", "store", "office", "offices", "suite", "suites", "space",
               "spaces", "center", "centre", "business", "executive", "coworking", "private", "units"}
    towns = {w for t in (town.get("would_cover") or []) + [town["town"]] for w in re.findall(r"[a-z]+", t.lower())}
    words = [w for w in re.findall(r"[a-z]+", nm.lower()) if len(w) > 2]
    toks = {w for w in words if w not in generic and w not in towns}
    if not toks:
        return {}                     # "Delano Storage": nothing distinctive to match a site on
    joined = "".join(w for w in words if w not in towns)
    c: dict = {"contact_role": "facility office" if o.get("tier") == "storage" else "leasing office",
               "company": nm}
    for r in res:
        if NO_FETCH.search(r["url"]):
            continue
        host = _host(r["url"])
        if joined not in host.replace("-", "") and not all(t in host for t in toks):
            continue
        sc = _site_contacts(ctx, r["url"])
        if sc.get("phone") or sc.get("email"):
            c.update({"phone": sc.get("phone"), "email": sc.get("email"),
                      "contact_url": sc.get("contact_url") or sc.get("phone_url") or r["url"],
                      "contact_source": f"{host} (own website via Google)"})
            break
    return c if (c.get("phone") or c.get("email")) else {}


def maps_contact(ctx: Contacts, o: dict) -> dict:
    tier = o.get("tier")
    c = {"contact_role": {"storage": "facility office", "coworking": "leasing office",
                          "office": "leasing office", "flex": "leasing office",
                          "broker": "broker office"}.get(tier, "office"),
         "company": o.get("name"), "phone": _e164(o.get("phone")),
         "contact_url": f"https://www.google.com/maps?cid={o['cid']}" if o.get("cid") else None,
         "contact_source": "google maps"}
    sc = _site_contacts(ctx, o.get("website") or "")
    if sc.get("email"):
        c["email"] = sc["email"]
        c["contact_url"] = sc.get("contact_url")
        c["contact_source"] = f"google maps + {_host(sc['contact_url'])}"
    if not c["phone"] and sc.get("phone"):
        c["phone"] = sc["phone"]
        c["contact_url"] = c["contact_url"] or sc.get("phone_url")
        c["contact_source"] = f"{_host(sc.get('phone_url') or '')} (website)"
    return c


def _memo(ctx: Contacts, key: str, fn) -> dict:
    """One lookup per address per run: the same suite shows up under two
    towns (911-913 Main St under McFarland AND Delano)."""
    with ctx.lock:
        hit = ctx.memo.get(key)
        if hit is None:
            ev = threading.Event()
            ctx.memo[key] = (ev, {})
    if hit is not None:
        hit[0].wait(120)
        return dict(hit[1])
    out = {}
    try:
        out = fn()
    finally:
        ctx.memo[key][1].update(out)
        ev.set()
    return dict(out)


def enrich_option(ctx: Contacts, o: dict, town: dict) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    src = o.get("source") or "google maps"
    mkey = (addr_key(o.get("address")) or re.sub(r"[^a-z0-9]", "", (o.get("name") or "").lower())) + \
        "|" + (o.get("city") or town["town"]).lower()
    try:
        if src == "craigslist":
            c = {"contact_role": "poster (craigslist relay)", "contact_url": o.get("website"),
                 "contact_source": "craigslist relay"}
        elif src == "google maps":
            c = maps_contact(ctx, o)
        elif src in ("sparefoot", "liquidspace", "coworker"):
            c = _memo(ctx, "f:" + mkey, lambda: facility_contact(ctx, o, town))
        else:
            c = _memo(ctx, "l:" + mkey, lambda: listing_contact(ctx, o, town))
    except Exception as e:  # noqa: BLE001   fail-open per option
        print(f"    [contacts] {o.get('name', '')[:50]}: {str(e)[:100]}")
        c = {}
    if c.get("phone"):
        c["phone_display"] = _display(c["phone"])
        c["phone_type"] = ctx.line_type(c["phone"])
        c["carrier"] = (ctx.types.get(c["phone"]) or {}).get("carrier")
    c["checked_at"] = now
    o["contact"] = c


def enrich_contacts(ctx: Contacts, results: list[dict]) -> None:
    # Local area codes (from the Maps phones of this run) vet a brokerage's
    # office line found in a SERP snippet.
    codes = {e[2:5] for t in results for o in t["options"] for e in [_e164(o.get("phone"))] if e}
    for t in results:
        t["_area_codes"] = codes
    jobs = [(o, t) for t in results for o in t["options"]]
    try:
        with ThreadPoolExecutor(max_workers=6) as ex:
            list(ex.map(lambda ot: enrich_option(ctx, *ot), jobs))
    finally:
        for t in results:
            t.pop("_area_codes", None)


def prev_phone_types(key: str | None) -> dict:
    """Line types from the previous run's blob, so an unchanged number is not
    looked up (and paid for) again."""
    if not key:
        return {}
    try:
        prev = kv_get(key) or {}
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for t in prev.get("towns") or []:
        for o in t.get("options") or []:
            c = o.get("contact") or {}
            if c.get("phone") and c.get("phone_type") and c["phone_type"] != "unknown":
                out[c["phone"]] = {"phone_type": c["phone_type"], "carrier": c.get("carrier")}
    return out


# ------------------------------------------------------------- app table
TABLE = "marketing_office_scout"


def _sb(method: str, path: str, body=None, prefer: str = "return=minimal"):
    """Service-role PostgREST call (client_ops_sync._sb pattern)."""
    url = os.environ["SUPABASE_URL"].rstrip("/") + path
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    r = requests.request(method, url, json=body, timeout=30, headers={
        "apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "Prefer": prefer, "User-Agent": UA})
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path.split('?')[0]} -> {r.status_code}: {r.text[:300]}")
    return r.json() if r.content else None


def _price_text(o: dict) -> str | None:
    if o.get("price_text"):
        return o["price_text"]
    if o.get("cost_source") in ("listing snippet", "website", "craigslist post"):
        return o.get("cost_band")
    return None


def _sqft(o: dict) -> str | None:
    lo, hi = o.get("sq_ft_min"), o.get("sq_ft_max")
    if not lo:
        return None
    return f"{lo:,}" + (f"-{hi:,}" if hi else "") + " SF"


def table_rows(out: dict) -> list[dict]:
    """One marketing_office_scout row per shown option, in rank order."""
    rows = []
    for t in out["towns"]:
        for i, o in enumerate(t["options"], 1):
            extra = []
            if o.get("listing_page") is False:
                extra.append("address only mentioned on a search page; open the link to find it")
            if o.get("category") and o.get("source") == "google maps":
                extra.append(f"Maps category: {o['category']}")
            if o.get("rating"):
                extra.append(f"{o['rating']} stars ({o.get('reviews') or 0} reviews)")
            extra.append(f"found by: {o.get('found_by')}")
            c = o.get("contact") or {}
            rows.append({
                "company_id": out["company_id"], "town": t["town"], "town_rank": t.get("town_rank"),
                "option_rank": i, "name": o.get("name"), "address": o.get("address"),
                "tier": o.get("tier"), "source": o.get("source") or "google maps",
                "url": o.get("website") if (o.get("website") or "").startswith("http")
                else (f"https://{o['website']}" if o.get("website") else None),
                "verification": o.get("verification_likelihood"),
                "verification_reason": o.get("verification_reason"),
                "cost_band": o.get("cost_band"), "price_text": _price_text(o), "sqft": _sqft(o),
                "distance_town_mi": o.get("distance_from_town_mi"),
                "distance_pin_mi": o.get("distance_from_pin_mi"),
                "ask_for": o.get("notes"), "notes": "; ".join(extra),
                "scanned_at": out["generated_at"],
                **({"contact_name": c.get("contact_name"), "contact_role": c.get("contact_role"),
                    "company": c.get("company"), "phone": c.get("phone"),
                    "phone_type": c.get("phone_type"), "email": c.get("email"),
                    "contact_url": c.get("contact_url"), "contact_source": c.get("contact_source"),
                    "contact_checked_at": c.get("checked_at")} if "contact" in o else {}),
            })
    return rows


def save_table(out: dict) -> int:
    """Insert the fresh set, then delete this company's older rows: the table
    is never empty mid-run, and ends holding exactly this run."""
    cid = out["company_id"]
    rows = table_rows(out)
    if rows:
        _sb("POST", f"/rest/v1/{TABLE}", rows)
    _sb("DELETE", f"/rest/v1/{TABLE}?company_id=eq.{cid}&scanned_at=lt.{requests.utils.quote(out['generated_at'])}")
    return len(rows)


def log_work(out: dict) -> None:
    """Reports tab (2026-09-29, every client action logs): research delivered
    to the client's app. Fail-soft: never breaks a saved run."""
    try:
        from work_log import work_log
        towns = [t.get("town") for t in out.get("towns") or [] if t.get("town")]
        n = sum(len(t.get("options") or []) for t in out.get("towns") or [])
        if not (n and out.get("company_id")):
            return
        work_log(out["company_id"], "research", "office-scout",
                 f"Office search delivered in your app: {n} rentable space"
                 f"{'s' if n != 1 else ''} rated for a second Google listing in "
                 f"{', '.join(towns[:5])}, with the best contact to call for each.",
                 evidence={"towns": towns, "options": n,
                           "generated_at": out.get("generated_at")},
                 actor="automation", source="office_scout.py")
    except Exception as e:  # noqa: BLE001
        print(f"  [work-log] warn: {str(e)[:100]}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description="Find rentable spaces for a second GBP in each scouted town")
    ap.add_argument("--slug", help="client slug (uses its location_scout shortlist)")
    ap.add_argument("--towns", default="", help='extra towns: "Delano, CA; Tehachapi, CA"')
    ap.add_argument("--top", type=int, default=DEFAULT_TOP_TOWNS,
                    help="how many shortlist seats to scout (default 3)")
    ap.add_argument("--fresh-scout", action="store_true",
                    help="re-run location_scout live instead of reading the saved shortlist")
    ap.add_argument("--cap", type=float, default=MAX_RUN_COST, help="DataForSEO spend cap in USD")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--contacts", action=argparse.BooleanOptionalAction, default=None,
                    help="find who to call per option (phone/email/broker + Twilio line type); "
                         "default ON with --apply, off for a dry-run")
    ap.add_argument("--contacts-cap", type=float, default=CONTACTS_CAP,
                    help=f"contacts-pass spend cap in USD, SERP + Twilio (default {CONTACTS_CAP})")
    ap.add_argument("--apply", action="store_true",
                    help="write marketing_office_scout rows + ops_kv office-scout:{company_id}")
    a = ap.parse_args()
    if not a.slug and not a.towns:
        ap.error("give --slug and/or --towns")
    ctx = client_ctx(a.slug) if a.slug else None
    towns, reach = gather_towns(ctx, a.towns, a.top, a.fresh_scout)
    if not towns:
        print("no towns to scout (no saved shortlist and no --towns)")
        return 1
    dfs = DFS(cap=a.cap)
    pin = (ctx or {}).get("pin") or (None, None)
    results = [scout_town(dfs, t, pin, reach if ctx else 0) for t in towns]
    key = f"office-scout:{ctx['company_id']}" if ctx and ctx.get("company_id") else None
    do_contacts = a.apply if a.contacts is None else a.contacts
    cinfo = None
    cdfs = None
    if do_contacts:
        cdfs = DFS(cap=a.contacts_cap)
        cx = Contacts(cdfs, prev_phone_types(key))
        prev_keys = set(cx.types)
        enrich_contacts(cx, results)
        opts = [o for t in results for o in t["options"]]
        cc = [o.get("contact") or {} for o in opts]
        cinfo = {"options": len(opts), "with_phone": sum(1 for c in cc if c.get("phone")),
                 "with_email": sum(1 for c in cc if c.get("email")),
                 "with_name": sum(1 for c in cc if c.get("contact_name")),
                 "serp_calls": cdfs.calls, "serp_usd": round(cdfs.cost, 4),
                 "serp_skipped": cdfs.skipped, "twilio_lookups": cx.twilio_calls,
                 "twilio_usd": cx.twilio_cost,
                 "twilio_reused": len({c["phone"] for c in cc if c.get("phone") in prev_keys}),
                 "fetches": cx.fetches, "cap_usd": a.contacts_cap}
    out = {"slug": a.slug, "company_id": (ctx or {}).get("company_id"),
           "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "pin": {"lat": pin[0], "lng": pin[1]} if pin[0] is not None else None,
           "reach_mi": reach if ctx else None,
           "spend_usd": round(dfs.cost, 4), "cap_usd": a.cap, "dfs_calls": dfs.calls,
           "dfs_skipped": dfs.skipped, "towns": results}
    if cinfo:
        out["contacts"] = cinfo
    out["spend_breakdown"] = {
        "maps": round(dfs.cost_maps, 4), "serp": round(dfs.cost_serp, 4),
        "contacts_serp": round(cdfs.cost, 4) if cdfs else 0.0, "onpage": 0.0,
        "twilio": cinfo["twilio_usd"] if cinfo else 0.0}
    out["spend_breakdown"]["total"] = round(sum(out["spend_breakdown"].values()), 4)
    if a.json:
        print(json.dumps(out, indent=2))
    else:
        render(out)
    log = sys.stderr if a.json else sys.stdout      # keep --json stdout parseable
    if a.apply:
        if not key:
            print("  not saved: no company_id (need --slug of a mapped client)", file=log)
            return 1
        kv_set(key, out)
        back = kv_get(key) or {}
        print(f"  wrote ops_kv {key} [{sum(len(t['options']) for t in results)} options across "
              f"{len(results)} town(s), generated_at {back.get('generated_at')}]", file=log)
        n = save_table(out)
        live = _sb("GET", f"/rest/v1/{TABLE}?company_id=eq.{out['company_id']}&select=source",
                   prefer="count=exact") or []
        by_src: dict[str, int] = {}
        for r in live:
            by_src[r["source"]] = by_src.get(r["source"], 0) + 1
        print(f"  wrote {n} rows to {TABLE}; now holds {len(live)} for {out['company_id']} "
              f"({', '.join(f'{k} {v}' for k, v in sorted(by_src.items(), key=lambda kv: -kv[1]))})",
              file=log)
        log_work(out)
    elif key:
        print(f"  (dry-run) would write {TABLE} rows + ops_kv {key}; re-run with --apply", file=log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
