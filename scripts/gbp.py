#!/usr/bin/env python3
"""
gbp.py — Google Business Profile pipeline module (System: GBP).

Reads a client's live GBP via the now-enabled Business Profile APIs using the
business.manage token stored by the app's connect flow (user_integrations), and
RECONCILES the GBP's categories/services against the website's pages — the local-SEO
consistency lever (a GBP service/category with no dedicated, crawlable page ranks
worse; a site service missing from the GBP is a lost signal).

Auth: pulls the client's (or, fallback, any agency) 'google' refresh_token from
Supabase user_integrations, refreshes it with the shared OAuth client. The agency
account manages all client locations, so any business.manage token can read them;
we match the right location by the client's brand.place_id.

Commands:
    python3 scripts/gbp.py read       --slug narestco
    python3 scripts/gbp.py reconcile  --slug narestco
    python3 scripts/gbp.py reconcile  --all

Read-only for now (no writes). Update operations + strategist wiring come next.
Env (rank-ai/.env): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GOOGLE_OAUTH_CLIENT_ID,
GOOGLE_OAUTH_CLIENT_SECRET.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
G_CID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
G_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")

ACCT_API = "https://mybusinessaccountmanagement.googleapis.com/v1"
INFO_API = "https://mybusinessbusinessinformation.googleapis.com/v1"
LOC_READ_MASK = "name,title,categories,storefrontAddress,regularHours,profile,serviceItems,metadata,phoneNumbers,websiteUri"


# --------------------------------------------------------------------------- #
# Supabase (runtime REST — service role; uses requests to avoid the urllib WAF block)
# --------------------------------------------------------------------------- #
def _sb(path: str) -> list:
    r = requests.get(f"{SB_URL}/rest/v1/{path}",
                     headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    r.raise_for_status()
    return r.json()


def company_id_for(slug: str) -> str | None:
    rec = ROOT / "clients" / f"{slug}.json"
    if rec.exists():
        cid = json.loads(rec.read_text()).get("company_id")
        if cid:
            return cid
    cmap = ROOT / "clients" / "company_map.json"
    return json.loads(cmap.read_text()).get(slug) if cmap.exists() else None


def get_access_token(company_id: str) -> str | None:
    """Refresh a business.manage access token for this company. Falls back to any
    agency 'google' integration (the agency account manages every client location)."""
    rows = _sb(f"user_integrations?provider=eq.google&select=client_id,refresh_token,"
               f"connection_metadata&client_id=eq.{company_id}")
    if not rows:
        rows = _sb("user_integrations?provider=eq.google&select=client_id,refresh_token,"
                   "connection_metadata&limit=5")  # agency fallback
    for row in rows:
        rt = row.get("refresh_token") or (row.get("connection_metadata") or {}).get("refresh_token")
        if not rt:
            continue
        resp = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": G_CID, "client_secret": G_SECRET,
            "refresh_token": rt, "grant_type": "refresh_token"})
        if resp.ok:
            return resp.json()["access_token"]
    return None


# --------------------------------------------------------------------------- #
# GBP reads
# --------------------------------------------------------------------------- #
def _g(url: str, token: str) -> dict:
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()


def find_location(token: str, place_id: str) -> dict | None:
    """Find the location matching the client's place_id across all managed accounts."""
    for acct in _g(f"{ACCT_API}/accounts", token).get("accounts", []):
        url = f"{INFO_API}/{acct['name']}/locations?readMask={LOC_READ_MASK}&pageSize=100"
        for loc in _g(url, token).get("locations", []):
            if (loc.get("metadata", {}) or {}).get("placeId") == place_id:
                return loc
    return None


def summarize(loc: dict) -> dict:
    cats = loc.get("categories", {}) or {}
    primary = (cats.get("primaryCategory") or {}).get("displayName")
    additional = [c.get("displayName") for c in cats.get("additionalCategories", [])]
    services = []
    for s in loc.get("serviceItems", []):
        # free-form or structured service
        label = (s.get("freeFormServiceItem", {}) or {}).get("label", {}).get("displayName")
        struct = (s.get("structuredServiceItem", {}) or {}).get("serviceTypeId")
        services.append(label or struct)
    return {
        "title": loc.get("title"),
        "website": loc.get("websiteUri"),
        "primary_category": primary,
        "additional_categories": [c for c in additional if c],
        "services": [s for s in services if s],
        "has_hours": bool(loc.get("regularHours")),
        "has_description": bool((loc.get("profile") or {}).get("description")),
        "description_len": len((loc.get("profile") or {}).get("description", "") or ""),
    }


