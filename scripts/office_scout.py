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
storage). Every run is capped at MAX_RUN_COST (~$0.10) and stops querying past
it; spend is printed.

Store: ops_kv `office-scout:{company_id}` (only with --apply; default is a
dry-run print):
  {"slug", "company_id", "generated_at", "pin", "reach_mi", "spend_usd",
   "towns": [{"town", "state", "lat", "lng", "source", "would_cover",
              "distance_from_pin_mi", "options": [...], "excluded": [...]}]}

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
import re
import sys
import time
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
COST_PER_QUERY = 0.002
MAX_RUN_COST = 0.10
DEFAULT_TOP_TOWNS = 3
PER_TOWN = 5            # options shown per town
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
IWG = re.compile(r"\bregus\b|\bspaces\b|\bhq\b|signature by regus|\biwg\b|\bbasepoint\b", re.I)
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
    if cat in RETAIL_CATS or re.search(r"\bwalmart\b|staples|office ?depot|fedex", title, re.I):
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
            return ("medium", "IWG private offices sometimes pass (Power Dry KC precedent); "
                    "the virtual-office product fails.",
                    "Regus/IWG: ask for a PRIVATE OFFICE, not a virtual office or membership; "
                    "confirm door/lobby signage is allowed.")
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
        self.calls = 0
        self.cap = cap
        self.skipped = 0

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
        self.calls += 1
        self.cost += float(task.get("cost") or 0)
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
                          "would_cover": s.get("would_cover") or [s["seat_city"]]})
            taken += 1
    have = {t["town"].lower() for t in towns}
    for city, state in parse_towns(towns_arg):
        if city.lower() in have:
            continue
        ll = ls.geocode(city, state)
        time.sleep(1.1)                                     # Nominatim courtesy
        if not ll:
            print(f"  could not geocode {city}, {state}; skipped")
            continue
        towns.append({"town": city, "state": state, "lat": ll[0], "lng": ll[1],
                      "source": "--towns", "would_cover": [city]})
        have.add(city.lower())
    pin = (ctx or {}).get("pin") or (None, None)
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
                "notes": note, "found_by": q,
            }

    def score(o):
        in_town = 1.5 if (o.get("city") or "").lower() == town["town"].lower() else 0.0
        social = min(math.log10((o.get("reviews") or 0) + 1), 2.5) * 0.4
        return (V_WEIGHT[o["verification_likelihood"]] * 10 - o["distance_from_town_mi"] * 0.8
                + in_town + social + cost_rank(o["tier"]))

    ranked = sorted(seen.values(), key=score, reverse=True)
    picks, per_tier = [], {}
    for o in ranked:
        if per_tier.get(o["tier"], 0) >= PER_TIER_CAP:
            continue
        per_tier[o["tier"]] = per_tier.get(o["tier"], 0) + 1
        o["score"] = round(score(o), 2)
        picks.append(o)
        if len(picks) >= PER_TOWN:
            break

    # One cheap GET per pick for a posted monthly price. Never scrapes deeper.
    with ThreadPoolExecutor(max_workers=5) as ex:
        prices = list(ex.map(lambda o: price_peek(o.get("website") or ""), picks))
    for o, p in zip(picks, prices):
        if p:
            o["cost_band"] = f"from ${p:,}/mo"
            o["cost_source"] = "website"
    return {**town, "options": picks, "candidates_seen": len(seen),
            "excluded": [{k: v for k, v in e.items() if k != "key"} for e in excluded]}


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
            print(f"    no rentable space found on Google Maps ({t['candidates_seen']} candidates); "
                  f"try a commercial broker or the nearest bigger town")
        for i, o in enumerate(t["options"], 1):
            rv = f"{o['rating']}* ({o['reviews']})" if o.get("rating") else "no reviews"
            print(f"    {i}. {o['name']}  [{o['tier']}]  verify: {o['verification_likelihood'].upper()}"
                  f"  cost: {o['cost_band']}")
            print(f"       {o['address']}  |  {o.get('phone') or 'no phone'}  |  {rv}  |  "
                  f"{o['distance_from_town_mi']}mi from center"
                  + (f", {o['distance_from_pin_mi']}mi from pin" if o.get("distance_from_pin_mi") else ""))
            print(f"       why: {o['verification_reason']}")
            print(f"       ask: {o['notes']}")
            if o.get("website"):
                print(f"       web: {o['website'][:100]}")
        if t["excluded"]:
            print("    filtered: " + "; ".join(f"{e['name']} ({e['reason'].split(' (')[0]})"
                                              for e in t["excluded"][:6]))
    print(f"\n  DataForSEO: {out['dfs_calls']} queries, ${out['spend_usd']:.3f} spent "
          f"(cap ${out['cap_usd']:.2f})"
          + (f"; {out['dfs_skipped']} queries SKIPPED at the cap" if out.get("dfs_skipped") else ""))


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
    ap.add_argument("--apply", action="store_true", help="write ops_kv office-scout:{company_id}")
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
    out = {"slug": a.slug, "company_id": (ctx or {}).get("company_id"),
           "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "pin": {"lat": pin[0], "lng": pin[1]} if pin[0] is not None else None,
           "reach_mi": reach if ctx else None,
           "spend_usd": round(dfs.cost, 4), "cap_usd": a.cap, "dfs_calls": dfs.calls,
           "dfs_skipped": dfs.skipped, "towns": results}
    if a.json:
        print(json.dumps(out, indent=2))
    else:
        render(out)
    key = f"office-scout:{out['company_id']}" if out.get("company_id") else None
    log = sys.stderr if a.json else sys.stdout      # keep --json stdout parseable
    if a.apply:
        if not key:
            print("  not saved: no company_id (need --slug of a mapped client)", file=log)
            return 1
        kv_set(key, out)
        back = kv_get(key) or {}
        print(f"  wrote ops_kv {key} [{sum(len(t['options']) for t in results)} options across "
              f"{len(results)} town(s), generated_at {back.get('generated_at')}]", file=log)
    elif key:
        print(f"  (dry-run) would write ops_kv {key}; re-run with --apply", file=log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
