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
        for pattern in ("best-*-in-*.md", "who-to-call-for-*.md", "*-cost-*.md"):
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
        # never list the client as their own competitor
        if client_tokens and client_tokens & {t for t in name.lower().split() if len(t) > 3}:
            continue
        out.append({"name": name, "google_rating": rating,
                    "review_count": votes or 0})
        if len(out) >= MAX_COMPETITORS:
            break
    return out


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
    services = pi.get("services") or []
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
    # rotate three formats — each works its own matrix via distinct combo keys
    n_seeded = sum(1 for it in items if it.get("source") == "best-of-seeder")
    fmt = ("best_of_comparison", "cost_guide", "who_to_call")[n_seeded % 3]

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
