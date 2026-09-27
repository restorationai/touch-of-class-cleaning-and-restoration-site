#!/usr/bin/env python3
"""brightlocal.py — Citation Builder fleet automation (Santino 2026-09-03).

The whole recipe was proven live tonight on our own location (campaign
996268: 10 credits drawn 500->490, campaign paid, 10 quality sites
auto-selected):

  1. POST /manage/v1/locations                 (NAP from clients/{slug}.json
                                                + companies row)
  2. POST /manage/v1/citation-builder          {location_id} -> campaign_id
  3. wait for lookup_status == 'complete'      (existing-citation lookup)
  4. PUT  /manage/v1/citation-builder/{id}/confirm
         {package_id: cb10|cb15|cb25|cb30|cb50|cb75|cb100, auto_select,
          citations[], publishers[], remove_duplicates, express, notes}
         -> pays with prepaid Quick credits (1 credit = 1 citation)
  5. GET  /manage/v1/citation-builder/{id}     -> citations_submission_status
         {ordered,to_do,submitted,pending,live,...} for progress polling

Auth: x-api-key header ONLY (BRIGHTLOCAL_API_KEY). One CB campaign per
location; the first order confirms it (PUT .../confirm), every later ladder
month is a SECONDARY order on the same campaign (POST
/citation-builder/{id}/secondary-campaigns, same body as confirm; BL only
allows it once the previous order has completed). package_id cb0 =
aggregators only. Duplicate removal is a paid add-on (~20% of the package
credits). developer.brightlocal.com is a Stoplight SPA; the raw operation
specs are at stoplight.io/api/v1/projects/cHJqOjMxMzc4OA/nodes/{node_id}.

Commands:
  audit                        fleet table: who has location/campaign/ladder
  setup   --slug X [--apply]   create location + campaign for one client
  order   --slug X --month N [--confirm]   ladder month 1/2/3 (see LADDER);
          DRY-RUN by default: prints directories, aggregators, credits and
          dollars; nothing is spent without --confirm. Month 1 options:
          --aggregators-only (cb0). Overrides: --package, --publishers,
          --no-aggregators, --let-bl-pick, --express.
  status  [--slug X]           submission progress for every order
State lives in clients/{slug}.json under "brightlocal":
  {location_id, campaign_id, ordered_at, package_id, publishers,
   ladder: {"1": {...}, "2": {...}, "3": {...}}, ladder_month, last_ordered_at}
  (ordered_at/package_id/publishers = month 1, kept for older readers;
   ladder is mirrored to user_integrations[citations].bl_ladder)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENTS = ROOT / "clients"
BASE = "https://api.brightlocal.com/manage/v1"
PACKAGES = ("cb10", "cb15", "cb25", "cb30", "cb50", "cb75", "cb100")

# BrightLocal business_category_id for restoration:
# 967 = "Water damage restoration service"
# (gcid:water_damage_restoration_service — verified via
# GET /business-categories/USA?query=water+damage 2026-09-03)
DEFAULT_CATEGORY_ID = 967

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut",
    "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota",
    "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}


def _bl(method: str, path: str, body=None):
    req = urllib.request.Request(BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"x-api-key": os.environ["BRIGHTLOCAL_API_KEY"],
                 "Content-Type": "application/json",
                 # Cloudflare 403s the default Python-urllib UA (code 1010)
                 "User-Agent": "curl/8.4.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:400]
        raise RuntimeError(f"BrightLocal {method} {path} -> {e.code}: "
                           f"{detail}") from None


def load_client(slug: str) -> dict:
    return json.loads((CLIENTS / f"{slug}.json").read_text())


def save_client(slug: str, data: dict) -> None:
    (CLIENTS / f"{slug}.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def credits() -> int:
    return int(_bl("GET", "/citation-builder/credits").get("credits", 0))


def _brand_ts(slug: str) -> dict:
    """Canonical NAP source: sites/{slug}/src/lib/brand.ts (schema-grade —
    the canonical phone, never the DNI tracking number)."""
    p = ROOT / "sites" / slug / "src" / "lib" / "brand.ts"
    if not p.is_file():
        return {}
    src = p.read_text(errors="ignore")
    out = {}
    for key in ("displayName", "phone", "streetAddress", "primaryCity",
                "primaryState", "postalCode", "domain"):
        m = re.search(rf'^\s*{key}:\s*"([^"]*)"', src, re.M)
        if m:
            out[key] = m.group(1)
    return out


def nap_for(slug: str, c: dict) -> dict | None:
    """NAP payload: brand.ts first (canonical), client json fallback."""
    b = _brand_ts(slug)
    name = b.get("displayName") or c.get("display_name")
    phone = b.get("phone")
    line1 = b.get("streetAddress")
    # NAP = physical location: addressCity when the brand splits the two
    # (DryCor: primaryCity carried a typo; addressCity was right)
    city = b.get("addressCity") or b.get("primaryCity")
    region_code = b.get("primaryState")
    postcode = b.get("postalCode")
    website = b.get("domain") or c.get("domain")
    # Placeholder domains (prospect scaffolds) are never NAP truth
    if website and website.endswith(".invalid"):
        website = None
    if not all([name, phone, line1, city, region_code, postcode, website]):
        # DB fallback (2026-09-13): SAB sites hide the street address ON
        # PURPOSE, so brand.ts legitimately lacks it — the companies row
        # is the canonical NAP store (single-source law) and fills any
        # gap here. all-pro/davis/flood-fixers/homepride class.
        cid = _company_id(slug)
        row = {}
        if cid:
            try:
                row = (_sb_req("GET", f"/rest/v1/companies?id=eq.{cid}"
                               "&select=name,phone,address,city,state,"
                               "postal_code,website") or [{}])[0]
            except Exception:  # noqa: BLE001 — offline stays offline
                row = {}
        name = name or (row.get("name") or "").strip() or None
        phone = phone or (row.get("phone") or "").strip() or None
        line1 = line1 or (row.get("address") or "").strip() or None
        # PHYSICAL city beats marketing city on citations (DryCor lesson;
        # flood-fixers: primaryCity San Diego but the address is San
        # Marcos). brand.ts addressCity > DB city > brand primaryCity.
        db_city = (row.get("city") or "").strip().title() or None
        if not b.get("addressCity") and db_city:
            city = db_city
        region_code = (region_code
                       or (row.get("state") or "").strip().upper() or None)
        postcode = (postcode
                    or (row.get("postal_code") or "").split("-")[0].strip()
                    or None)
        db_web = re.sub(r"^https?://|/$", "",
                        (row.get("website") or "").strip()) or None
        website = website or db_web
    if isinstance(city, str):
        city = city.strip()
    if not all([name, phone, line1, city, region_code, postcode, website]):
        return None
    # OPENING HOURS (2026-09-12): omitting them left every location
    # defaulting to "closed" all 7 days, which several citation sites
    # reject — the campaign error Santino saw in the portal. Our clients
    # are 24/7 emergency trades; the accepted API shape (probed live) is
    # status "open" with a 00:00-23:59 span.
    day_24 = {"status": "open", "hours": [{"start": "00:00", "end": "23:59"}]}
    return {
        "business_name": name,
        "country": "USA",
        "location_reference": slug[:50],
        "business_category_id": DEFAULT_CATEGORY_ID,
        "telephone": re.sub(r"[^\d]", "", phone)[-10:],
        "address": {
            "address1": line1, "city": city,
            "region": STATE_NAMES.get(region_code.upper(), region_code),
            "region_code": region_code.upper(),
            "postcode": postcode,
        },
        "urls": {"website_url": f"https://{website}"},
        "opening_hours": {"regular": {
            "apply_to_all": True,
            **{d: day_24 for d in ("monday", "tuesday", "wednesday",
                                   "thursday", "friday", "saturday",
                                   "sunday")}}},
    }


def cmd_setup(args) -> int:
    slug = args.slug
    c = load_client(slug)
    bl = c.get("brightlocal") or {}
    if bl.get("campaign_id"):
        print(f"[{slug}] already set up: location {bl.get('location_id')}, "
              f"campaign {bl.get('campaign_id')}")
        return 0
    nap = nap_for(slug, c)
    if not nap:
        print(f"[{slug}] NAP incomplete in clients/{slug}.json — fix first")
        return 1
    print(f"[{slug}] {nap['business_name']} | {nap['address']['address1']}, "
          f"{nap['address']['city']}, {nap['address']['region_code']} "
          f"{nap['address']['postcode']} | {nap['telephone']} | "
          f"{nap['urls']['website_url']}")
    if not args.apply:
        print("  [dry-run] would create BrightLocal location + CB campaign")
        return 0
    if not bl.get("location_id"):
        res = _bl("POST", "/locations", nap)
        bl["location_id"] = res["location_id"]
        print(f"  location created: {bl['location_id']}")
    res = _bl("POST", "/citation-builder",
              {"location_id": bl["location_id"]})
    bl["campaign_id"] = res["campaign_id"]
    print(f"  campaign created: {bl['campaign_id']} (lookup runs async)")
    c["brightlocal"] = bl
    save_client(slug, c)
    return 0


def rename_gate(slug: str) -> tuple[bool, str]:
    """Citations must carry the client's FINAL name (Santino 2026-09-12:
    profile renames are a house strategy for a majority of clients, and a
    citation run under the old name bakes it into dozens of directories
    the rename then orphans). Gate = DERIVED from the Profile Rename card
    the app already renders (marketing_gbp_suggestions item_type=name):
      - a row with status 'chosen'  -> RENAMING: blocked until the live GBP
        title matches the chosen string (marketing_gbp_profiles.title,
        synced by gbp.py) -> then clear.
      - ALL name rows dismissed     -> KEEPING the name -> clear.
      - open rows / no rows         -> UNDECIDED -> blocked (fail closed).
    Manual override: integration_settings.rename_intent.decision == 'keep'.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    from client_ops_sync import _sb, slug_map
    inv = {s: c for c, s in slug_map().items()}
    cid = inv.get(slug)
    if not cid:
        return False, "no company mapping — cannot evaluate the rename gate"
    co = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}"
              "&select=integration_settings", prefer="return=representation")
          or [{}])[0]
    ints = co.get("integration_settings") or {}
    if isinstance(ints, str):
        try:
            ints = json.loads(ints)
        except (ValueError, TypeError):
            ints = {}
    intent = (ints.get("rename_intent") or {}).get("decision")
    if intent == "keep":
        return True, "rename_intent=keep (explicit board decision)"
    rows = _sb("GET", f"/rest/v1/marketing_gbp_suggestions?company_id=eq.{cid}"
               "&item_type=eq.name&select=item,status",
               prefer="return=representation") or []
    if not rows:
        if intent == "rename":
            return False, ("rename=yes but NO name candidates on record — "
                           "seed them (rank-ai-gbp-rename) and choose")
        return False, ("UNDECIDED: no name candidates on record — seed them "
                       "(rank-ai-gbp-rename) and decide before citations")
    chosen = [r for r in rows if (r.get("status") or "").lower() == "chosen"]
    if chosen:
        def norm(s):
            return re.sub(r"\s+", " ", str(s)).strip().lower()
        prof = (_sb("GET", f"/rest/v1/marketing_gbp_profiles?company_id=eq.{cid}"
                    "&select=title&limit=1", prefer="return=representation")
                or [{}])[0]
        title = prof.get("title") or ""
        if norm(title) == norm(chosen[0]["item"]):
            return True, f"rename DONE: live GBP title matches {chosen[0]['item']!r}"
        # HOUSE SEQUENCE (Santino 2026-09-12): citations run BEFORE the GBP
        # rename, not after — pre-existing citations are the corroborating
        # evidence that makes the keyworded profile edit stick. The gate
        # only needs the name to be FINAL: chosen + the DBA actually filed
        # (rename_intent.dba_filed, captured on the Citations card). The
        # order command flips the BrightLocal location's business_name to
        # the chosen string before spending a credit.
        ri = ints.get("rename_intent") or {}
        if ri.get("dba_filed"):
            # the mark binds to the exact string: a stale checkmark from a
            # since-swapped candidate must never clear the gate
            dba_name = ri.get("dba_name")
            if dba_name and norm(dba_name) != norm(chosen[0]["item"]):
                return False, (f"DBA was marked filed for {dba_name!r} but "
                               f"the chosen name is now {chosen[0]['item']!r} "
                               "— re-confirm the DBA for the current choice")
            return True, (f"NAME FINAL: {chosen[0]['item']!r} chosen + DBA "
                          "filed — citations run with the NEW name (order "
                          "updates the BL location name first); GBP rename "
                          "follows the citations")
        return False, (f"RENAMING: {chosen[0]['item']!r} chosen but the DBA "
                       "is not marked filed — file it, mark 'DBA filed' on "
                       "the Citations card, then citations run with the new "
                       "name BEFORE the GBP change")
    open_rows = [r for r in rows if (r.get("status") or "").lower()
                 not in ("dismissed",)]
    if open_rows:
        return False, (f"UNDECIDED: {len(open_rows)} name candidate(s) still "
                       "open on the Profile Rename card — choose one or "
                       "dismiss all")
    if intent == "rename":
        return False, ("rename=yes but every candidate is dismissed — "
                       "choose a name (or flip the decision to keep)")
    return True, "KEEPING the current name (all candidates dismissed)"


