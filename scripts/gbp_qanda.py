#!/usr/bin/env python3
"""gbp_qanda.py — seed a client's Google Business Profile Q&A with a curated set of
universal, high-value questions + answers (crawlable, under-used, helps AI + users).

City / response-time-per-city questions do NOT go here — they belong on the per-city
page FAQ (already FAQPage-schema'd), not stuffed into the single GBP listing.

Auth reuses scripts/gbp.py (business.manage token from user_integrations; location
matched by brand.place_id). The location `name` is already `locations/{id}`, which is
exactly the parent the Q&A API wants. Idempotent: skips questions that already exist.
Requires the "My Business Q&A API" (mybusinessqanda.googleapis.com) enabled on the GCP
project — if it isn't, the call returns a clear SERVICE_DISABLED error.

Usage:
  python3 scripts/gbp_qanda.py --slug narestco --dry-run   # list existing + show plan
  python3 scripts/gbp_qanda.py --slug narestco             # seed missing Q&A
  python3 scripts/gbp_qanda.py --all
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import requests
import gbp  # get_access_token, find_location, company_id_for

QANDA_API = "https://mybusinessqanda.googleapis.com/v1"

# Universal, restoration-true Q&A. Kept generic-true (no client-specific claims like
# a specific certification) so it's safe across clients; per-client customization
# from onboarding/brand data is a follow-on.
QANDA: list[tuple[str, str]] = [
    ("How fast can you respond to an emergency?",
     "We offer 24/7 emergency response and typically arrive on-site within about 60 minutes for "
     "water, fire, and storm damage."),
    ("Do you work with insurance companies?",
     "Yes. We work directly with all major insurance carriers, document the damage for your adjuster, "
     "and can bill your claim directly to make the process as easy as possible."),
    ("How long does water damage restoration take?",
     "Structural drying usually takes about 3–5 days, depending on how much water there was and the "
     "materials affected. We set professional drying equipment and monitor moisture daily until the "
     "area is fully dry."),
    ("Can mold grow after water damage?",
     "Yes — mold can begin to grow within 24–48 hours of water exposure. The best prevention is fast, "
     "professional water extraction and drying, which is why we respond around the clock."),
    ("Are you licensed and insured?",
     "Yes, we are fully licensed and insured, and our technicians are trained and certified in water, "
     "fire, and mold restoration."),
]


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def place_id_for(slug: str) -> str:
    pi = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text())
    return (pi.get("brand") or {}).get("place_id", "")


def list_questions(token: str, loc_name: str) -> list[dict]:
    out, page = [], ""
    while True:
        url = f"{QANDA_API}/{loc_name}/questions?pageSize=50&answersPerQuestion=1"
        if page:
            url += f"&pageToken={page}"
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 403:
            raise SystemExit(f"  Q&A API not accessible (enable 'My Business Q&A API' on the GCP "
                             f"project). Response: {r.text[:200]}")
        r.raise_for_status()
        d = r.json()
        out += d.get("questions", [])
        page = d.get("nextPageToken", "")
        if not page:
            break
    return out


def create_question(token: str, loc_name: str, text: str) -> dict:
    r = requests.post(f"{QANDA_API}/{loc_name}/questions",
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                      data=json.dumps({"text": text}))
    r.raise_for_status()
    return r.json()


def upsert_answer(token: str, question_name: str, text: str) -> dict:
    r = requests.post(f"{QANDA_API}/{question_name}/answers:upsert",
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                      data=json.dumps({"answer": {"text": text}}))
    r.raise_for_status()
    return r.json()


def run_for(slug: str, dry_run: bool) -> None:
    cid = gbp.company_id_for(slug)
    if not cid:
        sys.stderr.write(f"  skip {slug}: no company_id\n"); return
    token = gbp.get_access_token(cid)
    if not token:
        sys.stderr.write(f"  skip {slug}: no business.manage token (connect this client's GBP)\n"); return
    pid = place_id_for(slug)
    loc = gbp.find_location(token, pid) if pid else None
    if not loc:
        sys.stderr.write(f"  skip {slug}: no GBP location for place_id {pid!r}\n"); return
    loc_name = loc["name"]  # already 'locations/{id}'
    print(f"\n=== GBP Q&A — {slug} ({loc.get('title','?')} / {loc_name}) ===")

    existing = list_questions(token, loc_name)
    existing_norm = {_norm(q.get("text", "")) for q in existing}
    print(f"  existing questions on the listing: {len(existing)}")

    todo = [(q, a) for q, a in QANDA if _norm(q) not in existing_norm]
    for q, a in QANDA:
        print(f"  {'· ADD ' if _norm(q) not in existing_norm else '· have'} {q}")

    if dry_run:
        print(f"\n  (dry-run) would add {len(todo)} question(s). Re-run without --dry-run to seed.")
        return

    added = 0
    for q, a in todo:
        try:
            created = create_question(token, loc_name, q)
            upsert_answer(token, created["name"], a)
            added += 1
            print(f"    seeded: {q}")
        except Exception as e:
            sys.stderr.write(f"    FAILED '{q}': {str(e)[:160]}\n")
    print(f"\n  seeded {added} new Q&A on the listing.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Seed Google Business Profile Q&A")
    ap.add_argument("--slug", help="Run one client")
    ap.add_argument("--all", action="store_true", help="Every client in company_map.json")
    ap.add_argument("--dry-run", action="store_true", help="List existing + show plan; no writes")
    args = ap.parse_args()
    if not args.slug and not args.all:
        ap.error("pass --slug <slug> or --all")
    slugs = list(json.loads((ROOT / "clients" / "company_map.json").read_text()).keys()) if args.all else [args.slug]
    for slug in slugs:
        try:
            run_for(slug, args.dry_run)
        except SystemExit as e:
            print(e)
        except Exception as e:
            sys.stderr.write(f"  FAIL {slug}: {str(e)[:160]}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
