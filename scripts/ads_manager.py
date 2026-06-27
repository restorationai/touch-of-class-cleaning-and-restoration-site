#!/usr/bin/env python3
"""
Rank AI — Google Ads Manager.

Full lifecycle management of Google Ads accounts for local service clients.
Uses the official google-ads Python library (pip install google-ads).

Subcommands:
  auth              --slug <slug>                    One-time OAuth per client
  list-accounts     --slug <slug>                    List MCC sub-accounts (find CIDs)
  list-campaigns    --slug <slug>                    List campaigns + status/budget
  scaffold          --slug <slug> [--dry-run]        Build full structure from plan-input.json
  report            --slug <slug> [--days N]         Performance report (campaigns + keywords)
  pause             --slug <slug> --resource <name>  Pause campaign or ad group
  enable            --slug <slug> --resource <name>  Enable campaign or ad group
  set-budget        --slug <slug> --campaign <name> --daily-budget N
  add-keywords      --slug <slug> --ad-group <name> --keywords "kw1,kw2,..."
  add-negatives     --slug <slug> --campaign <name> --keywords "kw1,kw2,..."
  generate-ads      --slug <slug> --ad-group <name> --service <slug> --city <name> --state <abbr>
  keyword-research  --slug <slug> [--services s1,s2,...] [--output path.csv]

Required env (rank-ai/.env):
  GOOGLE_ADS_DEVELOPER_TOKEN   From Google Ads Manager > Tools > API Center
  GOOGLE_ADS_MCC_CUSTOMER_ID   Manager Account CID (no dashes)
  ANTHROPIC_API_KEY            For RSA copy generation

OAuth client (agency-wide, same as GSC/YouTube/GBP):
  .gsc-oauth-client.json

Per-client token:  clients/{slug}/.ads-token.json
Ads structure:     clients/{slug}/ads-structure.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CLIENTS_DIR = REPO_ROOT / "clients"

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-6"

ADS_SCOPES = ["https://www.googleapis.com/auth/adwords"]

OAUTH_CLIENT_PATH = (
    REPO_ROOT / ".gsc-oauth-client.json"
    if (REPO_ROOT / ".gsc-oauth-client.json").exists()
    else REPO_ROOT / ".ads-oauth-client.json"
)

DEFAULT_NEGATIVES = [
    "diy", "how to", "yourself", "tutorial", "cheap", "jobs",
    "career", "salary", "hiring", "school", "training", "course",
    "definition", "wikipedia", "what is", "rent", "buy",
]


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


def get_customer_id(client: dict, slug: str) -> str:
    cid = (
        client.get("brand", {}).get("google_ads_customer_id")
        or client.get("google_ads_customer_id")
    )
    if not cid:
        die(
            f"No google_ads_customer_id in client record for {slug}.\n"
            f"Run list-accounts to find it, then add to clients/{slug}.json:\n"
            f'  "brand": {{"google_ads_customer_id": "123-456-7890"}}'
        )
    return cid.replace("-", "")


def token_path(slug: str) -> Path:
    return CLIENTS_DIR / slug / ".ads-token.json"


def structure_path(slug: str) -> Path:
    return CLIENTS_DIR / slug / "ads-structure.json"


def load_structure(slug: str) -> dict:
    path = structure_path(slug)
    if path.exists():
        return json.loads(path.read_text())
    return {"campaigns": {}, "ad_groups": {}, "budgets": {}}


def save_structure(slug: str, structure: dict) -> None:
    path = structure_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(structure, indent=2))


# ---------------------------------------------------------------------------
# Per-client ads journal — a running ops log of every change + decision.
# Read it before touching the account; an entry is auto-appended after every
# change command, and humans/agents can add freeform notes via `note --add`.
# ---------------------------------------------------------------------------
JOURNAL_MARKER = "<!-- entries below, newest first -->"


def journal_path(slug: str) -> Path:
    return CLIENTS_DIR / slug / "ads-journal.md"


def _journal_header(slug: str) -> str:
    name = load_client(slug).get("display_name", slug)
    return (
        f"# Ads Journal — {name} ({slug})\n\n"
        "Running log of every change + decision on this client's Google Ads. Newest first.\n"
        "Auto-appended by ads_manager.py change commands (budget / bid / pause / enable /\n"
        "negatives) and by `note --add`. **Read this before touching the account; add an\n"
        "entry after any change.**\n\n"
        f"{JOURNAL_MARKER}\n"
    )


def append_journal(slug: str, text: str, *, kind: str = "note",
                   campaign: str | None = None, author: str = "operator") -> Path:
    """Prepend a dated entry to the client's ads journal (newest first)."""
    path = journal_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    entry = f"## {stamp} · {kind} · {campaign or '—'}\n{text.strip()} — _{author}_\n\n"
    if path.exists() and JOURNAL_MARKER in path.read_text():
        content = path.read_text()
        head, rest = content.split(JOURNAL_MARKER, 1)
        content = head + JOURNAL_MARKER + "\n\n" + entry + rest.lstrip("\n")
    else:
        content = _journal_header(slug) + "\n" + entry
    path.write_text(content)
    return path


def read_journal(slug: str, limit: int = 12) -> list[str]:
    """Return the most-recent journal entries (each a multi-line '## ...' block)."""
    path = journal_path(slug)
    if not path.exists():
        return []
    content = path.read_text()
    body = content.split(JOURNAL_MARKER, 1)[-1] if JOURNAL_MARKER in content else content
    blocks = [b.strip() for b in re.split(r"(?m)^(?=## )", body.strip()) if b.strip().startswith("## ")]
    return blocks[:limit]


def print_journal_brief(slug: str, n: int = 6) -> None:
    """Print the latest journal entries — shown at the top of `report`."""
    entries = read_journal(slug, limit=n)
    if not entries:
        print(f"  📓 No ads journal yet for {slug}. Start one:")
        print(f"     ads_manager.py note --slug {slug} --add \"...\"\n")
        return
    print(f"\n  📓 ADS JOURNAL — last {len(entries)} (read before changing anything)")
    print(f"  {'-'*64}")
    for e in entries:
        for line in e.splitlines():
            print(f"  {line}")
    print(f"  {'-'*64}")


# Commands that mutate the live account → auto-logged to the journal on success.
CHANGE_CMDS = {"set-budget", "set-bid-strategy", "pause", "enable",
               "add-keywords", "add-negatives", "apply-negatives"}


def _describe_change(args) -> str:
    """Human-readable one-liner for a change command, for the journal entry."""
    c = args.cmd
    if c == "set-budget":
        return f"Set daily budget to ${args.daily_budget:.2f}."
    if c == "set-bid-strategy":
        tail = f" (max-CPC ${args.max_cpc:.2f}/click)" if getattr(args, "max_cpc", None) else ""
        return f"Set bid strategy → {args.strategy}{tail}."
    if c == "pause":
        return f"Paused {args.resource}."
    if c == "enable":
        return f"Enabled {args.resource}."
    if c == "add-keywords":
        return f"Added keywords to ad group {args.ad_group}: {args.keywords}"
    if c == "add-negatives":
        return f"Added campaign negatives: {args.keywords}"
    if c == "apply-negatives":
        return "Applied the universal negative-keyword list."
    return f"Ran {c}."


# ---------------------------------------------------------------------------
# Google Ads client
# ---------------------------------------------------------------------------

def build_ads_client(slug: str, login_as_mcc: bool = True):
    """Build a GoogleAdsClient from the per-client token file."""
    try:
        from google.ads.googleads.client import GoogleAdsClient
    except ImportError:
        die("Missing google-ads library. Run: pip install google-ads")

    t_path = token_path(slug)
    if t_path.exists():
        token_data = json.loads(t_path.read_text())
        client_id = token_data["client_id"]
        client_secret = token_data["client_secret"]
        refresh_token = token_data["refresh_token"]
    else:
        # Headless/Railway fallback: the agency MCC OAuth creds from env. The MCC
        # refresh token can read any linked client account, so a single env-based
        # credential serves every client for read-only reporting (e.g. ads_review cron).
        client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
        client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
        refresh_token = os.environ.get("GOOGLE_ADS_REFRESH_TOKEN")
        if not (client_id and client_secret and refresh_token):
            die(
                f"No Ads token file for {slug} and no GOOGLE_OAUTH_*/GOOGLE_ADS_REFRESH_TOKEN "
                f"env fallback.\nRun: python3 scripts/ads_manager.py auth --slug {slug}"
            )

    config = {
        "developer_token": require_env("GOOGLE_ADS_DEVELOPER_TOKEN"),
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "use_proto_plus": True,
    }
    if login_as_mcc:
        mcc_id = require_env("GOOGLE_ADS_MCC_CUSTOMER_ID").replace("-", "")
        config["login_customer_id"] = mcc_id

    return GoogleAdsClient.load_from_dict(config)


def gaql(client, customer_id: str, query: str) -> list:
    """Run a GAQL query and return all rows from the stream."""
    ga_service = client.get_service("GoogleAdsService")
    stream = ga_service.search_stream(customer_id=customer_id.replace("-", ""),
                                       query=query)
    rows = []
    for batch in stream:
        rows.extend(batch.results)
    return rows


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------

def cmd_auth(slug: str) -> int:
    if not OAUTH_CLIENT_PATH.exists():
        die(
            f"OAuth client not found at {OAUTH_CLIENT_PATH}.\n"
            "Use the same Desktop OAuth client as GSC/YouTube/GBP."
        )
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        die("Run: pip install google-auth-oauthlib")

    print(f"Opening browser for Google Ads OAuth ({slug})...")
    flow = InstalledAppFlow.from_client_secrets_file(
        str(OAUTH_CLIENT_PATH), scopes=ADS_SCOPES
    )
    creds = flow.run_local_server(port=0)

    client_data = json.loads(OAUTH_CLIENT_PATH.read_text())
    client_info = client_data.get("installed") or client_data.get("web", {})

    t_path = token_path(slug)
    t_path.parent.mkdir(parents=True, exist_ok=True)
    t_path.write_text(json.dumps({
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "client_id": client_info["client_id"],
        "client_secret": client_info["client_secret"],
        "scopes": list(creds.scopes or ADS_SCOPES),
    }, indent=2))
    print(f"  Token saved: {t_path}")
    return 0


# ---------------------------------------------------------------------------
# Account listing
# ---------------------------------------------------------------------------

