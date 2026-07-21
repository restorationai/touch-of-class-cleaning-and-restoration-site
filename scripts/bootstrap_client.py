#!/usr/bin/env python3
"""bootstrap_client.py — one-command sales→ops handoff for a new client.

Everything Gregory Arianoff was missing, in one shot:
  1. clients/company_map.json entry (slug -> company id)
  2. clients/{slug}.json registry stub + clients/{slug}/plan-input.json with
     brand.display_name + place_id (pulled from the company's connected
     Google integration when available)
  3. marketing_sites row (rank_ai_slug -> the app's photo-link chip + top-nav
     Upload Link button light up)
  4. Cloudflare KV upload link (restorationai.io/gbpphotos/{slug}) + crew hub
  5. Standard onboarding intake items (customer list, team photo, brand
     guide, job photos) — skipping any that already exist
  6. gbp.py sync so the app's Locations tab has data on day one

Usage:
  python3 scripts/bootstrap_client.py --company-id CO-... [--slug my-slug]
      [--domain example.com] [--dry-run]

The server-side backstop in client_ops_sync auto-creates the DB/KV pieces
(3+4) for any Active company it finds unbootstrapped; this script is the
full version that also writes the repo files and runs the GBP sync.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

import lead_audit as la  # noqa: E402  (env + NOTIFY_EMAIL; not audit logic)
import upload_links_sync as uls  # noqa: E402


def sb(method, path, body=None, prefer="return=representation"):
    import os
    import urllib.request
    url = os.environ["SUPABASE_URL"] + path
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    req = urllib.request.Request(url, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"apikey": key, "Authorization": "Bearer " + key,
                 "Content-Type": "application/json", "Prefer": prefer})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return re.sub(r"-{2,}", "-", s) or "client"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--company-id", required=True)
    ap.add_argument("--slug")
    ap.add_argument("--domain")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = sb("GET", "/rest/v1/companies?id=eq.{}&select=id,name,email,status".format(args.company_id))
    if not rows:
        sys.exit("company not found: " + args.company_id)
    co = rows[0]
    slug = args.slug or slugify(co["name"])
    print("company: {} ({}) -> slug {}".format(co["name"], co["id"], slug))
    if args.dry_run:
        print("dry run — stopping before writes")
        return

    # 1. company map
    map_path = ROOT / "clients" / "company_map.json"
    m = json.loads(map_path.read_text())
    if m.get(slug) not in (None, co["id"]):
        sys.exit("slug {} already maps to {}".format(slug, m[slug]))
    m[slug] = co["id"]
    map_path.write_text(json.dumps(m, indent=1) + "\n")

    # 2. repo stubs (never overwrite existing files)
    place_id = None
    try:
        ints = sb("GET", "/rest/v1/user_integrations?client_id=eq.{}&provider=eq.google&select=connection_metadata".format(co["id"]))
        md = (ints or [{}])[0].get("connection_metadata") or {}
        if isinstance(md, str):
            md = json.loads(md)
        place_id = md.get("place_id")
    except Exception:
        pass
    cdir = ROOT / "clients" / slug
    cdir.mkdir(exist_ok=True)
    pi = cdir / "plan-input.json"
    if not pi.exists():
        brand = {"display_name": co["name"]}
        if place_id:
            brand["place_id"] = place_id
        pi.write_text(json.dumps({"brand": brand}, indent=1) + "\n")
    reg = ROOT / "clients" / (slug + ".json")
    if not reg.exists():
        reg.write_text(json.dumps({
            "slug": slug, "display_name": co["name"],
            "domain": args.domain, "tier": "standard",
            "vertical": "restoration", "contact": co.get("email"),
            "status": "onboarding",
        }, indent=1) + "\n")

    # 3. marketing_sites (idempotent)
    existing = sb("GET", "/rest/v1/marketing_sites?company_id=eq.{}&select=id,rank_ai_slug".format(co["id"]))
    if existing:
        print("marketing_sites row exists (slug {})".format(existing[0].get("rank_ai_slug")))
    else:
        sb("POST", "/rest/v1/marketing_sites", body={
            "company_id": co["id"], "rank_ai_slug": slug,
            "domain": args.domain or (slug + ".invalid"),
            "tier": "standard", "plan_template": "restoration"})
        print("marketing_sites row created")

    # 4. KV upload link (whole-map sync keeps everything consistent)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "upload_links_sync.py")], check=True)

    # 5. standard intake items (skip duplicates by question text)
    have = {(r.get("question") or "").lower() for r in
            sb("GET", "/rest/v1/client_intake_items?company_id=eq.{}&select=question".format(co["id"])) or []}
    std = [
        ("Customer list for the review campaign", "Any format works: Excel, CSV, or a contact export", 10),
        ("Team photo for review outreach + Google profile",
         "Upload at restorationai.io/gbpphotos/" + slug + " (no login needed)", 20),
        ("Brand guide or brand preferences (fonts, colors, hex codes)",
         "Franchise HQ usually provides this as a PDF; independents can just tell us preferences", 30),
        ("Finished job photos for the Google Business Profile",
         "Same upload link, crews can send from their phones", 40),
    ]
    payload = [{"company_id": co["id"], "question": q, "help_text": h,
                "field_type": "checklist", "status": "pending",
                "source": "rank-ai", "sort": srt, "blocks": None}
               for q, h, srt in std if q.lower() not in have]
    if payload:
        sb("POST", "/rest/v1/client_intake_items", body=payload)
    print("intake items added: {}".format(len(payload)))

    # 6. GBP sync (needs place_id)
    if place_id:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "gbp.py"),
                        "sync", "--slug", slug])
    else:
        print("no place_id on the Google integration yet — GBP sync skipped")

    print("\nBootstrap complete for {} ({}).".format(co["name"], slug))
    print("Upload link: https://restorationai.io/gbpphotos/" + slug)
    print("Remember to commit clients/ changes.")


if __name__ == "__main__":
    main()
