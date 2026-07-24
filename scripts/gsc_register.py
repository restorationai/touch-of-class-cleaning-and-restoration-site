#!/usr/bin/env python3
"""gsc_register.py — register + verify a client domain in Google Search Console
and submit its sitemap. Fully hands-off for domains on our Cloudflare account:

  1. Site Verification API: get a DNS TXT token for the domain
  2. Cloudflare API: place the TXT record in the zone
  3. Site Verification API: complete verification (agency account becomes owner)
  4. Search Console API: add the property + submit sitemap-index.xml

Run at cutover for every client (TRG + All Pro were live for a day with no
GSC property — found 2026-07-23). Uses the shared agency GSC token via
gsc_client.GSCClient; requires the siteverification scope on that token.

Usage: python3 scripts/gsc_register.py --domain therestorationgroup.com [--slug x]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

from googleapiclient.discovery import build  # noqa: E402

from gsc_client import GSCClient  # noqa: E402


def cf(method: str, path: str, body=None):
    req = urllib.request.Request(
        "https://api.cloudflare.com/client/v4" + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + os.environ["CLOUDFLARE_API_TOKEN"],
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def zone_id(domain: str) -> str | None:
    d = cf("GET", "/zones?name=" + domain)
    res = d.get("result") or []
    return res[0]["id"] if res else None


def ensure_txt(zid: str, domain: str, content: str) -> None:
    existing = cf("GET", f"/zones/{zid}/dns_records?type=TXT&name={domain}").get("result") or []
    if any(r.get("content", "").strip('"') == content for r in existing):
        print("  TXT already present")
        return
    cf("POST", f"/zones/{zid}/dns_records",
       {"type": "TXT", "name": domain, "content": content, "ttl": 60})
    print("  TXT placed:", content[:50] + "…")


def register(domain: str) -> int:
    gc = GSCClient("agency", domain)
    gc._ensure_service()
    creds = gc._service._http.credentials
    sv = build("siteVerification", "v1", credentials=creds, cache_discovery=False)
    gsc = gc._service

    print(f"== {domain}")
    zid = zone_id(domain)
    if not zid:
        print("  no Cloudflare zone — cannot auto-verify (do it manually in GSC)")
        return 1

    tok = sv.webResource().getToken(body={
        "site": {"type": "INET_DOMAIN", "identifier": domain},
        "verificationMethod": "DNS_TXT"}).execute()["token"]
    ensure_txt(zid, domain, tok)

    verified = False
    for attempt in range(6):
        try:
            sv.webResource().insert(verificationMethod="DNS_TXT", body={
                "site": {"type": "INET_DOMAIN", "identifier": domain}}).execute()
            verified = True
            break
        except Exception as e:
            wait = 20 * (attempt + 1)
            print(f"  verify attempt {attempt + 1}: {str(e)[:90]} — retrying in {wait}s")
            time.sleep(wait)
    if not verified:
        print("  verification did not complete (DNS may still be propagating) — re-run later")
        return 1
    print("  VERIFIED (domain property)")

    for prop in (f"sc-domain:{domain}", f"https://{domain}/"):
        try:
            gsc.sites().add(siteUrl=prop).execute()
        except Exception:
            pass
    try:
        gsc.sitemaps().submit(siteUrl=f"sc-domain:{domain}",
                              feedpath=f"https://{domain}/sitemap-index.xml").execute()
        print("  sitemap submitted (domain property)")
    except Exception as e:
        print("  sitemap submit:", str(e)[:120])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True)
    args = ap.parse_args()
    return register(args.domain.lower().strip())


if __name__ == "__main__":
    sys.exit(main())