# ------------------------------------------------------------ order policy
# ONE place for every rule that decides what a Citation Builder order may
# contain (docs/CITATIONS-REBUILD.md §1-2). Every order path, including the
# BL-ordering fallback, goes through pick_citations() + _assert_clean().

CREDIT_USD = 2.40  # $1,200 per 500-credit bundle (Harvey Godden, 09-04)

# NEVER bought through Citation Builder, on ANY path.
EXCLUDED_DOMAINS: dict[str, str] = {
    # Santino 09-19 + rebuild rule 1: we own and API-manage every GBP; BL
    # tried to CREATE a Google listing for Dry Bros (duplicate/suspension
    # risk).
    "google.com": "we own every GBP; BL spawns duplicate Google listings",
    # Rebuild rule 3: Apple goes through Business Connect (Mini lane). Apple
    # rejects service-area businesses, and it scores DA 99 in the menu, so a
    # top-by-score pick would otherwise buy it.
    "apple.com": "Apple via Business Connect (Mini), never BL credits",
    "maps.apple.com": "Apple via Business Connect (Mini), never BL credits",
}

# Junk for a restoration trade: B2B/export marketplaces, bookmark and
# link-building farms, wrong-niche verticals. ec21.com (a B2B export
# marketplace) was top-by-DA-picked for Desert Valley on 09-27. Extend here.
JUNK_DOMAINS: dict[str, str] = {
    "ec21.com": "B2B export marketplace",
    "b2bmap.com": "B2B marketplace",
    "b2bco.com": "B2B marketplace",
    "onestopb2b.com": "B2B marketplace",
    "dealerbaba.com": "B2B wholesale marketplace",
    "trepup.com": "B2B marketplace",
    "industryhuddle.com": "B2B industrial network",
    "supplyautonomy.com": "B2B supplier directory",
    "anibookmark.com": "social bookmarking",
    "linkcentre.com": "link directory",
    "bizlinkbuilder.com": "link-building directory",
    "directory-seo.com": "SEO link directory",
    "blogbangboom.com": "blog/link farm",
    "smallbizblog.net": "blog/link farm",
    "bizcoupon.directory": "coupon directory",
    "autopros411.com": "wrong niche (automotive)",
    "selfemployedai.com": "wrong niche (freelancer AI directory)",
    # rebuild §5b: unrelated low-value site, never the YP we want (the YP
    # Network aggregator creates yellowpages.com)
    "yellowpages.net": "unrelated YP namesake (doc §5b)",
}