def cmd_list_accounts(slug: str) -> int:
    client = build_ads_client(slug, login_as_mcc=True)
    mcc_id = require_env("GOOGLE_ADS_MCC_CUSTOMER_ID").replace("-", "")
    query = """
        SELECT
          customer_client.id,
          customer_client.descriptive_name,
          customer_client.status,
          customer_client.manager,
          customer_client.level
        FROM customer_client
        WHERE customer_client.level = 1
    """
    rows = gaql(client, mcc_id, query)
    accounts = [r.customer_client for r in rows if not r.customer_client.manager]
    if not accounts:
        print("No sub-accounts found under MCC.")
        return 1
    print(f"\n  {'Customer ID':<15} {'Status':<12} {'Account Name'}")
    print(f"  {'-'*15} {'-'*12} {'-'*40}")
    for a in accounts:
        print(f"  {str(a.id):<15} {str(a.status.name):<12} {a.descriptive_name}")
    print(f"\n  {len(accounts)} accounts. Add the right ID to clients/{{slug}}.json as brand.google_ads_customer_id")
    return 0


# ---------------------------------------------------------------------------
# Campaign listing
# ---------------------------------------------------------------------------

def cmd_list_campaigns(slug: str) -> int:
    client_rec = load_client(slug)
    customer_id = get_customer_id(client_rec, slug)
    client = build_ads_client(slug)
    query = """
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          campaign.advertising_channel_type,
          campaign_budget.amount_micros
        FROM campaign
        WHERE campaign.status != 'REMOVED'
        ORDER BY campaign.name
    """
    rows = gaql(client, customer_id, query)
    if not rows:
        print("No campaigns found.")
        return 0
    print(f"\n  Campaigns — {client_rec.get('display_name', slug)}")
    print(f"  {'Status':<10} {'Daily Budget':>13}  {'Name'}")
    print(f"  {'-'*10} {'-'*13}  {'-'*50}")
    for row in rows:
        c = row.campaign
        budget_usd = row.campaign_budget.amount_micros / 1_000_000
        print(f"  {c.status.name:<10} ${budget_usd:>12.2f}  {c.name}")
    return 0


# ---------------------------------------------------------------------------
# Performance report
# ---------------------------------------------------------------------------

def cmd_note(slug: str, add: str | None = None, campaign: str | None = None,
             kind: str = "note", limit: int = 12) -> int:
    """Append a note to (or read) the client's ads journal."""
    load_client(slug)  # validates the slug exists
    if add:
        author = os.environ.get("ADS_JOURNAL_AUTHOR", "operator")
        path = append_journal(slug, add, kind=kind, campaign=campaign, author=author)
        print(f"  ✓ logged to {path}")
        return 0
    entries = read_journal(slug, limit=limit)
    if not entries:
        print(f"  (no journal yet for {slug})")
        print(f"  add one:  ads_manager.py note --slug {slug} --add \"...\"")
        return 0
    print(f"\n  📓 Ads journal — {slug}  (latest {len(entries)})\n")
    for e in entries:
        for line in e.splitlines():
            print(f"  {line}")
        print()
    return 0


def cmd_report(slug: str, days: int = 30) -> int:
    client_rec = load_client(slug)
    customer_id = get_customer_id(client_rec, slug)
    client = build_ads_client(slug)
    print_journal_brief(slug)

    end = date.today()
    start = end - timedelta(days=days - 1)

    query = f"""
        SELECT
          campaign.name,
          campaign.status,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value,
          metrics.ctr,
          metrics.average_cpc
        FROM campaign
        WHERE segments.date BETWEEN '{start}' AND '{end}'
          AND campaign.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC
    """
    rows = gaql(client, customer_id, query)

    campaigns = []
    for row in rows:
        m = row.metrics
        campaigns.append({
            "name": row.campaign.name,
            "status": row.campaign.status.name,
            "impressions": m.impressions,
            "clicks": m.clicks,
            "cost_usd": m.cost_micros / 1_000_000,
            "conversions": m.conversions,
            "conv_value": m.conversions_value,
            "ctr": m.ctr,
            "avg_cpc": m.average_cpc / 1_000_000,
        })

    total_spend = sum(c["cost_usd"] for c in campaigns)
    total_clicks = sum(c["clicks"] for c in campaigns)
    total_impr = sum(c["impressions"] for c in campaigns)
    total_conv = sum(c["conversions"] for c in campaigns)
    total_conv_val = sum(c["conv_value"] for c in campaigns)
    ctr = total_clicks / total_impr if total_impr else 0
    cpc = total_spend / total_clicks if total_clicks else 0
    roas = total_conv_val / total_spend if total_spend else 0

    print(f"\n  Google Ads Report — {client_rec.get('display_name', slug)}")
    print(f"  Period: {start} to {end} ({days} days)")
    print(f"  {'='*58}")
    print(f"  {'Spend':<30} ${total_spend:>10.2f}")
    print(f"  {'Impressions':<30} {total_impr:>10,}")
    print(f"  {'Clicks':<30} {total_clicks:>10,}")
    print(f"  {'CTR':<30} {ctr*100:>9.2f}%")
    print(f"  {'Avg CPC':<30} ${cpc:>10.2f}")
    print(f"  {'Conversions':<30} {total_conv:>10.1f}")
    print(f"  {'Conversion value':<30} ${total_conv_val:>10.2f}")
    print(f"  {'ROAS':<30} {roas:>10.2f}x")

    if campaigns:
        print(f"\n  {'CAMPAIGNS':}")
        print(f"  {'Campaign':<38} {'Status':<10} {'Spend':>8} {'Clicks':>7} {'Conv':>6}")
        print(f"  {'-'*38} {'-'*10} {'-'*8} {'-'*7} {'-'*6}")
        for c in campaigns:
            print(f"  {c['name'][:38]:<38} {c['status']:<10} "
                  f"${c['cost_usd']:>7.2f} {c['clicks']:>7,} {c['conversions']:>6.1f}")

    # Top keywords
    kw_query = f"""
        SELECT
          ad_group_criterion.keyword.text,
          ad_group_criterion.keyword.match_type,
          campaign.name,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.average_cpc
        FROM keyword_view
        WHERE segments.date BETWEEN '{start}' AND '{end}'
          AND ad_group_criterion.status != 'REMOVED'
          AND metrics.impressions > 0
        ORDER BY metrics.cost_micros DESC
        LIMIT 15
    """
    try:
        kw_rows = gaql(client, customer_id, kw_query)
        if kw_rows:
            print(f"\n  {'TOP KEYWORDS':}")
            print(f"  {'Keyword':<38} {'Match':<8} {'Spend':>8} {'Clicks':>7}")
            print(f"  {'-'*38} {'-'*8} {'-'*8} {'-'*7}")
            for row in kw_rows:
                kw = row.ad_group_criterion.keyword
                m = row.metrics
                print(f"  {kw.text[:38]:<38} {kw.match_type.name:<8} "
                      f"${m.cost_micros/1e6:>7.2f} {m.clicks:>7,}")
    except Exception:
        pass

    return 0


# ---------------------------------------------------------------------------
# Create primitives
# ---------------------------------------------------------------------------

def create_budget(client, customer_id: str, name: str,
                  daily_budget_usd: float, dry_run: bool = False) -> str:
    if dry_run:
        print(f"    [dry-run] budget: {name} (${daily_budget_usd}/day)")
        return f"customers/{customer_id}/campaignBudgets/0"

    # Idempotent: budget names are unique in Google Ads, so reuse one that
    # already exists (e.g. left by a partial/failed prior run) instead of
    # failing with DUPLICATE_NAME. The worker re-runs jobs, so this must be safe.
    safe_name = name.replace("'", "\\'")
    existing = gaql(
        client, customer_id,
        f"SELECT campaign_budget.resource_name FROM campaign_budget "
        f"WHERE campaign_budget.name = '{safe_name}' "
        f"AND campaign_budget.status != 'REMOVED'"
    )
    if existing:
        print(f"    [reuse] existing budget '{name}'")
        return existing[0].campaign_budget.resource_name

    budget_service = client.get_service("CampaignBudgetService")
    op = client.get_type("CampaignBudgetOperation")
    budget = op.create
    budget.name = name
    budget.amount_micros = int(daily_budget_usd * 1_000_000)
    budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
    # Must be non-shared: Maximize Conversions is incompatible with a shared budget.
    budget.explicitly_shared = False

    response = budget_service.mutate_campaign_budgets(
        customer_id=customer_id, operations=[op]
    )
    return response.results[0].resource_name


def create_campaign(client, customer_id: str, name: str,
                    budget_resource: str, dry_run: bool = False,
                    cold_start_max_cpc: float | None = 30.0) -> str:
    if dry_run:
        print(f"    [dry-run] campaign: {name}")
        return f"customers/{customer_id}/campaigns/0"

    campaign_service = client.get_service("CampaignService")
    op = client.get_type("CampaignOperation")
    campaign = op.create
    campaign.name = name
    campaign.advertising_channel_type = (
        client.enums.AdvertisingChannelTypeEnum.SEARCH
    )
    campaign.status = client.enums.CampaignStatusEnum.PAUSED
    campaign.campaign_budget = budget_resource
    # Cold-start: a brand-new campaign has NO conversion history, so Maximize
    # Conversions bids microscopically and loses ~90% impression share to rank
    # ($0 spend, 0 clicks). Start on Maximize Clicks (TARGET_SPEND) with a max-CPC
    # ceiling to win clicks + gather data; graduate to Maximize Conversions after
    # ~15-30 conversions via `set-bid-strategy` (see bidding-strategy-playbook.md).
    campaign.bidding_strategy_type = (
        client.enums.BiddingStrategyTypeEnum.TARGET_SPEND
    )
    # The bidding strategy oneof message must be set, not just the type enum,
    # or the API rejects with REQUIRED: campaign_bidding_strategy.
    if cold_start_max_cpc:
        campaign.target_spend.cpc_bid_ceiling_micros = int(cold_start_max_cpc * 1_000_000)
    else:
        campaign.target_spend.CopyFrom(client.get_type("TargetSpend"))
    campaign.network_settings.target_google_search = True
    campaign.network_settings.target_search_network = False
    campaign.network_settings.target_content_network = False
    campaign.geo_target_type_setting.positive_geo_target_type = (
        client.enums.PositiveGeoTargetTypeEnum.PRESENCE
    )
    # Required since API v24: declare EU political advertising status.
    campaign.contains_eu_political_advertising = (
        client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
    )

    response = campaign_service.mutate_campaigns(
        customer_id=customer_id, operations=[op]
    )
    return response.results[0].resource_name


