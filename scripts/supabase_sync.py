#!/usr/bin/env python3
"""
supabase_sync.py — Sync rank-ai local JSON state to Supabase marketing_* tables.

Writes to: marketing_sites, marketing_audit_runs, marketing_audit_url_scores,
           marketing_content_items, marketing_keywords, marketing_keyword_seeds

Never touches: companies, profiles, jobs, onboarding_states, or any non-marketing_* table.

Usage:
    python3 scripts/supabase_sync.py                    # all active clients
    python3 scripts/supabase_sync.py --slug narestco    # one client
    python3 scripts/supabase_sync.py --dry-run          # print what would be synced
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# Active clients only. Churned (probritegen) excluded.
# Single source of truth: clients/company_map.json (fail-soft on missing file).
try:
    COMPANY_MAP = json.loads((ROOT / "clients" / "company_map.json").read_text())
except Exception:
    COMPANY_MAP = {}


def load_json(path: Path):
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def ts(val):
    """Return ISO string as-is, or None."""
    return val if val else None


# ---------------------------------------------------------------------------
# marketing_sites
# ---------------------------------------------------------------------------

def sync_sites(client, slug: str, company_id: str, dry_run: bool) -> None:
    rec = load_json(ROOT / "clients" / f"{slug}.json")
    if not rec:
        print(f"  [sites] SKIP — clients/{slug}.json not found")
        return

    apex_live = bool(rec.get("cut_over_at") or (rec.get("apex_cutover") or {}).get("completed_at"))

    # BUILD STATUS IS DERIVED, NOT COPIED (Santino 2026-08-10, Build Stages
    # board): the record's build_status string goes stale — Reign had three
    # staging pushes in one day while it still said "preview_ready", and
    # Life Savers said "pending" with ns_live domain access. The deploy
    # timestamps in the build block are written by sync-deploy itself, so
    # they are the truth; the stored string is only the fallback for
    # records that predate the timestamps.
    b = rec.get("build") or {}
    if apex_live or b.get("last_pushed_main_at"):
        derived_status = "pushed_main"
    elif b.get("last_pushed_staging_at"):
        derived_status = "pushed_staging"
    elif b.get("last_rendered_at"):
        derived_status = "preview_ready"
    elif b.get("scaffolded_at"):
        derived_status = "scaffolded"
    else:
        derived_status = rec.get("build_status") or "pending"

    # PREVIEW URL: the naming convention is NOT universal (Santino 2026-08-04,
    # FireDEX). Clients whose apex still runs a live legacy site never get a
    # Cloudflare zone, so their build lands on a standalone `{slug}-preview`
    # Pages project instead of `rankai-{slug}` — and this line used to
    # hardcode the convention, so every sync overwrote the real URL with a
    # host that does not resolve. Monica then texted Bob Randig a dead link
    # ("The link does not work") and the app's Site tab iframed the same
    # nothing. Three clients were wrong at once: firedex-butler,
    # mcc-restoration and prorestoration.
    # `build.preview_url` in clients/{slug}.json is the explicit override and
    # wins whenever the site is not yet on its apex — that is exactly when the
    # Pages URL is what the client and the app actually see. Once apex_live is
    # true the app renders https://{domain} and `rankai-{slug}` is the real
    # production project, so the convention stays correct there.
    preview_override = str((rec.get("build") or {}).get("preview_url") or "").strip()
    pages_url = (preview_override if preview_override and not apex_live
                 else f"https://rankai-{slug}.pages.dev")

    # marketing_sites.domain is NOT NULL. Pre-cutover records carry domain:
    # null, which aborted the whole upsert (2026-08-10: Reign's corrected
    # build_status never landed because of this). Keep whatever the existing
    # row has, else the established .invalid placeholder.
    domain = rec.get("domain")
    if not domain:
        try:
            existing = (client.table("marketing_sites").select("domain")
                        .eq("rank_ai_slug", slug).limit(1).execute().data or [])
            domain = (existing[0].get("domain") if existing else None) or f"{slug}.invalid"
        except Exception:
            domain = f"{slug}.invalid"

    row = {
        "rank_ai_slug":          slug,
        "company_id":            company_id,
        "domain":                domain,
        "apex_live":             apex_live,
        "cloudflare_pages_url":  pages_url,
        "build_status":          derived_status,
        "plan_status":           rec.get("plan_status"),
        "tier":                  rec.get("tier"),
        "cf_zone_id":            (rec.get("zone") or {}).get("id"),
        "r2_bucket":             (rec.get("r2") or {}).get("bucket"),
        "r2_public_url":         (rec.get("r2") or {}).get("public_url"),
        "github_repo":           (rec.get("build") or {}).get("github_repo"),
        "plan_template":         (rec.get("plan") or {}).get("template"),
        "plan_url_count":        (rec.get("plan") or {}).get("url_count"),
        "plan_generated_at":     ts((rec.get("plan") or {}).get("generated_at")),
        "scaffolded_at":         ts((rec.get("build") or {}).get("scaffolded_at")),
        "last_pushed_main_at":   ts((rec.get("build") or {}).get("last_pushed_main_at")),
        "apex_completed_at":     ts((rec.get("apex_cutover") or {}).get("completed_at") or rec.get("cut_over_at")),
        "legacy_origin":         (rec.get("apex_cutover") or {}).get("legacy_origin"),
        "gsc_property_url":      (rec.get("gsc") or {}).get("property_url"),
        "gsc_verified_at":       ts((rec.get("gsc") or {}).get("verified_at")),
        "gsc_sitemap_url":       (rec.get("gsc") or {}).get("sitemap_url"),
        "ads_customer_id":       (rec.get("google_ads") or {}).get("customer_id"),
        "s3_last_run_at":        ts((rec.get("audit") or {}).get("last_audit_at")),
        "s4_last_run_at":        ts((rec.get("refresh") or {}).get("last_run_at")),
        "last_audit_verdict":    (rec.get("audit") or {}).get("last_audit_verdict"),
        "updated_at":            rec.get("updated_at"),
    }

    if dry_run:
        print(f"  [sites] WOULD upsert: {slug} | apex_live={apex_live} | build_status={row['build_status']}")
        return

    client.table("marketing_sites").upsert(row, on_conflict="rank_ai_slug").execute()
    print(f"  [sites] OK — {slug}")


# ---------------------------------------------------------------------------
# marketing_audit_runs + marketing_audit_url_scores
# ---------------------------------------------------------------------------

def sync_audit(client, slug: str, company_id: str, dry_run: bool) -> None:
    audit = load_json(ROOT / "clients" / slug / "onsite-audit.json")
    if not audit:
        print(f"  [audit] SKIP — no onsite-audit.json for {slug}")
        return

    run_date = audit.get("generated_at")
    rollup = audit.get("site_rollup", {})
    avg = rollup.get("avg_scores", {})
    raw_caveats = audit.get("environment_caveats", [])
    caveats = "; ".join(c if isinstance(c, str) else json.dumps(c) for c in raw_caveats)

    audit_row = {
        "company_id":       company_id,
        "run_date":         ts(run_date),
        "lighthouse_scores": avg,
        "top_issues":       rollup.get("template_issues", []),
        "verdict":          rollup.get("verdict"),
        "live_origin":      audit.get("live_origin"),
        "url_count":        len(audit.get("audited_urls", [])),
        "caveat":           caveats or None,
    }

    if dry_run:
        print(f"  [audit] WOULD upsert run: {run_date} | verdict={audit_row['verdict']}")
        print(f"  [audit] WOULD upsert {len(audit.get('audited_urls', []))} url scores")
        return

    # Fetch existing run by (company_id, run_date) to decide insert vs update
    existing = (
        client.table("marketing_audit_runs")
        .select("id")
        .eq("company_id", company_id)
        .eq("run_date", run_date)
        .execute()
    )

    if existing.data:
        run_id = existing.data[0]["id"]
        client.table("marketing_audit_runs").update(audit_row).eq("id", run_id).execute()
    else:
        result = client.table("marketing_audit_runs").insert(audit_row).execute()
        run_id = result.data[0]["id"]

    # Replace url scores for this run
    client.table("marketing_audit_url_scores").delete().eq("audit_run_id", run_id).execute()

    score_rows = []
    for u in audit.get("audited_urls", []):
        scores = u.get("scores", {})
        score_rows.append({
            "audit_run_id": run_id,
            "company_id":   company_id,
            "url":          u["url"],
            "verdict":      u.get("verdict"),
            "perf_score":   scores.get("performance"),
            "seo_score":    scores.get("seo"),
            "a11y_score":   scores.get("accessibility"),
            "bp_score":     scores.get("best_practices"),
            "issues":       u.get("onpage_issues", []),
        })

    if score_rows:
        client.table("marketing_audit_url_scores").insert(score_rows).execute()

    print(f"  [audit] OK — {slug} | verdict={audit_row['verdict']} | {len(score_rows)} URLs")


# ---------------------------------------------------------------------------
# marketing_content_items
# ---------------------------------------------------------------------------

def _upcoming_publish_slots(n: int) -> list:
    """Projected publish datetimes: the next n Mon/Thu 16:00 UTC slots — the
    weekly-maintenance cadence at which System 2 publishes one queued post each."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    cur = now.replace(hour=16, minute=0, second=0, microsecond=0)
    slots = []
    while len(slots) < n:
        if cur > now and cur.weekday() in (0, 3):   # Mon=0, Thu=3
            slots.append(cur.isoformat())
        cur += timedelta(days=1)
    return slots