# Consumer/home-services + local directories get a ranking bonus over
# generic business directories of similar authority.
HOME_SERVICES_DOMAINS = {
    "yelp.com", "trustburn.com", "manta.com", "merchantcircle.com",
    "hotfrog.com", "n49.com", "citysquares.com", "ezlocal.com",
    "cylex.us.com", "brownbook.net", "provenexpert.com", "bubblelife.com",
    "trustlink.org", "chamberofcommerce.com", "cybo.com",
}
HOME_SERVICES_BONUS = 15
LOCAL_TYPE_BONUS = 10          # BL types general_+_local / local+_niche
CLIENT_VERIFY_PENALTY = 10     # sites that need the client to verify

# The per-client $100/month ladder (rebuild §1). Publishers are EXPLICIT per
# month; nothing is ever re-bought (state + live campaign are checked).
LADDER: dict[int, dict] = {
    1: {"package": "cb10",
        "publishers": ("dataaxle", "neustar", "ypnetwork"),
        "label": "rename authority wall: aggregator trio"},
    2: {"package": "cb10",
        "publishers": ("foursquare", "gpsnetwork"),
        "label": "remaining feeds + visible breadth"},
    3: {"package": "cb25", "publishers": (),
        "label": "completion top-off of the remaining scored tier"},
}
# Not SAB-supported by BL: only orderable with a VISIBLE street address.
VISIBLE_ADDRESS_ONLY_PUBS = {"foursquare", "gpsnetwork"}
# A secondary campaign can only be created once the previous one completed
# (BL docs, Create Secondary Campaign). BL stays the final arbiter.
COMPLETED_STATUSES = {"submissions_complete", "complete", "finished"}
# Fallback surcharge table (GET /packages 409s once a campaign is bought);
# live values 09-27: cb10 2, cb15 3, cb25 5, cb35 10/7, cb50 10, cb75 15.
DEDUPE_CREDITS = {"cb10": 2, "cb15": 3, "cb25": 5, "cb30": 6, "cb50": 10,
                  "cb75": 15, "cb100": 20}
EXPRESS_CREDITS = dict(DEDUPE_CREDITS)


def _norm_domain(d: str) -> str:
    d = re.sub(r"^https?://", "", str(d or "").strip().lower())
    d = d.split("/")[0].split("?")[0]
    return d[4:] if d.startswith("www.") else d


def is_excluded(domain: str) -> str | None:
    d = _norm_domain(domain)
    for bad, why in EXCLUDED_DOMAINS.items():
        if d == bad or d.endswith("." + bad):
            return why
    return None


def _assert_clean(citations: list[str]) -> None:
    """Last line of defence right before any spend call."""
    bad = [d for d in citations if is_excluded(d)
           or _norm_domain(d) in JUNK_DOMAINS]
    if bad:
        raise SystemExit(f"REFUSING: excluded/junk domain(s) in order: {bad}")


def hide_address_optout(slug: str) -> bool:
    """Rebuild rule 4: addresses VISIBLE by default. The only opt-out is a
    genuine home-address privacy case, recorded on plan-input as
    brand.citations_hide_address = true."""
    pi = CLIENTS / slug / "plan-input.json"
    try:
        return bool(((json.loads(pi.read_text()).get("brand") or {})
                     .get("citations_hide_address")))
    except (OSError, json.JSONDecodeError):
        return False


def order_notes(hide_address: bool) -> str:
    base = ("Do NOT create or submit listings on google.com or Apple Maps "
            "(maps.apple.com): we manage those directly. ")
    if hide_address:
        return base + ("Home-address privacy case: hide the street address "
                       "on directories where possible.")
    return base + ("Publish the full street address exactly as on the "
                   "location (storefront-visible NAP).")


def ladder_state(bl: dict) -> dict[str, dict]:
    """Per-client ladder ledger. Orders placed before the ladder existed
    (top-level ordered_at/package_id/publishers) count as month 1."""
    lad = {str(k): v for k, v in (bl.get("ladder") or {}).items()}
    if "1" not in lad and bl.get("ordered_at"):
        lad["1"] = {"ordered_at": bl["ordered_at"],
                    "package_id": bl.get("package_id"),
                    "publishers": bl.get("publishers") or [],
                    "campaign_id": str(bl.get("campaign_id") or ""),
                    "legacy": True}
    return lad


def campaign_facts(campaign_id) -> dict:
    """What the LIVE campaign already holds, across the primary order and
    every secondary order in campaigns[]."""
    d = _bl("GET", f"/citation-builder/{campaign_id}")
    orders = d.get("campaigns") or []
    ordered, pubs = set(), {}
    for o in orders:
        if not o.get("paid"):
            continue
        for cit in o.get("citations") or []:
            if isinstance(cit, dict) and cit.get("domain"):
                ordered.add(_norm_domain(cit["domain"]))
        for p in o.get("publishers") or []:
            if isinstance(p, dict) and p.get("type"):
                pubs[p["type"]] = p.get("expiration") or ""
    return {"detail": d, "orders": orders, "ordered_domains": ordered,
            "bought_pubs": pubs}


