#!/usr/bin/env python3
"""best_of_seeder.py — System 0: seed one AI-citation post into the client's
content queue, rotating through the city x service matrix and ALTERNATING
between two formats (2026-07-23, the Hank/dialhank + Breesy play, per
Santino):
  best_of_comparison  'Best {service} Companies in {city}' — ranked list vs
                      real local competitors (commercial/comparison intent)
  who_to_call         'Who to Call for {service} in {city}' — direct-answer
                      triage page (emergency/voice intent, the query mode
                      where entity feeds usually beat content)
  cost_guide          'How Much Does {service} Cost in {ST}?' — the canonical
                      state-level cost answer w/ scenario table (the single
                      most AI-cited format; one per service, top 4 services)
  case_study          real-review-sourced story ("Case Study: ...") built
                      around a verbatim 4-5 star Google review — job facts
                      come ONLY from the customer's own words, never invented

Why: AI answer engines ("what's the best water damage company in Davie?")
cite ranked first-party comparison posts because almost nobody writes them
for local niches. One per client every ~2 weeks works through the matrix
without tripping the mass-produced-doorway-page pattern.

Rotation order (skipping combos already seeded/written):
  1. hero service x primary city          (the flagship)
  2. hero service x each other city       (ring order — "Tacoma, then Seattle")
  3. services 2..4 x primary city
  4. services 2..4 x other cities         (deep tail, years of runway)

Competitors: top rated local competitors from DataForSEO Google Maps for
that exact city+service — REAL names, REAL ratings, REAL review counts.
The writer prompt (BEST-OF COMPARISON MODE in content-writer.md) may only
use these provided fields for competitors; the client's own claims stay
truth-table gated as always.

Scheduling: master_scheduler SYSTEM 0, cadence_days=14, runs before the
content writer so the seeded item is written in the same Mon/Thu run.

Usage: python3 scripts/best_of_seeder.py --slug narestco [--dry-run]
"""
from __future__ import annotations

import argparse
import base64
import json
import pathlib
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

import requests

from geogrid_scan import load_dfs_creds  # noqa: E402

CLIENTS_DIR = ROOT / "clients"
SITES_DIR = ROOT / "sites"
DFS_MAPS = "https://api.dataforseo.com/v3/serp/google/maps/live/advanced"
MAX_COMPETITORS = 4


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def pretty(service_slug: str) -> str:
    return service_slug.replace("-", " ").title().replace("Hvac", "HVAC")


def load_queue(slug: str) -> tuple[dict | list, list]:
    """Return (raw_queue_object, items_list_reference)."""
    p = CLIENTS_DIR / slug / "content-queue.json"
    if not p.exists():
        raw: dict = {"items": []}
        return raw, raw["items"]
    raw = json.loads(p.read_text())
    if isinstance(raw, list):
        return raw, raw
    return raw, raw.setdefault("items", [])


def save_queue(slug: str, raw) -> None:
    (CLIENTS_DIR / slug / "content-queue.json").write_text(
        json.dumps(raw, indent=1) + "\n")


def combo_sequence(services: list[str], areas: list[dict]) -> list[tuple[str, dict]]:
    """The rotation: flagship first, then hero-service ring, then service depth."""
    if not services or not areas:
        return []
    primary = next((a for a in areas if a.get("primary")), areas[0])
    others = [a for a in areas if a is not primary]
    hero, rest = services[0], services[1:4]
    seq: list[tuple[str, dict]] = [(hero, primary)]
    seq += [(hero, a) for a in others]
    seq += [(s, primary) for s in rest]
    for a in others:
        seq += [(s, a) for s in rest]
    return seq


def existing_combo_keys(slug: str, items: list) -> set[str]:
    done = set()
    for it in items:
        if it.get("source") == "best-of-seeder" and it.get("combo_key"):
            done.add(it["combo_key"])
    blog_dir = SITES_DIR / slug / "src" / "content" / "blog"
    if blog_dir.exists():
        for pattern in ("best-*-in-*.md", "who-to-call-for-*.md", "*-cost-*.md",
                        "*-who-to-call-first.md"):
            for md in blog_dir.glob(pattern):
                done.add(md.stem)  # combo_key doubles as the intended post slug
    return done


