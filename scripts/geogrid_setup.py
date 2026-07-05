#!/usr/bin/env python3
"""
Rank AI — Geo-grid client onboarding helpers.

Turns "Claude hand-assembles geo-grid config for one client" into a repeatable,
one-command setup for any client. Derives the keyword list + city list from the
client's existing plan-input.json, looks up the business listing identity
(place_id / google_cid) needed to match the client in Maps results, resolves the
app company_id, and writes the two config files the scanner/cron read:

    clients/{slug}/geogrid-keywords.txt
    clients/{slug}/geogrid-cities.json

The bi-weekly cron (railway.geogrid-cron.toml) and POST /geogrid/scan auto-include
any client that has those two files + a resolvable company_id.

CLI:
  python3 scripts/geogrid_setup.py plan       --slug X [--max-keywords 10]
  python3 scripts/geogrid_setup.py identity    --slug X            # fill brand.place_id/google_cid
  python3 scripts/geogrid_setup.py company-id  --slug X [--set CO-123...]
  python3 scripts/geogrid_setup.py apply       --slug X --cities "Federal Way, WA;Tacoma, WA" [--max-keywords 10]

`plan` derives + previews + estimates cost and writes NOTHING. `apply` writes the
config files (cities filtered to the --cities subset you approve from `plan`).
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import geogrid_scan as gs  # noqa: E402  (load_dfs_creds, rank-at-point primitives)

# NOTE: the services catalog is per-client vertical — resolved in load_catalog()
# via scripts/verticals.py (fail-loud). Never hardcode templates/restoration.
TIER_RANK = {"core": 0, "specialty": 1, "adjacent": 2}
COST_PER_SCAN = 0.34   # ~ 169 points x ~$0.002 at 13x13 zoom 12 (observed)
NOMINATIM = "https://nominatim.openstreetmap.org/search"
UA = {"User-Agent": "RankAI-geogrid-setup/1.0 (+contact@restorationai.io)"}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_plan(slug: str) -> dict:
    p = ROOT / "clients" / slug / "plan-input.json"
    if not p.exists():
        sys.exit(f"ERROR: {p} not found — run rank-ai-plan-site first.")
    return json.loads(p.read_text())


def load_catalog(slug: str) -> dict:
    import verticals  # local sibling module (scripts/) — fail-loud vertical resolution
    s = json.loads(verticals.resolve_template(slug, "services.json").read_text())
    items = s if isinstance(s, list) else s.get("services", list(s.values()))
    return {it["slug"]: it for it in items if isinstance(it, dict) and "slug" in it}


# ---------------------------------------------------------------------------
# Keyword derivation (from the client's services)
# ---------------------------------------------------------------------------

def derive_keywords(slug: str, max_keywords: int = 10) -> list[str]:
    """Head map-pack keywords for the client's top services + 'near me' on the top 2.

    Geo-grid keywords are the head terms people type into Maps — the service's
    display_name (e.g. 'water damage restoration') — NOT long-tail/intent terms.
    We rank the client's services by tier (core>specialty>adjacent) then priority,
    take the head term of each, and add 'near me' variants for the two strongest.
    """
    plan = load_plan(slug)
    catalog = load_catalog(slug)
    services = [catalog[s] for s in plan.get("services", []) if s in catalog]
    services.sort(key=lambda it: (TIER_RANK.get(it.get("tier"), 9), -(it.get("priority") or 0)))

    keywords: list[str] = []
    heads: list[str] = []
    for it in services:
        head = (it.get("display_name") or it["slug"].replace("-", " ")).lower()
        # strip trailing qualifiers like "and sanitization" to keep the head term tight
        head = head.split(" and ")[0].strip()
        if head not in heads:
            heads.append(head)

    # head terms in priority order
    for h in heads:
        if len(keywords) >= max_keywords:
            break
        keywords.append(h)
    # 'near me' for the top 2 strongest services (if room)
    for h in heads[:2]:
        nm = f"{h} near me"
        if len(keywords) < max_keywords and nm not in keywords:
            keywords.append(nm)

    return keywords[:max_keywords]


# ---------------------------------------------------------------------------
# City derivation (service areas -> geocoded grid centers)
# ---------------------------------------------------------------------------

def geocode_city(city: str, state: str) -> tuple[float, float] | None:
    q = urllib.parse.urlencode({"q": f"{city}, {state}, USA", "format": "json", "limit": 1})
    req = urllib.request.Request(f"{NOMINATIM}?{q}", headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        if data:
            return round(float(data[0]["lat"]), 4), round(float(data[0]["lon"]), 4)
    except Exception as e:
        sys.stderr.write(f"  geocode '{city}, {state}' failed: {str(e)[:80]}\n")
    return None


def derive_cities(slug: str) -> list[dict]:
    """All service-area cities, geocoded. The primary area reuses the brand lat/lng
    (exact business location) instead of a city centroid; others geocode via OSM."""
    plan = load_plan(slug)
    brand = plan.get("brand", {})
    out = []
    for a in plan.get("service_areas", []):
        label = f"{a['city']}, {a['state']}"
        if a.get("primary") and brand.get("lat") and brand.get("lng"):
            lat, lng = float(brand["lat"]), float(brand["lng"])
        else:
            geo = geocode_city(a["city"], a["state"])
            time.sleep(1.1)  # Nominatim: <=1 req/sec
            if not geo:
                continue
            lat, lng = geo
        out.append({"label": label, "lat": lat, "lng": lng, "primary": bool(a.get("primary"))})
    return out


# ---------------------------------------------------------------------------
# Business listing identity (place_id / google_cid) for Maps matching
# ---------------------------------------------------------------------------

def lookup_business_identity(slug: str, zoom: int = 12) -> dict:
    """Find the client's Maps listing (place_id + cid) by searching its name at the
    brand location. Needed so the scanner can match the client in each grid cell."""
    plan = load_plan(slug)
    brand = plan.get("brand", {})
    name = brand.get("display_name")
    if not (name and brand.get("lat") and brand.get("lng")):
        sys.exit("ERROR: brand.display_name/lat/lng required in plan-input.json.")
    u, p = gs.load_dfs_creds()
    auth = base64.b64encode(f"{u}:{p}".encode()).decode()
    body = json.dumps([{
        "keyword": name,
        "location_coordinate": f"{brand['lat']},{brand['lng']},{zoom}z",
        "language_code": "en", "device": "desktop",
    }]).encode()
    req = urllib.request.Request(gs.DFS_URL, data=body, method="POST",
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read())
    items = (((resp.get("tasks") or [{}])[0].get("result") or [{}])[0] or {}).get("items") or []
    nlow = name.lower()
    for it in items:
        if isinstance(it, dict) and nlow in (it.get("title") or "").lower():
            return {"place_id": it.get("place_id"),
                    "cid": str(it.get("cid")) if it.get("cid") is not None else None,
                    "matched_title": it.get("title")}
    return {"place_id": None, "cid": None, "matched_title": None}


# ---------------------------------------------------------------------------
# company_id resolution (single source of truth -> the client record)
# ---------------------------------------------------------------------------

def resolve_company_id(slug: str) -> str | None:
    """Resolve the app company_id (companies.id, 'CO-...'). Prefers the client
    record (clients/{slug}.json -> company_id); falls back to the legacy hardcoded
    COMPANY_MAP so existing clients keep working during the migration."""
    rec_path = ROOT / "clients" / f"{slug}.json"
    if rec_path.exists():
        rec = json.loads(rec_path.read_text())
        cid = rec.get("company_id") or rec.get("marketing", {}).get("company_id")
        if cid:
            return cid
    from geogrid_store import COMPANY_MAP  # legacy fallback
    return COMPANY_MAP.get(slug)


def set_company_id(slug: str, company_id: str) -> None:
    rec_path = ROOT / "clients" / f"{slug}.json"
    if not rec_path.exists():
        sys.exit(f"ERROR: {rec_path} not found.")
    rec = json.loads(rec_path.read_text())
    rec["company_id"] = company_id
    rec_path.write_text(json.dumps(rec, indent=2))
    print(f"  set company_id={company_id} on clients/{slug}.json")


# ---------------------------------------------------------------------------
# Writing config
# ---------------------------------------------------------------------------

def write_config(slug: str, keywords: list[str], cities: list[dict]) -> None:
    d = ROOT / "clients" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "geogrid-keywords.txt").write_text("\n".join(keywords) + "\n")
    clean = [{"label": c["label"], "lat": c["lat"], "lng": c["lng"]} for c in cities]
    (d / "geogrid-cities.json").write_text(json.dumps(clean, indent=2) + "\n")
    print(f"  wrote clients/{slug}/geogrid-keywords.txt ({len(keywords)} keywords)")
    print(f"  wrote clients/{slug}/geogrid-cities.json ({len(cities)} cities)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_plan(args) -> int:
    keywords = derive_keywords(args.slug, args.max_keywords)
    cities = derive_cities(args.slug)
    company_id = resolve_company_id(args.slug)
    plan = load_plan(args.slug)
    brand = plan.get("brand", {})
    has_identity = bool(brand.get("place_id") or brand.get("google_cid"))

    print(f"\n==> Geo-grid setup plan: {args.slug}")
    print(f"\n  company_id: {company_id or 'MISSING — run: company-id --slug %s --set CO-...' % args.slug}")
    print(f"  business identity (place_id/cid): {'present' if has_identity else 'MISSING — run: identity --slug %s' % args.slug}")
    print(f"\n  KEYWORDS ({len(keywords)}):")
    for k in keywords:
        print(f"    - {k}")
    print(f"\n  CITIES ({len(cities)}) — geocoded, pick a subset for --cities:")
    for c in cities:
        star = " *primary" if c.get("primary") else ""
        print(f"    - {c['label']:22} {c['lat']},{c['lng']}{star}")
    n_cities = len(cities)
    print(f"\n  COST per run (all {n_cities} cities): {len(keywords)} kw x {n_cities} cities "
          f"x ${COST_PER_SCAN:.2f} = ${len(keywords)*n_cities*COST_PER_SCAN:.2f}")
    print(f"  COST per run (primary + 1 city):    {len(keywords)} kw x 2 cities "
          f"x ${COST_PER_SCAN:.2f} = ${len(keywords)*2*COST_PER_SCAN:.2f}  (x2 runs/month bi-weekly)")
    out = ROOT / "clients" / args.slug / "geogrid"
    out.mkdir(parents=True, exist_ok=True)
    (out / "setup-preview.json").write_text(json.dumps(
        {"keywords": keywords, "cities": cities, "company_id": company_id,
         "has_identity": has_identity}, indent=2))
    print(f"\n  preview -> clients/{args.slug}/geogrid/setup-preview.json")
    print("  Next: review, then `apply --slug %s --cities \"A, ST;B, ST\"`" % args.slug)
    return 0


def cmd_identity(args) -> int:
    ident = lookup_business_identity(args.slug)
    print(f"  matched: {ident.get('matched_title')}")
    print(f"  place_id: {ident.get('place_id')}")
    print(f"  cid:      {ident.get('cid')}")
    if args.write and (ident.get("place_id") or ident.get("cid")):
        p = ROOT / "clients" / args.slug / "plan-input.json"
        plan = json.loads(p.read_text())
        plan.setdefault("brand", {})
        if ident.get("place_id"):
            plan["brand"]["place_id"] = ident["place_id"]
        if ident.get("cid"):
            plan["brand"]["google_cid"] = ident["cid"]
        p.write_text(json.dumps(plan, indent=2))
        print(f"  wrote brand.place_id/google_cid into plan-input.json")
    return 0


def cmd_company_id(args) -> int:
    if args.set:
        set_company_id(args.slug, args.set)
    else:
        print(f"  resolved company_id: {resolve_company_id(args.slug)}")
    return 0


def cmd_apply(args) -> int:
    keywords = derive_keywords(args.slug, args.max_keywords)
    cities = derive_cities(args.slug)
    if args.cities:
        wanted = {c.strip() for c in args.cities.split(";")}
        cities = [c for c in cities if c["label"] in wanted]
        missing = wanted - {c["label"] for c in cities}
        if missing:
            sys.exit(f"ERROR: --cities not found among service areas: {sorted(missing)}")
    if not cities:
        sys.exit("ERROR: no cities selected (use --cities).")
    write_config(args.slug, keywords, cities)
    if not resolve_company_id(args.slug):
        print("  WARNING: no company_id resolvable — the cron will SKIP this client. "
              "Run: company-id --slug %s --set CO-..." % args.slug)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Rank AI geo-grid client setup helpers")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan"); p.add_argument("--slug", required=True)
    p.add_argument("--max-keywords", type=int, default=10); p.set_defaults(func=cmd_plan)

    p = sub.add_parser("identity"); p.add_argument("--slug", required=True)
    p.add_argument("--write", action="store_true", help="write place_id/cid into plan-input.json")
    p.set_defaults(func=cmd_identity)

    p = sub.add_parser("company-id"); p.add_argument("--slug", required=True)
    p.add_argument("--set", help="store this company_id (CO-...) on the client record")
    p.set_defaults(func=cmd_company_id)

    p = sub.add_parser("apply"); p.add_argument("--slug", required=True)
    p.add_argument("--cities", help='semicolon-separated labels, e.g. "Federal Way, WA;Tacoma, WA"')
    p.add_argument("--max-keywords", type=int, default=10); p.set_defaults(func=cmd_apply)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