def add_campaign_geo_target(client, customer_id: str, campaign_resource: str,
                             geo_resource: str, dry_run: bool = False) -> None:
    if dry_run:
        return
    criterion_service = client.get_service("CampaignCriterionService")
    op = client.get_type("CampaignCriterionOperation")
    criterion = op.create
    criterion.campaign = campaign_resource
    criterion.location.geo_target_constant = geo_resource
    criterion_service.mutate_campaign_criteria(
        customer_id=customer_id, operations=[op]
    )


def add_campaign_negatives(client, customer_id: str, campaign_resource: str,
                            keywords: list[str], dry_run: bool = False,
                            match_type=None) -> None:
    # Default negative match = BROAD (blocks any query containing ALL the words). For a
    # single word that is a SUBSET of a desired query (e.g. "fire" is inside "fire damage
    # restoration"), pass match_type=EXACT so it only blocks the literal lone-word search.
    mt = match_type or client.enums.KeywordMatchTypeEnum.BROAD
    if dry_run:
        print(f"    [dry-run] {len(keywords)} campaign negatives")
        return
    criterion_service = client.get_service("CampaignCriterionService")
    ops = []
    for kw in keywords:
        op = client.get_type("CampaignCriterionOperation")
        c = op.create
        c.campaign = campaign_resource
        c.negative = True
        c.keyword.text = kw
        c.keyword.match_type = mt
        ops.append(op)
    criterion_service.mutate_campaign_criteria(
        customer_id=customer_id, operations=ops
    )


def create_ad_group(client, customer_id: str, name: str,
                    campaign_resource: str, dry_run: bool = False) -> str:
    if dry_run:
        print(f"    [dry-run] ad group: {name}")
        return f"customers/{customer_id}/adGroups/0"

    ag_service = client.get_service("AdGroupService")
    op = client.get_type("AdGroupOperation")
    ag = op.create
    ag.name = name
    ag.campaign = campaign_resource
    ag.status = client.enums.AdGroupStatusEnum.ENABLED
    ag.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD

    response = ag_service.mutate_ad_groups(
        customer_id=customer_id, operations=[op]
    )
    return response.results[0].resource_name


def create_rsa(client, customer_id: str, ad_group_resource: str,
               copy: dict, final_url: str, dry_run: bool = False) -> str:
    if dry_run:
        print(f"    [dry-run] RSA with {len(copy['headlines'])} headlines")
        return f"customers/{customer_id}/adGroupAds/0~0"

    ad_service = client.get_service("AdGroupAdService")
    op = client.get_type("AdGroupAdOperation")
    ad_group_ad = op.create
    ad_group_ad.ad_group = ad_group_resource
    ad_group_ad.status = client.enums.AdGroupAdStatusEnum.ENABLED

    # Enforce Google's RSA limits (headline <=30, description <=90). Drop
    # over-limit assets; if that leaves too few, hard-truncate as a fallback.
    def _fit(items, limit, minimum, cap):
        kept = [s for s in items if len(s) <= limit]
        if len(kept) < minimum:
            kept = [s[:limit].rstrip() for s in items]
        return kept[:cap]

    rsa = ad_group_ad.ad.responsive_search_ad
    for headline_text in _fit(copy["headlines"], 30, 3, 15):
        headline = client.get_type("AdTextAsset")
        headline.text = headline_text
        rsa.headlines.append(headline)
    for desc_text in _fit(copy["descriptions"], 90, 2, 4):
        desc = client.get_type("AdTextAsset")
        desc.text = desc_text
        rsa.descriptions.append(desc)

    ad_group_ad.ad.final_urls.append(final_url)

    # Display path from the URL PATH segments only (never the host — a domain's
    # "." is a disallowed character in display paths). Keep alphanumerics/spaces.
    from urllib.parse import urlparse
    def _clean_path(seg: str) -> str:
        seg = seg.replace("-", " ").title()
        seg = "".join(ch for ch in seg if ch.isalnum() or ch == " ").strip()
        return seg[:15]
    segs = [p for p in urlparse(final_url).path.split("/") if p]
    if len(segs) > 0 and _clean_path(segs[0]):
        ad_group_ad.ad.responsive_search_ad.path1 = _clean_path(segs[0])
    if len(segs) > 1 and _clean_path(segs[1]):
        ad_group_ad.ad.responsive_search_ad.path2 = _clean_path(segs[1])

    response = ad_service.mutate_ad_group_ads(
        customer_id=customer_id, operations=[op]
    )
    return response.results[0].resource_name


def add_keywords_to_ad_group(client, customer_id: str, ad_group_resource: str,
                              keywords: list[str], dry_run: bool = False) -> int:
    if dry_run:
        print(f"    [dry-run] {len(keywords) * 3} keyword entries ({len(keywords)} x 3 match types)")
        return len(keywords) * 3

    criterion_service = client.get_service("AdGroupCriterionService")
    ops = []
    match_types = [
        client.enums.KeywordMatchTypeEnum.EXACT,
        client.enums.KeywordMatchTypeEnum.PHRASE,
        client.enums.KeywordMatchTypeEnum.BROAD,
    ]
    for kw in keywords:
        for match_type in match_types:
            op = client.get_type("AdGroupCriterionOperation")
            criterion = op.create
            criterion.ad_group = ad_group_resource
            criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
            criterion.keyword.text = kw
            criterion.keyword.match_type = match_type
            ops.append(op)

    criterion_service.mutate_ad_group_criteria(
        customer_id=customer_id, operations=ops
    )
    return len(ops)


US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia",
}


def geo_lookup(client, customer_id: str, city: str, state: str = "") -> str | None:
    """Resolve a city to its Google geo target constant, DISAMBIGUATED BY STATE.

    Many US cities share a name across states (Auburn AL/WA, Kent CT/WA, Redmond OR/WA).
    Matching on city name alone and taking the first row silently targets the wrong
    state. We therefore filter on the state in canonical_name. If a state is given but
    no city+state match exists, we return None (skip) rather than risk the wrong state.
    """
    safe_city = city.replace("'", "\\'")
    query = f"""
        SELECT
          geo_target_constant.resource_name,
          geo_target_constant.name,
          geo_target_constant.canonical_name,
          geo_target_constant.target_type,
          geo_target_constant.country_code
        FROM geo_target_constant
        WHERE geo_target_constant.country_code = 'US'
          AND geo_target_constant.target_type = 'City'
          AND geo_target_constant.name = '{safe_city}'
    """
    try:
        rows = gaql(client, customer_id, query)
    except Exception:
        return None
    if not rows:
        return None
    state_full = US_STATES.get((state or "").upper().strip(), "")
    if state_full:
        for r in rows:
            if f",{state_full}," in r.geo_target_constant.canonical_name:
                return r.geo_target_constant.resource_name
        # State was specified but no match — DO NOT fall back to a wrong-state city.
        sys.stderr.write(
            f"  geo_lookup: no '{city}, {state}' among {len(rows)} US cities named "
            f"'{city}'; skipping (avoids wrong-state targeting)\n"
        )
        return None
    # No state provided (legacy callers): keep old behaviour but warn.
    if len(rows) > 1:
        sys.stderr.write(
            f"  geo_lookup: '{city}' is ambiguous ({len(rows)} states) and no state "
            f"was given; using first — pass state to disambiguate\n"
        )
    return rows[0].geo_target_constant.resource_name


def ensure_location_assets(client, customer_id: str, place_id: str,
                            campaign_resources: list, dry_run: bool = False) -> int:
    """Link the client's OWN Business Profile location to the given campaigns so the
    ads are eligible for the local/Maps pack (the "Sponsored" map-pack slot).

    Keyed on the client's explicit `place_id` (from plan-input brand.place_id), so it
    can ONLY ever link the correct GBP. If no synced location matches that place_id, it
    SKIPS with a clear message rather than linking a wrong/stray location — the same
    fail-safe philosophy as geo_lookup(). (A real account had a stray second location
    asset for a different business; matching on place_id avoids ever attaching it.)
    """
    if not place_id:
        sys.stderr.write("  [location] no brand.place_id in plan-input — skipping map-pack "
                         "location asset. Add brand.place_id to enable it.\n")
        return 0
    cid = customer_id.replace("-", "")
    rows = gaql(client, cid,
        "SELECT asset.resource_name, asset.location_asset.place_id FROM asset WHERE asset.type = 'LOCATION'")
    match = next((r.asset.resource_name for r in rows
                  if r.asset.location_asset.place_id == place_id), None)
    if not match:
        sys.stderr.write(
            f"  [location] no synced Business Profile location for place_id {place_id}. "
            f"Link the client's GBP to this Ads account (Linked accounts -> Business Profile), "
            f"then re-run. Skipping — will NOT link a wrong/stray location.\n")
        return 0
    # Which ENABLED asset set(s) contain this exact location?
    asset_sets = {r.asset_set_asset.asset_set for r in gaql(client, cid,
        f"SELECT asset_set_asset.asset_set FROM asset_set_asset "
        f"WHERE asset_set_asset.asset = '{match}' AND asset_set_asset.status = 'ENABLED'")}
    if not asset_sets:
        sys.stderr.write(f"  [location] location {match} is in no ENABLED asset set — skipping\n")
        return 0
    # Already linked account-wide? then every campaign is already covered.
    acct_links = {r.customer_asset_set.asset_set for r in gaql(client, cid,
        "SELECT customer_asset_set.asset_set FROM customer_asset_set "
        "WHERE customer_asset_set.status = 'ENABLED'")}
    if asset_sets & acct_links:
        print(f"  [location] client GBP location ({place_id}) already linked account-wide — ok")
        return 0
    if dry_run:
        print(f"  [location] would link GBP location {place_id} to {len(campaign_resources)} campaign(s)")
        return 0
    aset = sorted(asset_sets)[0]
    ops = []
    for camp in campaign_resources:
        op = client.get_type("CampaignAssetSetOperation")
        op.create.campaign = camp
        op.create.asset_set = aset
        ops.append(op)
    req = client.get_type("MutateCampaignAssetSetsRequest")
    req.customer_id = cid
    req.operations = ops
    req.partial_failure = True
    client.get_service("CampaignAssetSetService").mutate_campaign_asset_sets(request=req)
    print(f"  [location] linked client GBP location ({place_id}) to {len(ops)} campaign(s)")
    return len(ops)