def fetch_competitors(service: str, city: str, state: str,
                      client_name: str) -> list[dict]:
    u, p = load_dfs_creds()
    auth = base64.b64encode(f"{u}:{p}".encode()).decode()
    kw = f"{pretty(service).lower()} {city} {state}"
    r = requests.post(DFS_MAPS, headers={
        "Authorization": "Basic " + auth, "Content-Type": "application/json"},
        json=[{"keyword": kw, "location_name": "United States",
               "language_code": "en", "depth": 20}], timeout=120)
    r.raise_for_status()
    task = (r.json().get("tasks") or [{}])[0]
    if task.get("status_code") != 20000:
        raise RuntimeError(f"DFS maps: {task.get('status_message')}")
    items = ((task.get("result") or [{}])[0] or {}).get("items") or []
    out = []
    client_tokens = {t for t in client_name.lower().split() if len(t) > 3}
    for it in items:
        name = (it.get("title") or "").strip()
        rating = ((it.get("rating") or {}).get("value"))
        votes = ((it.get("rating") or {}).get("votes_count"))
        if not name or rating is None:
            continue
        # never list the client as their own competitor — token overlap
        # AND collapsed-name containment ("RestorationXpress" vs Google's
        # "Restoration Xpress" shared zero tokens, so the client's own
        # listing shipped as competitor #5 in their Davie best-of, 08-28)
        _collapse = lambda x: __import__("re").sub(r"[^a-z0-9]", "", x.lower())
        _self_overlap = client_tokens and client_tokens & {t for t in name.lower().split() if len(t) > 3}
        _self_collapsed = _collapse(client_name) and (
            _collapse(client_name) in _collapse(name) or _collapse(name) in _collapse(client_name))
        if _self_overlap or _self_collapsed:
            continue
        out.append({"name": name, "google_rating": rating,
                    "review_count": votes or 0})
        if len(out) >= MAX_COMPETITORS:
            break
    return out


def variant_fanout(service: str, place: str, slug: str | None = None) -> list[str]:
    """Customer-language variants for this service, best-volume first.

    "water cleanup Federal Way" style phrasings from keyword-variants.json,
    volume-ranked via DataForSEO when reachable (falls back to file order).
    Titles keep the canonical phrasing; these ride as secondary keywords."""
    try:
        # RESOLVE THE VERTICAL, do not hardcode restoration (Santino
        # 2026-08-09, plumbing template pass). This read
        # templates/restoration/keyword-variants.json for every client, so a
        # plumbing client either got restoration phrasings ("water cleanup
        # Federal Way") or, more usually, silently got none at all because
        # their service slugs are absent from that file. Same class of bug as
        # bootstrap hardcoding vertical="restoration": it fails quietly and
        # looks like the feature simply has nothing to add.
        import verticals
        path = (verticals.resolve_template(slug, "keyword-variants.json")
                if slug else ROOT / "templates" / "restoration" / "keyword-variants.json")
        vmap = json.loads(pathlib.Path(path).read_text())
    except (Exception, SystemExit) as e:  # noqa: BLE001
        # resolve_template() sys.exit()s when the vertical lacks the asset
        # (templates/plumbing has no keyword-variants.json). SystemExit is not
        # an Exception, so it killed the WHOLE seeder: All Pro + RT Olson got
        # no System 0 post since 07-27 / ever (2026-10-01 audit). Variants are
        # optional enrichment; canonical phrasing ships without them.
        sys.stderr.write(f"  variant fan-out skipped for {slug}: {str(e)[:160]}\n")
        return []
    variants = [v for v in vmap.get(service, []) if isinstance(v, str)][:7]
    if not variants:
        return []
    kws = [f"{v} {place}".strip() for v in variants]
    try:
        u, p_ = load_dfs_creds()
        auth = base64.b64encode(f"{u}:{p_}".encode()).decode()
        r = requests.post(
            "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live",
            headers={"Authorization": "Basic " + auth, "Content-Type": "application/json"},
            json=[{"keywords": kws, "location_code": 2840, "language_code": "en"}],
            timeout=60)
        items = ((r.json().get("tasks") or [{}])[0].get("result") or [])
        vol = {i.get("keyword", "").lower(): i.get("search_volume") or 0 for i in items}
        kws.sort(key=lambda k: vol.get(k.lower(), 0), reverse=True)
    except Exception:
        pass  # file order is a fine fallback
    return kws[:3]


