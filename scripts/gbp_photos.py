#!/usr/bin/env python3
"""gbp_photos.py — weekly upload of a client's REAL job photos to their Google
Business Profile photo gallery.

Consumes the field-crew intake ([[gbp-photo-intake]]): lists new photos in
branding/{company_id}/job-photos/, posts up to --limit of them to the GBP media
gallery (v4 /media, mediaFormat=PHOTO, sourceUrl=public storage URL), then moves
each to job-photos/posted/ so it's never re-posted. Fresh GBP photos are a real
map-pack + trust signal.

REAL photos only — never AI-generated (deceptive + Google detects it via SynthID).
Auth reuses scripts/gbp.py (business.manage token; location by brand.place_id).

Usage:
  python3 scripts/gbp_photos.py --slug narestco --dry-run
  python3 scripts/gbp_photos.py --slug narestco --limit 4
  python3 scripts/gbp_photos.py --all
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
import requests
import gbp  # get_access_token, find_location, company_id_for, _g, ACCT_API

GBP_V4 = "https://mybusiness.googleapis.com/v4"
BUCKET = "branding"
SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]


def _sb_headers() -> dict:
    return {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}


def list_pending(cid: str) -> list[str]:
    """Base filenames of not-yet-posted job photos for this client."""
    r = requests.post(f"{SB_URL}/storage/v1/object/list/{BUCKET}", headers=_sb_headers(),
                      json={"prefix": f"{cid}/job-photos/", "limit": 200,
                            "sortBy": {"column": "created_at", "order": "asc"}})
    r.raise_for_status()
    out = []
    for f in r.json():
        n = f.get("name") or ""
        # list returns files at this level; the posted/ archive shows as a folder entry (id=None)
        if f.get("id") and n.lower().endswith(
                (".jpg", ".jpeg", ".png", ".mp4", ".mov")):
            # videos ride the same drain (Santino 2026-09-05: the hub accepts
            # them but nothing consumed them); GBP caps video at ~75MB/30s and
            # rejects oversized ones per-file, which fail-soft below.
            out.append(n)
    return out


def public_url(cid: str, name: str) -> str:
    return f"{SB_URL}/storage/v1/object/public/{BUCKET}/{cid}/job-photos/{name}"


def mark_posted(cid: str, name: str) -> None:
    requests.post(f"{SB_URL}/storage/v1/object/move", headers=_sb_headers(),
                  json={"bucketId": BUCKET, "sourceKey": f"{cid}/job-photos/{name}",
                        "destinationKey": f"{cid}/job-photos/posted/{name}"})


def resolve(slug: str):
    cid = gbp.company_id_for(slug)
    tok = gbp.get_access_token(cid) if cid else None
    if not tok:
        raise SystemExit(f"{slug}: no business.manage token (connect this client's GBP)")
    acct = gbp._g(f"{gbp.ACCT_API}/accounts", tok)["accounts"][0]["name"]
    brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
    loc = gbp.find_location(tok, brand.get("place_id", ""))
    if not loc:
        raise SystemExit(f"{slug}: no GBP location for place_id {brand.get('place_id')}")
    return tok, acct, loc["name"].split("/")[-1]


def upload_photo(tok: str, acct: str, locid: str, url: str) -> dict:
    fmt = "VIDEO" if url.lower().endswith((".mp4", ".mov")) else "PHOTO"
    body = {"mediaFormat": fmt, "locationAssociation": {"category": "ADDITIONAL"}, "sourceUrl": url}
    r = requests.post(f"{GBP_V4}/{acct}/locations/{locid}/media",
                      headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}, json=body)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def run_for(slug: str, limit: int, dry_run: bool) -> None:
    cid = gbp.company_id_for(slug)
    if not cid:
        sys.stderr.write(f"  skip {slug}: no company_id\n"); return
    names = list_pending(cid)
    print(f"\n=== GBP photos — {slug} — {len(names)} new, uploading up to {limit} ===")
    if not names:
        print("  no new photos to post (crews upload via restorationai.io/gbpphotos/<slug>)."); return
    batch = names[:limit]
    if dry_run:
        for n in batch:
            print(f"  [dry-run] would upload: {public_url(cid, n)}")
        return
    tok, acct, locid = resolve(slug)
    posted = 0
    for n in batch:
        try:
            upload_photo(tok, acct, locid, public_url(cid, n))
            mark_posted(cid, n)
            posted += 1
            print(f"  ✓ uploaded + archived: {n}")
        except Exception as e:
            sys.stderr.write(f"  FAILED {n}: {str(e)[:180]}\n")
    if posted:
        gbp.log_change(cid, "photo",
                       f"{posted} job photo{'s' if posted != 1 else ''} posted to the Google listing",
                       actor="automation", meta={"count": posted})
    print(f"  posted {posted} photo(s) to GBP.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Upload real job photos to GBP")
    ap.add_argument("--slug", help="Run one client")
    ap.add_argument("--all", action="store_true", help="Every client in company_map.json")
    ap.add_argument("--limit", type=int, default=4, help="Max photos to post per client per run")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.slug and not args.all:
        ap.error("pass --slug <slug> or --all")
    slugs = list(json.loads((ROOT / "clients" / "company_map.json").read_text()).keys()) if args.all else [args.slug]
    for slug in slugs:
        try:
            run_for(slug, args.limit, args.dry_run)
        except SystemExit as e:
            print(e)
        except Exception as e:
            sys.stderr.write(f"  FAIL {slug}: {str(e)[:160]}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
