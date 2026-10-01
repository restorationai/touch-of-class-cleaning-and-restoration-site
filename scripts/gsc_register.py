#!/usr/bin/env python3
"""gsc_register.py — register + verify a client domain in Google Search Console
and submit its sitemap. Fully hands-off for domains on our Cloudflare account:

  1. Search Console API: if the agency account already owns the property,
     skip straight to step 5 (idempotent fast path, safe to run weekly)
  2. Site Verification API: get a DNS TXT token for the domain
  3. Cloudflare API: place the TXT record in the zone
  4. Site Verification API: complete verification (agency account becomes owner)
  5. Search Console API: add the property + submit sitemap-index.xml
  6. Write gsc_property_url / gsc_verified_at / gsc_sitemap_url back to
     marketing_sites (the canonical store; 2026-10-01: 17 of 29 live sites
     had it empty because this script never wrote it back)

Run at cutover for every client (TRG + All Pro were live for a day with no
GSC property — found 2026-07-23). Uses the shared agency GSC token via
gsc_client.GSCClient; requires the siteverification scope on that token.

Usage:
  python3 scripts/gsc_register.py --domain therestorationgroup.com [--slug x]
  python3 scripts/gsc_register.py --slug narestco
  python3 scripts/gsc_register.py --all-live [--skip tdi-builders]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
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

OWNER_LEVELS = {"siteOwner", "siteFullUser"}


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


def slug_for_domain(domain: str) -> str | None:
    for f in sorted((ROOT / "clients").glob("*.json")):
        try:
            rec = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(rec, dict) and (rec.get("domain") or "").strip().lower() == domain:
            return f.stem
    return None


def write_back(slug: str | None, prop: str, sitemap: str | None) -> None:
    """Canonical store: marketing_sites (one row per rank_ai_slug). Fail-soft."""
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not (slug and url and key):
        print("  write-back skipped (no slug or Supabase env)")
        return
    body = {"gsc_property_url": prop,
            "gsc_verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if sitemap:
        body["gsc_sitemap_url"] = sitemap
    req = urllib.request.Request(
        f"{url.rstrip('/')}/rest/v1/marketing_sites?rank_ai_slug=eq.{slug}",
        method="PATCH", data=json.dumps(body).encode(),
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            rows = json.loads(r.read() or b"[]")
        print(f"  marketing_sites updated ({len(rows)} row)" if rows
              else f"  WARN: no marketing_sites row for {slug}")
    except Exception as e:  # noqa: BLE001
        print(f"  WARN: marketing_sites write-back failed: {str(e)[:120]}")


def owned_property(gsc, domain: str) -> str | None:
    """The property the agency account already owns for this domain, if any
    (domain property preferred over the URL-prefix one)."""
    try:
        entries = gsc.sites().list().execute().get("siteEntry") or []
    except Exception:  # noqa: BLE001
        return None
    have = {e["siteUrl"]: e.get("permissionLevel") for e in entries}
    for prop in (f"sc-domain:{domain}", f"https://{domain}/", f"https://www.{domain}/"):
        if have.get(prop) in OWNER_LEVELS:
            return prop
    return None


def submit_sitemap(gsc, prop: str, domain: str) -> str | None:
    feed = f"https://{domain}/sitemap-index.xml"
    try:
        gsc.sitemaps().submit(siteUrl=prop, feedpath=feed).execute()
        print(f"  sitemap submitted ({prop})")
        return feed
    except Exception as e:  # noqa: BLE001
        print("  sitemap submit:", str(e)[:120])
        return None


def register(domain: str, slug: str | None = None) -> int:
    slug = slug or slug_for_domain(domain)
    gc = GSCClient("agency", domain)
    gc._ensure_service()
    creds = gc._service._http.credentials
    gsc = gc._service

    print(f"== {domain}" + (f" ({slug})" if slug else ""))
    prop = owned_property(gsc, domain)
    if prop:
        print(f"  already a verified property: {prop}")
        write_back(slug, prop, submit_sitemap(gsc, prop, domain))
        return 0

    sv = build("siteVerification", "v1", credentials=creds, cache_discovery=False)
    zid = zone_id(domain)
    if not zid:
        print("  FAIL: no Cloudflare zone on our account, cannot auto-verify "
              "(verify in GSC by hand, or move NS to us)")
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
        print("  FAIL: verification did not complete (DNS may still be propagating) — re-run later")
        return 1
    print("  VERIFIED (domain property)")

    for p in (f"sc-domain:{domain}", f"https://{domain}/"):
        try:
            gsc.sites().add(siteUrl=p).execute()
        except Exception:
            pass
    prop = f"sc-domain:{domain}"
    write_back(slug, prop, submit_sitemap(gsc, prop, domain))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--domain")
    g.add_argument("--slug", help="resolve the domain from clients/{slug}.json")
    g.add_argument("--all-live", action="store_true",
                   help="every live site (index_watchdog.live_slugs)")
    ap.add_argument("--skip", action="append", default=[],
                    help="slug to leave alone (repeatable)")
    args = ap.parse_args()
    if args.domain:
        return register(args.domain.lower().strip())
    if args.slug:
        rec = json.loads((ROOT / "clients" / f"{args.slug}.json").read_text())
        return register(rec["domain"].strip().lower(), args.slug)
    from index_watchdog import live_slugs  # noqa: PLC0415
    fails = []
    for s in live_slugs():
        if s in args.skip:
            continue
        rec = json.loads((ROOT / "clients" / f"{s}.json").read_text())
        try:
            rc = register(rec["domain"].strip().lower(), s)
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL: {type(e).__name__}: {str(e)[:160]}")
            rc = 1
        if rc:
            fails.append(s)
    print(f"\ndone; failed: {fails or 'none'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
