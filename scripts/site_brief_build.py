#!/usr/bin/env python3
"""site_brief_build.py — turn the app's Site Build Brief into plan-input.json.

The app captures the brief (Site tab → Site Build card): theme, brand colors
(often extracted from the client's current website), fonts, and the list of
cities to build pages for. This script merges that brief with the company
row (NAP, services, place_id) into clients/{slug}/plan-input.json, enriching
each city with the neighborhoods/landmarks/zips profile the restoration
template expects (Claude, few-shot from an existing client's entry).

Never overwrites: existing service_areas entries (matched by slug) and any
hand-set brand keys win over generated ones.

Usage: python3 scripts/site_brief_build.py --slug restorationxpress
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

import lead_audit as la  # noqa: E402  _claude, claude_json, geocode


def sb(path):
    import os
    import urllib.request
    req = urllib.request.Request(os.environ["SUPABASE_URL"] + path, headers={
        "apikey": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        "Authorization": "Bearer " + os.environ["SUPABASE_SERVICE_ROLE_KEY"]})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


AREA_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"areas": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "city": {"type": "string"}, "state": {"type": "string"},
            "slug": {"type": "string"},
            "neighborhoods": {"type": "array", "items": {"type": "string"}},
            "landmarks": {"type": "array", "items": {"type": "string"}},
            "zip_codes": {"type": "array", "items": {"type": "string"}},
            "local_notes": {"type": "string"},
        },
        "required": ["city", "state", "slug", "neighborhoods", "landmarks",
                     "zip_codes", "local_notes"]}}},
    "required": ["areas"],
}

AREA_SYSTEM = """You write service-area profiles for a local restoration company's website
plan. For each requested city return REAL neighborhoods, REAL landmarks, REAL
zip codes (verifiable facts only — never invent places), and a short
local_notes sentence a local would find credible. slug = "city-st" lowercase
hyphenated. Return ONLY JSON: {"areas": [...]}"""


def service_slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower().replace("&", "and")).strip("-")
    return re.sub(r"-{2,}", "-", s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    args = ap.parse_args()
    slug = args.slug

    cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
    cid = cmap.get(slug)
    if not cid:
        sys.exit("slug not in company_map: " + slug)
    co = sb("/rest/v1/companies?id=eq.{}&select=name,phone,email,city,state,"
            "postal_code,address,services,website,integration_settings".format(cid))[0]
    ints = co.get("integration_settings") or {}
    if isinstance(ints, str):
        ints = json.loads(ints)
    brand_kit = ints.get("brand") or {}
    brief = ints.get("site_brief") or {}
    theme = ints.get("theme") or brief.get("theme") or "light"
    cities = brief.get("cities") or []
    if not cities:
        sys.exit("site_brief.cities is empty — save the brief in the app first")

    pi_path = ROOT / "clients" / slug / "plan-input.json"
    pi = json.loads(pi_path.read_text()) if pi_path.exists() else {}
    brand = pi.get("brand") or {}

    # brand: brief/kit values fill gaps; existing hand-set keys win
    brand.setdefault("display_name", co["name"].strip())
    brand.setdefault("short_name", co["name"].strip().split()[0])
    if brand_kit.get("primary_color"):
        brand.setdefault("primary_color", brand_kit["primary_color"])
    sec = (brand_kit.get("secondary_color") or "").lstrip("#")
    # A near-white accent on a light theme renders invisible elements — skip
    # it and let the template derive an accent from the primary instead.
    def _too_light(h):
        try:
            return (int(h[0:2], 16) + int(h[2:4], 16) + int(h[4:6], 16)) > 690
        except Exception:
            return False
    if sec and not (theme == "light" and _too_light(sec)):
        brand.setdefault("accent_color", "#" + sec)
    if brand_kit.get("heading_font"):
        brand.setdefault("heading_font", brand_kit["heading_font"])
    if brand_kit.get("body_font"):
        brand.setdefault("body_font", brand_kit["body_font"])
    for src, dst in (("phone", "phone"), ("email", "email"),
                     ("address", "street_address"), ("postal_code", "postal_code")):
        if co.get(src):
            brand.setdefault(dst, co[src])
    gmd = {}
    try:
        g = sb("/rest/v1/user_integrations?client_id=eq.{}&provider=eq.google"
               "&select=connection_metadata".format(cid))
        gmd = (g or [{}])[0].get("connection_metadata") or {}
        if isinstance(gmd, str):
            gmd = json.loads(gmd)
    except Exception:
        pass
    if gmd.get("place_id"):
        brand.setdefault("place_id", gmd["place_id"])
    brand.setdefault("theme", theme)
    pi["brand"] = brand

    pi.setdefault("template", "restoration")
    pi.setdefault("services", [service_slug(s) for s in (co.get("services") or [])]
                  or ["water-damage-restoration"])
    pi.setdefault("blog_seed_count", 12)

    # service areas: enrich only cities we don't already have
    existing = {a.get("slug") for a in (pi.get("service_areas") or [])}
    todo = []
    for c in cities[:25]:
        label = c.get("label") if isinstance(c, dict) else str(c)
        state = (c.get("state") if isinstance(c, dict) else "") or co.get("state") or ""
        cslug = service_slug("{} {}".format(label, state[:2] if len(state) > 2 else state))
        if cslug not in existing:
            todo.append({"city": label, "state": state})
    if todo:
        sample = json.dumps({
            "city": "Kenilworth", "state": "NJ", "slug": "kenilworth-nj",
            "neighborhoods": ["The Boulevard corridor", "North Kenilworth"],
            "landmarks": ["Black Brook Park", "Garden State Parkway Exit 138"],
            "zip_codes": ["07033"],
            "local_notes": "Home base — fastest response times in the area.",
        })
        user = ("COMPANY: {} ({}, {})\nEXAMPLE ENTRY SHAPE:\n{}\n\n"
                "CITIES TO PROFILE:\n{}").format(
            co["name"], co.get("city"), co.get("state"), sample,
            json.dumps(todo))
        out, _ = la.claude_json(la._claude(), AREA_SYSTEM, user,
                                max_tokens=8000, schema=AREA_SCHEMA)
        areas = pi.get("service_areas") or []
        primary_set = any(a.get("primary") for a in areas)
        for a in out.get("areas", []):
            if a["slug"] in existing:
                continue
            if not primary_set and a["city"].lower() == (co.get("city") or "").lower():
                a["primary"] = True
                primary_set = True
            areas.append(a)
        pi["service_areas"] = areas

    pi_path.parent.mkdir(exist_ok=True)
    pi_path.write_text(json.dumps(pi, indent=1) + "\n")
    print("plan-input updated: {} services, {} areas, theme={}, primary={} accent={}".format(
        len(pi["services"]), len(pi.get("service_areas") or []), theme,
        brand.get("primary_color"), brand.get("accent_color")))


if __name__ == "__main__":
    main()