def known_listing_domains(slug: str) -> set[str]:
    """Rebuild rule 5: listings we already hold or found — citation_listings
    rows, the Business Listings card URLs, audit 'found' slots, BL-built."""
    cid = _company_id(slug)
    out: set[str] = set()
    if not cid:
        return out
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from listings import PLATFORMS
    except ImportError:
        PLATFORMS = {}
    try:
        rows = _sb_req("GET", f"/rest/v1/citation_listings?company_id=eq.{cid}"
                       "&select=directory,status,listing_url") or []
        for r in rows:
            if (r.get("status") or "") == "missing":
                continue
            if r.get("listing_url"):
                out.add(_norm_domain(r["listing_url"]))
            for dom in (PLATFORMS.get(r.get("directory") or "") or ("", ()))[1]:
                out.add(dom)
        md = (_sb_req("GET", "/rest/v1/user_integrations?client_id=eq." + cid
                      + "&provider=eq.citations&select=connection_metadata")
              or [{}])[0].get("connection_metadata") or {}
        for url in (md.get("citation_urls") or {}).values():
            if url:
                out.add(_norm_domain(url))
        for slot, v in (md.get("nap_audit") or {}).items():
            if isinstance(v, dict) and v.get("status") == "found":
                out.update((PLATFORMS.get(slot) or ("", ()))[1])
        out.update(_norm_domain(k) for k in (md.get("built_listings") or {}))
    except Exception as e:  # noqa: BLE001 — dedupe is best-effort, BL is not
        print(f"  (known-listing dedupe partial: {str(e)[:80]})")
    return {d for d in out if d}


def pick_citations(menu: list[dict], n: int, taken: set[str],
                   allow_non_sab: bool, bl_order: bool = False):
    """Choose n directories. Hand-pick (default): DA + home-services/local
    bonus. bl_order: BrightLocal's own menu order. EITHER WAY the exclusion
    list, junk list and dedupe apply — auto_select is never sent."""
    skipped: dict[str, list[str]] = {"excluded": [], "junk": [],
                                     "already held/ordered": [],
                                     "not SAB-supported": []}
    cands = []
    for i, a in enumerate(menu):
        d = _norm_domain(a.get("domain") or "")
        if not d:
            continue
        if is_excluded(d):
            skipped["excluded"].append(d)
            continue
        if d in JUNK_DOMAINS:
            skipped["junk"].append(d)
            continue
        if d in taken:
            skipped["already held/ordered"].append(d)
            continue
        if not allow_non_sab and a.get("is_sab_supported") is False:
            skipped["not SAB-supported"].append(d)
            continue
        da = a.get("domain_authority") or 0
        score = da
        if d in HOME_SERVICES_DOMAINS:
            score += HOME_SERVICES_BONUS
        if "local" in str(a.get("type") or ""):
            score += LOCAL_TYPE_BONUS
        if a.get("client_verification"):
            score -= CLIENT_VERIFY_PENALTY
        cands.append((i, score, da, d))
    cands.sort(key=(lambda t: t[0]) if bl_order
               else (lambda t: (-t[1], -t[2], t[3])))
    return [(d, da, score) for _i, score, da, d in cands[:n]], skipped


def _pub_credits(pubs: list[str], pinfo: dict) -> tuple[int, int, int]:
    by_id = {p["id"]: p for p in (pinfo.get("publishers") or [])}
    base = sum((by_id.get(p) or {}).get("credits") or 15 for p in pubs)
    disc = max((d["discount"] for d in (pinfo.get("discount_ladder") or [])
                if len(pubs) >= d["count"]), default=0)
    # rachelle 09-27: trio 45 credits at -5% debited 43 -> round UP
    return math.ceil(base * (100 - disc) / 100), base, disc


def _surcharges(campaign_id, package: str) -> tuple[int, int, bool]:
    """(dedupe credits, express credits, live?) for a package."""
    if package == "cb0":
        return 0, 0, True
    try:
        rows = _bl("GET", f"/citation-builder/{campaign_id}/packages").get(
            "data") or []
        for r in rows:
            if r.get("package_name") == package:
                comp = r.get("components") or {}
                return (int((comp.get("duplicates_removal") or {})
                            .get("credits") or 0),
                        int((comp.get("express") or {}).get("credits") or 0),
                        True)
    except RuntimeError:
        pass  # 409 "already purchased" on every bought campaign
    return DEDUPE_CREDITS.get(package, 0), EXPRESS_CREDITS.get(package, 0), False


def build_plan(month: int, ctx: dict, taken: set[str], bought: dict,
               args=None) -> dict:
    """Pure: what month N would order given what is already taken/bought.
    args (only for the month actually being ordered) carries overrides."""
    spec = LADDER[month]
    notes_out: list[str] = []
    pkg = (getattr(args, "package", None) or spec["package"])
    if month == 1 and getattr(args, "aggregators_only", False):
        pkg = "cb0"
    if getattr(args, "publishers", None) is not None:
        want = [p.strip() for p in args.publishers.split(",") if p.strip()]
    elif getattr(args, "no_aggregators", False):
        want = []
    else:
        want = list(spec["publishers"])
    pubs = []
    for p in want:
        if p in bought:
            notes_out.append(f"aggregator {p} already bought (expires "
                             f"{bought[p] or '?'}) — NOT re-buying")
        elif ctx["hide_address"] and p in VISIBLE_ADDRESS_ONLY_PUBS:
            notes_out.append(f"aggregator {p} skipped: address-hidden opt-out "
                             "(needs a visible street address)")
        elif not (ctx["pub_by_id"].get(p) or {}):
            notes_out.append(f"aggregator {p} not offered for this campaign")
        else:
            pubs.append(p)
    if month > 1:
        missing_trio = [p for p in LADDER[1]["publishers"] if p not in bought]
        if missing_trio and getattr(args, "publishers", None) is None:
            notes_out.append("month-1 aggregators never bought for this "
                             f"client: {', '.join(missing_trio)} (legacy "
                             "order) — add via --publishers if wanted")
    n = 0 if pkg == "cb0" else int(pkg[2:])
    picks, skipped = pick_citations(ctx["menu"], n, taken,
                                    allow_non_sab=not ctx["sab_only"],
                                    bl_order=ctx["bl_order"])
    pub_cr, pub_base, disc = _pub_credits(pubs, ctx["pinfo"])
    dd_cr, ex_cr, live = _surcharges(ctx["campaign_id"], pkg)
    ex_cr = ex_cr if getattr(args, "express", False) else 0
    total = n + pub_cr + dd_cr + ex_cr
    return {"month": month, "package": pkg, "n": n, "picks": picks,
            "skipped": skipped, "publishers": pubs, "pub_credits": pub_cr,
            "pub_base": pub_base, "discount": disc, "dedupe_credits": dd_cr,
            "express_credits": ex_cr, "surcharge_live": live,
            "total": total, "usd": round(total * CREDIT_USD, 2),
            "notes": notes_out, "short": len(picks) < n}