def build_case_study_item(slug: str, items: list, done_keys: set) -> dict | None:
    """Pick the best unused story-worthy Google review as a case-study seed.

    Real reviews only (marketing_gbp_reviews, synced from the live GBP).
    Story-worthy = 4-5 stars, substantial text (>=140 chars). The writer's
    CASE STUDY MODE may only use job facts present in the review text itself.
    """
    import os
    import requests as rq
    cmap = json.loads((CLIENTS_DIR / "company_map.json").read_text())
    cid = cmap.get(slug)
    sb_url, sb_key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not (cid and sb_url and sb_key):
        return None
    try:
        rows = rq.get(
            f"{sb_url}/rest/v1/marketing_gbp_reviews?company_id=eq.{cid}"
            "&select=review_id,reviewer_name,star_rating,comment,create_time"
            "&order=create_time.desc&limit=40",
            headers={"apikey": sb_key, "Authorization": "Bearer " + sb_key},
            timeout=30).json()
    except Exception:
        return None
    for r in rows if isinstance(rows, list) else []:
        stars = str(r.get("star_rating") or "")
        comment = (r.get("comment") or "").strip()
        if stars not in ("4", "5", "FOUR", "FIVE") or len(comment) < 140:
            continue
        key = "case-study-" + str(r.get("review_id") or "")[:16]
        if key in done_keys:
            continue
        first_name = (r.get("reviewer_name") or "a customer").split()[0]
        return {
            "id": f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{key}",
            "status": "queued", "queued_at": now_iso(),
            "priority": 1, "prioritized": True,
            "content_type": "case_study", "combo_key": key,
            "primary_keyword": "",
            "intent": "commercial", "target_word_count": 1000,
            "case_study": {
                "review_id": r.get("review_id"),
                "reviewer_name": first_name,
                "star_rating": 5 if stars in ("5", "FIVE") else 4,
                "review_text": comment,
                "review_date": (r.get("create_time") or "")[:10],
            },
            "source": "best-of-seeder",
        }
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    slug = args.slug

    pi_path = CLIENTS_DIR / slug / "plan-input.json"
    if not pi_path.exists():
        print(f"{slug}: no plan-input.json — skip")
        return 0
    pi = json.loads(pi_path.read_text())
    brand = pi.get("brand", {})
    # The client's stated goals lead the rotation (2026-08-06). Without this the
    # hero service was just whatever sat first in plan-input.json, a file no
    # client can see — so "we want more water damage work" had nowhere to land.
    from content_focus import prioritise
    services = prioritise(slug, pi.get("services") or [])
    areas = pi.get("service_areas") or []
    client_name = brand.get("display_name") or slug

    raw, items = load_queue(slug)

    # one unwritten seeder item at a time (either format) — writer drains first
    pending = [it for it in items
               if it.get("source") == "best-of-seeder"
               and it.get("status") == "queued"]
    if pending:
        print(f"{slug}: seeder item already queued ({pending[0]['id']}) — nothing to seed")
        return 0

    done = existing_combo_keys(slug, items)
    # rotate four formats — each works its own matrix via distinct combo keys
    n_seeded = sum(1 for it in items if it.get("source") == "best-of-seeder")
    fmt = ("best_of_comparison", "cost_guide", "who_to_call", "case_study",
           "panic_moment")[n_seeded % 5]

    if fmt == "case_study":
        item = build_case_study_item(slug, items, done_keys=existing_combo_keys(slug, items))
        if item is None:
            print(f"{slug}: no unused story-worthy review — falling back to best-of")
            fmt = "best_of_comparison"
        else:
            if args.dry_run:
                print("  [dry-run] would queue:\n" + json.dumps(item, indent=2)[:800])
                return 0
            items.insert(0, item)
            save_queue(slug, raw)
            print(f"  queued {item['id']} (case study from review by {item['case_study']['reviewer_name']})")
            return 0

    if fmt == "panic_moment":
        # C4 (Santino 2026-09-17): the panic-moment format — the search a
        # homeowner types WHILE the water is running. Compliant by design:
        # the post honestly answers "plumber stops the source, restoration
        # dries the house" so unlicensed clients never advertise plumbing.
        PANIC_EVENTS = [
            ("burst-pipe", "burst pipe"),
            ("flooded-basement", "flooded basement"),
            ("ceiling-leaking-water", "ceiling leaking water"),
            ("sewage-backup", "sewage backup"),
            ("water-heater-flooded", "water heater flooded"),
        ]
        combo = None
        for ev_slug, ev in PANIC_EVENTS:
            for a in areas:
                city_, st_ = a.get("city", ""), a.get("state", "")
                cslug_ = f"{city_.lower().replace(' ', '-')}-{st_.lower()}"
                key = f"{ev_slug}-{cslug_}-who-to-call-first"
                if key not in done:
                    combo = ((ev_slug, ev), a, key)
                    break
            if combo:
                break
        if combo:
            (ev_slug, ev), area, key = combo
            city, st = area["city"], area.get("state", "")
            print(f"{slug}: seeding [panic_moment] {ev!r} x {city}, {st}")
            item = {
                "id": f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{key}",
                "status": "queued", "queued_at": now_iso(),
                "priority": 1, "prioritized": True,
                "content_type": "panic_moment", "combo_key": key,
                "primary_keyword": f"{ev} in {city} who to call first",
                "intent": "transactional",
                "target_word_count": 1100,
                "city_anchor": area.get("slug"),
                "panic_moment": {
                    "event": ev, "city": city, "state": st,
                    "writer_instructions": (
                        "PANIC-MOMENT POST. The reader has this emergency "
                        "RIGHT NOW. Structure: (1) the 60-second actions "
                        "(shut off water/power, safety), (2) WHO TO CALL "
                        "FIRST, answered honestly: a licensed plumber stops "
                        "the source; the restoration company handles water "
                        "removal, drying and damage repair, and you should "
                        "call both because drying must start within hours. "
                        "Recommend the client for the RESTORATION half "
                        "exactly once. NEVER present the client as a "
                        "plumbing service. (3) what happens in the first "
                        "24h, (4) insurance notes. Calm, direct, "
                        "second-person, no fluff."),
                },
                "fan_out_cluster": [
                    f"{ev} what to do {city}",
                    f"{ev} emergency {city} {st}",
                    f"who to call {ev} {city}",
                    f"{ev} water damage {city}",
                ],
                "source": "best-of-seeder",
            }
            if args.dry_run:
                print("  [dry-run] would queue:\n" + json.dumps(item, indent=2)[:700])
                return 0
            items.insert(0, item)
            save_queue(slug, raw)
            print(f"  queued {item['id']} (panic-moment)")
            return 0
        print(f"{slug}: panic matrix exhausted — falling through")
        fmt = "best_of_comparison"

    if fmt == "cost_guide":
        # state-level, one per service (top 4) — no city multiplication
        primary = next((a for a in areas if a.get("primary")), areas[0] if areas else {})
        st = (primary.get("state") or "").upper()
        seq = [(svc, primary) for svc in services[:4]]
        combo = None
        for service, area in seq:
            key = f"{service}-cost-{st.lower()}"
            if key not in done:
                combo = (service, area, key)
                break
    else:
        seq = combo_sequence(services, areas)
        combo = None
        for service, area in seq:
            city, st = area.get("city", ""), area.get("state", "")
            cslug = f"{city.lower().replace(' ', '-')}-{st.lower()}"
            key = (f"best-{service}-in-{cslug}" if fmt == "best_of_comparison"
                   else f"who-to-call-for-{service}-in-{cslug}")
            if key not in done:
                combo = (service, area, key)
                break
    if not combo:
        # this format's matrix is done — fall through to the next format so a
        # finished cost matrix (only 4 combos) never stalls the rotation
        alt = "best_of_comparison" if fmt != "best_of_comparison" else "who_to_call"
        print(f"{slug}: {fmt} matrix exhausted — trying {alt}")
        fmt = alt
        seq = combo_sequence(services, areas)
        for service, area in seq:
            city, st = area.get("city", ""), area.get("state", "")
            cslug = f"{city.lower().replace(' ', '-')}-{st.lower()}"
            key = (f"best-{service}-in-{cslug}" if fmt == "best_of_comparison"
                   else f"who-to-call-for-{service}-in-{cslug}")
            if key not in done:
                combo = (service, area, key)
                break
    if not combo:
        print(f"{slug}: all format matrices exhausted")
        return 0

    service, area, key = combo
    city, st = area["city"], area.get("state", "")
    svc_pretty = pretty(service)
    print(f"{slug}: seeding [{fmt}] {svc_pretty!r} x {city}, {st}")

    competitors = []
    if fmt == "best_of_comparison":
        try:
            competitors = fetch_competitors(service, city, st, client_name)
        except Exception as e:  # noqa: BLE001 — a failed lookup must not kill the run
            print(f"  competitor lookup failed ({e}) — seeding without comparison data")
        for c in competitors:
            print(f"  competitor: {c['name']} ({c['google_rating']}★ / {c['review_count']})")

    if fmt == "best_of_comparison":
        primary_kw = f"best {svc_pretty.lower()} company in {city}, {st}"
        fan_out = [
            f"best {svc_pretty.lower()} companies {city}",
            f"top rated {svc_pretty.lower()} {city} {st}",
            f"who is the best {svc_pretty.lower()} company in {city}",
        ]
    elif fmt == "cost_guide":
        primary_kw = f"{svc_pretty.lower()} cost {st}"
        fan_out = [
            f"how much does {svc_pretty.lower()} cost in {st}",
            f"{svc_pretty.lower()} price {st}",
            f"average cost of {svc_pretty.lower()} {st}",
        ]
    else:
        primary_kw = f"who to call for {svc_pretty.lower()} in {city}, {st}"
        fan_out = [
            f"who do you call for {svc_pretty.lower()} {city}",
            f"who do I call for {svc_pretty.lower()} in {city}",
            f"{svc_pretty.lower()} emergency number {city} {st}",
        ]

    fan_out = (fan_out + variant_fanout(
        service, city if fmt != "cost_guide" else st, slug))[:6]

    item = {
        "id": f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{key}",
        "status": "queued",
        "queued_at": now_iso(),
        "priority": 1,
        "prioritized": True,   # pop_next_queued's jump-the-line lane — a seeder
                               # item must be the NEXT post, not queue #26
        "content_type": fmt,
        "combo_key": key,
        "primary_keyword": primary_kw,
        "intent": "commercial" if fmt == "best_of_comparison" else "transactional",
        "target_word_count": {"best_of_comparison": 1600, "who_to_call": 1200,
                              "cost_guide": 1500}[fmt],
        "city_anchor": area.get("slug"),
        "best_of": {
            "service": service,
            "service_pretty": svc_pretty,
            "city": city,
            "state": st,
            "competitors": competitors,
        },
        "fan_out_cluster": fan_out,
        "source": "best-of-seeder",
    }
    if args.dry_run:
        print("  [dry-run] would queue:\n" + json.dumps(item, indent=2)[:800])
        return 0
    items.insert(0, item)
    save_queue(slug, raw)
    print(f"  queued {item['id']} (priority 1 — next post the writer produces)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
