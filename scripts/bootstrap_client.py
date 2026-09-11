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
  7. photo_harvest — the client's OWN photos (GBP library + any pre-existing or
     franchise website) pulled, classified and banked BEFORE anything is ever
     generated for them. A restoration company that has been trading for years
     arrives with a photo library; generating a van for them while their real
     one sits on their Google listing is the mistake this step exists to
     prevent.

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


def domain_from_website(website):
    """companies.website -> bare apex domain, or None.

    Only accepts a domain the client actually owns: free site builders and
    social profiles (wixsite.com, facebook.com/..., a GBP-generated
    business.site page) are NOT a domain we can ever cut over, so they stay
    unset rather than becoming a fake apex the ledger then chases."""
    host = (website or "").strip()
    if not host:
        return None
    host = re.sub(r"^https?://", "", host, flags=re.I).split("/")[0].split("?")[0]
    host = re.sub(r"^www\.", "", host.strip().lower()).strip(".")
    if not host or "." not in host or " " in host:
        return None
    NOT_OURS = ("wixsite.com", "squarespace.com", "weebly.com", "business.site",
                "godaddysites.com", "myshopify.com", "facebook.com", "wordpress.com",
                "blogspot.com", "webflow.io", "netlify.app", "pages.dev", "sites.google.com")
    if any(host == d or host.endswith("." + d) for d in NOT_OURS):
        return None
    return host



# VERTICAL IS DERIVED, NOT ASSUMED (Santino 2026-08-09). This was hardcoded to
# "restoration" for EVERY new client. RT Olson Plumbing signed up on 08-08 with
# industry ["Plumbing"] and services Plumbing / Leak Detection / HVAC, and the
# geo-grid promptly scanned him for "water damage restoration": 0 of 169 points
# found, avg_rank null, $0.34 spent proving a plumber does not rank for
# restoration. His dashboard has been blank ever since.
#
# The same hardcode is what the davis-construction incident was about, where a
# construction client silently received restoration prompts. verticals.py was
# written to stop implicit cross-vertical borrowing; this is the other end of
# the same problem, a client being ASSIGNED the wrong vertical at birth.
#
# Falls back to restoration only when nothing matches, because that is what the
# fleet mostly is — but it says so out loud rather than silently.
_VERTICAL_KEYWORDS = (
    ("plumbing",     ("plumb",)),
    ("construction", ("construct", "remodel", "renovation", "builder")),
    ("restoration",  ("restoration", "restore", "mitigation", "damage")),
)