def _print_plan(plan: dict, title: str) -> None:
    m = plan["month"]
    print(f"  --- {title}: month {m} ({LADDER[m]['label']}) ---")
    print(f"  package: {plan['package']}"
          + (" (aggregators only, no directories)" if plan["package"] == "cb0"
             else f" -> {plan['n']} directories"))
    for i, (d, da, score) in enumerate(plan["picks"], 1):
        tag = (" [home-svc]" if d in HOME_SERVICES_DOMAINS else "")
        print(f"    {i:2}. {d:32} DA {da:3}  score {score:3}{tag}")
    if plan["short"]:
        print(f"    !! only {len(plan['picks'])} eligible directories for "
              f"{plan['n']} — drop the package size")
    for k, v in plan["skipped"].items():
        if v:
            print(f"    skipped {k}: {', '.join(sorted(set(v)))}")
    print(f"  aggregators: {', '.join(plan['publishers']) or 'none'}"
          + ((f" ({plan['pub_base']} cr, -{plan['discount']}% ladder = "
              f"{plan['pub_credits']} cr)" if plan["discount"]
              else f" ({plan['pub_credits']} cr)")
             if plan["publishers"] else ""))
    for note in plan["notes"]:
        print(f"    note: {note}")
    print(f"  credits: {plan['n']} directories + {plan['pub_credits']} "
          f"aggregators + {plan['dedupe_credits']} duplicate-removal"
          + ("" if plan["surcharge_live"] else " (table est.)")
          + (f" + {plan['express_credits']} express"
             if plan["express_credits"] else "")
          + f" = {plan['total']} credits = ${plan['usd']:.2f} "
          f"@ ${CREDIT_USD:.2f}/cr")


def _pre_spend_location_sync(slug: str, bl: dict, why: str,
                             apply: bool) -> None:
    """SYSTEM enrichment (Santino 2026-09-16) + NAME FINAL flip: every order
    self-enriches the BL location (description, services, socials,
    contact) and, when the rename gate cleared on NAME FINAL, sets the
    location's business_name to the chosen string (house sequence: DBA ->
    citations -> ONE GBP change). apply=False only reports."""
    try:
        print("  " + enrich_location(slug, apply=apply))
    except Exception as e:  # noqa: BLE001 — never blocks an order
        print(f"  (enrich warn: {str(e)[:80]})")
    if "NAME FINAL" not in why or not bl.get("location_id"):
        return
    m = re.search(r"NAME FINAL: '([^']+)'", why)
    if not m:
        return
    new_name = m.group(1)
    # BrightLocal hard-caps business_name at 90 chars (Kenny 2026-09-19:
    # his 94-char chosen name 400'd the whole order). Trim at a word
    # boundary; the full string stays canonical everywhere else.
    if len(new_name) > 90:
        cut = new_name[:90]
        cut = cut[:cut.rfind(" ")].rstrip(" ,;-&")
        print(f"  NAME >90 chars for directories — trimmed to {cut!r} "
              f"({len(cut)})")
        new_name = cut
    loc = _bl("GET", f"/locations/{bl['location_id']}")
    cur = ((loc.get("location") or loc) or {}).get("business_name") or ""
    if cur.strip().lower() == new_name.strip().lower():
        return
    if apply:
        _bl("PUT", f"/locations/{bl['location_id']}",
            {"business_name": new_name})
        print(f"  BL location name updated: {cur!r} -> {new_name!r}")
    else:
        print(f"  would update BL location name: {cur!r} -> {new_name!r}")


def cmd_order(args) -> int:
    slug, month = args.slug, args.month
    confirm = bool(args.confirm)
    if args.package and args.package not in PACKAGES + ("cb0",):
        print(f"package must be one of {PACKAGES + ('cb0',)}")
        return 1
    print(f"[{slug}] ORDER month {month} — "
          + ("CONFIRM: credits WILL be spent" if confirm
             else "DRY-RUN: nothing is ordered (add --confirm to spend)"))
    blockers: list[str] = []
    ok, why = rename_gate(slug)
    print(f"  rename gate: {'CLEAR' if ok else 'BLOCKED'} — {why}")
    if not ok:
        blockers.append("rename gate")
    c = load_client(slug)
    bl = c.get("brightlocal") or {}
    if not bl.get("campaign_id"):
        print(f"[{slug}] no campaign — run setup first")
        return 1
    # Location sync (enrich + final-name flip) is REPORTED here and only
    # APPLIED after every blocker has cleared, right before the spend.
    _pre_spend_location_sync(slug, bl, why if ok else "", apply=False)
    lad = ladder_state(bl)
    if str(month) in lad:
        e = lad[str(month)]
        print(f"[{slug}] month {month} already ordered {e.get('package_id')} "
              f"at {e.get('ordered_at')} — refusing (never re-order a month)")
        return 1
    camp_id = bl["campaign_id"]
    facts = campaign_facts(camp_id)
    detail = facts["detail"]
    primary_paid = any(o.get("paid") for o in facts["orders"])
    if month == 1 and primary_paid:
        print(f"[{slug}] the campaign already holds a paid order but the "
              f"ladder has no month 1 — reconcile clients/{slug}.json first")
        return 1
    if month == 1 and detail.get("lookup_status") != "complete":
        blockers.append(f"citation lookup still {detail.get('lookup_status')}")
    try:
        loc = _bl("GET", f"/locations/{bl['location_id']}")
        loc = loc.get("location") or loc
    except RuntimeError:
        loc = {}
    hide = hide_address_optout(slug)
    pinfo = _bl("GET", f"/citation-builder/{camp_id}/publishers")
    menu = _bl("GET", f"/citation-builder/{camp_id}/citations").get("data") or []
    ctx = {"menu": menu, "pinfo": pinfo, "campaign_id": camp_id,
           "pub_by_id": {p["id"]: p for p in (pinfo.get("publishers") or [])},
           "hide_address": hide,
           "sab_only": hide or bool(loc.get("is_service_area_business")),
           "bl_order": not args.pick_top}
    known = known_listing_domains(slug)
    taken = set(facts["ordered_domains"]) | known
    for e in lad.values():
        taken.update(_norm_domain(d) for d in (e.get("citations") or []))
    bought = dict(facts["bought_pubs"])
    for e in lad.values():
        for p in e.get("publishers") or []:
            bought.setdefault(p, "")
    print(f"  address: {'HIDDEN (plan-input opt-out)' if hide else 'VISIBLE'}"
          f" | BL location SAB flag: {loc.get('is_service_area_business')}")
    print(f"  already ordered on BL: {len(facts['ordered_domains'])} "
          f"directories, aggregators {sorted(bought) or 'none'}; "
          f"{len(known)} listing domains on file (dedupe)")
    # Earlier months not yet ordered: dry-run projects them first so the
    # target month is shown net of them; --confirm refuses.
    for prev in range(1, month):
        if str(prev) in lad:
            continue
        blockers.append(f"month {prev} not ordered yet")
        pplan = build_plan(prev, ctx, taken, bought)
        _print_plan(pplan, "PROJECTED prerequisite (not ordered)")
        taken.update(d for d, _da, _s in pplan["picks"])
        bought.update({p: "(projected)" for p in pplan["publishers"]})
    if month > 1:
        last = next((o for o in reversed(facts["orders"]) if o.get("paid")),
                    None)
        st = (last or {}).get("status")
        if st not in COMPLETED_STATUSES:
            blockers.append(
                f"previous BL order {(last or {}).get('campaign_id')} is "
                f"'{st}' (est. completion "
                f"{((last or {}).get('dates') or {}).get('completion_date')})"
                " — BL only allows a secondary campaign once it completes")
    plan = build_plan(month, ctx, taken, bought, args)
    _print_plan(plan, "THIS ORDER")
    bal = credits()
    print(f"  balance: {bal} credits -> {bal - plan['total']} after")
    if bal < plan["total"]:
        blockers.append("insufficient credits")
    if plan["short"]:
        blockers.append("not enough eligible directories")
    if plan["total"] == 0:
        blockers.append("nothing to order")
    citations_out = [d for d, _da, _s in plan["picks"]]
    body = {"package_id": plan["package"], "auto_select": False,
            "citations": citations_out, "publishers": plan["publishers"],
            # rebuild §2: always on for directory packages (+~20% credits,
            # BL finds+suppresses duplicate listings on the ordered sites).
            # cb0 has no directories to dedupe (no surcharge component).
            "remove_duplicates": plan["package"] != "cb0",
            "express": bool(args.express),
            "notes": order_notes(hide)}
    endpoint = (f"PUT /citation-builder/{camp_id}/confirm" if month == 1
                else f"POST /citation-builder/{camp_id}/secondary-campaigns")
    print(f"  would call: {endpoint}")
    print(f"  remove_duplicates={body['remove_duplicates']} | notes: "
          f"{body['notes']}")
    if blockers:
        print(f"  BLOCKERS: {'; '.join(blockers)}")
    if not confirm:
        print("  [dry-run] nothing ordered. Re-run with --confirm once this "
              "month is approved.")
        return 0 if not blockers else 2
    if blockers:
        print("  refusing to spend")
        return 1
    _assert_clean(citations_out)
    _pre_spend_location_sync(slug, bl, why, apply=True)
    before = {str(o.get("campaign_id")) for o in facts["orders"]}
    if month == 1:
        res = _bl("PUT", f"/citation-builder/{camp_id}/confirm", body)
    else:
        res = _bl("POST", f"/citation-builder/{camp_id}/secondary-campaigns",
                  body)
    after = campaign_facts(camp_id)
    new = [o for o in after["orders"] if str(o.get("campaign_id")) not in before]
    order = (new or after["orders"][:1])[0] if after["orders"] else {}
    left = credits()
    print(f"  paid: {order.get('paid')} | order {order.get('campaign_id')} "
          f"| ordered: {order.get('citations_ordered')} | credits left: {left}"
          f" (spent {bal - left})")
    now = datetime.now(timezone.utc).isoformat()
    lad[str(month)] = {
        "ordered_at": now, "package_id": plan["package"],
        "citations": citations_out, "publishers": plan["publishers"],
        "credits_est": plan["total"], "credits_spent": bal - left,
        "usd": round((bal - left) * CREDIT_USD, 2),
        "campaign_id": str(order.get("campaign_id") or camp_id),
        "parent_campaign_id": str(camp_id),
        "remove_duplicates": body["remove_duplicates"],
        "express": body["express"],
        "response": res if isinstance(res, dict) and len(str(res)) < 800
        else str(res)[:800],
    }
    bl["ladder"] = {k: v for k, v in lad.items()}
    bl["ladder_month"] = month
    bl["last_ordered_at"] = now
    if month == 1:  # legacy keys other scripts read (watchdog, rename)
        bl["ordered_at"] = now
        bl["package_id"] = plan["package"]
        bl["publishers"] = plan["publishers"]
    c["brightlocal"] = bl
    save_client(slug, c)
    cid = _company_id(slug)
    if cid:
        try:
            _merge_citations_meta(cid, lambda md: md.__setitem__(
                "bl_ladder", bl["ladder"]))
        except Exception as e:  # noqa: BLE001
            print(f"  (bl_ladder meta mirror failed: {str(e)[:80]})")
        parts = []
        if plan["n"]:
            parts.append(f"{plan['n']} new business listings")
        if plan["publishers"]:
            parts.append(f"{len(plan['publishers'])} data-aggregator "
                         "submissions (the feeds maps and directories copy)")
        _work_log(cid, "citations-building",
                  f"Building {' and '.join(parts)} for your company. Each "
                  "one will be listed here and in your Listings view as it "
                  "goes live over the next few weeks",
                  {"campaign_id": camp_id, "ladder_month": month,
                   "package_id": plan["package"],
                   "publishers": plan["publishers"],
                   "credits_spent": bal - left})
    return 0