# ---------------------------------------------------------------------------
# Claude RSA copy generation
# ---------------------------------------------------------------------------

INTENT_RSA_PROMPT = """Generate Google Ads Responsive Search Ad copy for a local {industry_label}.
This ad targets a specific search intent — no city name required (geo targeting handles location).

Company: {company}
Service: {service_label}
Intent angle: {angle_desc}
Industry guidance: {rsa_guidance}
Landing page: {url}
Phone: {phone}

Return ONLY valid JSON in this exact shape:
{{
  "headlines": ["headline 1", ...],
  "descriptions": ["description 1", ...]
}}

Rules:
- Exactly 15 headlines, each 3-30 characters (count carefully)
- Exactly 4 descriptions, each 60-90 characters (count carefully)
- Do NOT include a city name in any headline — geo targeting places this ad locally
- First 3 headlines must directly match the intent angle (they will be pinned to Slot 1)
- Remaining 12 headlines: mix urgency, trust, offer, guarantee, and CTA angles
- No exclamation marks in headlines
- No all-caps words
- No special characters except commas, periods, hyphens, and the middle dot ·
"""

RSA_PROMPT = """Generate Google Ads Responsive Search Ad copy for a local {industry_label}.

Company: {company}
Service: {service_label}
City: {city}, {state}
Industry guidance: {rsa_guidance}
Landing page: {url}
Phone: {phone}

Return ONLY valid JSON in this exact shape:
{{
  "headlines": ["headline 1", ...],
  "descriptions": ["description 1", ...]
}}

Rules:
- Exactly 15 headlines, each 3-30 characters (count carefully)
- Exactly 4 descriptions, each 60-90 characters (count carefully)
- Mix brand, service, city, urgency, and benefit angles in headlines
- At least 3 headlines include the city name (for Slot 1 pinning)
- Descriptions: availability, free estimate, local expertise, credentials
- No exclamation marks in headlines
- No all-caps words
- No special characters except commas, periods, hyphens, and the middle dot ·
"""


def load_industry_config(template: str) -> dict:
    """Load Ads/industries/{template}.json, falling back to general.json."""
    industries_dir = REPO_ROOT / "Ads" / "industries"
    for name in (template, "general"):
        path = industries_dir / f"{name}.json"
        if path.exists():
            return json.loads(path.read_text())
    return {"industry": "general", "rsa_label": "local service company",
            "rsa_guidance": "", "service_labels": {}, "service_groups": [],
            "lp_body_content": {}}


def get_service_label(service_slug: str, industry_config: dict) -> str:
    """Resolve a service slug to a display label, checking industry config first."""
    label = industry_config.get("service_labels", {}).get(service_slug)
    if label:
        return label
    return SERVICE_LABELS.get(service_slug, service_slug.replace("-", " ").title())


def get_service_groups(services: list[str], industry_config: dict) -> dict[str, list[str]]:
    """Build campaign groups from industry config, falling back to hardcoded SERVICE_GROUPS."""
    groups_spec = industry_config.get("service_groups")
    if groups_spec:
        mapping: dict[str, list[str]] = {}
        for group in groups_spec:
            matched = [s for s in services if s in group["services"]]
            if matched:
                mapping[group["name"]] = matched
        grouped = {s for svcs in mapping.values() for s in svcs}
        for s in services:
            if s not in grouped:
                label = get_service_label(s, industry_config)
                mapping[label] = [s]
        return mapping
    return services_to_groups(services)


ANGLE_GUIDANCE = {
    "speed": "ANGLE: Speed / Emergency. Lead headlines with response time, 24/7 availability, same-day/emergency urgency.",
    "trust": "ANGLE: Trust / Credentials. Lead headlines with IICRC certification, licensed & insured, years in business, local reviews.",
    "value": "ANGLE: Value / Process. Lead headlines with free inspection, direct insurance billing, upfront pricing, and what happens next.",
}

def generate_rsa_copy(client_rec: dict, service_label: str, city: str,
                      state: str, url: str, industry_config: dict | None = None,
                      angle: str | None = None) -> dict:
    api_key = require_env("ANTHROPIC_API_KEY")
    cfg = industry_config or {}
    phone = client_rec.get("phone", client_rec.get("brand", {}).get("phone", ""))
    prompt = RSA_PROMPT.format(
        company=client_rec.get("display_name", ""),
        service_label=service_label,
        city=city,
        state=state,
        url=url,
        phone=phone,
        industry_label=cfg.get("rsa_label", "local service company"),
        rsa_guidance=cfg.get("rsa_guidance", ""),
    )
    if angle and angle in ANGLE_GUIDANCE:
        prompt += "\n\n" + ANGLE_GUIDANCE[angle] + " Keep 3 keyword+location headlines pinned to slot 1; vary the rest to this angle."
    body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1200,
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
    text = payload["content"][0]["text"].strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def generate_intent_rsa_copy(client_rec: dict, service_label: str,
                              intent: dict, url: str,
                              industry_config: dict | None = None) -> dict:
    api_key = require_env("ANTHROPIC_API_KEY")
    cfg = industry_config or {}
    phone = client_rec.get("phone", client_rec.get("brand", {}).get("phone", ""))
    prompt = INTENT_RSA_PROMPT.format(
        company=client_rec.get("display_name", ""),
        service_label=service_label,
        angle_desc=intent["angle_desc"],
        url=url,
        phone=phone,
        industry_label=cfg.get("rsa_label", "local service company"),
        rsa_guidance=cfg.get("rsa_guidance", ""),
    )
    body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1200,
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
    text = payload["content"][0]["text"].strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


# ---------------------------------------------------------------------------
# Scaffold
# ---------------------------------------------------------------------------

SERVICE_LABELS = {
    "water-damage-restoration": "Water Damage",
    "fire-damage-restoration": "Fire Damage",
    "mold-remediation": "Mold Removal",
    "smoke-damage-restoration": "Smoke Damage",
    "storm-damage-restoration": "Storm Damage",
    "sewage-cleanup": "Sewage Cleanup",
    "carpet-cleaning": "Carpet Cleaning",
    "air-duct-cleaning": "Air Duct Cleaning",
    "biohazard-cleanup": "Biohazard Cleanup",
    "asbestos-removal": "Asbestos Removal",
    "lead-paint-removal": "Lead Removal",
    "trauma-cleanup": "Trauma Cleanup",
    "hoarding-cleanup": "Hoarding Cleanup",
    "reconstruction": "Reconstruction",
    "roof-repair": "Roof Repair",
    "flood-cleanup": "Flood Cleanup",
    "basement-waterproofing": "Waterproofing",
    "emergency-board-up": "Board Up Service",
}

SERVICE_GROUPS: list[tuple[str, list[str]]] = [
    ("Water and Flood", ["water-damage-restoration", "flood-cleanup",
                         "sewage-cleanup", "basement-waterproofing"]),
    ("Fire and Smoke", ["fire-damage-restoration", "smoke-damage-restoration"]),
    ("Mold and Air Quality", ["mold-remediation", "air-duct-cleaning"]),
    ("Storm and Structural", ["storm-damage-restoration", "reconstruction",
                               "emergency-board-up", "roof-repair"]),
    ("Specialty", ["biohazard-cleanup", "trauma-cleanup", "hoarding-cleanup",
                   "asbestos-removal", "lead-paint-removal", "carpet-cleaning"]),
]


# Intent-based ad groups added once per service per campaign (geo-targeted, no city).
# Each entry defines the ad group label suffix, seed keywords, URL suffix, and copy angle.
INTENT_AD_GROUPS = [
    {
        "key": "near-me",
        "label_suffix": "Near Me",
        "keywords": ["{base} near me", "local {base}", "{base} near me open now"],
        "url_suffix": "",
        "angle": "proximity",
        "angle_desc": "nearby/local availability — no city in copy, rely on geo targeting",
    },
    {
        "key": "emergency",
        "label_suffix": "Emergency",
        "keywords": ["emergency {base}", "24/7 {base}", "{base} open now", "after hours {base}"],
        "url_suffix": "",
        "angle": "urgency",
        "angle_desc": "speed, 24/7 availability, immediate response, same-day",
    },
    {
        "key": "cost",
        "label_suffix": "Cost",
        "keywords": ["{base} cost", "{base} quote", "affordable {base}", "{base} price"],
        "url_suffix": "",
        "angle": "price",
        "angle_desc": "upfront pricing, free estimate, no hidden fees, insurance billing",
    },
    {
        "key": "company",
        "label_suffix": "Company",
        "keywords": ["{base} company", "{base} contractor", "{base} specialist", "professional {base}"],
        "url_suffix": "",
        "angle": "vendor",
        "angle_desc": "licensed/insured, IICRC certified, years in business, local company",
    },
    {
        "key": "free-estimate",
        "label_suffix": "Free Estimate",
        "keywords": ["free {base} estimate", "free {base} inspection", "free {base} quote"],
        "url_suffix": "",
        "angle": "offer",
        "angle_desc": "free inspection/estimate/assessment offer, no obligation, fast response",
    },
    {
        "key": "insurance",
        "label_suffix": "Insurance",
        "keywords": ["insurance {base}", "{base} insurance claim", "{base} covered by insurance"],
        "url_suffix": "",
        "angle": "insurance",
        "angle_desc": "works with all insurers, direct billing, claim assistance, maximize payout",
    },
    {
        "key": "removal",
        "label_suffix": "Removal",
        "keywords": ["{base} removal", "{base} cleanup", "{base} repair"],
        "url_suffix": "",
        "angle": "variant",
        "angle_desc": "removal/cleanup/repair framing — catches searchers who avoid 'restoration' terminology",
    },
]