def sync_content(client, slug: str, company_id: str, dry_run: bool) -> None:
    queue = load_json(ROOT / "clients" / slug / "content-queue.json")
    if not queue:
        print(f"  [content] SKIP — no content-queue.json for {slug}")
        return

    items = queue.get("items", [])

    # Project a publish date onto each queued item (FIFO by queued_at) so the app
    # can show "Scheduled for <date>" instead of a bare "Scheduled".
    queued_sorted = sorted(
        [i for i in items if (i.get("status") or "queued") == "queued"],
        key=lambda i: i.get("queued_at") or "")
    _slots = _upcoming_publish_slots(len(queued_sorted))
    schedule_map = {i.get("suggested_slug"): _slots[idx]
                    for idx, i in enumerate(queued_sorted) if i.get("suggested_slug")}

    if dry_run:
        queued = sum(1 for i in items if i.get("status") == "queued")
        written = sum(1 for i in items if i.get("status") in ("written", "published"))
        print(f"  [content] WOULD sync {len(items)} items ({queued} queued, {written} published)")
        return

    # Fetch existing items keyed by suggested_slug, with a normalized-title
    # fallback: strategist-pin queue items carry no suggested_slug, and
    # slug-less rows matched nothing — every sync re-inserted them as
    # duplicates (and their stale "queued" originals never updated).
    existing_raw = (
        client.table("marketing_content_items")
        .select("id,suggested_slug,title")
        .eq("company_id", company_id)
        .execute()
    )
    existing = {r["suggested_slug"]: r["id"] for r in existing_raw.data
                if r.get("suggested_slug")}
    existing_by_title = {(r.get("title") or "").strip().lower(): r["id"]
                         for r in existing_raw.data if r.get("title")}

    to_insert, to_update = [], []
    for item in items:
        raw_status = item.get("status", "queued")
        # "written" in our JSON means published to the blog. The DB check
        # constraint only knows queued/published-style states: "banked" (the
        # C3 overflow reserve, 09-17) is still upcoming work -> queued, and
        # archived/other local-only states are not mirrored. Before 10-01 one
        # banked row raised marketing_content_items_status_check and aborted
        # the WHOLE sync, so the app's Content view stopped updating for
        # every client with a bank.
        if raw_status in ("written", "published"):
            status = "published"
        elif raw_status in ("queued", "banked"):
            status = "queued"
        else:
            continue

        row = {
            "company_id":       company_id,
            "type":             "blog",
            "status":           status,
            "title":            item.get("suggested_title") or item.get("primary_keyword", ""),
            "live_url":         item.get("post_url"),
            "published_at":     ts(item.get("written_at")) if status == "published" else None,
            "primary_keyword":  item.get("primary_keyword"),
            "suggested_slug":   item.get("suggested_slug"),
            "intent":           item.get("intent"),
            "search_volume":    item.get("volume"),
            "difficulty":       item.get("kd"),
            "priority":         1,
            "target_word_count": item.get("target_word_count", 1400),
            "internal_links":   item.get("internal_link_targets", []),
            "service_tags":     item.get("service_tags", []),
            "city_anchor":      item.get("city_anchor"),
            "notes":            item.get("notes"),
            "queued_at":        ts(item.get("queued_at")),
            "written_at":       ts(item.get("written_at")),
            "scheduled_for":    (schedule_map.get(item.get("suggested_slug"))
                                 if raw_status == "queued" else None),
        }

        suggested_slug = item.get("suggested_slug")
        title_key = (row["title"] or "").strip().lower()
        if suggested_slug and suggested_slug in existing:
            to_update.append((existing[suggested_slug], row))
        elif title_key in existing_by_title:
            to_update.append((existing_by_title[title_key], row))
        else:
            to_insert.append(row)

    for item_id, row in to_update:
        client.table("marketing_content_items").update(row).eq("id", item_id).execute()

    if to_insert:
        client.table("marketing_content_items").insert(to_insert).execute()

    print(f"  [content] OK — {slug} | {len(to_insert)} inserted, {len(to_update)} updated")


