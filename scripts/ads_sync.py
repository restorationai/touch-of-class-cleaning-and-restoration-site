#!/usr/bin/env python3
"""
Rank AI — Google Ads Sync (Reporting Pipeline)

Syncs daily performance metrics and campaign structure from Google Ads to Supabase `marketing_ads_*` tables.
Uses per-contractor OAuth tokens stored in `user_integrations` (provider = 'google_ads').

Requires:
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
- GOOGLE_OAUTH_CLIENT_ID
- GOOGLE_OAUTH_CLIENT_SECRET
- GOOGLE_ADS_DEVELOPER_TOKEN
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from supabase import create_client, Client
from google.oauth2.credentials import Credentials
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

# 1. Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# 2. Init Supabase (Service Role)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
GOOGLE_DEV_TOKEN = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")

missing_vars = []
if not SUPABASE_URL: missing_vars.append("SUPABASE_URL")
if not SUPABASE_KEY: missing_vars.append("SUPABASE_SERVICE_ROLE_KEY")
if not GOOGLE_CLIENT_ID: missing_vars.append("GOOGLE_OAUTH_CLIENT_ID")
if not GOOGLE_CLIENT_SECRET: missing_vars.append("GOOGLE_OAUTH_CLIENT_SECRET")
if not GOOGLE_DEV_TOKEN: missing_vars.append("GOOGLE_ADS_DEVELOPER_TOKEN")

if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_rank_ai_slug(company_id: str) -> str:
    """Resolve company_id to rank_ai_slug using marketing_sites table."""
    res = supabase.table("marketing_sites").select("rank_ai_slug").eq("company_id", company_id).execute()
    if res.data and "rank_ai_slug" in res.data[0]:
        return res.data[0]["rank_ai_slug"]
    return "unknown"

def mark_needs_reauth(integration_id: str):
    logger.warning(f"Marking integration {integration_id} as 'needs_reauth'")
    supabase.table("user_integrations").update({"status": "needs_reauth"}).eq("id", integration_id).execute()

def sync_structure(google_ads_client: GoogleAdsClient, customer_id: str, company_id: str, rank_ai_slug: str) -> Dict[str, str]:
    """
    Step 1: Sync Campaigns and Ad Groups first.
    Returns a mapping of resource_name -> Supabase UUID for foreign key mapping.
    """
    ga_service = google_ads_client.get_service("GoogleAdsService")
    
    mapping = {}

    # 1a. Sync Campaigns
    campaign_query = """
        SELECT
            campaign.id,
            campaign.resource_name,
            campaign.name,
            campaign.status,
            campaign.bidding_strategy_type,
            campaign_budget.amount_micros
        FROM campaign
        WHERE campaign.status != 'REMOVED'
    """
    
    try:
        campaign_response = ga_service.search(customer_id=customer_id, query=campaign_query)
        for row in campaign_response:
            campaign = row.campaign
            budget = row.campaign_budget
            
            # Upsert into Supabase
            payload = {
                "company_id": company_id,
                "rank_ai_slug": rank_ai_slug,
                "customer_id": customer_id,
                "campaign_resource_name": campaign.resource_name,
                "name": campaign.name,
                "status": campaign.status.name.lower(),
                "daily_budget": budget.amount_micros / 1_000_000 if budget else 0.0,
                "synced_at": datetime.utcnow().isoformat()
            }
            
            # Using on_conflict on the unique column 'campaign_resource_name'
            res = supabase.table("marketing_ads_campaigns").upsert(
                payload, on_conflict="campaign_resource_name"
            ).execute()
            
            if res.data:
                mapping[campaign.resource_name] = res.data[0]["id"]
                
    except GoogleAdsException as ex:
        logger.error(f"Failed to fetch campaigns for {customer_id}: {ex}")

    # 1b. Sync Ad Groups
    ad_group_query = """
        SELECT
            ad_group.id,
            ad_group.resource_name,
            ad_group.name,
            ad_group.status,
            campaign.resource_name
        FROM ad_group
        WHERE ad_group.status != 'REMOVED'
    """
    
    try:
        ag_response = ga_service.search(customer_id=customer_id, query=ad_group_query)
        for row in ag_response:
            ag = row.ad_group
            camp_resource = row.campaign.resource_name
            
            camp_uuid = mapping.get(camp_resource)
            
            payload = {
                "company_id": company_id,
                "rank_ai_slug": rank_ai_slug,
                "campaign_id": camp_uuid,
                "ad_group_resource_name": ag.resource_name,
                "name": ag.name,
                "status": ag.status.name.lower(),
                "ad_group_type": "city_skag",
                "synced_at": datetime.utcnow().isoformat()
            }
            
            res = supabase.table("marketing_ads_ad_groups").upsert(
                payload, on_conflict="ad_group_resource_name"
            ).execute()
            
            if res.data:
                mapping[ag.resource_name] = res.data[0]["id"]
                
    except GoogleAdsException as ex:
        logger.error(f"Failed to fetch ad groups for {customer_id}: {ex}")

    return mapping

def sync_metrics(google_ads_client: GoogleAdsClient, customer_id: str, company_id: str, rank_ai_slug: str, mapping: Dict[str, str]):
    """
    Step 2: Sync Daily Metrics using a Trailing 14-Day Window.
    Uses metric_key to prevent Postgres NULL traps on upsert.
    """
    ga_service = google_ads_client.get_service("GoogleAdsService")
    
    # We use a 14 day trailing window because conversions (like calls) backfill.
    query = """
        SELECT
            campaign.resource_name,
            ad_group.resource_name,
            segments.date,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value
        FROM ad_group
        WHERE segments.date DURING LAST_14_DAYS
    """
    
    try:
        response = ga_service.search(customer_id=customer_id, query=query)
        upsert_payloads = []
        
        for row in response:
            campaign_res = row.campaign.resource_name
            ag_res = row.ad_group.resource_name
            date_str = row.segments.date
            
            camp_uuid = mapping.get(campaign_res)
            ag_uuid = mapping.get(ag_res)
            
            if not camp_uuid or not ag_uuid:
                continue # Skip if structure failed to sync
            
            # Construct the unique metric_key to avoid NULL uniqueness traps
            metric_key = f"{company_id}:ad_group:{camp_uuid}:{ag_uuid}:{date_str}"
            
            payload = {
                "metric_key": metric_key,
                "company_id": company_id,
                "rank_ai_slug": rank_ai_slug,
                "scope": "ad_group",
                "campaign_id": camp_uuid,
                "ad_group_id": ag_uuid,
                "date": date_str,
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "cost": row.metrics.cost_micros / 1_000_000,
                "conversions": row.metrics.conversions,
                "conversion_value": row.metrics.conversions_value,
                "synced_at": datetime.utcnow().isoformat()
            }
            upsert_payloads.append(payload)
            
        # Add Account-Scope Rollups
        account_metrics = {}
        for row in response:
            date_str = row.segments.date
            if date_str not in account_metrics:
                account_metrics[date_str] = {
                    "impressions": 0, "clicks": 0, "cost": 0, "conversions": 0, "conversion_value": 0
                }
            account_metrics[date_str]["impressions"] += row.metrics.impressions
            account_metrics[date_str]["clicks"] += row.metrics.clicks
            account_metrics[date_str]["cost"] += row.metrics.cost_micros / 1_000_000
            account_metrics[date_str]["conversions"] += row.metrics.conversions
            account_metrics[date_str]["conversion_value"] += row.metrics.conversions_value
            
        for date_str, am in account_metrics.items():
            payload = {
                "metric_key": f"{company_id}:account:{date_str}",
                "company_id": company_id,
                "rank_ai_slug": rank_ai_slug,
                "scope": "account",
                "date": date_str,
                "impressions": am["impressions"],
                "clicks": am["clicks"],
                "cost": am["cost"],
                "conversions": am["conversions"],
                "conversion_value": am["conversion_value"],
                "synced_at": datetime.utcnow().isoformat()
            }
            upsert_payloads.append(payload)
            
        # Bulk Upsert Ad Group Metrics
        if upsert_payloads:
            supabase.table("marketing_ads_metrics").upsert(
                upsert_payloads, on_conflict="metric_key"
            ).execute()
            logger.info(f"Upserted {len(upsert_payloads)} ad_group metric rows for {customer_id}")
            
    except GoogleAdsException as ex:
        logger.error(f"Failed to fetch metrics for {customer_id}: {ex}")

def main():
    logger.info("Starting Rank AI Ads Sync Pipeline...")
    
    # 1. Get all connected Google Ads accounts. Two shapes exist:
    #    - legacy dedicated rows (provider='google_ads')
    #    - the unified Google connect (provider='google') whose metadata
    #      carries selected_ads_customer_id (Kyle/Crew3r 2026-07-26: PPC
    #      invisible in the app because only 'google_ads' rows were swept).
    #    Legacy row wins when a company has both.
    ga_rows = supabase.table("user_integrations").select("*") \
        .eq("provider", "google_ads").execute().data or []
    g_rows = supabase.table("user_integrations").select("*") \
        .eq("provider", "google").execute().data or []
    seen = {r["client_id"] for r in ga_rows}
    merged = ga_rows + [
        r for r in g_rows
        if r["client_id"] not in seen
        and (r.get("connection_metadata") or {}).get("selected_ads_customer_id")]

    if not merged:
        logger.info("No ads-connected integrations found.")
        return

    for integration in merged:
        company_id = integration["client_id"] # client_id == company_id in our architecture
        metadata = integration.get("connection_metadata", {})

        refresh_token = integration.get("refresh_token") or metadata.get("refresh_token")
        client_customer_id = metadata.get("selected_ads_customer_id")
        login_customer_id = metadata.get("login_customer_id", client_customer_id) # Default to self if no MCC saved
        
        if not refresh_token or not client_customer_id:
            logger.warning(f"Skipping {company_id}: Missing refresh_token or customer_id")
            continue
            
        logger.info(f"Processing Company: {company_id} | Target CID: {client_customer_id} | Login MCC: {login_customer_id}")
        
        try:
            # 2. Dynamic Per-Contractor Auth
            credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
                client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"]
            )
            
            google_ads_client = GoogleAdsClient(
                credentials=credentials,
                developer_token=os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
                login_customer_id=str(login_customer_id).replace("-", ""),
                use_proto_plus=True
            )
            
            rank_ai_slug = get_rank_ai_slug(company_id)
            clean_customer_id = str(client_customer_id).replace("-", "")
            
            # 3. Execute Structure Sync (Gets UUID mapping)
            uuid_mapping = sync_structure(google_ads_client, clean_customer_id, company_id, rank_ai_slug)
            
            # 4. Execute Metrics Sync (Trailing 14 Days)
            sync_metrics(google_ads_client, clean_customer_id, company_id, rank_ai_slug, uuid_mapping)
            
        except Exception as e:
            error_str = str(e).lower()
            if "invalid_grant" in error_str or "unauthenticated" in error_str or "permission_denied" in error_str or "authorizationerror" in error_str:
                mark_needs_reauth(integration["id"])
            logger.error(f"Error syncing account {company_id}: {str(e)}")
            continue

if __name__ == "__main__":
    main()