def services_to_groups(services: list[str]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for group_name, group_services in SERVICE_GROUPS:
        matched = [s for s in services if s in group_services]
        if matched:
            mapping[group_name] = matched
    grouped = {s for svcs in mapping.values() for s in svcs}
    for s in services:
        if s not in grouped:
            label = SERVICE_LABELS.get(s, s.replace("-", " ").title())
            mapping[label] = [s]
    return mapping


# Intent signal tokens — used to map real research keywords to the right intent ad group.
INTENT_MATCH_TOKENS = {
    "near-me": ["near me", "near you", "local"],
    "emergency": ["emergency", "24 hour", "24/7", "urgent", "same day"],
    "cost": ["cost", "price", "pricing", "how much", "quote"],
    "company": ["company", "companies", "contractor", "specialist", "professional"],
    "free-estimate": ["free estimate", "free inspection", "free quote"],
    "insurance": ["insurance", "claim", "covered"],
    "removal": ["removal", "cleanup", "clean up", "remediation"],
}


def pick_research_kws(research_list, intent_key, limit=5):
    """Top research keywords (by volume) whose text matches an intent's signal tokens —
    enriches an intent ad group with real, volume-validated query variants."""
    tokens = INTENT_MATCH_TOKENS.get(intent_key, [])
    if not tokens:
        return []
    matched = [r for r in research_list if any(t in r["keyword"].lower() for t in tokens)]
    matched.sort(key=lambda r: r.get("avg_monthly_searches", 0), reverse=True)
    return [r["keyword"] for r in matched[:limit]]


def load_keyword_research(slug):
    p = CLIENTS_DIR / slug / "keyword-research.json"
    if p.exists():
        return json.loads(p.read_text()).get("by_service", {})
    return {}


def cmd_scaffold(slug: str, dry_run: bool = False, services_filter: list = None,
                 auto_keywords: bool = False) -> int:
    client_rec = load_client(slug)
    customer_id = get_customer_id(client_rec, slug)
    client = build_ads_client(slug)

    plan_path = CLIENTS_DIR / slug / "plan-input.json"
    if not plan_path.exists():
        die(f"plan-input.json not found for {slug}. Run rank-ai-plan-site first.")
    plan = json.loads(plan_path.read_text())

    services = plan.get("services", [])
    # Optional subset filter — the productized worker passes payload.services here,
    # so a launch builds only the requested campaigns, not every service in the profile.
    if services_filter:
        valid = [s for s in services_filter if s in services]
        missing = [s for s in services_filter if s not in services]
        if missing:
            print(f"  [warn] ignoring services not in plan-input.json: {', '.join(missing)}")
        if not valid:
            die("No valid services after --services filter.")
        services = valid
    service_areas = plan.get("service_areas", [])
    domain = client_rec.get("domain", "")
    display_name = client_rec.get("display_name", slug)
    daily_budget = 50.0

    if not services:
        die("No services in plan-input.json.")
    if not service_areas:
        die("No service_areas in plan-input.json.")

    template = plan.get("template", "general")
    industry_config = load_industry_config(template)

    # Auto keyword research: pull real, volume-validated keywords (run it if missing)
    # and use them to enrich the intent ad groups. Falls back to templates if unavailable.
    research_by_service: dict = {}
    if auto_keywords:
        if not (CLIENTS_DIR / slug / "keyword-research.json").exists() and not dry_run:
            print("    [auto-keywords] no research on file — running keyword research first...")
            try:
                cmd_keyword_research(slug, services=services)
            except Exception as exc:
                print(f"    [auto-keywords] research failed ({str(exc)[:80]}) — falling back to templates")
        research_by_service = load_keyword_research(slug)
        print(f"    [auto-keywords] research loaded for {len(research_by_service)} service(s)")

    print(f"\n==> Scaffolding Google Ads for {display_name}")
    print(f"    Industry: {industry_config.get('industry', template)}")
    print(f"    Services: {len(services)}  |  Areas: {len(service_areas)}")
    if dry_run:
        print("    [DRY RUN — no changes will be made]")
    print()

    campaign_groups = get_service_groups(services, industry_config)
    structure = load_structure(slug)

    for group_name, group_services in campaign_groups.items():
        campaign_key = group_name.lower().replace(" ", "-").replace("and", "")
        campaign_key = campaign_key.replace("--", "-").strip("-")

        if campaign_key in structure["campaigns"]:
            print(f"  [skip] campaign '{group_name}' already scaffolded")
            campaign_resource = structure["campaigns"][campaign_key]["resource_name"]
        else:
            budget_name = f"{display_name} - {group_name}"
            print(f"  Creating budget: {budget_name} (${daily_budget}/day)")
            budget_resource = create_budget(client, customer_id, budget_name,
                                            daily_budget, dry_run=dry_run)

            campaign_name = f"{display_name} - {group_name}"
            print(f"  Creating campaign: {campaign_name}")
            campaign_resource = create_campaign(client, customer_id, campaign_name,
                                                budget_resource, dry_run=dry_run)

            print(f"  Adding {len(DEFAULT_NEGATIVES)} default negatives")
            add_campaign_negatives(client, customer_id, campaign_resource,
                                   DEFAULT_NEGATIVES, dry_run=dry_run)

            if not dry_run:
                structure["campaigns"][campaign_key] = {
                    "name": campaign_name,
                    "resource_name": campaign_resource,
                    "budget_resource": budget_resource,
                    "services": group_services,
                }
                save_structure(slug, structure)

        # Map-pack eligibility: link the client's OWN GBP location (place_id-matched, fail-safe)
        ensure_location_assets(client, customer_id,
                               (plan.get("brand") or {}).get("place_id", ""),
                               [campaign_resource], dry_run=dry_run)

        for area in service_areas:
            city = area.get("city", "")
            state = area.get("state", "")
            area_slug = area.get("slug", f"{city}-{state}".lower())

            for service_slug in group_services:
                ag_key = f"{campaign_key}_{area_slug}_{service_slug}"
                if ag_key in structure.get("ad_groups", {}):
                    print(f"    [skip] ad group: {city} / {service_slug}")
                    continue

                service_label = get_service_label(service_slug, industry_config)
                ag_name = f"{service_label} - {city}, {state}"
                print(f"    Creating ad group: {ag_name}")
                ag_resource = create_ad_group(client, customer_id, ag_name,
                                              campaign_resource, dry_run=dry_run)

                # Geo target (state-disambiguated — see geo_lookup)
                geo_resource = geo_lookup(client, customer_id, city, state)
                if geo_resource:
                    add_campaign_geo_target(client, customer_id, campaign_resource,
                                            geo_resource, dry_run=dry_run)
                else:
                    print(f"    [warn] geo not found for {city} — add manually")

                # Seed keywords
                base = service_label.lower()
                c = city.lower()
                seed_kws = [
                    f"{base} {c}",
                    f"{c} {base}",
                    f"emergency {base} {c}",
                    f"{base} company {c}",
                    f"{base} services {c}",
                ]
                print(f"    Adding {len(seed_kws)} seed keywords")
                add_keywords_to_ad_group(client, customer_id, ag_resource,
                                         seed_kws, dry_run=dry_run)

                # Generate RSA
                landing_url = f"https://{domain}/service-areas/{area_slug}/{service_slug}/"
                if dry_run:
                    print(f"    [dry-run] RSA: 3-angle copy + final URL {landing_url}")
                    ad_resource = None
                else:
                    print(f"    Generating RSA copy...")
                    try:
                        copy = generate_rsa_copy(client_rec, service_label, city, state,
                                                 landing_url, industry_config)
                        print(f"    Creating RSA ({len(copy['headlines'])} headlines)")
                        ad_resource = create_rsa(client, customer_id, ag_resource, copy,
                                                 landing_url, dry_run=dry_run)
                    except Exception as exc:
                        print(f"    [warn] RSA failed: {exc}")
                        ad_resource = None

                if not dry_run:
                    structure.setdefault("ad_groups", {})[ag_key] = {
                        "name": ag_name,
                        "resource_name": ag_resource,
                        "campaign_key": campaign_key,
                        "service": service_slug,
                        "area": area_slug,
                        "ad_resource": ad_resource,
                    }
                    save_structure(slug, structure)
        # Intent-based ad groups: one set per service per campaign, geo-targeted (no city)
        for service_slug in group_services:
            service_label = get_service_label(service_slug, industry_config)
            base = service_label.lower()
            landing_url = f"https://{domain}/services/{service_slug}/"

            for intent in INTENT_AD_GROUPS:
                ag_key = f"{campaign_key}_{service_slug}_{intent['key']}"
                if ag_key in structure.get("ad_groups", {}):
                    print(f"    [skip] intent ad group: {service_label} / {intent['label_suffix']}")
                    continue

                ag_name = f"{service_label} - {intent['label_suffix']}"
                print(f"    Creating intent ad group: {ag_name}")
                ag_resource = create_ad_group(client, customer_id, ag_name,
                                              campaign_resource, dry_run=dry_run)

                intent_kws = [kw.format(base=base) for kw in intent["keywords"]]
                # Enrich with real, volume-validated keywords matched to this intent
                if research_by_service:
                    for rk in pick_research_kws(research_by_service.get(service_slug, []), intent["key"], limit=5):
                        if rk.lower() not in [k.lower() for k in intent_kws]:
                            intent_kws.append(rk)
                print(f"    Adding {len(intent_kws)} intent keywords"
                      + (f" (+research)" if research_by_service else ""))
                add_keywords_to_ad_group(client, customer_id, ag_resource,
                                         intent_kws, dry_run=dry_run)

                if dry_run:
                    print(f"    [dry-run] intent RSA: {intent['angle']} copy + final URL {landing_url}")
                    ad_resource = None
                else:
                    print(f"    Generating intent RSA copy ({intent['angle']})...")
                    try:
                        copy = generate_intent_rsa_copy(client_rec, service_label,
                                                        intent, landing_url, industry_config)
                        print(f"    Creating RSA ({len(copy['headlines'])} headlines)")
                        ad_resource = create_rsa(client, customer_id, ag_resource, copy,
                                                 landing_url, dry_run=dry_run)
                    except Exception as exc:
                        print(f"    [warn] intent RSA failed: {exc}")
                        ad_resource = None

                if not dry_run:
                    structure.setdefault("ad_groups", {})[ag_key] = {
                        "name": ag_name,
                        "resource_name": ag_resource,
                        "campaign_key": campaign_key,
                        "service": service_slug,
                        "intent": intent["key"],
                        "ad_resource": ad_resource,
                    }
                    save_structure(slug, structure)

        print()

    if dry_run:
        print(f"==> Dry run complete. Remove --dry-run to execute.")
    else:
        print(f"==> Scaffold complete for {display_name}")
        print(f"    All campaigns PAUSED. Review then enable:")
        print(f"      python3 scripts/ads_manager.py list-campaigns --slug {slug}")
        print(f"      python3 scripts/ads_manager.py enable --slug {slug} --resource <campaign>")
    return 0


# ---------------------------------------------------------------------------
# Management commands
# ---------------------------------------------------------------------------

def cmd_pause_or_enable(slug: str, resource_name: str, action: str) -> int:
    client_rec = load_client(slug)
    customer_id = get_customer_id(client_rec, slug)
    client = build_ads_client(slug)

    if "/campaigns/" in resource_name:
        service = client.get_service("CampaignService")
        op = client.get_type("CampaignOperation")
        op.update.resource_name = resource_name
        op.update.status = (client.enums.CampaignStatusEnum.PAUSED
                            if action == "pause"
                            else client.enums.CampaignStatusEnum.ENABLED)
        op.update_mask.paths.append("status")
        service.mutate_campaigns(customer_id=customer_id, operations=[op])
    elif "/adGroups/" in resource_name:
        service = client.get_service("AdGroupService")
        op = client.get_type("AdGroupOperation")
        op.update.resource_name = resource_name
        op.update.status = (client.enums.AdGroupStatusEnum.PAUSED
                            if action == "pause"
                            else client.enums.AdGroupStatusEnum.ENABLED)
        op.update_mask.paths.append("status")
        service.mutate_ad_groups(customer_id=customer_id, operations=[op])
    else:
        die(f"Unrecognized resource name: {resource_name}")

    print(f"  {action.capitalize()}d: {resource_name}")
    return 0


def cmd_set_budget(slug: str, campaign_resource: str, daily_budget: float) -> int:
    client_rec = load_client(slug)
    customer_id = get_customer_id(client_rec, slug)
    client = build_ads_client(slug)

    # Fetch the budget resource name from the campaign
    campaign_id = campaign_resource.split("/campaigns/")[-1]
    rows = gaql(client, customer_id,
                f"SELECT campaign.campaign_budget FROM campaign WHERE campaign.id = {campaign_id}")
    if not rows:
        die(f"Campaign not found: {campaign_resource}")

    budget_resource = rows[0].campaign.campaign_budget
    budget_service = client.get_service("CampaignBudgetService")
    op = client.get_type("CampaignBudgetOperation")
    budget = op.update
    budget.resource_name = budget_resource
    budget.amount_micros = int(daily_budget * 1_000_000)
    op.update_mask.paths.append("amount_micros")

    budget_service.mutate_campaign_budgets(customer_id=customer_id, operations=[op])
    print(f"  Budget updated to ${daily_budget:.2f}/day")
    return 0


def cmd_set_bid_strategy(slug: str, campaign_resource: str, strategy: str,
                         max_cpc: float | None = None) -> int:
    """Switch a campaign's portfolio-free bidding strategy.

    strategy:
      maximize-clicks      -> TARGET_SPEND (Maximize Clicks), optional --max-cpc ceiling.
                              The cold-start strategy: forces the campaign into the auction
                              to win clicks + gather conversion data (fixes IS-lost-to-rank).
      maximize-conversions -> MAXIMIZE_CONVERSIONS (graduate here once ~15-30 conv exist).

    Uses the field-mask helper (Google's recommended pattern) so the bidding-strategy
    oneof switches cleanly.
    """
    from google.api_core import protobuf_helpers

    client_rec = load_client(slug)
    customer_id = get_customer_id(client_rec, slug)
    client = build_ads_client(slug)

    service = client.get_service("CampaignService")
    op = client.get_type("CampaignOperation")
    campaign = op.update
    campaign.resource_name = campaign_resource

    if strategy == "maximize-clicks":
        # Setting the target_spend oneof switches the strategy away from maximize_conversions.
        if max_cpc is not None:
            campaign.target_spend.cpc_bid_ceiling_micros = int(max_cpc * 1_000_000)
        else:
            # Touch the message so the oneof is set even without a ceiling.
            campaign.target_spend.CopyFrom(client.get_type("TargetSpend"))
        label = f"Maximize Clicks" + (f" (max CPC ${max_cpc:.2f})" if max_cpc else "")
    elif strategy == "maximize-conversions":
        campaign.maximize_conversions.CopyFrom(client.get_type("MaximizeConversions"))
        label = "Maximize Conversions"
    else:
        die(f"Unknown strategy: {strategy} (use maximize-clicks | maximize-conversions)")

    op.update_mask.CopyFrom(protobuf_helpers.field_mask(None, campaign._pb))
    service.mutate_campaigns(customer_id=customer_id, operations=[op])
    print(f"  Bid strategy -> {label}: {campaign_resource}")
    return 0


def cmd_add_keywords(slug: str, ad_group_resource: str, keywords_str: str) -> int:
    client_rec = load_client(slug)
    customer_id = get_customer_id(client_rec, slug)
    client = build_ads_client(slug)

    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    if not keywords:
        die("No keywords provided.")

    count = add_keywords_to_ad_group(client, customer_id, ad_group_resource, keywords)
    print(f"  Added {count} keyword entries ({len(keywords)} terms x 3 match types)")
    return 0


def cmd_add_negatives(slug: str, campaign_resource: str, keywords_str: str) -> int:
    client_rec = load_client(slug)
    customer_id = get_customer_id(client_rec, slug)
    client = build_ads_client(slug)

    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    if not keywords:
        die("No keywords provided.")

    add_campaign_negatives(client, customer_id, campaign_resource, keywords)
    print(f"  Added {len(keywords)} negative keywords")
    return 0


def cmd_generate_ads(slug: str, ad_group_resource: str, service_slug: str,
                     city: str, state: str) -> int:
    client_rec = load_client(slug)
    customer_id = get_customer_id(client_rec, slug)
    client = build_ads_client(slug)
    domain = client_rec.get("domain", "")

    service_label = SERVICE_LABELS.get(service_slug,
                                       service_slug.replace("-", " ").title())
    area_slug = f"{city.lower().replace(' ', '-')}-{state.lower()}"
    final_url = f"https://{domain}/service-areas/{area_slug}/{service_slug}/"

    print(f"  Generating RSA copy for {service_label} - {city}, {state}...")
    copy = generate_rsa_copy(client_rec, service_label, city, state, final_url)

    print(f"  Headlines ({len(copy['headlines'])}):")
    for i, h in enumerate(copy["headlines"], 1):
        print(f"    {i:2d}. {h}  ({len(h)} chars)")

    print(f"\n  Descriptions ({len(copy['descriptions'])}):")
    for i, d in enumerate(copy["descriptions"], 1):
        print(f"    {i}. {d}  ({len(d)} chars)")

    print(f"\n  Creating RSA...")
    resource = create_rsa(client, customer_id, ad_group_resource, copy, final_url)
    print(f"  Created: {resource}")
    return 0


# ---------------------------------------------------------------------------
# Keyword research
# ---------------------------------------------------------------------------

# Maps service slugs to seed keyword phrases for keyword idea generation.
SERVICE_SEED_KEYWORDS: dict[str, list[str]] = {
    "water-damage-restoration": ["water damage restoration", "water damage repair", "flood cleanup"],
    "flood-damage-restoration": ["flood damage restoration", "flood cleanup service", "flooded home repair"],
    "burst-pipe-repair": ["burst pipe repair", "broken pipe water damage", "pipe burst cleanup"],
    "basement-flooding-cleanup": ["basement flooding cleanup", "flooded basement", "basement water damage"],
    "appliance-leak-cleanup": ["appliance leak water damage", "washing machine flood", "dishwasher leak repair"],
    "frozen-pipe-restoration": ["frozen pipe burst repair", "frozen pipe water damage"],
    "roof-leak-repair": ["roof leak repair", "roof water damage", "emergency roof leak"],
    "sewage-cleanup": ["sewage cleanup", "sewage backup cleanup", "raw sewage removal"],
    "fire-damage-restoration": ["fire damage restoration", "fire damage repair", "house fire cleanup"],
    "smoke-damage-restoration": ["smoke damage restoration", "smoke damage repair"],
    "soot-removal": ["soot removal", "soot cleanup after fire"],
    "odor-removal": ["odor removal service", "smoke odor elimination", "deodorization service"],
    "mold-remediation": ["mold remediation", "mold removal", "black mold removal"],
    "mold-inspection-testing": ["mold inspection", "mold testing", "mold assessment"],
    "storm-damage-restoration": ["storm damage restoration", "storm damage repair", "hurricane damage repair"],
    "biohazard-cleanup": ["biohazard cleanup", "crime scene cleanup", "trauma scene cleanup"],
    "reconstruction": ["damage reconstruction", "home reconstruction after damage"],
    "general-contracting": ["general contractor restoration", "restoration contractor"],
}


def cmd_keyword_research(slug: str, services: list[str] | None = None,
                         output_csv: str | None = None) -> int:
    """Pull keyword ideas from Google Ads KeywordPlanIdeaService."""
    try:
        from google.ads.googleads.client import GoogleAdsClient
        from google.ads.googleads.errors import GoogleAdsException
    except ImportError:
        die("Missing google-ads library. Run: pip install google-ads")

    client_rec = load_client(slug)
    customer_id = get_customer_id(client_rec, slug)
    ads_client = build_ads_client(slug)

    plan_path = CLIENTS_DIR / slug / "plan-input.json"
    plan = json.loads(plan_path.read_text()) if plan_path.exists() else {}

    target_services = services or plan.get("services", list(SERVICE_SEED_KEYWORDS.keys()))
    service_areas = plan.get("service_areas", [])

    # Build geo target resource names for the service areas
    geo_targets: list[str] = []
    if service_areas:
        for area in service_areas[:5]:  # Limit to avoid quota
            geo = geo_lookup(ads_client, customer_id, area.get("city", ""), area.get("state", ""))
            if geo:
                geo_targets.append(geo)

    kpi_service = ads_client.get_service("KeywordPlanIdeaService")

    # English language constant
    language = "languageConstants/1000"

    all_results: list[dict] = []

    print(f"\n==> Keyword Research — {client_rec.get('display_name', slug)}")
    print(f"    Services: {len(target_services)}  |  Geo targets: {len(geo_targets)}")
    print()

    for service_slug in target_services:
        seeds = SERVICE_SEED_KEYWORDS.get(
            service_slug,
            [service_slug.replace("-", " ")]
        )

        # Add city-qualified seeds for top city
        if service_areas:
            top_city = service_areas[0].get("city", "")
            seeds = seeds + [f"{s} {top_city}" for s in seeds[:2]]

        request = ads_client.get_type("GenerateKeywordIdeasRequest")
        request.customer_id = customer_id.replace("-", "")
        request.language = language
        if geo_targets:
            request.geo_target_constants.extend(geo_targets)
        request.include_adult_keywords = False
        request.keyword_seed.keywords.extend(seeds)
        request.keyword_plan_network = (
            ads_client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
        )

        try:
            response = kpi_service.generate_keyword_ideas(request=request)
            ideas = list(response)
        except Exception as exc:
            print(f"  [warn] {service_slug}: {exc}")
            continue

        service_results: list[dict] = []
        for idea in ideas:
            metrics = idea.keyword_idea_metrics
            avg_monthly = metrics.avg_monthly_searches
            competition = metrics.competition.name  # LOW / MEDIUM / HIGH
            low_bid = metrics.low_top_of_page_bid_micros / 1_000_000
            high_bid = metrics.high_top_of_page_bid_micros / 1_000_000
            service_results.append({
                "service": service_slug,
                "keyword": idea.text,
                "avg_monthly_searches": avg_monthly,
                "competition": competition,
                "low_top_cpc": round(low_bid, 2),
                "high_top_cpc": round(high_bid, 2),
            })

        # Sort by volume desc
        service_results.sort(key=lambda x: x["avg_monthly_searches"], reverse=True)
        all_results.extend(service_results)

        top = service_results[:5]
        label = SERVICE_LABELS.get(service_slug, service_slug.replace("-", " ").title())
        print(f"  {label} — {len(service_results)} ideas (top 5):")
        for r in top:
            print(f"    {r['keyword']:<50} {r['avg_monthly_searches']:>6,} searches  "
                  f"{r['competition']:<6}  ${r['low_top_cpc']:.2f}–${r['high_top_cpc']:.2f} CPC")
        print()

    if not all_results:
        print("  No results returned.")
        return 1

    # Write CSV
    if output_csv is None:
        out_dir = CLIENTS_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        output_csv = str(out_dir / f"keyword-research-{date.today()}.csv")

    import csv
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "service", "keyword", "avg_monthly_searches",
            "competition", "low_top_cpc", "high_top_cpc"
        ])
        writer.writeheader()
        writer.writerows(all_results)

    # Structured JSON grouped by service — consumed by `scaffold --auto-keywords`.
    by_service: dict = {}
    for r in all_results:
        by_service.setdefault(r["service"], []).append(
            {k: r[k] for k in ("keyword", "avg_monthly_searches", "competition", "low_top_cpc", "high_top_cpc")})
    json_path = CLIENTS_DIR / slug / "keyword-research.json"
    json_path.write_text(json.dumps({"generated_at": str(date.today()), "by_service": by_service}, indent=2))

    print(f"  Total keywords: {len(all_results)}")
    print(f"  Saved to: {output_csv}")
    print(f"  Structured:   {json_path}")
    return 0