# ---------------------------------------------------------------------------
# marketing_keywords + marketing_keyword_seeds
# ---------------------------------------------------------------------------

def sync_keywords(client, slug: str, company_id: str, dry_run: bool) -> None:
    bank = load_json(ROOT / "clients" / slug / "keyword-bank.json")
    if not bank:
        print(f"  [keywords] SKIP — no keyword-bank.json for {slug}")
        return

    keywords = bank.get("keywords", [])
    seeds = bank.get("seeds_researched", [])

    if dry_run:
        print(f"  [keywords] WOULD upsert {len(keywords)} keywords, {len(seeds)} seeds")
        return

    # keywords — unique on (company_id, keyword, city)
    kw_rows = []
    for kw in keywords:
        kw_rows.append({
            "company_id":     company_id,
            "keyword":        kw["keyword"],
            "city":           kw.get("city_modifier"),
            "priority":       kw.get("priority", 2),
            "intent":         kw.get("intent"),
            "search_volume":  kw.get("volume"),
            "difficulty":     kw.get("kd"),
            "seed":           kw.get("fan_out_parent") or kw.get("seed"),
            "covered_by":     kw.get("covered_by"),
            "cpc":            kw.get("cpc"),
            "last_researched": ts(kw.get("discovered")),
            # NOTE: 'status' is intentionally omitted — it's operator-set in the app
            # (queue/dismiss); upsert leaves it untouched on conflict.
        })

    if kw_rows:
        # upsert in batches of 200
        for i in range(0, len(kw_rows), 200):
            batch = kw_rows[i:i+200]
            client.table("marketing_keywords").upsert(
                batch, on_conflict="company_id,keyword,city"
            ).execute()

    # seeds — unique on (company_id, seed)
    seed_rows = []
    for s in seeds:
        seed_name = s["seed"]
        count = sum(1 for kw in keywords if (kw.get("fan_out_parent") or kw.get("seed")) == seed_name)
        seed_rows.append({
            "company_id":     company_id,
            "seed":           seed_name,
            "last_researched": ts(s.get("last_researched")),
            "keyword_count":  count,
        })

    if seed_rows:
        client.table("marketing_keyword_seeds").upsert(
            seed_rows, on_conflict="company_id,seed"
        ).execute()

    print(f"  [keywords] OK — {slug} | {len(kw_rows)} keywords, {len(seed_rows)} seeds")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def sync_client(client, slug: str, dry_run: bool) -> None:
    company_id = COMPANY_MAP.get(slug)
    if not company_id:
        print(f"  ERROR: no company_id mapping for slug '{slug}'. Add it to COMPANY_MAP.")
        return

    print(f"\n--- {slug} ({company_id}) ---")
    sync_sites(client, slug, company_id, dry_run)
    sync_audit(client, slug, company_id, dry_run)
    sync_content(client, slug, company_id, dry_run)
    sync_keywords(client, slug, company_id, dry_run)


def main():
    parser = argparse.ArgumentParser(description="Sync rank-ai JSON state to Supabase")
    parser.add_argument("--slug", help="Sync a single client slug")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be synced, no writes")
    args = parser.parse_args()

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    slugs = [args.slug] if args.slug else list(COMPANY_MAP.keys())

    mode = "DRY RUN" if args.dry_run else "SYNC"
    print(f"supabase_sync — {mode} — {len(slugs)} client(s): {', '.join(slugs)}")

    for slug in slugs:
        sync_client(sb, slug, args.dry_run)

    print("\nDone.")


if __name__ == "__main__":
    main()
