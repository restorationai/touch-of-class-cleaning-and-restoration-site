#!/usr/bin/env python3
"""
Rank AI — System 6: Google Business Profile Manager.

Creates a Google Post for each published blog post, pulling performance
insights and keeping the GBP listing active with fresh content.

Subcommands:
  auth      --slug <slug>               One-time OAuth per client GBP
  post      --slug <slug> --post <slug> Create a GBP post from a blog post
  insights  --slug <slug> [--days N]    Pull view/search/direction metrics
  locations --slug <slug>               List verified locations for the account

Required env (rank-ai/.env):
  ANTHROPIC_API_KEY   For generating post summary copy

OAuth client (agency-wide, same as GSC/YouTube):
  .gsc-oauth-client.json

Per-client token:
  clients/{slug}/.gbp-token.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CLIENTS_DIR = REPO_ROOT / "clients"
SITES_DIR = REPO_ROOT / "sites"

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-5"

# Google Business Profile APIs
ACCOUNT_MGMT_API = "https://mybusinessaccountmanagement.googleapis.com/v1"
BIZ_INFO_API = "https://mybusinessbusinessinformation.googleapis.com/v1"
POSTS_API = "https://mybusiness.googleapis.com/v4"  # v4 still needed for posts
PERFORMANCE_API = "https://businessprofileperformance.googleapis.com/v1"

GBP_SCOPES = ["https://www.googleapis.com/auth/business.manage"]

OAUTH_CLIENT_PATH = (
    REPO_ROOT / ".gsc-oauth-client.json"
    if (REPO_ROOT / ".gsc-oauth-client.json").exists()
    else REPO_ROOT / ".gbp-oauth-client.json"
)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def die(msg: str) -> None:
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        die(f"Missing env var {name}. Source rank-ai/.env first.")
    return val


def load_client(slug: str) -> dict:
    path = CLIENTS_DIR / f"{slug}.json"
    if not path.exists():
        die(f"Client record not found: {path}")
    return json.loads(path.read_text())


def load_post(slug: str, post_slug: str) -> dict:
    path = SITES_DIR / slug / "src" / "content" / "blog" / f"{post_slug}.md"
    if not path.exists():
        die(f"Blog post not found: {path}")
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not match:
        die(f"Could not parse frontmatter in {path}")
    fm: dict = {}
    for line in match.group(1).splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            fm[k.strip()] = v.strip().strip('"')
    return {"frontmatter": fm, "body": match.group(2).strip()}


def token_path(slug: str) -> Path:
    return CLIENTS_DIR / slug / ".gbp-token.json"


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------

def load_credentials(slug: str):
    t_path = token_path(slug)
    if not t_path.exists():
        die(
            f"No GBP token for {slug}.\n"
            f"Run: python3 scripts/gbp_manager.py auth --slug {slug}"
        )
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        die("Missing google-auth. Run: pip install google-auth google-auth-oauthlib")

    data = json.loads(t_path.read_text())
    creds = Credentials(
        token=data.get("token"),
        refresh_token=data["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        scopes=GBP_SCOPES,
    )
    if not creds.valid:
        creds.refresh(Request())
        data["token"] = creds.token
        t_path.write_text(json.dumps(data, indent=2))
    return creds


def gbp_get(creds, url: str) -> dict:
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {creds.token}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        err = exc.read().decode(errors="replace")
        die(f"GBP GET {url} failed {exc.code}: {err[:400]}")


def gbp_post(creds, url: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={
            "Authorization": f"Bearer {creds.token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        err = exc.read().decode(errors="replace")
        die(f"GBP POST {url} failed {exc.code}: {err[:400]}")


# ---------------------------------------------------------------------------
# Location discovery
# ---------------------------------------------------------------------------

def list_accounts(creds) -> list[dict]:
    data = gbp_get(creds, f"{ACCOUNT_MGMT_API}/accounts")
    return data.get("accounts", [])


def list_locations(creds, account_name: str) -> list[dict]:
    url = f"{ACCOUNT_MGMT_API}/{account_name}/locations?readMask=name,title,storeCode,websiteUri"
    data = gbp_get(creds, url)
    return data.get("locations", [])


def find_location_for_client(creds, client: dict) -> str:
    """Return the location resource name (accounts/X/locations/Y) for this client."""
    domain = client.get("domain", "").lower()
    display_name = client.get("display_name", "").lower()

    accounts = list_accounts(creds)
    if not accounts:
        die("No GBP accounts found. Make sure contact@restorationai.io has Manager access.")

    for account in accounts:
        acct_name = account["name"]
        locations = list_locations(creds, acct_name)
        for loc in locations:
            loc_title = loc.get("title", "").lower()
            loc_site = loc.get("websiteUri", "").lower()
            if domain in loc_site or display_name in loc_title:
                return loc["name"]

    # If no match, show what we found and ask
    print("\nCould not auto-match a GBP location. Found these locations:")
    for account in accounts:
        for loc in list_locations(creds, account["name"]):
            print(f"  {loc['name']}  —  {loc.get('title')} ({loc.get('websiteUri', 'no site')})")
    die(
        f"No location matched domain '{domain}'. "
        "Add 'gbp_location_name' to the client record to pin it manually."
    )


def get_location_name(creds, client: dict) -> str:
    """Return location resource name, using pinned value from client record if set."""
    pinned = client.get("gbp_location_name")
    if pinned:
        return pinned
    name = find_location_for_client(creds, client)
    # Auto-save back to client record so future calls are instant
    client_path = CLIENTS_DIR / f"{client['slug']}.json"
    client["gbp_location_name"] = name
    client_path.write_text(json.dumps(client, indent=2))
    print(f"  [gbp] pinned location: {name}")
    return name


# ---------------------------------------------------------------------------
# Post generation
# ---------------------------------------------------------------------------

POST_PROMPT = """Write a concise Google Business Profile post for a home restoration company.
The post promotes a blog article. It must be 150-200 words, conversational, and end with
a clear call to action inviting readers to read the full article.

