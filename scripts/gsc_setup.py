#!/usr/bin/env python3
"""
Rank AI — Google Search Console OAuth setup + headless domain provisioning.

ONE-TIME agency setup: run the browser OAuth flow for contact@restorationai.io.
Then provision any client domain fully headlessly — no manual GSC clicks needed.

Provisioning does, in order:
  1. Get a DNS TXT verification token from the Site Verification API
  2. Add the TXT record to Cloudflare DNS (zone must be active in CF)
  3. Poll until the record resolves (typically <60s)
  4. Trigger site ownership verification via the Site Verification API
  5. Add the domain property to Search Console (sc-domain:{domain})
  6. Submit the sitemap
  7. Write gsc: {...} back to clients/{slug}.json

Prerequisites (one-time, agency-wide):
  - Google Cloud project with Search Console API + Site Verification API enabled
  - OAuth 2.0 Desktop client created, secret saved to rank-ai/.gsc-oauth-client.json
  - contact@restorationai.io added as a test user on the consent screen
    (only required while app is in Testing; skip once published)
  - CLOUDFLARE_API_TOKEN env var (zone:DNS:Edit permission) for TXT record addition

Usage:
  python3 scripts/gsc_setup.py                          # agency OAuth flow (one-time)
  python3 scripts/gsc_setup.py --force                  # re-run OAuth even if token exists
  python3 scripts/gsc_setup.py provision --slug narestco  # full headless provisioning
  python3 scripts/gsc_setup.py test --slug narestco       # verify existing access
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OAUTH_CLIENT_PATH = ROOT / ".gsc-oauth-client.json"
AGENCY_TOKEN_PATH = ROOT / ".gsc-agency-token.json"

# Full scopes needed — webmasters (read+write) + siteverification
SCOPES = [
    "https://www.googleapis.com/auth/webmasters",
    "https://www.googleapis.com/auth/siteverification",
]

CF_API_BASE = "https://api.cloudflare.com/client/v4"
SITEVERIF_BASE = "https://www.googleapis.com/siteVerification/v1"
GSC_BASE = "https://www.googleapis.com/webmasters/v3"


# ---------------------------------------------------------------------------
# Credential helpers
# ---------------------------------------------------------------------------


def _load_credentials():
    """Load and refresh the agency OAuth credentials. Returns a Credentials object."""
    if not AGENCY_TOKEN_PATH.exists():
        sys.exit(
            f"ERROR: Agency token not found at {AGENCY_TOKEN_PATH}.\n"
            f"Run: python3 scripts/gsc_setup.py"
        )
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        sys.exit(
            "Missing deps. Run: pip install google-auth google-auth-oauthlib "
            "google-api-python-client"
        )

    token_data = json.loads(AGENCY_TOKEN_PATH.read_text())

    # Check scopes — if token was issued with readonly only, force re-auth
    stored_scopes = set(token_data.get("scopes", []))
    required_scopes = set(SCOPES)
    if not required_scopes.issubset(stored_scopes):
        sys.exit(
            "ERROR: Existing agency token has insufficient scopes.\n"
            "       Re-run: python3 scripts/gsc_setup.py --force\n"
            "       (opens browser once, then all future ops are headless)"
        )

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=SCOPES,
    )
    # Stored tokens often lack an `expiry`, which makes google-auth treat a
    # stale access token as still valid (it skips the refresh -> 401). Whenever
    # a refresh token is present, mint a fresh access token if the creds aren't
    # provably valid, and persist the expiry so later loads can judge validity.
    if creds.refresh_token and (not creds.valid or creds.expiry is None):
        creds.refresh(Request())
        token_data["token"] = creds.token
        if creds.expiry is not None:
            token_data["expiry"] = creds.expiry.isoformat()
        AGENCY_TOKEN_PATH.write_text(json.dumps(token_data, indent=2))
    return creds


def _auth_header(creds) -> dict:
    return {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}


def _cf_auth_header() -> dict:
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not token:
        sys.exit(
            "ERROR: CLOUDFLARE_API_TOKEN env var not set.\n"
            "       `set -a && source rank-ai/.env && set +a` first."
        )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _http(method: str, url: str, headers: dict, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {method} {url}: {detail}") from exc


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------


def _get_or_fetch_zone_id(domain: str, client_record: dict, slug: str) -> str:
    """Return CF zone_id from client record or look it up and store it."""
    zone_id = (client_record.get("cloudflare") or {}).get("zone_id")
    if zone_id:
        return zone_id

    print(f"    Looking up Cloudflare zone for {domain} ...")
    result = _http(
        "GET",
        f"{CF_API_BASE}/zones?name={domain}",
        _cf_auth_header(),
    )
    zones = result.get("result", [])
    if not zones:
        sys.exit(
            f"ERROR: No Cloudflare zone found for {domain}.\n"
            f"       Complete the onboarding (nameserver migration) before provisioning GSC."
        )
    zone_id = zones[0]["id"]
    print(f"    Zone ID: {zone_id}")

    # Persist zone_id back to client record
    record_path = ROOT / "clients" / f"{slug}.json"
    client_record.setdefault("cloudflare", {})["zone_id"] = zone_id
    record_path.write_text(json.dumps(client_record, indent=2))

    return zone_id


def _get_siteverification_token(domain: str, creds) -> str:
    """Request a DNS TXT verification token from the Site Verification API."""
    print(f"    Requesting Site Verification token for {domain} ...")
    resp = _http(
        "POST",
        f"{SITEVERIF_BASE}/token",
        _auth_header(creds),
        {"verificationMethod": "DNS_TXT", "site": {"type": "INET_DOMAIN", "identifier": domain}},
    )
    token = resp.get("token", "")
    if not token:
        sys.exit(f"ERROR: Site Verification API returned no token: {resp}")
    print(f"    TXT token: {token}")
    return token


def _add_cloudflare_txt(zone_id: str, domain: str, txt_value: str) -> str:
    """Add a TXT DNS record to Cloudflare. Returns the record ID."""
    print(f"    Adding TXT record to Cloudflare DNS ...")

    # Check if record already exists (idempotent re-run)
    existing = _http(
        "GET",
        f"{CF_API_BASE}/zones/{zone_id}/dns_records?type=TXT&name={domain}&content={urllib.parse.quote(txt_value)}",
        _cf_auth_header(),
    )
    if existing.get("result"):
        record_id = existing["result"][0]["id"]
        print(f"    TXT record already exists (id={record_id}), reusing.")
        return record_id

    resp = _http(
        "POST",
        f"{CF_API_BASE}/zones/{zone_id}/dns_records",
        _cf_auth_header(),
        {"type": "TXT", "name": domain, "content": txt_value, "ttl": 1},
    )
    record_id = resp.get("result", {}).get("id", "")
    print(f"    TXT record created (id={record_id})")
    return record_id


def _poll_dns_txt(domain: str, txt_value: str, timeout: int = 120) -> bool:
    """Poll Cloudflare's public DNS API until the TXT record resolves."""
    print(f"    Polling DNS propagation (up to {timeout}s) ...")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = _http(
                "GET",
                f"https://cloudflare-dns.com/dns-query?name={domain}&type=TXT",
                {"Accept": "application/dns-json"},
            )
            answers = resp.get("Answer", [])
            for a in answers:
                if txt_value.strip('"') in a.get("data", "").strip('"'):
                    print(f"    TXT record resolved.")
                    return True
        except Exception:
            pass
        time.sleep(8)
    return False