def cmd_backfill_rsas(slug: str) -> int:
    """Recovery: create RSAs for ad groups in the structure that have no ad yet
    (e.g. after a partial build where ad creation failed). Idempotent — skips
    ad groups that already carry an ad_resource."""
    client_rec = load_client(slug)
    customer_id = get_customer_id(client_rec, slug)
    client = build_ads_client(slug)
    domain = client_rec.get("domain", "")

    plan = json.loads((CLIENTS_DIR / slug / "plan-input.json").read_text())
    industry_config = load_industry_config(plan.get("template", "general"))
    areas_by_slug = {a.get("slug", ""): a for a in plan.get("service_areas", [])}
    intents_by_key = {i["key"]: i for i in INTENT_AD_GROUPS}

    structure = load_structure(slug)
    ad_groups = structure.get("ad_groups", {})
    pending = [(k, v) for k, v in ad_groups.items() if not v.get("ad_resource")]
    print(f"==> Backfilling RSAs for {len(pending)} ad group(s) missing an ad")

    done = 0
    for ag_key, entry in pending:
        service_slug = entry.get("service", "")
        service_label = get_service_label(service_slug, industry_config)
        try:
            if entry.get("area"):
                area = areas_by_slug.get(entry["area"], {})
                landing_url = f"https://{domain}/service-areas/{entry['area']}/{service_slug}/"
                copy = generate_rsa_copy(client_rec, service_label,
                                         area.get("city", ""), area.get("state", ""),
                                         landing_url, industry_config)
            else:
                intent = intents_by_key.get(entry.get("intent", ""), {})
                landing_url = f"https://{domain}/services/{service_slug}/"
                copy = generate_intent_rsa_copy(client_rec, service_label, intent,
                                                landing_url, industry_config)
            ad_resource = create_rsa(client, customer_id, entry["resource_name"],
                                     copy, landing_url)
            entry["ad_resource"] = ad_resource
            save_structure(slug, structure)
            done += 1
            print(f"  [{done}/{len(pending)}] RSA created: {entry.get('name', ag_key)}")
        except Exception as exc:
            print(f"  [warn] RSA failed for {entry.get('name', ag_key)}: {exc}")

    print(f"==> Backfill complete: {done}/{len(pending)} RSAs created")
    return 0


