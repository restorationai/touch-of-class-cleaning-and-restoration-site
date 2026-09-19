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
location. Top-ups after the first order go via create-secondary-campaign
(not yet wired). Aggregator (publisher) submissions cost extra credits, we
default to none. developer.brightlocal.com docs are a JS-only SPA: render
with playwright, plain curl gets a stub.

Commands:
  audit                        fleet table: who has location/campaign/order
  setup   --slug X [--apply]   create location + campaign for one client
  order   --slug X --package cb25 [--express] [--apply]   spend credits
  status  [--slug X]           submission progress for ordered campaigns
State lives in clients/{slug}.json under "brightlocal":
  {location_id, campaign_id, ordered_at, package_id}
"""
from __future__ import annotations

import argparse
import json
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


def cmd_order(args) -> int:
    slug = args.slug
    if args.package not in PACKAGES:
        print(f"package must be one of {PACKAGES}")
        return 1
    ok, why = rename_gate(slug)
    print(f"[{slug}] rename gate: {'CLEAR' if ok else 'BLOCKED'} — {why}")
    if not ok:
        return 1
    # SYSTEM enrichment (Santino 2026-09-16): every order self-enriches the
    # location first — description, services, socials, contact — so no
    # campaign ever submits a bare-NAP listing again. Never blocks an order.
    try:
        print("  " + enrich_location(slug, apply=args.apply))
    except Exception as e:  # noqa: BLE001
        print(f"  (enrich warn: {str(e)[:80]})")
    c = load_client(slug)
    bl = c.get("brightlocal") or {}
    # NAME FINAL but GBP not yet renamed: the citations must print the NEW
    # name — flip the BrightLocal location's business_name to the chosen
    # string before a single credit is spent (house sequence: DBA ->
    # citations -> ONE GBP change).
    if "NAME FINAL" in why and bl.get("location_id"):
        m = re.search(r"NAME FINAL: '([^']+)'", why)
        if m:
            new_name = m.group(1)
            # BrightLocal hard-caps business_name at 90 chars (Kenny
            # 2026-09-19: his 94-char chosen name 400'd the whole order).
            # Trim at a word boundary and say so loudly — the directories
            # carry the closest printable variant of the DBA name; the
            # full string stays canonical everywhere else.
            if len(new_name) > 90:
                cut = new_name[:90]
                cut = cut[:cut.rfind(" ")].rstrip(" ,;-&")
                print(f"  NAME >90 chars for directories — trimmed to "
                      f"{cut!r} ({len(cut)})")
                new_name = cut
            loc = _bl("GET", f"/locations/{bl['location_id']}")
            cur = ((loc.get("location") or loc) or {}).get("business_name") or ""
            if cur.strip().lower() != new_name.strip().lower():
                _bl("PUT", f"/locations/{bl['location_id']}",
                    {"business_name": new_name})
                print(f"  BL location name updated: {cur!r} -> {new_name!r}")
    if not bl.get("campaign_id"):
        print(f"[{slug}] no campaign — run setup first")
        return 1
    if bl.get("ordered_at"):
        print(f"[{slug}] already ordered {bl.get('package_id')} at "
              f"{bl['ordered_at']} — top-ups need the secondary-campaign "
              "flow (unwired); refusing")
        return 1
    cid = bl["campaign_id"]
    detail = _bl("GET", f"/citation-builder/{cid}")
    if detail.get("lookup_status") != "complete":
        print(f"[{slug}] citation lookup still "
              f"{detail.get('lookup_status')} — try again in a few minutes")
        return 1
    bal = credits()
    cost = int(args.package[2:])
    # A3 (Santino 2026-09-16): data-aggregator submissions ride EVERY order
    # by default — Data Axle, Neustar/Localeze and YP Network push the (new)
    # NAP into the feeds Google and the directories cross-check: the deepest
    # layer of the rename evidence stack, and the first thing that
    # propagates a DBA beyond the sites we hand-pick. SAB-supported only:
    # Foursquare and GPS Network are not, and this fleet is service-area
    # businesses with hidden addresses. 15 credits each, ladder discount
    # from 3 up. --no-aggregators opts out; --publishers overrides.
    pinfo = _bl("GET", f"/citation-builder/{cid}/publishers")
    by_id = {p["id"]: p for p in (pinfo.get("publishers") or [])}
    if args.publishers is not None:
        pubs = [p.strip() for p in args.publishers.split(",") if p.strip()]
        not_sab = [p for p in pubs
                   if not (by_id.get(p) or {}).get("is_sab_supported")]
        if not_sab:
            print(f"  WARNING: not SAB-supported: {', '.join(not_sab)}")
    elif args.no_aggregators:
        pubs = []
    else:
        pubs = [p for p in ("dataaxle", "neustar", "ypnetwork")
                if (by_id.get(p) or {}).get("is_sab_supported")]
    pub_credits = sum((by_id.get(p) or {}).get("credits") or 15 for p in pubs)
    disc = max((d["discount"] for d in (pinfo.get("discount_ladder") or [])
                if len(pubs) >= d["count"]), default=0)
    total = cost + pub_credits
    print(f"[{slug}] campaign {cid}: ordering {args.package} "
          f"({cost} credits)"
          + (f" + aggregators {'+'.join(pubs)} ({pub_credits} credits"
             + (f", -{disc}% ladder" if disc else "") + ")" if pubs else "")
          + f" | {total} of {bal} available"
          + (" EXPRESS" if args.express else ""))
    if bal < total:
        print("  insufficient credits — refusing")
        return 1
    if not args.apply:
        print("  [dry-run] would confirm with credits")
        return 0
    picked: list[str] = []
    # NEVER submit google.com through Citation Builder (Santino 2026-09-19:
    # "definitely exclude Google"). We hold owner access + API write on every
    # client's GBP and execute the rename ourselves — BL's Google line only
    # adds an owner-verification chore for a surface we already control.
    # yelp.com stays IN pending Santino's separate call on it.
    pick_exclude = {"google.com"}
    if args.pick_top:
        # Hand-pick: highest domain-authority SAB-supported sites first
        # (Santino 2026-09-03: we choose the sources, not their picker)
        avail = _bl("GET", f"/citation-builder/{cid}/citations").get("data") or []
        ranked = sorted(
            (a for a in avail if a.get("is_sab_supported") is not False
             and a.get("domain") not in pick_exclude),
            key=lambda a: -(a.get("domain_authority") or 0))
        picked = [a["domain"] for a in ranked[:cost]]
        print(f"  hand-picked top {len(picked)} by DA: "
              + ", ".join(picked[:8]) + (" ..." if len(picked) > 8 else ""))
        if len(picked) < cost:
            print(f"  only {len(picked)} SAB-suitable sites available — "
                  "refusing (drop the package size)")
            return 1
    _bl("PUT", f"/citation-builder/{cid}/confirm", {
        "package_id": args.package, "auto_select": not picked,
        "citations": picked, "publishers": pubs,
        "remove_duplicates": False, "express": bool(args.express),
        "notes": "Service-area business (SAB): hide the street address on "
                 "directories where possible.",
    })
    after = _bl("GET", f"/citation-builder/{cid}")["campaigns"][0]
    print(f"  paid: {after['paid']} | ordered: {after['citations_ordered']} "
          f"| credits left: {credits()}")
    bl["ordered_at"] = datetime.now(timezone.utc).isoformat()
    bl["package_id"] = args.package
    bl["publishers"] = pubs
    c["brightlocal"] = bl
    save_client(slug, c)
    cid = _company_id(slug)
    if cid:
        _work_log(cid, "citations-building",
                  f"Building {cost} new business listings for your company. "
                  "Each one will be listed here and in your Listings view "
                  "as it goes live over the next few weeks",
                  {"campaign_id": bl["campaign_id"],
                   "package_id": args.package, "credits_spent": cost})
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
        camp = d["campaigns"][0]
        synced = set(bl.get("synced_live") or [])
        ordered_rows, new_live = [], []
        for cit in camp.get("citations") or []:
            if not isinstance(cit, dict):
                continue
            domain = cit.get("domain") or cit.get("site")
            if not domain:
                continue
            status = str(cit.get("status") or "").lower()
            url = cit.get("url") or cit.get("live_url") or ""
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
        camp = d["campaigns"][0]
        s = camp["citations_submission_status"]
        print(f"{f.stem:42} {camp['status']:8} "
              f"ordered={s['ordered']} submitted={s['submitted']} "
              f"pending={s['pending']} live={s['live']}")
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
        rows.append((f.stem, nap_ok, bl.get("location_id"),
                     bl.get("campaign_id"), bl.get("package_id")))
    for slug, nap_ok, loc, camp, pkg in rows:
        state = (f"ordered {pkg}" if pkg else "campaign ready" if camp
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
    po.add_argument("--package", required=True)
    po.add_argument("--express", action="store_true")
    # DEFAULT is hand-pick (Santino 2026-09-13: "we choose the sources" —
    # BL's auto-select must never run by accident; opting into it takes an
    # explicit flag).
    po.add_argument("--pick-top", action="store_true", default=True,
                    help="hand-pick highest-DA SAB sites (DEFAULT)")
    po.add_argument("--let-bl-pick", dest="pick_top", action="store_false",
                    help="let BrightLocal auto-select the sites instead")
    po.add_argument("--publishers", default=None,
                    help="comma list overriding the aggregator default "
                         "(dataaxle,neustar,ypnetwork); see also "
                         "--no-aggregators")
    po.add_argument("--no-aggregators", action="store_true",
                    help="order citations only, skip aggregator submissions")
    po.add_argument("--apply", action="store_true")
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
