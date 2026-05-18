#!/usr/bin/env python3
"""
Rank AI — System 4 v2: per-client GSC OAuth setup.

ONE-TIME setup per client. Walks through the browser-based OAuth flow,
obtains an access + refresh token, and writes them to
`clients/{slug}/.gsc-token.json` (gitignored).

Prerequisites (see docs/system-4-v2-activation.md):
  1. Google Cloud project with Search Console API enabled
  2. OAuth 2.0 Desktop client created
  3. OAuth client secret JSON downloaded and saved to
     `rank-ai/.gsc-oauth-client.json`
  4. The Google account that owns the GSC properties added as a test user
     on the OAuth consent screen
  5. Domain property for {domain} verified in Search Console (via DNS TXT
     in our Cloudflare zone — see activation doc for the TXT helper)

Usage:
  python3 scripts/gsc_setup.py --slug narestco

After success, this script:
  - Writes `clients/{slug}/.gsc-token.json` (refresh + access tokens)
  - Makes one test API call (URL inspection on the client's homepage) to
    verify the token works and the property is correctly verified
  - Prints the verification result
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OAUTH_CLIENT_PATH = ROOT / ".gsc-oauth-client.json"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def main() -> int:
    ap = argparse.ArgumentParser(description="One-time GSC OAuth setup for a Rank AI client")
    ap.add_argument("--slug", required=True, help="Client slug (e.g. narestco)")
    ap.add_argument("--force", action="store_true",
                    help="Re-run flow even if a token already exists")
    args = ap.parse_args()

    if not OAUTH_CLIENT_PATH.exists():
        sys.stderr.write(
            f"ERROR: OAuth client secret not found at {OAUTH_CLIENT_PATH}.\n"
            f"Follow docs/system-4-v2-activation.md steps 1-4 first.\n"
        )
        return 1

    client_record = ROOT / "clients" / f"{args.slug}.json"
    if not client_record.exists():
        sys.stderr.write(f"ERROR: client {args.slug} not found at {client_record}\n")
        return 1
    domain = json.loads(client_record.read_text())["domain"]

    token_path = ROOT / "clients" / args.slug / ".gsc-token.json"
    if token_path.exists() and not args.force:
        sys.stderr.write(f"Token already exists at {token_path}. Use --force to redo.\n")
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

    print(f"==> Running OAuth flow for {args.slug} ({domain})")
    print(f"    A browser window will open. Sign in with the Google account that owns")
    print(f"    the {domain} GSC property.\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(OAUTH_CLIENT_PATH), SCOPES)
    creds = flow.run_local_server(port=0)

    # Persist
    client_info = json.loads(OAUTH_CLIENT_PATH.read_text())
    installed = client_info.get("installed") or client_info.get("web") or {}
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "client_id": installed["client_id"],
        "client_secret": installed["client_secret"],
        "scopes": SCOPES,
        "domain": domain,
        "slug": args.slug,
    }
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(json.dumps(token_data, indent=2))
    # Make sure it's gitignored (defense in depth — should already be covered by .gitignore)
    print(f"\nToken saved to {token_path}")

    # Test call: inspect the homepage
    print(f"\n==> Test: inspecting https://{domain}/ ...")
    service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    try:
        result = service.urlInspection().index().inspect(body={
            "inspectionUrl": f"https://{domain}/",
            "siteUrl": f"sc-domain:{domain}",
        }).execute()
    except Exception as e:
        sys.stderr.write(f"Test inspection FAILED: {e}\n")
        sys.stderr.write(
            f"Most likely cause: the {domain} domain property is not verified in GSC,\n"
            f"or this Google account doesn't have access to it. See activation doc step 6.\n"
        )
        return 2

    idx = result.get("inspectionResult", {}).get("indexStatusResult", {})
    print(f"    verdict:         {idx.get('verdict')}")
    print(f"    coverage_state:  {idx.get('coverageState')}")
    print(f"    last_crawl:      {idx.get('lastCrawlTime', 'never')}")
    print(f"\n==> Setup complete for {args.slug}.")
    print(f"    System 4 v2 is now active for this client.")
    print(f"    Next refresh_scorer run will include GSC indexing flags.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