# --------------------------------------------------------------------------- #
# Website reconciliation
# --------------------------------------------------------------------------- #
def _norm(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"\b(service|services|restoration|repair|cleanup|remediation|removal)\b", " ", t)
    return re.sub(r"[^a-z]+", " ", t).strip()


def site_services(slug: str) -> list[str]:
    """Service display names that have a dedicated page on the client's site."""
    pi = ROOT / "clients" / slug / "plan-input.json"
    if not pi.exists():
        return []
    services = json.loads(pi.read_text()).get("services", [])
    cat = json.loads((ROOT / "templates" / "restoration" / "services.json").read_text())
    by_slug = {s["slug"]: s.get("display_name", s["slug"]) for s in cat["services"]}
    return [by_slug.get(s, s) for s in services]


def reconcile(slug: str) -> dict:
    cid = company_id_for(slug)
    brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
    place_id = brand.get("place_id")
    out = {"slug": slug, "company_id": cid, "place_id": place_id}
    if not place_id:
        out["error"] = "no brand.place_id (client GBP identity unknown)"
        return out
    token = get_access_token(cid)
    if not token:
        out["error"] = "no business.manage token (connect this client's GBP)"
        return out
    loc = find_location(token, place_id)
    if not loc:
        out["error"] = f"no GBP location found for place_id {place_id} on the connected account(s)"
        return out
    g = summarize(loc)
    out["gbp"] = g

    # GBP categories + services that the client offers (on the listing)
    gbp_terms = [g["primary_category"]] + g["additional_categories"] + g["services"]
    gbp_norm = {_norm(t): t for t in gbp_terms if t}
    site = site_services(slug)
    site_norm = {_norm(s): s for s in site if s}

    # GBP service/category with NO dedicated website page -> build a page
    out["gbp_without_page"] = sorted(
        orig for n, orig in gbp_norm.items()
        if n and not any(n in sn or sn in n for sn in site_norm))
    # Website service with NO GBP entry -> add it to the GBP
    out["site_without_gbp"] = sorted(
        orig for n, orig in site_norm.items()
        if n and not any(n in gn or gn in n for gn in gbp_norm))
    return out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _clients(args) -> list[str]:
    if args.all:
        cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
        return list(cmap.keys())
    return [args.slug]


def cmd_read(args) -> int:
    for slug in _clients(args):
        cid = company_id_for(slug)
        token = get_access_token(cid) if cid else None
        if not token:
            print(f"\n## {slug}: no business.manage token — connect this client's GBP")
            continue
        brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
        loc = find_location(token, brand.get("place_id", ""))
        if not loc:
            print(f"\n## {slug}: no matching GBP location for place_id {brand.get('place_id')}")
            continue
        g = summarize(loc)
        print(f"\n## {slug} — {g['title']}  ({g['website']})")
        print(f"   primary category: {g['primary_category']}")
        print(f"   additional categories: {g['additional_categories'] or '(none)'}")
        print(f"   services on listing: {g['services'] or '(none)'}")
        print(f"   hours set: {g['has_hours']} | description: {g['description_len']} chars")
    return 0


def cmd_reconcile(args) -> int:
    for slug in _clients(args):
        r = reconcile(slug)
        print(f"\n## {slug}")
        if r.get("error"):
            print(f"   SKIP — {r['error']}")
            continue
        print(f"   GBP primary: {r['gbp']['primary_category']} | "
              f"{len(r['gbp']['additional_categories'])} more categories | "
              f"{len(r['gbp']['services'])} services")
        if r["gbp_without_page"]:
            print(f"   ⚠ GBP item with NO dedicated website page (build one): {r['gbp_without_page']}")
        if r["site_without_gbp"]:
            print(f"   ⚠ Website service NOT on the GBP (add to listing): {r['site_without_gbp']}")
        if not r["gbp_without_page"] and not r["site_without_gbp"]:
            print("   ✓ GBP categories/services and website pages are consistent")
    return 0


def main() -> int:
    if not (SB_URL and SB_KEY and G_CID and G_SECRET):
        print("ERROR: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GOOGLE_OAUTH_CLIENT_ID, "
              "GOOGLE_OAUTH_CLIENT_SECRET must be set in rank-ai/.env", file=sys.stderr)
        return 1
    ap = argparse.ArgumentParser(description="Google Business Profile module")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("read", "reconcile"):
        p = sub.add_parser(name)
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument("--slug")
        g.add_argument("--all", action="store_true")
    args = ap.parse_args()
    return cmd_read(args) if args.cmd == "read" else cmd_reconcile(args)


if __name__ == "__main__":
    raise SystemExit(main())