def _sb_req(method: str, path: str, body=None, prefer="return=representation"):
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    req = urllib.request.Request(
        os.environ["SUPABASE_URL"].rstrip("/") + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Prefer": prefer})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


def _merge_citations_meta(cid: str, mutate) -> None:
    """Read-modify-write the company's citations integration metadata (the
    same row the app's Business Listings card reads). mutate(md) edits in
    place. Creates the row when missing. Never clobbers keys it doesn't
    touch."""
    now = datetime.now(timezone.utc).isoformat()
    rows = _sb_req("GET", "/rest/v1/user_integrations?client_id=eq." + cid
                   + "&provider=eq.citations&select=id,connection_metadata") or []
    if rows:
        md = rows[0].get("connection_metadata") or {}
        mutate(md)
        _sb_req("PATCH", f"/rest/v1/user_integrations?id=eq.{rows[0]['id']}",
                {"connection_metadata": md, "updated_at": now},
                prefer="return=minimal")
    else:
        md = {}
        mutate(md)
        _sb_req("POST", "/rest/v1/user_integrations", {
            "client_id": cid, "provider": "citations", "status": "active",
            "connection_metadata": md}, prefer="return=minimal")


def _company_id(slug: str) -> str | None:
    try:
        cmap = json.loads((CLIENTS / "company_map.json").read_text())
        return cmap.get(slug)
    except (OSError, json.JSONDecodeError):
        return None


def _work_log(cid: str, action: str, detail: str, evidence=None) -> None:
    """One client-readable activity line — the same feed the app's activity
    view and monthly summaries read. Never fatal."""
    try:
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        req = urllib.request.Request(
            os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/marketing_work_log",
            data=json.dumps({
                "company_id": cid, "actor": "restoration-ai",
                "category": "citations", "action": action,
                "detail": detail, "evidence": evidence or {},
            }).encode(),
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Content-Type": "application/json",
                     "Prefer": "return=minimal"})
        urllib.request.urlopen(req, timeout=20)
    except Exception as e:  # noqa: BLE001
        print(f"  (work_log failed: {str(e)[:80]})")