def _verify_site(domain: str, creds, retries: int = 5) -> None:
    """Trigger ownership verification via the Site Verification API."""
    print(f"    Triggering site ownership verification ...")
    for attempt in range(1, retries + 1):
        try:
            _http(
                "POST",
                f"{SITEVERIF_BASE}/webResource?verificationMethod=DNS_TXT",
                _auth_header(creds),
                {"site": {"type": "INET_DOMAIN", "identifier": domain}},
            )
            print(f"    Verification successful.")
            return
        except RuntimeError as exc:
            if "400" in str(exc) and attempt < retries:
                print(f"    Verification attempt {attempt} failed (DNS may still be propagating). Retrying in 15s ...")
                time.sleep(15)
            else:
                raise


def _add_gsc_property(domain: str, creds) -> None:
    """Add the domain property to Search Console. Idempotent — 200 or 204 both fine."""
    site_url = urllib.parse.quote(f"sc-domain:{domain}", safe="")
    print(f"    Adding sc-domain:{domain} to Search Console ...")
    try:
        _http("PUT", f"{GSC_BASE}/sites/{site_url}", _auth_header(creds))
    except RuntimeError as exc:
        # 400 with "already a site owner" is fine
        if "400" in str(exc) and "already" in str(exc).lower():
            print(f"    Property already exists in Search Console.")
        else:
            raise
    print(f"    Property added.")


