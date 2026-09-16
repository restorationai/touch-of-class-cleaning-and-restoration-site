#!/usr/bin/env python3
"""
create_ga4.py — create a GA4 property + web data stream for a client and save the
Measurement ID into their site (via analytics_set). Uses the Analytics Admin API
with an OAuth refresh token from our agency Google account (analytics.edit scope).

The property is created under OUR agency GA account (we own/retain the data; grant
the client viewer access separately). Idempotent-ish: skips if brand.ts already has
a ga4MeasurementId, unless --force.

One-time setup (see the consent URL printed by --auth-url):
    GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET   (already in .env)
    GOOGLE_ANALYTICS_REFRESH_TOKEN  — refresh token with scope
        https://www.googleapis.com/auth/analytics.edit
    GOOGLE_ANALYTICS_ACCOUNT_ID     — our agency GA account id (digits only)

Usage:
    python3 scripts/create_ga4.py --auth-url                  # print consent URL
    python3 scripts/create_ga4.py --slug narestco            # create + save
    python3 scripts/create_ga4.py --all --push               # all clients, deploy
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass
import analytics_set  # noqa: E402  reuse the brand.ts writer

ADMIN = "https://analyticsadmin.googleapis.com/v1beta"
SCOPE = "https://www.googleapis.com/auth/analytics.edit"
CLIENTS = ROOT / "clients"
SITES = ROOT / "sites"


def auth_url() -> str:
    cid = os.environ["GOOGLE_OAUTH_CLIENT_ID"]
    # urn:ietf:wg:oauth:2.0:oob is deprecated; use loopback/manual copy via prompt=consent.
    params = {
        "client_id": cid,
        "redirect_uri": "http://localhost:5173/oauth/callback",
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)


def access_token() -> str:
    # Prefer a service-account key (Editor on our GA4 account) — no OAuth consent needed.
    sa = os.environ.get("GOOGLE_ANALYTICS_SA_KEY")
    if sa and Path(sa).exists():
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request as GReq
        creds = service_account.Credentials.from_service_account_file(sa, scopes=[SCOPE])
        creds.refresh(GReq())
        return creds.token
    rt = os.environ.get("GOOGLE_ANALYTICS_REFRESH_TOKEN")
    cid = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if not (rt and cid and secret):
        raise SystemExit("Missing GOOGLE_ANALYTICS_REFRESH_TOKEN / GOOGLE_OAUTH_CLIENT_ID / "
                         "GOOGLE_OAUTH_CLIENT_SECRET. Run --auth-url first.")
    data = urllib.parse.urlencode({
        "client_id": cid, "client_secret": secret,
        "refresh_token": rt, "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["access_token"]


def _api(method: str, path: str, token: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        ADMIN + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def client_meta(slug: str) -> dict:
    rec = json.loads((CLIENTS / f"{slug}.json").read_text())
    pi = json.loads((CLIENTS / slug / "plan-input.json").read_text())
    brand = pi.get("brand", {})
    domain = rec.get("domain") or ""
    areas = pi.get("service_areas", [])
    primary = next((a for a in areas if a.get("primary")), areas[0] if areas else {})
    return {"name": brand.get("display_name") or rec.get("display_name") or slug,
            "domain": domain, "state": primary.get("state", "")}


def has_ga4(slug: str) -> bool:
    bp = SITES / slug / "src" / "lib" / "brand.ts"
    if not bp.exists():
        return False
    import re
    m = re.search(r'ga4MeasurementId:\s*"([^"]*)"', bp.read_text())
    return bool(m and m.group(1))


_SKIP_STATUSES = {"suspended", "paused", "inactive", "cancelled", "canceled", "churned"}


def create_for(slug: str, token: str, account_id: str, push: bool, force: bool) -> int:
    if has_ga4(slug) and not force:
        print(f"  {slug}: already has a GA4 id — skipping (use --force to recreate)")
        return 0
    # Gate BEFORE creating the property: no scaffolded site means nowhere to
    # put the tag (Burley 2026-08-31 got an orphan property this way), and
    # suspended/paused clients get nothing new provisioned.
    status = ""
    try:
        status = str(json.loads((CLIENTS / f"{slug}.json").read_text()).get("status") or "")
    except Exception:
        pass
    if status.lower() in _SKIP_STATUSES:
        print(f"  {slug}: status '{status}' — skipping")
        return 0
    if not (SITES / slug / "src" / "lib" / "brand.ts").exists():
        print(f"  {slug}: no scaffolded site (no brand.ts) — skipping")
        return 0
    meta = client_meta(slug)
    # 1) property
    prop = _api("POST", "/properties", token, {
        "parent": f"accounts/{account_id}",
        "displayName": meta["name"],
        "timeZone": "America/Los_Angeles",
        "currencyCode": "USD",
    })
    pid = prop["name"].split("/")[-1]   # "properties/123" -> "123"
    # 2) web data stream
    uri = f"https://{meta['domain']}" if meta["domain"] else "https://example.com"
    stream = _api("POST", f"/properties/{pid}/dataStreams", token, {
        "type": "WEB_DATA_STREAM",
        "displayName": f"{meta['name']} — Website",
        "webStreamData": {"defaultUri": uri},
    })
    mid = stream.get("webStreamData", {}).get("measurementId", "")
    print(f"  {slug}: property {pid} + stream -> {mid}")
    if not mid:
        print(f"  ! {slug}: no measurementId returned", file=sys.stderr)
        return 1
    # 3) save into the site + plan-input
    analytics_set.update_brand_ts(slug, mid, None)
    analytics_set.mirror_plan_input(slug, mid, None)
    # E18 (2026-09-16): finish the wiring in the same breath — key events
    # (click_to_call, generate_lead) + Ads link when the customer id is on
    # file. Fail-open: a wiring hiccup never blocks property creation.
    try:
        import subprocess as _sp
        r = _sp.run([sys.executable, str(ROOT / "scripts" / "ga4_wire.py"),
                     "--slug", slug], capture_output=True, text=True,
                    timeout=300)
        tail = (r.stdout or r.stderr).strip().splitlines()[-1:]
        print(f"  ga4-wire: {tail[0][:100] if tail else r.returncode}")
    except Exception as e:  # noqa: BLE001
        print(f"  ga4-wire failed (run scripts/ga4_wire.py --slug {slug}): "
              f"{str(e)[:80]}")
    if push:
        analytics_set.git_push_site(slug)
        print(f"  {slug}: pushed site repo (Cloudflare redeploys)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--auth-url", action="store_true", help="print the one-time consent URL")
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--slug")
    grp.add_argument("--all", action="store_true")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if args.auth_url:
        print(auth_url())
        print("\nAfter granting, exchange the ?code= for a refresh token and set "
              "GOOGLE_ANALYTICS_REFRESH_TOKEN in .env.")
        return 0

    account_id = os.environ.get("GOOGLE_ANALYTICS_ACCOUNT_ID")
    if not account_id:
        print("ERROR: set GOOGLE_ANALYTICS_ACCOUNT_ID (our agency GA account id).", file=sys.stderr)
        return 1
    token = access_token()
    slugs = (list(json.loads((CLIENTS / "company_map.json").read_text()))
             if args.all else [args.slug] if args.slug else [])
    if not slugs:
        print("Pass --slug or --all.", file=sys.stderr)
        return 1
    rc = 0
    for s in slugs:
        try:
            rc |= create_for(s, token, account_id, args.push, args.force)
        except Exception as ex:  # noqa: BLE001 — one client never sinks the fleet
            print(f"  {s}: ERROR {type(ex).__name__}: {str(ex)[:140]}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