def cmd_sync(_args) -> int:
    """Nightly: poll every ordered campaign's per-citation status; log every
    NEWLY LIVE citation to the activity feed and the app's Business Listings
    card (listings.record_listing). Idempotent via the synced_live ledger in
    clients/{slug}.json brightlocal state."""
    for f in sorted(CLIENTS.glob("*.json")):
        try:
            c = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        if not isinstance(c, dict):
            continue
        bl = c.get("brightlocal") or {}
        # campaign without an order still syncs its acquirable-directory menu
        # (fleet rollout 2026-09-04: every client's card shows the menu)
        if not bl.get("campaign_id"):
            continue
        slug = f.stem
        cid = _company_id(slug)
        d = _bl("GET", f"/citation-builder/{bl['campaign_id']}")
        synced = set(bl.get("synced_live") or [])
        ordered_rows, new_live = [], []
        # primary + every secondary (ladder months 2/3) order
        all_cits = [cit for camp in (d.get("campaigns") or [])
                    for cit in (camp.get("citations") or [])]
        for cit in all_cits:
            if not isinstance(cit, dict):
                continue
            domain = cit.get("domain") or cit.get("site")
            if not domain:
                continue
            status = str(cit.get("status") or "").lower()
            url = (cit.get("profile_url") or cit.get("url")
                   or cit.get("live_url") or "")
            ordered_rows.append({"domain": domain, "status": status,
                                 "url": url})
            if status in ("live", "updated") and domain not in synced:
                new_live.append((domain, url))
        # availability menu (for the superadmin ranked panel), DA descending
        try:
            avail = _bl("GET", f"/citation-builder/{bl['campaign_id']}"
                        "/citations").get("data") or []
        except RuntimeError:
            avail = []
        avail_rows = sorted(
            ({"domain": a.get("domain"),
              "da": a.get("domain_authority") or 0,
              "sab": a.get("is_sab_supported"),
              "type": a.get("type")}
             for a in avail if a.get("domain")),
            key=lambda r: -r["da"])
        if cid:
            now = datetime.now(timezone.utc).isoformat()

            def mut(md, _now=now, _ordered=ordered_rows, _avail=avail_rows,
                    _live=new_live):
                built = dict(md.get("built_listings") or {})
                for domain, url in _live:
                    prev = built.get(domain) or {}
                    built[domain] = {
                        "url": url or prev.get("url") or "",
                        "status": "live",
                        "created_at": prev.get("created_at") or _now,
                        "source": "restoration_ai",
                    }
                md["built_listings"] = built
                md["bl_ordered"] = _ordered
                md["bl_available"] = _avail
                md["bl_available_updated_at"] = _now

            try:
                _merge_citations_meta(cid, mut)
            except Exception as e:  # noqa: BLE001
                print(f"  (citations meta merge failed: {str(e)[:100]})")
        if not new_live:
            continue
        print(f"[{slug}] {len(new_live)} newly live citation(s)")
        # domains matching a NAMED app slot (Yelp, Apple Maps, BBB...) fill
        # that slot via record_listing (URL input + audit entry + its own
        # ledger line); everything else logs here and lives in
        # built_listings (Santino 2026-09-04: live URLs must land in the
        # right citation source automatically).
        try:
            sys.path.insert(0, str(ROOT / "scripts"))
            from listings import PLATFORMS as _APP_SLOTS, record_listing
        except ImportError:
            _APP_SLOTS, record_listing = {}, None
        for domain, url in new_live:
            if cid:
                slot = next((k for k, (_lbl, doms) in _APP_SLOTS.items()
                             if any(d in domain or domain in d
                                    for d in doms)), None)
                slotted = False
                if slot and url and record_listing:
                    try:
                        slotted = record_listing(cid, slot, url)
                    except Exception as e:  # noqa: BLE001
                        print(f"  (slot write {slot}: {str(e)[:80]})")
                if not slotted:
                    _work_log(cid, "citation-live",
                              f"New business listing built for you on {domain}"
                              + (f": {url}" if url else ""),
                              {"domain": domain, "url": url,
                               "campaign_id": bl["campaign_id"]})
            synced.add(domain)
        bl["synced_live"] = sorted(synced)
        c["brightlocal"] = bl
        save_client(slug, c)
    _backfill_generic_menu()
    # SYSTEM enrichment sweep (Santino 2026-09-16): every location with a
    # shell re-enriches nightly, so socials confirmed or bios written after
    # setup flow into BL automatically before any future order.
    class _A:  # minimal args shim
        slug = None
        dry_run = False
    try:
        cmd_enrich(_A())
    except Exception as e:  # noqa: BLE001
        print(f"(fleet enrich warn: {str(e)[:80]})")
    return 0


def _backfill_generic_menu() -> None:
    """Every ACTIVE client's Business Listings card shows the upcoming-build
    projection, shell or no shell (Santino 2026-09-15, Desert Valley support
    call: the list stopped after ContractorsRanked because bl_available only
    existed for clients with a BrightLocal campaign). The acquirable-
    directory menu is effectively identical across US SAB clients, so
    clients without a campaign inherit the freshest synced menu, marked
    source=generic; a real campaign sync later overwrites it in place."""
    rows = _sb_req("GET", "/rest/v1/user_integrations?provider=eq.citations"
                   "&select=client_id,connection_metadata") or []
    freshest, freshest_at = None, ""
    have: dict = {}
    for r in rows:
        md = r.get("connection_metadata") or {}
        have[r["client_id"]] = bool(md.get("bl_available"))
        at = md.get("bl_available_updated_at") or ""
        if md.get("bl_available") and at > freshest_at \
                and md.get("bl_available_source") != "generic":
            freshest, freshest_at = md["bl_available"], at
    if not freshest:
        return
    comps = _sb_req("GET", "/rest/v1/companies?status=eq.Active"
                    "&select=id") or []
    now = datetime.now(timezone.utc).isoformat()
    n = 0
    for co in comps:
        cid = co["id"]
        if have.get(cid):
            continue

        def mut(md, _menu=freshest, _now=now):
            if md.get("bl_available"):
                return
            md["bl_available"] = _menu
            md["bl_available_updated_at"] = _now
            md["bl_available_source"] = "generic"

        try:
            _merge_citations_meta(cid, mut)
            n += 1
        except Exception as e:  # noqa: BLE001
            print(f"  (generic menu {cid}: {str(e)[:80]})")
    if n:
        print(f"generic directory menu backfilled for {n} client(s)")


# ---------------------------------------------------------------- enrich
def _enrich_payload(slug: str, c: dict) -> dict:
    """Everything beyond NAP that makes a citation rich, from the canonical
    stores (Santino 2026-09-16: BL's own UI says richer locations produce
    richer listings; description/socials/services/contact were all empty).
    Truth law: only facts we actually hold — no defaults invented."""
    cid = _company_id(slug)
    payload: dict = {}
    co = {}
    if cid:
        rows = _sb_req("GET", f"/rest/v1/companies?id=eq.{cid}"
                       "&select=bio,services,email,integration_settings") or []
        co = rows[0] if rows else {}
    # description: companies.bio, else the GBP business description
    # (client-approved, written for local search, same 750 limit —
    # Santino 2026-09-16), else plan-input brand description
    desc = (co.get("bio") or "").strip()
    if not desc and cid:
        gp = _sb_req("GET", f"/rest/v1/marketing_gbp_profiles?company_id="
                     f"eq.{cid}&select=description") or []
        desc = ((gp[0].get("description") if gp else "") or "").strip()
    if not desc:
        pi = CLIENTS / slug / "plan-input.json"
        if pi.exists():
            try:
                desc = ((json.loads(pi.read_text()).get("brand") or {})
                        .get("description") or "").strip()
            except (json.JSONDecodeError, OSError):
                pass
    if desc:
        payload["description"] = desc[:750]
    # services (names only)
    # BL validation: max 5 services, and long strings get rejected on some
    # locations — keep the 5 highest-priority, each trimmed to 50 chars.
    svcs = [str(x).strip()[:50] for x in (co.get("services") or []) if x]
    if svcs:
        payload["services_or_products"] = svcs[:5]
    # socials: confirmed rows from the Connect card
    if cid:
        socs = _sb_req("GET", "/rest/v1/citation_listings"
                       f"?company_id=eq.{cid}&kind=eq.social"
                       "&social_state=in.(confirmed,connected_to_gsc)"
                       "&select=directory,listing_url") or []
        sp = {}
        keymap = {"facebook": "facebook_url", "instagram": "instagram_url",
                  "linkedin": "linkedin_url", "youtube": "youtube_url",
                  "tiktok": "tiktok_url", "x": "x_url",
                  "twitter": "x_url", "pinterest": "pinterest_url"}
        for r in socs:
            k = keymap.get(str(r.get("directory") or "").lower())
            if k and r.get("listing_url"):
                sp[k] = r["listing_url"]
        if sp:
            payload["social_profiles"] = sp
    # contact: the preferred human on the card
    ints = co.get("integration_settings") or {}
    pref = next((x for x in (ints.get("contacts") or [])
                 if x.get("preferred")), None) or         next(iter(ints.get("contacts") or []), None)
    if pref and (pref.get("first_name") or pref.get("email")):
        import re as _re
        def _name_ok(v):  # BL rejects empty/odd name strings
            return bool(v) and bool(_re.fullmatch(r"[A-Za-z][A-Za-z .'-]{0,39}", str(v).strip()))
        payload["contact"] = {
            k: str(v).strip() for k, v in {
                "first_name": pref.get("first_name"),
                "last_name": pref.get("last_name"),
                "email": pref.get("email") or co.get("email"),
            }.items()
            if v and (k == "email" or _name_ok(v))}
        if not payload["contact"]:
            payload.pop("contact")
    return payload