def cmd_update_final_urls(slug: str) -> int:
    """Repoint every ad group's RSA final URL to its /lp/ landing page
    (city ad groups -> {service}-{area}; intent ad groups -> {service}-{intent})."""
    from google.api_core import protobuf_helpers
    client_rec = load_client(slug)
    customer_id = get_customer_id(client_rec, slug)
    client = build_ads_client(slug)
    domain = client_rec.get("domain", "")
    structure = load_structure(slug)
    ad_groups = structure.get("ad_groups", {})
    ad_service = client.get_service("AdService")

    updated = 0
    skipped = 0
    for ag_key, entry in ad_groups.items():
        ad_resource = entry.get("ad_resource")
        if not ad_resource:
            skipped += 1
            continue
        if entry.get("area"):
            lp_slug = f"{entry['service']}-{entry['area']}"
        else:
            lp_slug = f"{entry['service']}-{entry.get('intent', '')}"
        url = f"https://{domain}/lp/{lp_slug}/"

        # Update the Ad's final_urls (derive Ad resource from the adGroupAd resource)
        ad_id = ad_resource.split("~")[-1]
        op = client.get_type("AdOperation")
        ad = op.update
        ad.resource_name = f"customers/{customer_id}/ads/{ad_id}"
        ad.final_urls.append(url)
        client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, ad._pb))
        try:
            ad_service.mutate_ads(customer_id=customer_id, operations=[op])
            entry["final_url"] = url
            updated += 1
            print(f"  [{updated}] {entry.get('name', ag_key)} -> {url}")
        except Exception as exc:
            print(f"  [warn] failed for {entry.get('name', ag_key)}: {exc}")
    save_structure(slug, structure)
    print(f"==> Updated {updated} final URLs ({skipped} skipped — no ad)")
    return 0


def cmd_create_conversion(slug: str, name: str, value: float, currency: str = "USD") -> int:
    """Create a click-to-call (PHONE_CALL_LEAD / WEBPAGE) conversion action, then
    print the AW global-tag id + full conversion label to wire into brand.ts."""
    import re
    client_rec = load_client(slug)
    customer_id = get_customer_id(client_rec, slug)
    client = build_ads_client(slug)

    ga0 = client.get_service("GoogleAdsService")
    # Idempotent: reuse an existing conversion action with this name (retry-safe).
    safe = name.replace("'", "\\'")
    existing = list(ga0.search(customer_id=customer_id, query=(
        f"SELECT conversion_action.resource_name FROM conversion_action "
        f"WHERE conversion_action.name = '{safe}' AND conversion_action.status != 'REMOVED'")))
    if existing:
        rn = existing[0].conversion_action.resource_name
        print(f"  [reuse] existing conversion action: {rn}")
    else:
        svc = client.get_service("ConversionActionService")
        op = client.get_type("ConversionActionOperation")
        ca = op.create
        ca.name = name
        ca.type_ = client.enums.ConversionActionTypeEnum.WEBPAGE
        ca.category = client.enums.ConversionActionCategoryEnum.PHONE_CALL_LEAD
        ca.status = client.enums.ConversionActionStatusEnum.ENABLED
        ca.primary_for_goal = True
        ca.counting_type = client.enums.ConversionActionCountingTypeEnum.ONE_PER_CLICK
        ca.click_through_lookback_window_days = 90
        ca.value_settings.default_value = float(value)
        ca.value_settings.default_currency_code = currency
        ca.value_settings.always_use_default_value = True

        resp = svc.mutate_conversion_actions(customer_id=customer_id, operations=[op])
        rn = resp.results[0].resource_name
        print(f"  Conversion action created: {rn}")

    ga = client.get_service("GoogleAdsService")
    # AW global-tag id
    aw = None
    for r in ga.search(customer_id=customer_id,
                       query="SELECT customer.conversion_tracking_setting.conversion_tracking_id FROM customer"):
        cid = r.customer.conversion_tracking_setting.conversion_tracking_id
        if cid:
            aw = f"AW-{cid}"
    # full send_to label from the action's tag snippet
    label = None
    for r in ga.search(customer_id=customer_id,
                       query=f"SELECT conversion_action.tag_snippets FROM conversion_action WHERE conversion_action.resource_name = '{rn}'"):
        for ts in r.conversion_action.tag_snippets:
            m = re.search(r"AW-\d+/[\w-]+", ts.event_snippet or "")
            if m:
                label = m.group(0)
                break
    print(f"  gadsId:                  {aw}")
    print(f"  gadsCallConversionLabel: {label}")
    # Persist for the provisioning worker to read (avoids stdout parsing)
    out_dir = CLIENTS_DIR / slug / "ads"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "conversion.json").write_text(json.dumps(
        {"resource_name": rn, "gads_id": aw, "conversion_label": label}, indent=2))
    return 0


# Angle guidance for the two extra RSAs added to city ad groups (speed = scaffold RSA).
def cmd_angle_rsas(slug: str) -> int:
    """Add Trust + Value angle RSAs to every city ad group (→ 3 RSAs each).
    Idempotent — records added angles in the structure file and skips them."""
    client_rec = load_client(slug)
    customer_id = get_customer_id(client_rec, slug)
    client = build_ads_client(slug)
    domain = client_rec.get("domain", "")
    plan = json.loads((CLIENTS_DIR / slug / "plan-input.json").read_text())
    industry_config = load_industry_config(plan.get("template", "general"))
    areas_by_slug = {a.get("slug", ""): a for a in plan.get("service_areas", [])}
    structure = load_structure(slug)
    city_ags = [(k, v) for k, v in structure.get("ad_groups", {}).items() if v.get("area")]
    added = 0
    for ag_key, entry in city_ags:
        area = areas_by_slug.get(entry["area"], {})
        service_label = get_service_label(entry["service"], industry_config)
        url = entry.get("final_url") or f"https://{domain}/lp/{entry['service']}-{entry['area']}/"
        made = entry.setdefault("extra_ad_resources", [])
        for angle in ("trust", "value"):
            if any(a.get("angle") == angle for a in made):
                continue
            try:
                copy = generate_rsa_copy(client_rec, service_label, area.get("city", ""),
                                         area.get("state", ""), url, industry_config, angle=angle)
                res = create_rsa(client, customer_id, entry["resource_name"], copy, url)
                made.append({"angle": angle, "ad_resource": res})
                save_structure(slug, structure)
                added += 1
            except Exception as exc:
                print(f"  [warn] {entry.get('name', ag_key)} [{angle}]: {str(exc)[:90]}")
    print(f"==> Added {added} angle RSAs to {len(city_ags)} city ad groups")
    return 0


