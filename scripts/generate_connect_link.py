#!/usr/bin/env python3
"""
generate_connect_link.py — mint a one-time, HMAC-signed "connect your account" link
to email/text a client so they can authorize Google Ads / GBP / Search Console /
YouTube WITHOUT logging into the app.

Flow: this inserts a one-time row in Supabase `connect_links`, signs a token over
{cid, provider, jti, exp} with CONNECT_LINK_SIGNING_SECRET (same secret set on the
connect-link-* edge functions), and prints the tappable link
(<SUPABASE_URL>/functions/v1/connect-link-start?t=<token>).

Usage:
    python3 scripts/generate_connect_link.py --slug narestco --provider google
    python3 scripts/generate_connect_link.py --slug narestco --provider youtube --days 14
    python3 scripts/generate_connect_link.py --company-id CO-123 --provider google

Env (rank-ai/.env): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, CONNECT_LINK_SIGNING_SECRET
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

PROVIDERS = {
    "google":  "Google Ads + Business Profile + Search Console",
    "youtube": "YouTube channel",
}


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def company_id_for(slug: str) -> str | None:
    # record first, then the centralized map (mirrors the pipeline)
    rec = ROOT / "clients" / f"{slug}.json"
    if rec.exists():
        cid = json.loads(rec.read_text()).get("company_id")
        if cid:
            return cid
    cmap = ROOT / "clients" / "company_map.json"
    if cmap.exists():
        return json.loads(cmap.read_text()).get(slug)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--company-id")
    ap.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    ap.add_argument("--days", type=int, default=30, help="link validity window")
    ap.add_argument("--label", default="", help="note stored in connect_links.created_by")
    args = ap.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    secret = os.environ.get("CONNECT_LINK_SIGNING_SECRET")
    if not (url and key and secret):
        print("ERROR: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, and CONNECT_LINK_SIGNING_SECRET "
              "must be set (rank-ai/.env). The secret must match the edge functions.", file=sys.stderr)
        return 1

    company_id = args.company_id or company_id_for(args.slug)
    if not company_id:
        print(f"ERROR: no company_id for slug '{args.slug}' (not in clients/company_map.json).", file=sys.stderr)
        return 1

    jti = str(uuid.uuid4())
    exp = int(time.time()) + args.days * 86400

    # 1) insert the one-time row (service role)
    row = {
        "jti": jti, "company_id": company_id, "provider": args.provider,
        "expires_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(exp)),
        "created_by": args.label or (args.slug or company_id),
    }
    req = urllib.request.Request(
        url.rstrip("/") + "/rest/v1/connect_links",
        data=json.dumps(row).encode(),
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        print(f"ERROR inserting connect_links row: {e.code} {e.read().decode(errors='replace')}", file=sys.stderr)
        return 1

    # 2) sign the token over base64url(payload)
    payload = {"cid": company_id, "p": args.provider, "jti": jti, "exp": exp}
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig_b64 = _b64url(hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).digest())
    token = f"{payload_b64}.{sig_b64}"

    link = f"{url.rstrip('/')}/functions/v1/connect-link-start?t={token}"

    print(f"\n  Client:    {args.slug or company_id}  ({company_id})")
    print(f"  Connect:   {PROVIDERS[args.provider]}")
    print(f"  Expires:   {row['expires_at']}  (one-time use)")
    print(f"\n  LINK (email/text this to the client):\n  {link}\n")
    label = "Google Ads" if args.provider == "google" else "YouTube"
    print(f"  Suggested message:\n"
          f"  \"Here's your secure link to connect your {label} to Rank AI — "
          f"just tap and approve, no login needed: {link}\"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
