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


# Wizard service names don't always match catalog slugs ("Fire & Smoke
# Restoration" -> fire-and-smoke-restoration, which plan_site rejects).
# Resolve every service against the template catalog; unknowns are DROPPED
# with a warning rather than blocking the build (2026-07-23 maiden voyage).
_ALIASES = {
    "fire-and-smoke-restoration": "fire-damage-restoration",
    "smoke-and-fire-restoration": "fire-damage-restoration",
    "water-damage-mitigation": "water-damage-restoration",
    "mold-removal": "mold-remediation",
    "mold-removal-and-remediation": "mold-remediation",
}


def catalog_services(names):
    catalog = []
    try:
        d = json.loads((ROOT / "templates" / "restoration" / "services.json").read_text())
        catalog = [s["slug"] if isinstance(s, dict) else s
                   for s in (d if isinstance(d, list) else d.get("services", []))]
    except Exception:
        pass
    out = []
    for n in names:
        slug = service_slug(n)
        if not catalog or slug in catalog:
            resolved = slug
        elif slug in _ALIASES:
            resolved = _ALIASES[slug]
        else:
            # token-subset: catalog slug whose every token appears in the
            # wizard slug ("sewage-cleanup" in "sewage-cleanup-and-remediation")
            toks = set(slug.split("-"))
            subset = [c for c in catalog if set(c.split("-")) <= toks]
            if subset:
                resolved = max(subset, key=len)
            else:
                import difflib
                close = difflib.get_close_matches(slug, catalog, n=1, cutoff=0.8)
                if close:
                    resolved = close[0]
                else:
                    print(f"  service {n!r} ({slug}) not in catalog — dropped")
                    continue
        if resolved not in out:
            out.append(resolved)
    return out


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

    # Licensing & Trust from the onboarding wizard (integration_settings.licensing,
    # persisted by the wizard since 2026-07-26) -> brand truth: powers trust
    # badges + footer license line + claims-lint. Kyle's IICRC/license never
    # reached his site because this hop didn't exist.
    lic = ints.get("licensing") or {}
    if lic.get("license_number") and not brand.get("license_numbers"):
        brand["license_numbers"] = [str(lic["license_number"])]
    if lic.get("certifications") and not brand.get("certifications"):
        brand["certifications"] = [c.strip() for c in str(lic["certifications"]).replace(";", ",").split(",") if c.strip()]
    if isinstance(lic.get("insured"), bool):
        brand.setdefault("insured", lic["insured"])
    if lic.get("founded_year"):
        brand.setdefault("founded_year", str(lic["founded_year"]))

    # Logo: pull the newest uploaded logo from branding/{cid}/brand/ into the
    # site as a LOCAL file (never a cross-domain URL that may not exist yet —
    # crew shipped with logoUrl https://images.None/brand/logo.png). SVGs are
    # kept as-is; browsers render them fine in <img>.
    try:
        import requests as _rq
        sb_url = os.environ["SUPABASE_URL"].rstrip("/")
        sb_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        hdrs = {"apikey": sb_key, "Authorization": "Bearer " + sb_key,
                "Content-Type": "application/json"}
        objs = _rq.post(sb_url + "/storage/v1/object/list/branding", headers=hdrs,
                        json={"prefix": cid + "/brand", "limit": 50,
                              "sortBy": {"column": "created_at", "order": "desc"}},
                        timeout=30).json()
        img = next((o for o in objs if isinstance(o, dict) and o.get("id")
                    and str(o.get("name", "")).lower().endswith(
                        (".png", ".jpg", ".jpeg", ".webp", ".svg"))), None)
        if img:
            ext = Path(img["name"]).suffix.lower()
            raw = _rq.get(f"{sb_url}/storage/v1/object/branding/{cid}/brand/{img['name']}",
                          headers=hdrs, timeout=60).content
            out = ROOT / "sites" / slug / "public" / "images" / f"logo{ext}"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(raw)
            brand.setdefault("logo_url", f"/images/logo{ext}")
            print(f"  logo: pulled {img['name']} -> public/images/logo{ext}")
    except Exception as e:
        print(f"  logo pull skipped: {str(e)[:100]}")

    pi["brand"] = brand

    pi.setdefault("template", "restoration")
    pi.setdefault("services", catalog_services(co.get("services") or [])
                  or ["water-damage-restoration"])
    pi.setdefault("blog_seed_count", 12)

    # service areas: enrich only cities we don't already have
    existing = {a.get("slug") for a in (pi.get("service_areas") or [])}
    todo = []
    # No silent truncation (Santino 2026-07-26: complete coverage in ONE build,
    # no renditions — a [:25] here quietly cut Kyle's 45 declared cities to 25).
    # The demand floor happens upstream when the list is composed; 75 is a pure
    # runaway guard, not a product cap.
    for c in cities[:75]:
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