def enrich_location(slug: str, apply: bool = True) -> str:
    """Push the enrichment payload to the BL location. Partial PUT — only
    fields we hold get written; nothing is blanked. Called automatically
    from cmd_order (pre-payment) and the nightly sweep."""
    c = load_client(slug)
    bl = c.get("brightlocal") or {}
    loc = bl.get("location_id")
    if not loc:
        return f"[{slug}] no BL location — nothing to enrich"
    payload = _enrich_payload(slug, c)
    if not payload:
        return f"[{slug}] no enrichment data on file yet"
    fields = ", ".join(sorted(payload.keys()))
    if not apply:
        return f"[{slug}] would enrich location {loc}: {fields}"
    _bl("PUT", f"/locations/{loc}", payload)
    return f"[{slug}] location {loc} enriched: {fields}"


def cmd_enrich(args) -> int:
    """Enrich one client (--slug) or the whole fleet (--all). Fleet mode
    rides the nightly sync so locations stay current as client data
    improves (socials confirmed later, bio written later)."""
    if getattr(args, "slug", None):
        print(enrich_location(args.slug, apply=not args.dry_run))
        return 0
    for f in sorted(CLIENTS.glob("*.json")):
        try:
            c = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        if not isinstance(c, dict) or not (c.get("brightlocal") or {}).get("location_id"):
            continue
        try:
            out = enrich_location(f.stem, apply=not args.dry_run)
            if "no enrichment data" not in out:
                print(out)
        except Exception as e:  # noqa: BLE001 — one client never kills the sweep
            print(f"[{f.stem}] enrich failed: {str(e)[:100]}")
    return 0


def cmd_status(args) -> int:
    for f in sorted(CLIENTS.glob("*.json")):
        if f.name in ("company_map.json",):
            continue
        try:
            c = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        bl = c.get("brightlocal") or {}
        if not bl.get("campaign_id"):
            continue
        if args.slug and f.stem != args.slug:
            continue
        d = _bl("GET", f"/citation-builder/{bl['campaign_id']}")
        for camp in d.get("campaigns") or []:
            s = camp.get("citations_submission_status") or {}
            print(f"{f.stem:42} {camp.get('campaign_id')!s:8} "
                  f"{camp.get('status')!s:8} "
                  f"ordered={s.get('ordered')} submitted={s.get('submitted')} "
                  f"pending={s.get('pending')} live={s.get('live')}")
    return 0


def cmd_audit(_args) -> int:
    print(f"credits available: {credits()}\n")
    rows = []
    for f in sorted(CLIENTS.glob("*.json")):
        try:
            c = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        if not isinstance(c, dict) or not c.get("display_name"):
            continue
        bl = c.get("brightlocal") or {}
        nap_ok = nap_for(f.stem, c) is not None
        lad = ladder_state(bl)
        rows.append((f.stem, nap_ok, bl.get("location_id"),
                     bl.get("campaign_id"),
                     "+".join(f"m{k}:{v.get('package_id')}"
                              for k, v in sorted(lad.items()))))
    for slug, nap_ok, loc, camp, pkg in rows:
        state = (f"ladder {pkg}" if pkg else "campaign ready" if camp
                 else "location only" if loc
                 else "NAP ready" if nap_ok else "NAP INCOMPLETE")
        print(f"  {slug:44} {state}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("audit")
    ps = sub.add_parser("setup")
    ps.add_argument("--slug", required=True)
    ps.add_argument("--apply", action="store_true")
    po = sub.add_parser("order")
    po.add_argument("--slug", required=True)
    po.add_argument("--month", type=int, required=True, choices=(1, 2, 3),
                    help="ladder month: 1 = primary order (aggregator trio "
                         "+ cb10), 2 = secondary (foursquare+gpsnetwork + "
                         "cb10), 3 = secondary (cb25 top-off)")
    po.add_argument("--package", default=None,
                    help="override the month's default package (cb10/cb25/"
                         "...; cb0 = aggregators only)")
    po.add_argument("--aggregators-only", action="store_true",
                    help="month 1 only: cb0 package, the aggregator trio "
                         "with no directories")
    po.add_argument("--express", action="store_true")
    # DEFAULT is hand-pick (Santino 2026-09-13: "we choose the sources").
    # BL's auto_select is NEVER sent: --let-bl-pick takes BL's own menu
    # order but still passes an explicit, exclusion-filtered list.
    po.add_argument("--pick-top", action="store_true", default=True,
                    help="hand-pick by DA + home-services/local bonus "
                         "(DEFAULT)")
    po.add_argument("--let-bl-pick", dest="pick_top", action="store_false",
                    help="use BrightLocal's menu order (exclusions, junk "
                         "list and dedupe still apply)")
    po.add_argument("--publishers", default=None,
                    help="comma list overriding the month's aggregators "
                         "(already-bought ones are still never re-bought)")
    po.add_argument("--no-aggregators", action="store_true",
                    help="skip the month's aggregator submissions")
    # FREEZE GUARD: dry-run is the default; spending needs --confirm.
    po.add_argument("--confirm", action="store_true",
                    help="actually place the order and spend credits")
    pt = sub.add_parser("status")
    pt.add_argument("--slug")
    sub.add_parser("sync")
    pe = sub.add_parser("enrich")
    pe.add_argument("--slug")
    pe.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.cmd == "setup":
        return cmd_setup(args)
    if args.cmd == "order":
        return cmd_order(args)
    if args.cmd == "status":
        return cmd_status(args)
    if args.cmd == "sync":
        return cmd_sync(args)
    if args.cmd == "enrich":
        return cmd_enrich(args)
    return cmd_audit(args)


if __name__ == "__main__":
    sys.exit(main())