def _submit_sitemap(domain: str, sitemap_url: str, creds) -> None:
    """Submit the sitemap to Search Console."""
    site_url = urllib.parse.quote(f"sc-domain:{domain}", safe="")
    sm_url = urllib.parse.quote(sitemap_url, safe="")
    print(f"    Submitting sitemap: {sitemap_url} ...")
    try:
        _http("PUT", f"{GSC_BASE}/sites/{site_url}/sitemaps/{sm_url}", _auth_header(creds))
        print(f"    Sitemap submitted.")
    except RuntimeError as exc:
        # Non-fatal — sitemap submission errors don't block usage
        print(f"    WARNING: sitemap submission failed (non-fatal): {exc}")


def _update_client_gsc(slug: str, domain: str, sitemap_url: str) -> None:
    """Write gsc: {...} into the client record."""
    record_path = ROOT / "clients" / f"{slug}.json"
    client = json.loads(record_path.read_text())
    client["gsc"] = {
        "property_url": f"sc-domain:{domain}",
        "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sitemap_url": sitemap_url,
    }
    client["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record_path.write_text(json.dumps(client, indent=2))
    print(f"    Client record updated with gsc block.")


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_setup(args) -> int:
    """Run (or re-run) the browser OAuth flow for the agency account."""
    if not OAUTH_CLIENT_PATH.exists():
        sys.stderr.write(
            f"ERROR: OAuth client secret not found at {OAUTH_CLIENT_PATH}.\n"
            f"Download it from Google Cloud Console > APIs & Services > Credentials\n"
            f"and save it to that path.\n"
        )
        return 1

    if AGENCY_TOKEN_PATH.exists() and not args.force:
        token_data = json.loads(AGENCY_TOKEN_PATH.read_text())
        stored_scopes = set(token_data.get("scopes", []))
        required_scopes = set(SCOPES)
        if required_scopes.issubset(stored_scopes):
            print(f"Agency token already exists with correct scopes.")
            print("Use --force to redo the OAuth flow.")
            return 0
        else:
            print("Agency token exists but has insufficient scopes — re-running OAuth flow.")

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        sys.stderr.write(
            "Missing Python deps. Run:\n"
            "  pip install google-auth google-auth-oauthlib google-api-python-client\n"
        )
        return 1

    print("==> Agency GSC OAuth flow")
    print("    Sign in as contact@restorationai.io when the browser opens.")
    print("    New scopes requested: webmasters (read+write) + siteverification")
    print("    This token covers ALL Rank AI clients.\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(OAUTH_CLIENT_PATH), SCOPES)
    creds = flow.run_local_server(port=0)

    client_info = json.loads(OAUTH_CLIENT_PATH.read_text())
    installed = client_info.get("installed") or client_info.get("web") or {}

    token_data = {
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "client_id":     installed["client_id"],
        "client_secret": installed["client_secret"],
        "scopes":        SCOPES,
        "account":       "contact@restorationai.io",
    }
    AGENCY_TOKEN_PATH.write_text(json.dumps(token_data, indent=2))
    print(f"\nAgency token saved to {AGENCY_TOKEN_PATH}")
    print("Run `python3 scripts/gsc_setup.py provision --slug <slug>` to provision any client.")
    return 0


def cmd_provision(args) -> int:
    """Fully headless: verify domain + add to GSC + submit sitemap for one client."""
    slug = args.slug
    record_path = ROOT / "clients" / f"{slug}.json"
    if not record_path.exists():
        sys.stderr.write(f"ERROR: Client not found: {slug}\n")
        return 1

    client = json.loads(record_path.read_text())
    if client.get("status") not in ("active",):
        sys.stderr.write(f"ERROR: Client {slug} is not active (status={client.get('status')}).\n")
        return 1

    domain = client["domain"]
    sitemap_url = client.get("sitemap_url") or f"https://{domain}/sitemap-index.xml"

    print(f"\n==> GSC Provision: {slug} ({domain})")

    # Load credentials (exits with clear message if scopes are wrong)
    creds = _load_credentials()

    # 1. Get zone ID
    zone_id = _get_or_fetch_zone_id(domain, client, slug)

    # 2. Get Site Verification TXT token
    txt_token = _get_siteverification_token(domain, creds)

    # 3. Add TXT record to Cloudflare
    _add_cloudflare_txt(zone_id, domain, txt_token)

    # 4. Poll DNS propagation
    resolved = _poll_dns_txt(domain, txt_token, timeout=120)
    if not resolved:
        print("    WARNING: TXT record did not resolve within 120s. Attempting verification anyway ...")

    # 5. Trigger verification
    _verify_site(domain, creds)

    # 6. Add property to Search Console
    _add_gsc_property(domain, creds)

    # 7. Submit sitemap
    _submit_sitemap(domain, sitemap_url, creds)

    # 8. Update client record
    _update_client_gsc(slug, domain, sitemap_url)

    print(f"\nDone. sc-domain:{domain} is live in Search Console.")
    print(f"Data will appear in GSC within 24-48h as Google crawls.")
    return 0


def cmd_test(args) -> int:
    """Verify the agency token has access to a client's GSC property."""
    slug = args.slug
    record_path = ROOT / "clients" / f"{slug}.json"
    if not record_path.exists():
        sys.stderr.write(f"ERROR: Client not found: {slug}\n")
        return 1

    client = json.loads(record_path.read_text())
    domain = client["domain"]
    site_url = (client.get("gsc") or {}).get("property_url") or f"sc-domain:{domain}"

    creds = _load_credentials()

    try:
        from googleapiclient.discovery import build
    except ImportError:
        sys.stderr.write("Missing deps. Run: pip install google-api-python-client\n")
        return 1

    print(f"\n==> Testing GSC access: {slug} ({site_url}) ...")
    service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    try:
        result = service.urlInspection().index().inspect(body={
            "inspectionUrl": f"https://{domain}/",
            "siteUrl": site_url,
        }).execute()
    except Exception as exc:
        msg = str(exc)
        if "403" in msg:
            sys.stderr.write(
                f"Access denied. If you just provisioned, wait 1-2 minutes and retry.\n"
                f"Error: {exc}\n"
            )
        else:
            sys.stderr.write(f"Error: {exc}\n")
        return 2

    idx = result.get("inspectionResult", {}).get("indexStatusResult", {})
    print(f"    verdict:        {idx.get('verdict', 'N/A')}")
    print(f"    coverage_state: {idx.get('coverageState', 'N/A')}")
    print(f"    last_crawl:     {idx.get('lastCrawlTime', 'never')}")
    print(f"\nAccess confirmed for {slug}.")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser(
        prog="gsc_setup",
        description="Rank AI GSC agency setup + headless client provisioning",
    )
    p.add_argument("--force", action="store_true", help="Re-run OAuth even if token exists")
    sub = p.add_subparsers(dest="cmd")

    # Default (no subcommand) = setup/re-auth
    pprov = sub.add_parser("provision", help="Headlessly verify domain + add to GSC + submit sitemap")
    pprov.add_argument("--slug", required=True, help="Client slug (e.g. narestco)")
    pprov.set_defaults(func=cmd_provision)

    ptest = sub.add_parser("test", help="Verify agency token has access to a client's GSC property")
    ptest.add_argument("--slug", required=True, help="Client slug")
    ptest.set_defaults(func=cmd_test)

    args = p.parse_args()

    if args.cmd is None:
        # No subcommand = setup/OAuth flow
        return cmd_setup(args)

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
