#!/usr/bin/env python3
"""
Rank AI — Agency GSC OAuth setup.

ONE-TIME setup for the entire agency. Runs the browser-based OAuth flow for
contact@restorationai.io, then writes a single token to
`rank-ai/.gsc-agency-token.json` (gitignored).

After this, adding GSC v2 to any client requires only:
  1. Client adds contact@restorationai.io as Full user in GSC
     (Settings > Users and permissions > Add user)
  2. Optionally set "gsc_property_url" in clients/{slug}.json
     (defaults to sc-domain:{domain} if omitted)

That's it. No per-client OAuth flow.

Prerequisites:
  1. Google Cloud project with Search Console API enabled
  2. OAuth 2.0 Desktop client created in that project
  3. OAuth client secret JSON downloaded and saved to rank-ai/.gsc-oauth-client.json
  4. contact@restorationai.io added as a test user on the OAuth consent screen
     (only required while the app is in Testing status; skip once published)

Usage:
  python3 scripts/gsc_setup.py                      # agency OAuth flow
  python3 scripts/gsc_setup.py --test-slug narestco  # flow + verify access to narestco
  python3 scripts/gsc_setup.py --force               # redo even if token exists
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OAUTH_CLIENT_PATH = ROOT / ".gsc-oauth-client.json"
AGENCY_TOKEN_PATH = ROOT / ".gsc-agency-token.json"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="One-time agency GSC OAuth setup for Rank AI"
    )
    ap.add_argument(
        "--test-slug",
        help="After setup, verify access to this client's GSC property (e.g. narestco)",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Re-run OAuth flow even if a token already exists",
    )
    args = ap.parse_args()

    if not OAUTH_CLIENT_PATH.exists():
        sys.stderr.write(
            f"ERROR: OAuth client secret not found at {OAUTH_CLIENT_PATH}.\n"
            f"Download it from Google Cloud Console > APIs & Services > Credentials\n"
            f"and save it to that path.\n"
        )
        return 1

    if AGENCY_TOKEN_PATH.exists() and not args.force:
        print(f"Agency token already exists at {AGENCY_TOKEN_PATH}.")
        print("Use --force to redo the OAuth flow.")
        if args.test_slug:
            return _test_access(args.test_slug)
        return 0

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        sys.stderr.write(
            "Missing Python deps. Run:\n"
            "  pip install google-auth google-auth-oauthlib google-api-python-client\n"
        )
        return 1

    print("==> Agency GSC OAuth flow")
    print("    Sign in as contact@restorationai.io when the browser opens.")
    print("    This token will be used for ALL Rank AI clients.\n")

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
    print("GSC v2 is now active for any client that grants access to contact@restorationai.io.")

    if args.test_slug:
        return _test_access(args.test_slug)

    print("\nTo verify access to a specific client, run:")
    print("  python3 scripts/gsc_setup.py --test-slug {slug}")
    return 0


def _test_access(slug: str) -> int:
    """Verify the agency token has access to the given client's GSC property."""
    client_record = ROOT / "clients" / f"{slug}.json"
    if not client_record.exists():
        sys.stderr.write(f"ERROR: client {slug} not found.\n")
        return 1

    c = json.loads(client_record.read_text())
    domain = c["domain"]
    site_url = c.get("gsc_property_url") or f"sc-domain:{domain}"

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        sys.stderr.write("Missing deps. Run: pip install google-auth google-auth-oauthlib google-api-python-client\n")
        return 1

    token_data = json.loads(AGENCY_TOKEN_PATH.read_text())
    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=SCOPES,
    )
    if not creds.valid:
        creds.refresh(Request())
        token_data["token"] = creds.token
        AGENCY_TOKEN_PATH.write_text(json.dumps(token_data, indent=2))

    print(f"\n==> Testing access to {slug} ({site_url}) ...")
    service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    try:
        result = service.urlInspection().index().inspect(body={
            "inspectionUrl": f"https://{domain}/",
            "siteUrl":       site_url,
        }).execute()
    except Exception as e:
        msg = str(e)
        if "403" in msg:
            sys.stderr.write(
                f"Access denied for {slug}.\n"
                f"Ask the client to add contact@restorationai.io as a Full user in\n"
                f"GSC > Settings > Users and permissions, then re-run this test.\n"
            )
        else:
            sys.stderr.write(f"Error: {e}\n")
        return 2

    idx = result.get("inspectionResult", {}).get("indexStatusResult", {})
    print(f"    verdict:         {idx.get('verdict')}")
    print(f"    coverage_state:  {idx.get('coverageState')}")
    print(f"    last_crawl:      {idx.get('lastCrawlTime', 'never')}")
    print(f"\nAccess confirmed for {slug}. System 4 v2 is active for this client.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