def derive_vertical(co: dict) -> str:
    """Pick the vertical from the company's INDUSTRY, then its name.

    DELIBERATELY NOT the services list. The first version of this matched a
    blob of industry + services + name, and it was wrong for half the fleet:
    Davis Construction came out "plumbing" and Coastal Restoration came out
    "construction", because restoration firms sell drain cleaning and leak
    detection, and the plumbing keywords hit those first. Services describe
    what a company DOES; the vertical is what a company IS, and only industry
    and the trading name speak to that.

    Order matters too: restoration is checked LAST, because "Crew Restoration
    & Construction" and "Quality Contracting" are restoration firms whose
    names contain construction words. Anything genuinely ambiguous should land
    on restoration, which is what the fleet mostly is.
    """
    industry = co.get("industry")
    industry = " ".join(industry) if isinstance(industry, list) else str(industry or "")
    for source in (industry.lower(), str(co.get("name") or "").lower()):
        if not source.strip():
            continue
        # Restoration WINS when the name carries both, e.g. "National
        # Restoration Construction" and "Crew Restoration & Construction" are
        # restoration firms. Only fall through to the others when restoration
        # is absent.
        if any(w in source for w in dict(_VERTICAL_KEYWORDS)["restoration"]):
            return "restoration"
        for vertical, words in _VERTICAL_KEYWORDS:
            if any(w in source for w in words):
                return vertical
    print("vertical: nothing matched for {!r} — defaulting to restoration"
          .format(co.get("name")))
    return "restoration"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--company-id", required=True)
    ap.add_argument("--slug")
    ap.add_argument("--domain")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = sb("GET", "/rest/v1/companies?id=eq.{}&select=id,name,email,status,website".format(args.company_id))
    if not rows:
        sys.exit("company not found: " + args.company_id)
    co = rows[0]
    slug = args.slug or slugify(co["name"])
    # The automated path (client_ops_sync --bootstrap-only) never passes
    # --domain, so every auto-bootstrapped client used to be stamped
    # "{slug}.invalid" even when companies.website held their real site —
    # DISS Restoration shipped with domain "diss-restoration.invalid" while
    # the onboarding wizard had dissrestoration.com on file the whole time
    # (2026-08-04). The wizard answer is the truth; --domain still overrides.
    args.domain = args.domain or domain_from_website(co.get("website"))
    if args.domain:
        print("domain: {}".format(args.domain))
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
            "vertical": derive_vertical(co), "contact": co.get("email"),
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

    # 4. KV upload link (whole-map sync keeps everything consistent) + hub URL
    subprocess.run([sys.executable, str(ROOT / "scripts" / "upload_links_sync.py")], check=True)
    hub = "https://restorationai.io/hub/{}/{}".format(slug, uls.hub_token(slug))
    rows2 = sb("GET", "/rest/v1/companies?id=eq.{}&select=integration_settings".format(co["id"]))
    ints = (rows2 or [{}])[0].get("integration_settings") or {}
    if isinstance(ints, str):
        try:
            ints = json.loads(ints)
        except Exception:
            ints = {}
    ints["hub_url"] = hub
    sb("PATCH", "/rest/v1/companies?id=eq." + co["id"], body={"integration_settings": ints},
       prefer="return=minimal")
    print("hub url: " + hub)

    # 4b. seed the site-brief city ring — the metro towns around the client's
    # city, pre-ticked in the Site Build card so the brief starts as "Davie +
    # the 8 towns a truck actually drives to", not a single lonely city.
    # Only fills an EMPTY list; anything a human saved always wins.
    try:
        rows3 = sb("GET", "/rest/v1/companies?id=eq.{}&select=city,state,integration_settings".format(co["id"]))
        co3 = (rows3 or [{}])[0]
        ints3 = co3.get("integration_settings") or {}
        if isinstance(ints3, str):
            ints3 = json.loads(ints3)
        brief = ints3.get("site_brief") or {}
        # WIZARD TERRITORIES FIRST (Frontline 2026-09-11: the client entered
        # 164 cities across 5 counties in onboarding and the site got an
        # AI-invented 9-city ring instead — companies.service_areas is the
        # single source of truth for territory and must drive the brief).
        # Claude RANKS the client's own list (top 15-20 by population/search
        # demand); the remainder is recorded as expansion tiers, never lost.
        # The AI-guess ring below survives only as the fallback when the
        # wizard captured nothing.
        wiz_cities = []
        try:
            sa_rows = sb("GET", "/rest/v1/companies?id=eq.{}&select=service_areas".format(co["id"]))
            sa = (sa_rows or [{}])[0].get("service_areas")
            if isinstance(sa, str):
                sa = json.loads(sa)
            for grp in sa or []:
                st = (grp.get("state") or "")[:2].upper() if isinstance(grp, dict) else ""
                for cty in (grp.get("cities") or []) if isinstance(grp, dict) else []:
                    wiz_cities.append({"label": cty, "state": st})
        except Exception:  # noqa: BLE001
            wiz_cities = []
        if wiz_cities and co3.get("city") and not (brief.get("cities") or []):
            rank_schema = {
                "type": "object", "additionalProperties": False,
                "properties": {"top": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "properties": {"label": {"type": "string"},
                                   "state": {"type": "string"}},
                    "required": ["label", "state"]}}},
                "required": ["top"]}
            listing = ", ".join(f"{c['label']} ({c['state']})" for c in wiz_cities[:250])
            out, _ = la.claude_json(
                la._claude(),
                "You RANK a service company's own confirmed territory list for "
                "website city pages. From ONLY the cities given, return the top "
                "15-20 by population and search demand, the company's own city "
                "FIRST. Never add cities that are not in the list. "
                'Return ONLY JSON: {"top": [{"label": "...", "state": "XX"}]}',
                "Company city: {}, {}\nTheir confirmed territory: {}".format(
                    co3["city"], co3.get("state") or "", listing),
                max_tokens=1500, schema=rank_schema)
            top = (out.get("top") or [])[:20]
            if top:
                chosen = {(c["label"].lower(), c["state"]) for c in top}
                brief["cities"] = top
                brief["expansion_cities"] = [
                    c for c in wiz_cities
                    if (c["label"].lower(), c["state"]) not in chosen]
                ints3["site_brief"] = brief
                sb("PATCH", "/rest/v1/companies?id=eq." + co["id"],
                   body={"integration_settings": ints3}, prefer="return=minimal")
                print("site-brief cities from WIZARD territories: "
                      + ", ".join(c["label"] for c in top)
                      + " (+{} expansion)".format(len(brief["expansion_cities"])))
        elif co3.get("city") and not (brief.get("cities") or []):
            ring_schema = {
                "type": "object", "additionalProperties": False,
                "properties": {"cities": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "properties": {"label": {"type": "string"},
                                   "state": {"type": "string"}},
                    "required": ["label", "state"]}}},
                "required": ["cities"]}
            out, _ = la.claude_json(
                la._claude(),
                "You pick the service-area ring for a local restoration/home-services "
                "company's website. Return the company's own city FIRST, then the 7-8 "
                "nearby REAL cities/towns (within ~25 miles) a service truck would "
                "actually drive to, ordered by population/search demand. Real places "
                "only, never invented. state = 2-letter abbreviation. "
                'Return ONLY JSON: {"cities": [{"label": "...", "state": "XX"}]}',
                "Company city: {}, {}".format(co3["city"], co3.get("state") or ""),
                max_tokens=1000, schema=ring_schema)
            ring = (out.get("cities") or [])[:9]
            if ring:
                brief["cities"] = ring
                ints3["site_brief"] = brief
                sb("PATCH", "/rest/v1/companies?id=eq." + co["id"],
                   body={"integration_settings": ints3}, prefer="return=minimal")
                print("site-brief city ring seeded: " + ", ".join(c["label"] for c in ring))
    except Exception as e:  # noqa: BLE001 — ring seeding must never block bootstrap
        print("city-ring seeding skipped: {}".format(e))

    # 5. standard intake items (skip duplicates by question text)
    have = {(r.get("question") or "").lower() for r in
            sb("GET", "/rest/v1/client_intake_items?company_id=eq.{}&select=question".format(co["id"])) or []}
    std = [
        ("Customer list for the review campaign", "Any format works: Excel, CSV, or a contact export", 10),
        ("Team photo for review outreach + Google profile",
         "Upload at " + hub + " (no login needed)", 20),
        # Added 2026-08-06: there was no logo item at all. Jerrott (Reign) was
        # asked for a new logo in conversation, but nothing durable recorded
        # that we were waiting on it, so Monica had no open item to chase and
        # no way to know when it arrived. Carries the hub link for the same
        # reason the photo asks do: an emailed attachment only lands in an ops
        # row that needs a human to file it, whereas a hub upload goes straight
        # to storage and pins itself.
        ("Company logo (high-resolution or vector)",
         "Upload at " + hub + " (no login needed) — PNG, SVG, AI or EPS. "
         "Used on the website, Google profile and monthly reports", 25),
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

    # 6b. geo-grid config + first scan — without this the app's Local Maps
    # stays empty (the Gregory question, 2026-07-21). Keywords = top services,
    # grid centered on the company's city until a storefront is known.
    kw_f = cdir / "geogrid-keywords.txt"
    ct_f = cdir / "geogrid-cities.json"
    # Keywords and cities are seeded INDEPENDENTLY. Gating both on kw_f used
    # to strand half-bootstrapped clients forever: DryCor's geocode failed
    # (DB city typo), the cities file was left absent per the AAA guard, and
    # every later bootstrap run skipped the whole block because the keywords
    # file existed (2026-09-02).
    if not (kw_f.exists() and ct_f.exists()):
        full = sb("GET", "/rest/v1/companies?id=eq.{}&select=services,city,state,address".format(co["id"]))[0]
        # Keywords from the DATA-VALIDATED vertical canon (keyword_truth.py:
        # Keyword Planner volumes x fleet GBP/GSC evidence), not a blind
        # services[:2] slice — Frontline bootstrapped with ONE keyword that
        # way (Santino 2026-09-02). Canon seed terms ranked by real score,
        # top 5; services list only as a last-resort fallback.
        vertical = "restoration"
        try:
            vertical = (json.loads((ROOT / "clients" / f"{slug}.json").read_text())
                        .get("vertical") or "restoration")
        except Exception:
            pass
        keywords = []
        canon_f = ROOT / "clients" / "_ops" / "keyword-canon" / "canons" / f"{vertical}.json"
        if canon_f.exists():
            try:
                from keyword_truth import VERTICAL_SEEDS
                canon = {t["term"]: t["score"]
                         for t in json.loads(canon_f.read_text()).get("terms", [])}
                seeds = VERTICAL_SEEDS.get(vertical, [])
                keywords = sorted((s for s in seeds if canon.get(s)),
                                  key=lambda s: -canon[s])[:5]
            except Exception as e:
                print(f"  [canon] unavailable ({str(e)[:60]}) — falling back to services")
        if not keywords:
            keywords = [x.lower() for x in (full.get("services") or [])][:2] or ["water damage restoration"]
        if not kw_f.exists():
            kw_f.write_text("\n".join(keywords) + "\n")
        cities = []
        if ct_f.exists():
            pass  # already configured — only keywords were missing
        elif full.get("city"):
            ll = la.geocode(full["city"], full.get("state") or "")
            if not ll and full.get("address"):
                # City-only geocode can fail on a typo'd or hyper-local town
                # name ("Thonotosasa"); the street address usually still
                # resolves and centers the grid on the business itself.
                ll = la.geocode("{}, {}".format(full["address"], full["city"]),
                                full.get("state") or "")
            if ll:
                # Home city gets the three standard grid sizes (6.5 tight /
                # 9.5 standard / 15 metro-wide) so Map Rankings shows the
                # multi-radius picture from day one.
                cities = [{"label": full["city"], "lat": ll[0], "lng": ll[1],
                           "miles_list": [6.5, 9.5, 15]}]
                d2 = json.loads(pi.read_text())
                d2.setdefault("brand", {})
                d2["brand"].setdefault("lat", ll[0])
                d2["brand"].setdefault("lng", ll[1])
                pi.write_text(json.dumps(d2, indent=1) + "\n")
        # NEVER write an empty ring (AAA 2026-08-04). A `[]` cities file reads
        # as "configured" to every exists()-based check in the fleet, so the
        # client is silently skipped by the cron forever AND is invisible to
        # the freshness watchdog — AAA sat that way from bootstrap until the
        # map-rankings audit found it. Leaving the file ABSENT is the honest
        # state: setup_ledger's map-rankings heal then generates a real ring
        # from plan-input service areas on the next overnight pass.
        if cities:
            ct_f.write_text(json.dumps(cities, indent=1) + "\n")
            subprocess.run([sys.executable, str(ROOT / "scripts" / "geogrid_cron.py"),
                            "--slug", slug])
        elif not ct_f.exists():
            print("geo-grid: could not geocode '{}' — leaving the city ring "
                  "UNwritten; setup_ledger heals it overnight and the ops "
                  "digest carries a NO MAP DATA alarm until scans exist"
                  .format(full.get("city")))

    # 6. GBP sync (needs place_id)
    if place_id:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "gbp.py"),
                        "sync", "--slug", slug])
    else:
        print("no place_id on the Google integration yet — GBP sync skipped")

    # 7. Real-photo harvest — day one, before any image is generated for this
    # client. Non-fatal by design: a brand-new business with an empty listing
    # simply banks nothing and falls through to generation later.
    print("\nHarvesting the client's own photos (GBP + any existing website)...")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "photo_harvest.py"),
                    "run", "--slug", slug])

    print("\nBootstrap complete for {} ({}).".format(co["name"], slug))
    print("Hub link (use this in all client messages): " + hub)
    print("Remember to commit clients/ changes.")


if __name__ == "__main__":
    main()