Blog title: {title}
Meta description: {meta_description}
Company name: {company}
Blog URL: {url}

Rules:
- Do NOT use hashtags
- Do NOT use all-caps words
- Start with a hook sentence related to the topic
- Include the company name once naturally
- End with: "Read the full guide at the link below."
- Return ONLY the post text, no quotes or extra formatting
"""


def generate_post_text(post: dict, client: dict) -> str:
    api_key = require_env("ANTHROPIC_API_KEY")
    fm = post["frontmatter"]
    domain = client.get("domain", "")
    post_slug = fm.get("slug", "")
    url = f"https://{domain}/blog/{post_slug}/"

    prompt = POST_PROMPT.format(
        title=fm.get("title", ""),
        meta_description=fm.get("meta_description", ""),
        company=client.get("display_name", ""),
        url=url,
    )
    body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 400,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        ANTHROPIC_API, data=body, method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode())
    return payload["content"][0]["text"].strip()


# ---------------------------------------------------------------------------
# Create GBP post
# ---------------------------------------------------------------------------

def create_gbp_post(creds, location_name: str, post_text: str,
                    cta_url: str, hero_image_url: str | None = None) -> dict:
    """Create a Google Post (STANDARD type with LEARN_MORE CTA)."""
    body: dict = {
        "languageCode": "en-US",
        "summary": post_text,
        "callToAction": {
            "actionType": "LEARN_MORE",
            "url": cta_url,
        },
        "topicType": "STANDARD",
    }
    if hero_image_url:
        body["media"] = [{
            "mediaFormat": "PHOTO",
            "sourceUrl": hero_image_url,
        }]

    url = f"{POSTS_API}/{location_name}/localPosts"
    return gbp_post(creds, url, body)


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

def get_insights(creds, location_name: str, days: int = 30) -> dict:
    end = date.today()
    start = end - timedelta(days=days)

    metrics = [
        "BUSINESS_IMPRESSIONS_DESKTOP_MAPS",
        "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH",
        "BUSINESS_IMPRESSIONS_MOBILE_MAPS",
        "BUSINESS_IMPRESSIONS_MOBILE_SEARCH",
        "BUSINESS_DIRECTION_REQUESTS",
        "CALL_CLICKS",
        "WEBSITE_CLICKS",
    ]

    results = {}
    for metric in metrics:
        params = urllib.parse.urlencode({
            "dailyMetric": metric,
            "dailyRange.start_date.year": start.year,
            "dailyRange.start_date.month": start.month,
            "dailyRange.start_date.day": start.day,
            "dailyRange.end_date.year": end.year,
            "dailyRange.end_date.month": end.month,
            "dailyRange.end_date.day": end.day,
        })
        url = f"{PERFORMANCE_API}/{location_name}:getDailyMetricsTimeSeries?{params}"
        try:
            data = gbp_get(creds, url)
            time_series = data.get("timeSeries", {})
            daily_metrics = time_series.get("datedValues", [])
            total = sum(int(d.get("value", 0)) for d in daily_metrics if d.get("value"))
            results[metric] = total
        except SystemExit:
            results[metric] = None  # metric not available for this location

    return results


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_auth(slug: str) -> int:
    if not OAUTH_CLIENT_PATH.exists():
        die(
            f"OAuth client not found at {OAUTH_CLIENT_PATH}.\n"
            "Use the same Desktop OAuth client as GSC/YouTube (already on disk)."
        )
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        die("Run: pip install google-auth-oauthlib")

    print(f"Opening browser for GBP OAuth ({slug})...")
    flow = InstalledAppFlow.from_client_secrets_file(
        str(OAUTH_CLIENT_PATH), scopes=GBP_SCOPES
    )
    creds = flow.run_local_server(port=0)

    client_data = json.loads(OAUTH_CLIENT_PATH.read_text())
    client_info = client_data.get("installed") or client_data.get("web", {})

    t_path = token_path(slug)
    t_path.write_text(json.dumps({
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "client_id": client_info["client_id"],
        "client_secret": client_info["client_secret"],
        "scopes": list(creds.scopes or GBP_SCOPES),
    }, indent=2))
    print(f"  Token saved: {t_path}")
    return 0


def cmd_locations(slug: str) -> int:
    client = load_client(slug)
    creds = load_credentials(slug)
    accounts = list_accounts(creds)
    if not accounts:
        print("No accounts found.")
        return 1
    for account in accounts:
        print(f"\nAccount: {account['name']}  ({account.get('accountName', '')})")
        for loc in list_locations(creds, account["name"]):
            print(f"  {loc['name']}")
            print(f"    Title:   {loc.get('title', '')}")
            print(f"    Website: {loc.get('websiteUri', '')}")
    return 0


def cmd_post(slug: str, post_slug: str, use_ai: bool = True) -> int:
    client = load_client(slug)
    post = load_post(slug, post_slug)
    creds = load_credentials(slug)

    fm = post["frontmatter"]
    domain = client.get("domain", "")
    cta_url = f"https://{domain}/blog/{post_slug}/"
    hero = fm.get("hero", "")

    location_name = get_location_name(creds, client)
    print(f"  [gbp] location: {location_name}")

    # Generate post copy
    if use_ai:
        print("  [gbp] generating post copy via Claude...")
        post_text = generate_post_text(post, client)
    else:
        post_text = fm.get("meta_description", "")[:500]

    print(f"  [gbp] post text ({len(post_text)} chars):\n    {post_text[:120]}...")

    # Create the post
    print("  [gbp] creating Google Post...")
    result = create_gbp_post(creds, location_name, post_text, cta_url,
                             hero_image_url=hero or None)

    post_name = result.get("name", "")
    post_url = result.get("searchUrl", "")
    print(f"\n==> GBP post created")
    print(f"  Name:    {post_name}")
    print(f"  CTA URL: {cta_url}")
    if post_url:
        print(f"  Live at: {post_url}")
    return 0


def cmd_insights(slug: str, days: int = 30) -> int:
    client = load_client(slug)
    creds = load_credentials(slug)
    location_name = get_location_name(creds, client)

    print(f"  [gbp] pulling {days}-day insights for {location_name}...")
    metrics = get_insights(creds, location_name, days=days)

    label_map = {
        "BUSINESS_IMPRESSIONS_DESKTOP_MAPS": "Maps impressions (desktop)",
        "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH": "Search impressions (desktop)",
        "BUSINESS_IMPRESSIONS_MOBILE_MAPS": "Maps impressions (mobile)",
        "BUSINESS_IMPRESSIONS_MOBILE_SEARCH": "Search impressions (mobile)",
        "BUSINESS_DIRECTION_REQUESTS": "Direction requests",
        "CALL_CLICKS": "Call clicks",
        "WEBSITE_CLICKS": "Website clicks",
    }
    print(f"\n  GBP Insights — last {days} days ({client.get('display_name', slug)})")
    print(f"  {'Metric':<38} {'Total':>8}")
    print(f"  {'-'*38} {'-'*8}")
    for key, label in label_map.items():
        val = metrics.get(key)
        val_str = str(val) if val is not None else "n/a"
        print(f"  {label:<38} {val_str:>8}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Rank AI — GBP Manager (System 6)")
    sub = parser.add_subparsers(dest="cmd")

    p_auth = sub.add_parser("auth", help="One-time OAuth setup per client")
    p_auth.add_argument("--slug", required=True)

    p_loc = sub.add_parser("locations", help="List verified GBP locations")
    p_loc.add_argument("--slug", required=True)

    p_post = sub.add_parser("post", help="Create a GBP post from a blog post")
    p_post.add_argument("--slug", required=True)
    p_post.add_argument("--post", required=True, dest="post_slug")
    p_post.add_argument("--no-ai", action="store_true",
                        help="Use meta_description as copy instead of generating")

    p_ins = sub.add_parser("insights", help="Pull GBP performance metrics")
    p_ins.add_argument("--slug", required=True)
    p_ins.add_argument("--days", type=int, default=30)

    args = parser.parse_args()

    if args.cmd == "auth":
        return cmd_auth(args.slug)
    elif args.cmd == "locations":
        return cmd_locations(args.slug)
    elif args.cmd == "post":
        return cmd_post(args.slug, args.post_slug, use_ai=not args.no_ai)
    elif args.cmd == "insights":
        return cmd_insights(args.slug, days=args.days)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