def _parse_negative_terms() -> list:
    """Universal (Section A) + trades (B.1) + restoration DIY/product/symptoms (B.6)
    negatives from the spec file. B.6 is mandatory for restoration clients (every Rank
    AI client is one) — it blocks the homeowner-DIY / product-shopping / symptom queries
    that water/fire/mold keywords flood in, which Section A's generic DIY list misses."""
    spec = (REPO_ROOT / "Ads" / "universal-negative-keywords.md").read_text()
    def block_terms(start, end):
        s = spec.index(start); e = spec.index(end, s)
        terms, fence = [], False
        for line in spec[s:e].splitlines():
            if line.strip().startswith("```"):
                fence = not fence; continue
            if fence and line.strip() and not line.strip().startswith("#"):
                terms.append(line.strip().lower())
        return terms
    out, seen = [], set()
    for t in (block_terms("## A. Universal", "## B. Industry")
              + block_terms("### B.1", "### B.2")
              + block_terms("### B.6", "## C. Geographic")
              + block_terms("### D.1", "### D.2")):  # national restoration competitors
        if t not in seen:
            seen.add(t); out.append(t)
    return out


def cmd_apply_negatives(slug: str) -> int:
    """Apply the universal + trades negative list to every non-removed campaign.
    Idempotent — dedupes against each campaign's existing negatives."""
    client_rec = load_client(slug)
    customer_id = get_customer_id(client_rec, slug)
    client = build_ads_client(slug)
    master = _parse_negative_terms()
    ga = client.get_service("GoogleAdsService")
    # Only SEARCH campaigns take keyword negatives — LOCAL_SERVICES (LSA), Performance Max,
    # etc. reject them with OPERATION_NOT_PERMITTED_FOR_CONTEXT and would abort the batch.
    campaigns = [(r.campaign.id, r.campaign.resource_name, r.campaign.name) for r in ga.search(
        customer_id=customer_id,
        query="SELECT campaign.id, campaign.resource_name, campaign.name FROM campaign "
              "WHERE campaign.status != 'REMOVED' AND campaign.advertising_channel_type = 'SEARCH'")]
    # Skip dedicated Competitor Conquest campaigns — they intentionally bid on competitor
    # brands, so we must NOT push the national-competitor negatives (D.1) onto them.
    conquest = [c for c in campaigns if "conquest" in c[2].lower()]
    campaigns = [c for c in campaigns if "conquest" not in c[2].lower()]
    if conquest:
        print(f"  (skipping {len(conquest)} Conquest campaign(s): {', '.join(c[2] for c in conquest)})")
    total = 0
    for cid, res, name in campaigns:
        existing = {r.campaign_criterion.keyword.text.lower() for r in ga.search(
            customer_id=customer_id,
            query=f"SELECT campaign_criterion.keyword.text FROM campaign_criterion "
                  f"WHERE campaign.id = {cid} AND campaign_criterion.negative = true "
                  f"AND campaign_criterion.type = 'KEYWORD'")}
        new_terms = [t for t in master if t not in existing]
        try:
            for i in range(0, len(new_terms), 100):
                add_campaign_negatives(client, customer_id, res, new_terms[i:i+100])
            total += len(new_terms)
        except Exception as e:  # don't let one campaign abort the rest
            print(f"  ! skipped {name[:40]}: {str(e)[:90]}")
    print(f"==> Applied {total} negatives across {len(campaigns)} search campaigns ({len(master)}-term list)")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Rank AI — Google Ads Manager")
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("auth")
    p.add_argument("--slug", required=True)

    p = sub.add_parser("list-accounts")
    p.add_argument("--slug", required=True)

    p = sub.add_parser("list-campaigns")
    p.add_argument("--slug", required=True)

    p = sub.add_parser("scaffold")
    p.add_argument("--slug", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--services", help="Comma-separated service slugs to build (default: all from plan-input.json)")
    p.add_argument("--auto-keywords", action="store_true", help="Run keyword research and enrich ad groups with real, volume-validated keywords")

    p = sub.add_parser("backfill-rsas")
    p.add_argument("--slug", required=True)

    p = sub.add_parser("update-final-urls")
    p.add_argument("--slug", required=True)

    p = sub.add_parser("create-conversion")
    p.add_argument("--slug", required=True)
    p.add_argument("--name", default="Lead · Phone Call")
    p.add_argument("--value", type=float, required=True)
    p.add_argument("--currency", default="USD")

    p = sub.add_parser("angle-rsas")
    p.add_argument("--slug", required=True)

    p = sub.add_parser("apply-negatives")
    p.add_argument("--slug", required=True)

    p = sub.add_parser("report")
    p.add_argument("--slug", required=True)
    p.add_argument("--days", type=int, default=30)

    p = sub.add_parser("note", help="Read or append the client's ads journal")
    p.add_argument("--slug", required=True)
    p.add_argument("--add", help="Append this note (omit to list recent entries)")
    p.add_argument("--campaign", help="Optional campaign this note is about")
    p.add_argument("--kind", default="note", help="Entry tag: note | watch | budget | bid | etc.")
    p.add_argument("--limit", type=int, default=12, help="How many recent entries to list")

    p = sub.add_parser("pause")
    p.add_argument("--slug", required=True)
    p.add_argument("--resource", required=True)

    p = sub.add_parser("enable")
    p.add_argument("--slug", required=True)
    p.add_argument("--resource", required=True)

    p = sub.add_parser("set-budget")
    p.add_argument("--slug", required=True)
    p.add_argument("--campaign", required=True)
    p.add_argument("--daily-budget", type=float, required=True)

    p = sub.add_parser("set-bid-strategy")
    p.add_argument("--slug", required=True)
    p.add_argument("--campaign", required=True)
    p.add_argument("--strategy", required=True, choices=["maximize-clicks", "maximize-conversions"])
    p.add_argument("--max-cpc", type=float, help="CPC ceiling for maximize-clicks (dollars)")

    p = sub.add_parser("add-keywords")
    p.add_argument("--slug", required=True)
    p.add_argument("--ad-group", required=True)
    p.add_argument("--keywords", required=True)

    p = sub.add_parser("add-negatives")
    p.add_argument("--slug", required=True)
    p.add_argument("--campaign", required=True)
    p.add_argument("--keywords", required=True)

    p = sub.add_parser("generate-ads")
    p.add_argument("--slug", required=True)
    p.add_argument("--ad-group", required=True)
    p.add_argument("--service", required=True)
    p.add_argument("--city", required=True)
    p.add_argument("--state", default="US")

    p = sub.add_parser("keyword-research")
    p.add_argument("--slug", required=True)
    p.add_argument("--services", help="Comma-separated service slugs (default: all from plan-input.json)")
    p.add_argument("--output", help="Output CSV path (default: clients/{slug}/keyword-research-{date}.csv)")

    args = parser.parse_args()

    dispatch = {
        "auth": lambda: cmd_auth(args.slug),
        "list-accounts": lambda: cmd_list_accounts(args.slug),
        "list-campaigns": lambda: cmd_list_campaigns(args.slug),
        "scaffold": lambda: cmd_scaffold(
            args.slug, dry_run=args.dry_run,
            services_filter=[s.strip() for s in args.services.split(",")] if getattr(args, "services", None) else None,
            auto_keywords=getattr(args, "auto_keywords", False),
        ),
        "backfill-rsas": lambda: cmd_backfill_rsas(args.slug),
        "update-final-urls": lambda: cmd_update_final_urls(args.slug),
        "create-conversion": lambda: cmd_create_conversion(args.slug, args.name, args.value, args.currency),
        "angle-rsas": lambda: cmd_angle_rsas(args.slug),
        "apply-negatives": lambda: cmd_apply_negatives(args.slug),
        "report": lambda: cmd_report(args.slug, days=args.days),
        "note": lambda: cmd_note(args.slug, add=args.add, campaign=args.campaign,
                                 kind=args.kind, limit=args.limit),
        "pause": lambda: cmd_pause_or_enable(args.slug, args.resource, "pause"),
        "enable": lambda: cmd_pause_or_enable(args.slug, args.resource, "enable"),
        "set-budget": lambda: cmd_set_budget(args.slug, args.campaign, args.daily_budget),
        "set-bid-strategy": lambda: cmd_set_bid_strategy(args.slug, args.campaign, args.strategy, getattr(args, "max_cpc", None)),
        "add-keywords": lambda: cmd_add_keywords(args.slug, args.ad_group, args.keywords),
        "add-negatives": lambda: cmd_add_negatives(args.slug, args.campaign, args.keywords),
        "generate-ads": lambda: cmd_generate_ads(
            args.slug, args.ad_group, args.service, args.city,
            getattr(args, "state", "US")
        ),
        "keyword-research": lambda: cmd_keyword_research(
            args.slug,
            services=[s.strip() for s in args.services.split(",")] if getattr(args, "services", None) else None,
            output_csv=getattr(args, "output", None),
        ),
    }

    if args.cmd not in dispatch:
        parser.print_help()
        return 1

    rc = dispatch[args.cmd]()

    # Auto-log every successful change command to the client's ads journal, so the
    # record of "what we did" builds itself even when a cron (not a human) acts.
    if rc == 0 and args.cmd in CHANGE_CMDS:
        try:
            append_journal(
                args.slug, _describe_change(args), kind=args.cmd,
                campaign=getattr(args, "campaign", None) or getattr(args, "resource", None),
                author=os.environ.get("ADS_JOURNAL_AUTHOR", "auto"),
            )
        except Exception as e:  # never let journaling break a real change
            print(f"  (note: could not auto-log to ads journal: {e})")
    return rc


if __name__ == "__main__":
    sys.exit(main())
