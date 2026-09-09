#!/usr/bin/env python3
"""upload_links_sync.py — sync the branded photo-upload link map (slug -> {cid, name})
into Cloudflare KV, so restorationai.io/gbpphotos/<slug> works for EVERY client with no
Worker redeploy. Run after adding a client (or wire into onboarding).

Env: CLOUDFLARE_R2_API_TOKEN (the token with Workers/KV access on the restorationai.io
account) + CLOUDFLARE_ACCOUNT_ID. KV namespace: 'upload-links' (created once).
"""
from __future__ import annotations

import json, os, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

TOKEN = os.environ.get("CLOUDFLARE_R2_API_TOKEN")
ACCT = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
KV_TITLE = "upload-links"


def cf(method: str, path: str, body=None) -> dict:
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4{path}",
        data=json.dumps(body).encode() if body is not None else None, method=method,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def kv_namespace_id() -> str:
    d = cf("GET", f"/accounts/{ACCT}/storage/kv/namespaces?per_page=100")
    for ns in d.get("result", []):
        if ns.get("title") == KV_TITLE:
            return ns["id"]
    raise SystemExit(f"KV namespace '{KV_TITLE}' not found — create it first.")


def client_name(slug: str) -> str:
    p = ROOT / "clients" / slug / "plan-input.json"
    if p.exists():
        return (json.loads(p.read_text()).get("brand") or {}).get("display_name") or slug
    return slug


_DB_PLACE_IDS = None


def _db_place_ids() -> dict:
    """company_id -> place_id from the app's google connections. The ROOT
    CAUSE of every missing hub QR (Reign 08-13, Arch 09-07, DryCor/DISS/
    Frontline 09-09): the OAuth connect stores place_id in the app DB, but
    nothing copied it into clients/{slug}.json, and review_url only read the
    json. This fallback makes the DB the authority so a connected GBP ALWAYS
    yields a QR, no stamping step required. Fail-soft: without Supabase env
    the old json-only behavior remains."""
    global _DB_PLACE_IDS
    if _DB_PLACE_IDS is not None:
        return _DB_PLACE_IDS
    _DB_PLACE_IDS = {}
    sb = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if sb and key:
        try:
            import requests as _rq
            rows = _rq.get(
                f"{sb}/rest/v1/user_integrations?provider=eq.google"
                "&status=eq.active&select=client_id,connection_metadata",
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
                timeout=30).json()
            for r in rows:
                pid = (r.get("connection_metadata") or {}).get("place_id")
                if pid:
                    _DB_PLACE_IDS[r["client_id"]] = pid
        except Exception as e:  # noqa: BLE001
            print(f"  [review-url] DB place_id fetch failed: {str(e)[:80]}")
    return _DB_PLACE_IDS


def review_url(slug: str, company_id: str | None = None):
    p = ROOT / "clients" / f"{slug}.json"
    g = json.loads(p.read_text()).get("gbp") if p.exists() else {}
    g = g or {}
    # 2026-08-13 (Santino, Reign's hub had no QR): the review URL is fully
    # derivable from place_id, so a recorded place_id must ALWAYS yield the
    # QR card — hand-filled google_review_url was an early-client artifact.
    if g.get("google_review_url"):
        return g["google_review_url"]
    pid = g.get("place_id") or (_db_place_ids().get(company_id) if company_id else None)
    if pid:
        return f"https://search.google.com/local/writereview?placeid={pid}"
    return None


def hub_token(slug: str) -> str:
    """Deterministic per-client secret for /hub/{slug}/{token} — derived from
    CONNECT_LINK_SIGNING_SECRET so the URL is stable and printable anywhere
    without extra storage. Worker just compares against the KV value."""
    import hashlib
    import hmac as hmac_mod
    secret = os.environ.get("CONNECT_LINK_SIGNING_SECRET", "")
    if not secret:
        sys.exit("CONNECT_LINK_SIGNING_SECRET required for hub tokens")
    return hmac_mod.new(secret.encode(), f"hub:{slug}".encode(),
                        hashlib.sha256).hexdigest()[:10]


def main() -> int:
    if not (TOKEN and ACCT):
        sys.exit("CLOUDFLARE_R2_API_TOKEN + CLOUDFLARE_ACCOUNT_ID required")
    ns = kv_namespace_id()
    m = json.loads((ROOT / "clients" / "company_map.json").read_text())
    bulk = []
    for slug, cid in m.items():
        v = {"cid": cid, "name": client_name(slug), "hub": hub_token(slug)}
        ru = review_url(slug, cid)
        if ru:
            v["review_url"] = ru
        bulk.append({"key": slug, "value": json.dumps(v)})
    d = cf("PUT", f"/accounts/{ACCT}/storage/kv/namespaces/{ns}/bulk", bulk)
    print(f"synced {len(bulk)} upload links to KV | success: {d.get('success')}")

    # SELF-HOSTED REVIEW QR (2026-08-19, build queue #11): pre-generate each
    # client's QR PNG into the public branding bucket; the hub serves it with
    # the third-party generator only as an onerror fallback. Idempotent:
    # skips clients whose PNG already exists.
    try:
        import io
        import segno
        import requests as _rq
        sb = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
        sk = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
              or os.environ.get("SUPABASE_SERVICE_KEY"))
        if sb and sk:
            hdr = {"apikey": sk, "Authorization": f"Bearer {sk}"}
            made = 0
            for slug, cid in m.items():
                ru = review_url(slug, cid)
                if not ru:
                    continue
                path = f"{cid}/brand/review-qr.png"
                head = _rq.get(f"{sb}/storage/v1/object/public/branding/{path}",
                               timeout=15)
                if head.status_code == 200:
                    continue
                buf = io.BytesIO()
                segno.make(ru, error="m").save(buf, kind="png", scale=14,
                                               border=2)
                up = _rq.post(f"{sb}/storage/v1/object/branding/{path}",
                              headers={**hdr, "Content-Type": "image/png",
                                       "x-upsert": "true"},
                              data=buf.getvalue(), timeout=30)
                if up.ok:
                    made += 1
            if made:
                print(f"generated {made} self-hosted review QR code(s)")
    except ImportError:
        print("segno not installed — QR pre-generation skipped (hub falls "
              "back to qrserver)")
    for slug in m:
        print(f"  hub: https://restorationai.io/hub/{slug}/{hub_token(slug)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
