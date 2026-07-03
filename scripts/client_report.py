#!/usr/bin/env python3
"""
Rank AI — Monthly Client Report Generator (v1).

Produces a self-contained HTML report per client summarizing what we did
that month, the site's current health, and what's coming next. Output
goes to clients/{slug}/reports/{YYYY-MM}-monthly.html and is suitable
for email (inlined styles, no external assets except the R2-hosted logo).

v1 sections (what we have data for today):
  1. Header + period
  2. Summary highlights
  3. Content delivered this month (blog posts written)
  4. Site health (System 3 audit verdict + top issues)
  5. Refresh activity (System 4 queue + completed actions)
  6. Coming up next month

v2 will add:
  - Search Console keyword/ranking deltas (requires GSC v2)
  - GA4 organic traffic deltas (requires GA4 integration)
  - Lighthouse score trend across multiple audits

Usage:
  python3 scripts/client_report.py preview --slug narestco
  python3 scripts/client_report.py preview --slug probritegen --period 2026-05
  python3 scripts/client_report.py send --slug narestco  # delegates to sendgrid (task #40)
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
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = ROOT / "clients"


def _load_env_file() -> None:
    """Fail-soft .env loader so Supabase/SendGrid creds work without sourcing.
    Never overrides variables already present in the environment."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


_load_env_file()


def sb_select(table: str, params: list[tuple[str, str]]) -> list | None:
    """Read rows from Supabase via PostgREST. Returns None when creds are
    missing or the request fails — callers treat None as 'no data, skip'."""
    sb = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not (sb and key):
        return None
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{sb}/rest/v1/{table}?{qs}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:  # noqa: BLE001 — report sections are best-effort
        sys.stderr.write(f"    [warn] Supabase read {table} failed: {str(e)[:120]}\n")
        return None


# ----------------------------------------------------------------------------
# Data model
# ----------------------------------------------------------------------------


@dataclass
class ReportData:
    slug: str
    display_name: str
    domain: str
    period_label: str           # e.g. "May 2026"
    period_start: datetime
    period_end: datetime
    brand: dict                 # colors, logo
    posts_this_month: list      # list of blog post metadata
    audit_latest: dict | None   # state from onsite-audit.json
    refresh_latest: dict | None # state from refresh-queue.json
    queue_depth: int            # priority-1 items in content-queue.json
    upcoming_schedule: list     # next monthly cadence dates
    # v2 data sections — each None when no data exists (section is skipped)
    geogrid: dict | None = None     # local map-pack rankings (Supabase)
    gbp: dict | None = None         # Google Business Profile stats (Supabase)
    ai_search: dict | None = None   # AI-engine citation rate (Supabase)
    ads: dict | None = None         # Google Ads last-30d totals (Ads API)


# ----------------------------------------------------------------------------
# State assembly
# ----------------------------------------------------------------------------


def load_client(slug: str) -> dict:
    path = CLIENTS_DIR / f"{slug}.json"
    if not path.exists():
        sys.stderr.write(f"ERROR: client record not found at {path}\n")
        sys.exit(1)
    return json.loads(path.read_text())


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except ValueError:
        return None


def parse_period(period: str | None) -> tuple[datetime, datetime, str]:
    """Return (start, end, label) for the period. Default to current calendar month."""
    if period:
        # Format: YYYY-MM
        try:
            d = datetime.strptime(period, "%Y-%m").replace(tzinfo=timezone.utc)
        except ValueError:
            sys.stderr.write(f"ERROR: invalid period {period!r} (expected YYYY-MM)\n")
            sys.exit(1)
    else:
        d = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start = d.replace(day=1)
    # End = first of next month
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    label = start.strftime("%B %Y")
    return start, end, label


def collect_posts_this_month(slug: str, start: datetime, end: datetime) -> list[dict]:
    """Read blog post frontmatter from sites/{slug}/src/content/blog/*.md, return those
    with published_at within [start, end)."""
    blog_dir = ROOT / "sites" / slug / "src" / "content" / "blog"
    if not blog_dir.exists():
        return []
    out = []
    for md in blog_dir.glob("*.md"):
        try:
            text = md.read_text()
        except Exception:
            continue
        fm = parse_frontmatter(text)
        pub = fm.get("published_at")
        if not pub:
            continue
        pub_dt = parse_iso(pub) or parse_iso(pub + "T00:00:00+00:00")
        if not pub_dt:
            continue
        if not (start <= pub_dt < end):
            continue
        out.append({
            "slug": md.stem,
            "title": fm.get("title", md.stem),
            "meta_description": fm.get("meta_description", ""),
            "primary_keyword": fm.get("primary_keyword", ""),
            "hero": fm.get("hero", ""),
            "published_at": pub,
            "url_path": f"/blog/{md.stem}/",
        })
    return sorted(out, key=lambda x: x["published_at"], reverse=True)


def parse_frontmatter(text: str) -> dict:
    """Naive YAML frontmatter parser — handles flat key: value lines only.
    Sufficient for the fields the report needs (title, meta_description,
    primary_keyword, hero, published_at).
    """
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm = {}
    for line in parts[1].splitlines():
        m = re.match(r'^([a-z_]+):\s*(.*)$', line.strip(), re.IGNORECASE)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        elif val.startswith("'") and val.endswith("'"):
            val = val[1:-1]
        if val == "null":
            val = None
        fm[key] = val
    return fm


def collect_state(slug: str) -> tuple[dict | None, dict | None, int]:
    """Latest onsite-audit, latest refresh-queue, content-queue depth."""
    client_dir = CLIENTS_DIR / slug
    audit_path = client_dir / "onsite-audit.json"
    refresh_path = client_dir / "refresh-queue.json"
    queue_path = client_dir / "content-queue.json"

    audit = json.loads(audit_path.read_text()) if audit_path.exists() else None
    refresh = json.loads(refresh_path.read_text()) if refresh_path.exists() else None
    queue_depth = 0
    if queue_path.exists():
        q = json.loads(queue_path.read_text())
        queue_depth = sum(1 for i in q.get("items", []) if i.get("status") == "queued")
    return audit, refresh, queue_depth


# ----------------------------------------------------------------------------
# v2 data collectors (Supabase + Google Ads) — all fail-soft, return None on
# missing creds / missing data so the report gracefully skips the section.
# ----------------------------------------------------------------------------


def resolve_company_id(slug: str, client: dict) -> str | None:
    cid = client.get("company_id")
    if cid:
        return cid
    cm_path = CLIENTS_DIR / "company_map.json"
    if cm_path.exists():
        try:
            return json.loads(cm_path.read_text()).get(slug)
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _latest_per_city_keyword(rows: list[dict]) -> dict:
    """rows must be sorted scanned_at DESC. Returns {(city, keyword): row}."""
    seen: dict = {}
    for row in rows:
        k = (row.get("city_label"), row.get("keyword"))
        if k not in seen:
            seen[k] = row
    return seen


def collect_geogrid(company_id: str | None, start: datetime, end: datetime) -> dict | None:
    """Latest geo-grid scan per city×keyword (as of period end) + MoM delta vs
    the latest prior-month scan. Returns None when there's nothing to show."""
    if not company_id:
        return None
    rows = sb_select("marketing_geogrid_scans", [
        ("company_id", f"eq.{company_id}"),
        ("select", "keyword,city_label,avg_rank,pct_in_top3,found_points,total_points,scanned_at"),
        ("order", "scanned_at.desc"),
        ("limit", "1000"),
    ])
    if not rows:
        return None
    for row in rows:
        row["_dt"] = parse_iso(row.get("scanned_at"))
    rows = [row for row in rows if row["_dt"]]

    prev_start = (start - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    current = _latest_per_city_keyword([row for row in rows if row["_dt"] < end])
    prior = _latest_per_city_keyword([row for row in rows if prev_start <= row["_dt"] < start])
    if not current:
        return None

    cities: dict[str, list[dict]] = {}
    for (city, _kw), row in current.items():
        cities.setdefault(city, []).append(row)

    out_cities = []
    for city, rs in sorted(cities.items()):
        ranked = [x for x in rs if x.get("avg_rank") is not None]
        best = min(ranked, key=lambda x: x["avg_rank"]) if ranked else None
        top3 = sum((x.get("pct_in_top3") or 0) for x in rs) / len(rs)
        prior_rs = [prior.get((city, x["keyword"])) for x in rs]
        prior_rs = [p for p in prior_rs if p]
        prior_top3 = (sum((p.get("pct_in_top3") or 0) for p in prior_rs) / len(prior_rs)) if prior_rs else None
        out_cities.append({
            "city": city,
            "keywords_tracked": len(rs),
            "best_keyword": best["keyword"] if best else "",
            "best_avg_rank": best["avg_rank"] if best else None,
            "best_top3": (best.get("pct_in_top3") or 0) if best else None,
            "top3": round(top3, 1),
            "prior_top3": round(prior_top3, 1) if prior_top3 is not None else None,
            "top3_delta": round(top3 - prior_top3, 1) if prior_top3 is not None else None,
            "scanned_at": max(x["scanned_at"] for x in rs)[:10],
        })

    cur_vals = [row.get("pct_in_top3") or 0 for row in current.values()]
    overall_cur = round(sum(cur_vals) / len(cur_vals), 1)
    overall_prior = None
    if prior:
        pv = [row.get("pct_in_top3") or 0 for row in prior.values()]
        overall_prior = round(sum(pv) / len(pv), 1)
    return {
        "cities": out_cities,
        "overall_top3": overall_cur,
        "prior_overall_top3": overall_prior,
        "latest_scan_date": max(row["scanned_at"] for row in current.values())[:10],
    }


def collect_gbp(company_id: str | None, start: datetime, end: datetime) -> dict | None:
    """GBP profile snapshot (rating, reviews) + this-month vs prior-month daily
    totals (calls, website clicks)."""
    if not company_id:
        return None
    profiles = sb_select("marketing_gbp_profiles", [
        ("company_id", f"eq.{company_id}"),
        ("select", "title,rating,review_count,primary_category,synced_at"),
        ("limit", "1"),
    ])
    prev_start = (start - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    daily = sb_select("marketing_gbp_daily", [
        ("company_id", f"eq.{company_id}"),
        ("select", "date,call_clicks,website_clicks"),
        ("date", f"gte.{prev_start.strftime('%Y-%m-%d')}"),
        ("date", f"lt.{end.strftime('%Y-%m-%d')}"),
        ("order", "date.asc"),
        ("limit", "1000"),
    ])
    profile = profiles[0] if profiles else None
    this_month = [d for d in (daily or []) if d["date"] >= start.strftime("%Y-%m-%d")]
    prior_month = [d for d in (daily or []) if d["date"] < start.strftime("%Y-%m-%d")]
    if not profile and not this_month and not prior_month:
        return None

    def _tot(rows: list[dict], col: str) -> int:
        return sum(int(x.get(col) or 0) for x in rows)

    return {
        "title": (profile or {}).get("title", ""),
        "rating": (profile or {}).get("rating"),
        "review_count": (profile or {}).get("review_count"),
        "calls": _tot(this_month, "call_clicks"),
        "web_clicks": _tot(this_month, "website_clicks"),
        "days": len(this_month),
        "prior_calls": _tot(prior_month, "call_clicks") if prior_month else None,
        "prior_web_clicks": _tot(prior_month, "website_clicks") if prior_month else None,
        "prior_days": len(prior_month),
    }


def collect_ai_search(company_id: str | None, start: datetime, end: datetime) -> dict | None:
    """AI-engine citation rate for the period (cited/total by engine) + up to 3
    example queries where the client WAS cited."""
    if not company_id:
        return None
    rows = sb_select("marketing_ai_search_scans", [
        ("company_id", f"eq.{company_id}"),
        ("select", "engine,query,cited,scanned_at"),
        ("scanned_at", f"gte.{start.isoformat()}"),
        ("scanned_at", f"lt.{end.isoformat()}"),
        ("order", "scanned_at.desc"),
        ("limit", "2000"),
    ])
    if not rows:
        return None

    engines: dict[str, dict] = {}
    for row in rows:
        e = engines.setdefault(row.get("engine") or "unknown", {"total": 0, "cited": 0})
        e["total"] += 1
        e["cited"] += 1 if row.get("cited") else 0
    engine_rows = [
        {"engine": name, "total": v["total"], "cited": v["cited"],
         "rate": round(100.0 * v["cited"] / v["total"], 1) if v["total"] else 0.0}
        for name, v in sorted(engines.items())
    ]

    # Example queries where the client WAS cited (this period first; fall back
    # to the most recent citations on record so the section still shows proof).
    def _dedup_queries(rs: list[dict]) -> list[dict]:
        out, seen = [], set()
        for row in rs:
            key = (row.get("query") or "").strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append({"query": row["query"], "engine": row.get("engine", "")})
            if len(out) >= 3:
                break
        return out

    examples = _dedup_queries([row for row in rows if row.get("cited")])
    examples_from_prior = False
    if not examples:
        older = sb_select("marketing_ai_search_scans", [
            ("company_id", f"eq.{company_id}"),
            ("select", "engine,query,scanned_at"),
            ("cited", "eq.true"),
            ("order", "scanned_at.desc"),
            ("limit", "25"),
        ])
        if older:
            examples = _dedup_queries(older)
            examples_from_prior = bool(examples)

    total = sum(e["total"] for e in engine_rows)
    cited = sum(e["cited"] for e in engine_rows)
    return {
        "engines": engine_rows,
        "total": total,
        "cited": cited,
        "rate": round(100.0 * cited / total, 1) if total else 0.0,
        "examples": examples,
        "examples_from_prior": examples_from_prior,
    }


def collect_ads(slug: str, client: dict) -> dict | None:
    """Last-30d Google Ads totals via the same data path scripts/ads_dashboard.py
    uses (ads_manager as a library). Only for clients with linked campaigns;
    returns None on any failure (no ads section rather than a broken report)."""
    gads = client.get("google_ads") or {}
    if not gads.get("customer_id"):
        return None
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import ads_manager as am  # noqa: PLC0415 — heavy import, only when needed
        ads_client = am.build_ads_client(slug, login_as_mcc=True)
        cid = am.get_customer_id(am.load_client(slug), slug)
        campaigns = []
        for r in am.gaql(ads_client, cid, """
            SELECT campaign.name, campaign.status, metrics.cost_micros, metrics.clicks,
              metrics.impressions, metrics.conversions
            FROM campaign WHERE segments.date DURING LAST_30_DAYS
              AND campaign.advertising_channel_type IN ('SEARCH','LOCAL_SERVICES')
            ORDER BY metrics.cost_micros DESC"""):
            c, m = r.campaign, r.metrics
            campaigns.append({
                "name": c.name, "status": c.status.name,
                "cost": m.cost_micros / 1e6, "clicks": m.clicks,
                "impr": m.impressions, "conv": round(m.conversions, 1),
            })
        if not campaigns:
            return None
        return {
            "window": "last 30 days",
            "customer_id": cid,
            "campaigns": campaigns,
            "spend": round(sum(c["cost"] for c in campaigns), 2),
            "clicks": sum(c["clicks"] for c in campaigns),
            "impr": sum(c["impr"] for c in campaigns),
            "conv": round(sum(c["conv"] for c in campaigns), 1),
        }
    except Exception as e:  # noqa: BLE001 — ads section is best-effort
        sys.stderr.write(f"    [warn] Ads section skipped for {slug}: {str(e)[:140]}\n")
        return None


def build_report_data(slug: str, period: str | None) -> ReportData:
    client = load_client(slug)
    start, end, label = parse_period(period)

    # Guard: reports are meant to be generated at month end. Running for the
    # CURRENT month before the 25th means the numbers below are partial.
    now = datetime.now(timezone.utc)
    if start <= now < end and now.day < 25:
        sys.stderr.write(
            f"WARNING: generating the {label} report on {now.strftime('%Y-%m-%d')} — "
            f"this is the CURRENT month and it's before the 25th, so all monthly "
            f"numbers are PARTIAL. Monthly reports should be generated at month end.\n"
        )

    posts = collect_posts_this_month(slug, start, end)
    audit, refresh, queue_depth = collect_state(slug)
    company_id = resolve_company_id(slug, client)
    return ReportData(
        slug=slug,
        display_name=client.get("display_name", slug),
        domain=client.get("domain", ""),
        period_label=label,
        period_start=start,
        period_end=end,
        brand=client.get("brand", {}),
        posts_this_month=posts,
        audit_latest=audit,
        refresh_latest=refresh,
        queue_depth=queue_depth,
        upcoming_schedule=[
            (start.replace(month=start.month + 1 if start.month < 12 else 1), "System 1 keyword research"),
            (start.replace(month=start.month + 1 if start.month < 12 else 1) + timedelta(days=4), "System 3 onsite audit"),
            (start.replace(month=start.month + 1 if start.month < 12 else 1) + timedelta(days=6), "System 4 refresh recommender"),
        ],
        geogrid=collect_geogrid(company_id, start, end),
        gbp=collect_gbp(company_id, start, end),
        ai_search=collect_ai_search(company_id, start, end),
        ads=collect_ads(slug, client),
    )


# ----------------------------------------------------------------------------
# HTML rendering
# ----------------------------------------------------------------------------


def html_escape(s: str | None) -> str:
    if s is None:
        return ""
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
              .replace('"', "&quot;").replace("'", "&#39;"))


def verdict_badge(verdict: str) -> str:
    color = {"green": "#16a34a", "amber": "#f59e0b", "red": "#dc2626", "error": "#6b7280"}.get(verdict, "#6b7280")
    label = verdict.upper() if verdict else "N/A"
    return f'<span style="display:inline-block;padding:4px 12px;border-radius:4px;background:{color};color:#fff;font-weight:700;font-size:12px;letter-spacing:0.05em;">{label}</span>'


def render_html(r: ReportData) -> str:
    primary = r.brand.get("colors", {}).get("primary", "#1E5AD4") if isinstance(r.brand.get("colors"), dict) else r.brand.get("primary_color", "#1E5AD4")
    dark = r.brand.get("colors", {}).get("navy") or r.brand.get("primary_dark", "#0D1B3E") if isinstance(r.brand.get("colors"), dict) else r.brand.get("primary_dark", "#0D1B3E")
    accent = r.brand.get("colors", {}).get("accent") or r.brand.get("accent_color", "#F97316") if isinstance(r.brand.get("colors"), dict) else r.brand.get("accent_color", "#F97316")

    # Summary highlights
    audit_verdict = r.audit_latest.get("site_rollup", {}).get("verdict") if r.audit_latest else None
    audit_avg = r.audit_latest.get("site_rollup", {}).get("avg_scores") if r.audit_latest else {}
    refresh_actions = r.refresh_latest.get("totals", {}).get("total_actions", 0) if r.refresh_latest else 0

    # Posts section
    if r.posts_this_month:
        posts_html = "".join(
            f'''
            <tr><td style="padding:20px;border-bottom:1px solid #e5e7eb;">
              <a href="https://{r.domain}{p["url_path"]}" style="color:{primary};text-decoration:none;font-weight:700;font-size:18px;">{html_escape(p["title"])}</a>
              <div style="margin-top:6px;font-size:13px;color:#6b7280;font-family:ui-monospace,monospace;">{r.domain}{p["url_path"]}</div>
              <p style="margin:10px 0 0;color:#374151;font-size:14px;line-height:1.6;">{html_escape(p["meta_description"])}</p>
              <div style="margin-top:8px;font-size:12px;color:#9ca3af;">Target keyword: <span style="color:#6b7280;">{html_escape(p["primary_keyword"])}</span></div>
            </td></tr>
            ''' for p in r.posts_this_month
        )
    else:
        posts_html = '<tr><td style="padding:30px;color:#6b7280;text-align:center;font-style:italic;">No new blog posts published in this period.</td></tr>'

    # Audit section
    if r.audit_latest:
        rollup = r.audit_latest.get("site_rollup", {})
        avg = rollup.get("avg_scores", {})
        money_alerts = rollup.get("money_page_alerts", [])
        template_issues = rollup.get("template_issues", [])
        audit_html = f'''
        <table style="width:100%;border-collapse:collapse;margin-top:12px;">
          <tr>
            <th style="text-align:left;padding:8px 12px;background:#f9fafb;font-weight:700;font-size:12px;color:#6b7280;letter-spacing:0.05em;border-bottom:1px solid #e5e7eb;">METRIC</th>
            <th style="text-align:right;padding:8px 12px;background:#f9fafb;font-weight:700;font-size:12px;color:#6b7280;letter-spacing:0.05em;border-bottom:1px solid #e5e7eb;">SCORE</th>
          </tr>
          <tr><td style="padding:10px 12px;border-bottom:1px solid #f3f4f6;">Performance</td><td style="padding:10px 12px;border-bottom:1px solid #f3f4f6;text-align:right;font-family:ui-monospace,monospace;font-weight:700;">{avg.get("performance", "—")}</td></tr>
          <tr><td style="padding:10px 12px;border-bottom:1px solid #f3f4f6;">Accessibility</td><td style="padding:10px 12px;border-bottom:1px solid #f3f4f6;text-align:right;font-family:ui-monospace,monospace;font-weight:700;">{avg.get("accessibility", "—")}</td></tr>
          <tr><td style="padding:10px 12px;border-bottom:1px solid #f3f4f6;">Best Practices</td><td style="padding:10px 12px;border-bottom:1px solid #f3f4f6;text-align:right;font-family:ui-monospace,monospace;font-weight:700;">{avg.get("best_practices", "—")}</td></tr>
          <tr><td style="padding:10px 12px;">SEO</td><td style="padding:10px 12px;text-align:right;font-family:ui-monospace,monospace;font-weight:700;">{avg.get("seo", "—")}</td></tr>
        </table>
        '''
        if template_issues:
            audit_html += '<h4 style="margin:24px 0 8px;color:' + dark + ';font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;">Template Issues</h4><ul style="margin:0;padding-left:20px;color:#374151;font-size:14px;line-height:1.7;">'
            for ti in template_issues[:3]:
                audit_html += f'<li><strong>{html_escape(ti.get("id", ""))}</strong> — affects {ti.get("affected_urls", "?")} pages. {html_escape(ti.get("title", ""))}</li>'
            audit_html += '</ul>'
        if money_alerts:
            audit_html += '<h4 style="margin:24px 0 8px;color:' + dark + ';font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;">Money Page Alerts</h4><ul style="margin:0;padding-left:20px;color:#374151;font-size:14px;line-height:1.7;">'
            for ma in money_alerts[:5]:
                short_url = ma["url"].replace(f"https://{r.domain}", "")
                audit_html += f'<li><code style="font-family:ui-monospace,monospace;color:#374151;">{html_escape(short_url)}</code> — {html_escape(ma.get("main_issue", ""))}</li>'
            audit_html += '</ul>'
    else:
        audit_html = '<p style="color:#6b7280;font-style:italic;">No audit data yet — System 3 has not been run for this client.</p>'

    # Refresh activity
    if r.refresh_latest and r.refresh_latest.get("totals", {}).get("total_actions", 0) > 0:
        items = r.refresh_latest.get("items", [])
        refresh_html = '<ul style="margin:0;padding-left:20px;color:#374151;font-size:14px;line-height:1.7;">'
        for it in items[:5]:
            short_url = it["url"].replace(f"https://{r.domain}", "")
            refresh_html += f'<li><strong>{html_escape(it.get("action", ""))}</strong> — <code style="font-family:ui-monospace,monospace;">{html_escape(short_url)}</code>: {html_escape(it.get("recommendation", "")[:200])}</li>'
        refresh_html += '</ul>'
    else:
        refresh_html = '<p style="color:#6b7280;font-style:italic;">No refresh actions surfaced this month — content remains within freshness threshold.</p>'

    # Coming up
    coming_html = '<ul style="margin:0;padding-left:20px;color:#374151;font-size:14px;line-height:1.7;">'
    for date, label in r.upcoming_schedule:
        coming_html += f'<li><strong>{date.strftime("%b %-d, %Y")}</strong> — {html_escape(label)}</li>'
    coming_html += f'<li><strong>Content queue</strong> — {r.queue_depth} priority-1 topic(s) ready to write next</li>'
    coming_html += '</ul>'

    posts_count = len(r.posts_this_month)

    # ---- Table style helpers (match existing inlined style) ----
    TH = ('style="text-align:left;padding:8px 12px;background:#f9fafb;font-weight:700;'
          'font-size:12px;color:#6b7280;letter-spacing:0.05em;border-bottom:1px solid #e5e7eb;"')
    THR = TH.replace("text-align:left", "text-align:right")
    TD = 'style="padding:10px 12px;border-bottom:1px solid #f3f4f6;"'
    TDR = ('style="padding:10px 12px;border-bottom:1px solid #f3f4f6;text-align:right;'
           'font-family:ui-monospace,monospace;font-weight:700;"')

    def delta_span(delta: float | None, unit: str = " pts", better_up: bool = True) -> str:
        if delta is None:
            return '<span style="color:#9ca3af;">—</span>'
        good = (delta > 0) if better_up else (delta < 0)
        color = "#16a34a" if good else ("#6b7280" if delta == 0 else "#dc2626")
        arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "•")
        return f'<span style="color:{color};font-weight:700;">{arrow} {delta:+.1f}{unit}</span>'

    # ---- Section 2 (v2): Local map rankings (geo-grid) ----
    geogrid_section = None
    if r.geogrid and r.geogrid.get("cities"):
        gg = r.geogrid
        rows_html = ""
        for c in gg["cities"]:
            best_rank = f'#{c["best_avg_rank"]:.1f}' if c.get("best_avg_rank") is not None else "—"
            rows_html += (
                f'<tr><td {TD}><strong>{html_escape(c["city"])}</strong>'
                f'<div style="font-size:11px;color:#9ca3af;">{c["keywords_tracked"]} keywords · scanned {c["scanned_at"]}</div></td>'
                f'<td {TD}>{html_escape(c["best_keyword"])}</td>'
                f'<td {TDR}>{best_rank}</td>'
                f'<td {TDR}>{c["top3"]:.1f}%</td>'
                f'<td {TDR}>{delta_span(c.get("top3_delta"))}</td></tr>'
            )
        overall_html = ""
        if gg.get("prior_overall_top3") is not None:
            overall_html = (
                f'<p style="margin-top:14px;color:#374151;font-size:14px;line-height:1.7;">'
                f'Across every tracked keyword and city, your top-3 map coverage moved from '
                f'<strong>{gg["prior_overall_top3"]:.1f}%</strong> last month to '
                f'<strong>{gg["overall_top3"]:.1f}%</strong> this period '
                f'({delta_span(round(gg["overall_top3"] - gg["prior_overall_top3"], 1))}).</p>'
            )
        geogrid_section = (
            "Local Map Rankings (Geo-Grid)",
            "Where your business ranks in the Google Maps pack across your service area, "
            "measured on a mile-by-mile grid. “Top-3 coverage” is the share of grid "
            "points where you appear in the map pack's top 3.",
            f'''<table style="width:100%;border-collapse:collapse;margin-top:12px;">
          <tr><th {TH}>CITY</th><th {TH}>BEST KEYWORD</th><th {THR}>AVG RANK</th><th {THR}>TOP-3 COVERAGE</th><th {THR}>VS LAST MONTH</th></tr>
          {rows_html}
        </table>{overall_html}'''
        )

    # ---- Section (v2): Google Business Profile ----
    gbp_section = None
    if r.gbp:
        g = r.gbp
        rating_html = ""
        if g.get("rating") is not None:
            rating_html = (
                f'<p style="color:#374151;font-size:14px;line-height:1.7;margin-top:8px;">'
                f'Your profile currently holds a <strong>{g["rating"]}★</strong> rating across '
                f'<strong>{g.get("review_count", "?")}</strong> reviews.</p>'
            )
        def _gbp_row(label: str, cur: int, prior: int | None) -> str:
            d = delta_span(float(cur - prior), unit="", better_up=True) if prior is not None else '<span style="color:#9ca3af;">—</span>'
            prior_txt = prior if prior is not None else "—"
            return (f'<tr><td {TD}>{label}</td><td {TDR}>{cur}</td>'
                    f'<td {TDR}>{prior_txt}</td><td {TDR}>{d}</td></tr>')
        gbp_table = (
            f'<table style="width:100%;border-collapse:collapse;margin-top:12px;">'
            f'<tr><th {TH}>PROFILE ACTION</th><th {THR}>THIS PERIOD</th><th {THR}>PRIOR MONTH</th><th {THR}>CHANGE</th></tr>'
            + _gbp_row("Phone calls from profile", g["calls"], g.get("prior_calls"))
            + _gbp_row("Website clicks from profile", g["web_clicks"], g.get("prior_web_clicks"))
            + '</table>'
        )
        days_note = ""
        if g.get("days") and g.get("prior_days") and g["days"] < g["prior_days"]:
            days_note = (f'<p style="margin-top:10px;font-size:12px;color:#9ca3af;">This period covers '
                         f'{g["days"]} day(s) of data so far vs {g["prior_days"]} days last month.</p>')
        gbp_section = (
            "Google Business Profile",
            "How your Google Business Profile (the Maps listing) performed: direct calls and "
            "website visits generated from the listing itself.",
            rating_html + gbp_table + days_note,
        )

    # ---- Section (v2): AI search visibility ----
    ai_section = None
    if r.ai_search:
        a = r.ai_search
        engine_rows = "".join(
            f'<tr><td {TD}>{html_escape(e["engine"])}</td><td {TDR}>{e["total"]}</td>'
            f'<td {TDR}>{e["cited"]}</td><td {TDR}>{e["rate"]:.1f}%</td></tr>'
            for e in a["engines"]
        )
        examples_html = ""
        if a.get("examples"):
            hdr = ("Queries where AI engines cited your business"
                   + (" (from recent scans)" if a.get("examples_from_prior") else " this period"))
            examples_html = (
                f'<h4 style="margin:24px 0 8px;color:{dark};font-size:14px;font-weight:700;'
                f'text-transform:uppercase;letter-spacing:0.05em;">{hdr}</h4>'
                '<ul style="margin:0;padding-left:20px;color:#374151;font-size:14px;line-height:1.7;">'
                + "".join(
                    f'<li>&ldquo;{html_escape(x["query"])}&rdquo; '
                    f'<span style="color:#9ca3af;font-size:12px;">({html_escape(x["engine"])})</span></li>'
                    for x in a["examples"]
                ) + '</ul>'
            )
        ai_section = (
            "AI Search Visibility",
            f'We test whether ChatGPT, Gemini, Perplexity, and Google AI recommend your business '
            f'when buyers ask for help. This period: cited in <strong>{a["cited"]} of {a["total"]}</strong> '
            f'test queries ({a["rate"]:.1f}%).',
            f'''<table style="width:100%;border-collapse:collapse;margin-top:12px;">
          <tr><th {TH}>ENGINE</th><th {THR}>QUERIES TESTED</th><th {THR}>CITED</th><th {THR}>CITATION RATE</th></tr>
          {engine_rows}
        </table>{examples_html}'''
        )

    # ---- Section (v2): Google Ads (only when campaigns exist) ----
    ads_section = None
    if r.ads:
        ad = r.ads
        cpc = f'${ad["spend"] / ad["clicks"]:.2f}' if ad["clicks"] else "—"
        cpa = f'${ad["spend"] / ad["conv"]:,.0f}' if ad["conv"] else "—"
        camp_rows = "".join(
            f'<tr><td {TD}>{html_escape(c["name"])}'
            f'<div style="font-size:11px;color:#9ca3af;">{c["status"]}</div></td>'
            f'<td {TDR}>${c["cost"]:,.0f}</td><td {TDR}>{c["clicks"]:,}</td>'
            f'<td {TDR}>{c["conv"]}</td></tr>'
            for c in ad["campaigns"][:6]
        )
        ads_section = (
            "Google Ads",
            f'Paid search totals for the {html_escape(ad["window"])} '
            f'(Google Ads account {html_escape(str(ad["customer_id"]))}).',
            f'''<table style="width:100%;border-collapse:collapse;margin-top:12px;">
          <tr><th {TH}>METRIC</th><th {THR}>VALUE</th></tr>
          <tr><td {TD}>Spend</td><td {TDR}>${ad["spend"]:,.2f}</td></tr>
          <tr><td {TD}>Clicks</td><td {TDR}>{ad["clicks"]:,}</td></tr>
          <tr><td {TD}>Impressions</td><td {TDR}>{ad["impr"]:,}</td></tr>
          <tr><td {TD}>Calls / conversions</td><td {TDR}>{ad["conv"]}</td></tr>
          <tr><td {TD}>Avg. cost per click</td><td {TDR}>{cpc}</td></tr>
          <tr><td {TD}>Cost per conversion</td><td {TDR}>{cpa}</td></tr>
        </table>
        <table style="width:100%;border-collapse:collapse;margin-top:20px;">
          <tr><th {TH}>CAMPAIGN</th><th {THR}>SPEND</th><th {THR}>CLICKS</th><th {THR}>CONV</th></tr>
          {camp_rows}
        </table>'''
        )

    # ---- Assemble all sections in order with dynamic numbering ----
    ordered = [
        ("Content Delivered",
         f'Below is the SEO content we wrote, published, and indexed on your site in {html_escape(r.period_label)}.',
         f'<table style="width:100%;border-collapse:collapse;margin-top:16px;">{posts_html}</table>'),
    ]
    for opt in (geogrid_section, gbp_section, ai_section, ads_section):
        if opt:
            ordered.append(opt)
    ordered.extend([
        (f'Site Health &nbsp; {verdict_badge(audit_verdict)}',
         "Monthly technical audit of your site's core SEO health (performance, accessibility, on-page signals).",
         audit_html),
        ("Content Refresh Activity",
         "Existing pages we identified as needing refresh, fix, or re-indexing.",
         refresh_html),
        ("Coming Up Next Month",
         "Scheduled work + the queue we're drawing from to write next.",
         coming_html),
    ])
    sections_html = "\n".join(
        f'''
    <section>
      <div class="eyebrow">Section {i}</div>
      <h2>{title}</h2>
      <p>{intro}</p>
      {body}
    </section>''' for i, (title, intro, body) in enumerate(ordered, 1)
    )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{html_escape(r.display_name)} — Monthly Report — {html_escape(r.period_label)}</title>
  <style>
    body {{ margin:0; padding:0; background:#f3f4f6; font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif; color:#111827; }}
    .container {{ max-width:680px; margin:0 auto; background:#fff; }}
    .header {{ background:{dark}; color:#fff; padding:48px 32px; }}
    .header h1 {{ margin:0; font-size:32px; font-weight:900; text-transform:uppercase; letter-spacing:-0.02em; line-height:1; }}
    .header .period {{ margin-top:12px; font-size:14px; opacity:0.7; text-transform:uppercase; letter-spacing:0.1em; }}
    .header .domain {{ margin-top:6px; font-size:14px; color:{primary}; font-family:ui-monospace,monospace; }}
    .summary {{ background:{primary}; color:#fff; padding:32px;display:flex; gap:24px; flex-wrap:wrap;justify-content:space-around; }}
    .summary-stat {{ text-align:center; }}
    .summary-stat .num {{ font-size:36px; font-weight:900; line-height:1; }}
    .summary-stat .label {{ font-size:11px; opacity:0.9; text-transform:uppercase; letter-spacing:0.1em; margin-top:6px; }}
    section {{ padding:36px 32px; border-bottom:1px solid #e5e7eb; }}
    section h2 {{ margin:0 0 4px; font-size:20px; font-weight:900; text-transform:uppercase; letter-spacing:-0.01em; color:{dark}; }}
    section .eyebrow {{ font-size:11px; color:{primary}; text-transform:uppercase; letter-spacing:0.1em; font-weight:700; margin-bottom:6px; }}
    section p {{ color:#374151; font-size:14px; line-height:1.7; }}
    .footer {{ padding:24px 32px; font-size:12px; color:#6b7280; background:#f9fafb; }}
    a {{ color:{primary}; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="period">{html_escape(r.period_label)} Report</div>
      <h1>{html_escape(r.display_name)}</h1>
      <div class="domain">{html_escape(r.domain)}</div>
    </div>

    <div class="summary">
      <div class="summary-stat">
        <div class="num">{posts_count}</div>
        <div class="label">New Blog Posts</div>
      </div>
      <div class="summary-stat">
        <div class="num">{audit_avg.get("performance", "—")}</div>
        <div class="label">Performance Score</div>
      </div>
      <div class="summary-stat">
        <div class="num">{refresh_actions}</div>
        <div class="label">Refresh Actions</div>
      </div>
      <div class="summary-stat">
        <div class="num">{r.queue_depth}</div>
        <div class="label">In Pipeline</div>
      </div>
    </div>

{sections_html}

    <div class="footer">
      Generated {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")} by Rank AI. Questions? Reply to this email.
    </div>
  </div>
</body>
</html>
'''


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


def _avg_lighthouse(r: ReportData) -> int | None:
    s = (r.audit_latest or {}).get("site_rollup", {}).get("avg_scores", {}) or {}
    vals = [s.get(k) for k in ("performance", "accessibility", "best_practices", "seo")
            if isinstance(s.get(k), (int, float))]
    return round(sum(vals) / len(vals)) if vals else None


def _videos_in_period(slug: str, start: datetime, end: datetime) -> int:
    bdir = CLIENTS_DIR.parent / "sites" / slug / "src" / "content" / "blog"
    if not bdir.exists():
        return 0
    n = 0
    for md in bdir.glob("*.md"):
        t = md.read_text()
        yid = re.search(r'youtube_id:\s*"?([A-Za-z0-9_-]{6,})"?', t)
        pub = re.search(r'published_at:\s*"?(\d{4}-\d{2}-\d{2})', t)
        if yid and yid.group(1) and pub:
            d = datetime.fromisoformat(pub.group(1)).replace(tzinfo=timezone.utc)
            if start <= d <= end:
                n += 1
    return n


def cmd_publish(args) -> int:
    """Render the monthly report AND upsert it (metrics + full HTML) to Supabase
    marketing_reports, so the app's Reports tab shows real data and 'View' opens it."""
    import os
    import requests
    sb = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not (sb and key):
        sys.stderr.write("ERROR: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required.\n")
        return 1
    if args.all:
        slugs = list(json.loads((CLIENTS_DIR / "company_map.json").read_text()).keys())
    else:
        slugs = [args.slug]
    rc = 0
    for slug in slugs:
        try:
            client = load_client(slug)
            cid = client.get("company_id")
            if not cid:
                print(f"  {slug}: skip (no company_id)")
                continue
            r = build_report_data(slug, args.period)
            html = render_html(r)
            # keep the file artifact too (parity with preview)
            out_dir = CLIENTS_DIR / slug / "reports"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{r.period_start.strftime('%Y-%m')}-monthly.html").write_text(html)
            row = {
                "company_id": cid, "report_month": r.period_label,
                "posts_published": len(r.posts_this_month),
                "videos_created": _videos_in_period(slug, r.period_start, r.period_end),
                "avg_lighthouse_score": _avg_lighthouse(r),
                "status": "completed", "report_html": html,  # CHECK: draft|completed
            }
            resp = requests.post(
                f"{sb}/rest/v1/marketing_reports?on_conflict=company_id,report_month",
                headers={"apikey": key, "Authorization": f"Bearer {key}",
                         "Content-Type": "application/json",
                         "Prefer": "resolution=merge-duplicates,return=minimal"},
                data=json.dumps([row]))
            resp.raise_for_status()
            print(f"  {slug}: published {r.period_label} — {row['posts_published']} posts, "
                  f"{row['videos_created']} videos, lighthouse {row['avg_lighthouse_score']}")
        except Exception as e:
            rc = 1
            print(f"  {slug}: ERROR ({type(e).__name__}: {str(e)[:160]})")
    return rc


def cmd_preview(args) -> int:
    r = build_report_data(args.slug, args.period)
    html = render_html(r)
    out_dir = CLIENTS_DIR / args.slug / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{r.period_start.strftime('%Y-%m')}-monthly.html"
    out_path.write_text(html)
    print(f"==> Wrote {out_path}")
    print(f"    Open in browser:  file://{out_path}")
    print(f"    Period:           {r.period_label}")
    print(f"    Posts this month: {len(r.posts_this_month)}")
    print(f"    Audit verdict:    {r.audit_latest.get('site_rollup', {}).get('verdict') if r.audit_latest else 'n/a'}")
    print(f"    Refresh actions:  {r.refresh_latest.get('totals', {}).get('total_actions', 0) if r.refresh_latest else 0}")
    if r.geogrid:
        gg = r.geogrid
        prior = f" (prior month {gg['prior_overall_top3']}%)" if gg.get("prior_overall_top3") is not None else ""
        print(f"    Geo-grid:         top-3 coverage {gg['overall_top3']}%{prior} — latest scan {gg['latest_scan_date']}")
        for c in gg["cities"]:
            d = f"  MoM {c['top3_delta']:+.1f} pts" if c.get("top3_delta") is not None else ""
            rank = f"#{c['best_avg_rank']:.1f}" if c.get("best_avg_rank") is not None else "—"
            print(f"      {c['city']}: best '{c['best_keyword']}' avg rank {rank}, top-3 {c['top3']}%{d}")
    else:
        print(f"    Geo-grid:         no data (section skipped)")
    if r.gbp:
        g = r.gbp
        print(f"    GBP:              {g.get('rating', '—')}★ / {g.get('review_count', '—')} reviews · "
              f"calls {g['calls']} (prior {g.get('prior_calls', '—')}) · "
              f"web clicks {g['web_clicks']} (prior {g.get('prior_web_clicks', '—')})")
    else:
        print(f"    GBP:              no data (section skipped)")
    if r.ai_search:
        a = r.ai_search
        print(f"    AI search:        cited {a['cited']}/{a['total']} ({a['rate']}%) · "
              f"{len(a['examples'])} example citation(s)"
              f"{' from earlier scans' if a.get('examples_from_prior') else ''}")
    else:
        print(f"    AI search:        no data (section skipped)")
    if r.ads:
        ad = r.ads
        print(f"    Ads (last 30d):   spend ${ad['spend']:,.2f} · {ad['clicks']} clicks · {ad['conv']} conv")
    else:
        print(f"    Ads:              no campaigns / no data (section skipped)")
    return 0


def cmd_send(args) -> int:
    import os, json, urllib.request, urllib.error
    from datetime import datetime, timezone

    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        sys.stderr.write("ERROR: SENDGRID_API_KEY not in env. `set -a && source ./.env && set +a` first.\n")
        return 1

    client = load_client(args.slug)
    enabled = client.get("report_email_enabled", False)
    if not enabled and not args.test:
        sys.stderr.write(
            f"ERROR: client.report_email_enabled is false for {args.slug}. "
            f"Set it to true in clients/{args.slug}.json (opt-in safety), "
            f"or re-run with --test to send to contact@restorationai.io instead.\n"
        )
        return 2

    # Build the report if it doesn't exist
    r = build_report_data(args.slug, args.period)
    out_dir = CLIENTS_DIR / args.slug / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{r.period_start.strftime('%Y-%m')}-monthly.html"
    if not out_path.exists():
        out_path.write_text(render_html(r))
    html = out_path.read_text()

    # Recipient: --test always overrides to the operator inbox
    if args.test:
        to_email = "contact@restorationai.io"
        to_name = "Santino (TEST)"
        subject = f"TEST - Rank AI Monthly Report - {r.display_name} - {r.period_label}"
        test_banner = (
            '<div style="background:#dc2626;color:#fff;padding:14px 32px;'
            'text-align:center;font-weight:700;text-transform:uppercase;'
            'letter-spacing:0.08em;font-size:13px;">TEST DELIVERY - not sent to actual client</div>'
        )
        html = html.replace('<div class="container">', f'<div class="container">{test_banner}', 1)
    else:
        to_email = (client.get("report_email_to_override")
                    or client.get("contact", {}).get("email")
                    or client.get("contact", {}).get("primary_email"))
        if not to_email:
            sys.stderr.write(f"ERROR: no recipient email for {args.slug} (contact.email missing).\n")
            return 3
        to_name = client.get("display_name", args.slug)
        subject = f"Rank AI Monthly Report - {r.display_name} - {r.period_label}"

    body = {
        "personalizations": [{"to": [{"email": to_email, "name": to_name}], "subject": subject}],
        "from": {"email": "no-reply@restorationai.io", "name": "Rank AI"},
        "reply_to": {"email": "contact@restorationai.io", "name": "Rank AI"},
        "content": [{"type": "text/html", "value": html}],
    }
    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            msg_id = resp.headers.get("X-Message-Id", "")
            print(f"==> HTTP {resp.status}  sent to {to_email}  X-Message-Id: {msg_id}")
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"SendGrid HTTP {e.code}: {e.read().decode()}\n")
        return 4

    # Log delivery
    deliveries_path = out_dir / "_deliveries.jsonl"
    record = {
        "sent_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "slug": args.slug,
        "period": r.period_start.strftime("%Y-%m"),
        "to": to_email,
        "test_mode": bool(args.test),
        "subject": subject,
        "x_message_id": msg_id,
        "report_path": str(out_path.relative_to(CLIENTS_DIR.parent)),
    }
    with open(deliveries_path, "a") as f:
        f.write(json.dumps(record) + "\n")
    print(f"    Logged to {deliveries_path}")
    return 0


def cmd_portfolio(args) -> int:
    """Generate + (optionally) send a single internal digest email summarizing
    ALL active clients. This is the agency-owner dashboard delivered to
    contact@restorationai.io — NOT a client-facing artifact."""
    import os, json, urllib.request, urllib.error
    from datetime import datetime, timezone

    start, end, label = parse_period(args.period)
    # Build rows for every active client
    rows_data = []
    for path in sorted(CLIENTS_DIR.glob("*.json")):
        c = json.loads(path.read_text())
        if c.get("status") != "active":
            continue
        slug = c["slug"]
        r = build_report_data(slug, args.period)
        rows_data.append({
            "slug": slug,
            "display_name": c.get("display_name", slug),
            "domain": c.get("domain", ""),
            "report_path": str(
                CLIENTS_DIR / slug / "reports" / f"{r.period_start.strftime('%Y-%m')}-monthly.html"
            ),
            "verdict": r.audit_latest.get("site_rollup", {}).get("verdict") if r.audit_latest else None,
            "avg_perf": r.audit_latest.get("site_rollup", {}).get("avg_scores", {}).get("performance") if r.audit_latest else None,
            "money_alerts": len(r.audit_latest.get("site_rollup", {}).get("money_page_alerts", [])) if r.audit_latest else 0,
            "posts_this_month": len(r.posts_this_month),
            "refresh_actions": (r.refresh_latest or {}).get("totals", {}).get("total_actions", 0),
            "queue_depth": r.queue_depth,
            "audit_last_run": (c.get("audit") or {}).get("last_audit_at"),
            "build_status": c.get("build_status"),
        })

    if not rows_data:
        sys.stderr.write("No active clients found.\n")
        return 1

    def verdict_dot(v):
        color = {"green": "#16a34a", "amber": "#f59e0b", "red": "#dc2626", "error": "#6b7280"}.get(v, "#9ca3af")
        return f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{color};margin-right:8px;vertical-align:middle;"></span>{(v or "n/a").upper()}'

    # HTML rows
    tbody = ""
    for r in rows_data:
        report_url = f'file://{r["report_path"]}'
        tbody += f'''
        <tr style="border-bottom:1px solid #e5e7eb;">
          <td style="padding:14px 12px;font-weight:700;color:#0D1B3E;">
            {html_escape(r["display_name"])}
            <div style="font-size:12px;color:#6b7280;font-family:ui-monospace,monospace;margin-top:2px;">{html_escape(r["domain"])}</div>
          </td>
          <td style="padding:14px 12px;font-size:13px;white-space:nowrap;">{verdict_dot(r["verdict"])}</td>
          <td style="padding:14px 12px;text-align:right;font-family:ui-monospace,monospace;font-weight:700;">{r["avg_perf"] if r["avg_perf"] is not None else "-"}</td>
          <td style="padding:14px 12px;text-align:right;font-family:ui-monospace,monospace;">{r["posts_this_month"]}</td>
          <td style="padding:14px 12px;text-align:right;font-family:ui-monospace,monospace;">{r["refresh_actions"]}</td>
          <td style="padding:14px 12px;text-align:right;font-family:ui-monospace,monospace;">{r["queue_depth"]}</td>
          <td style="padding:14px 12px;text-align:right;font-family:ui-monospace,monospace;font-size:13px;color:#dc2626;">{r["money_alerts"] if r["money_alerts"] else "-"}</td>
          <td style="padding:14px 12px;text-align:right;font-size:13px;">
            <a href="{report_url}" style="color:#1E5AD4;font-weight:700;">Open report</a>
          </td>
        </tr>
        '''

    # Action items summary across portfolio
    red_clients = [r for r in rows_data if r["verdict"] == "red"]
    amber_clients = [r for r in rows_data if r["verdict"] == "amber"]
    total_posts = sum(r["posts_this_month"] for r in rows_data)
    total_alerts = sum(r["money_alerts"] for r in rows_data)

    issues_block = ""
    if red_clients:
        issues_block += f'<p style="margin:6px 0;"><strong style="color:#dc2626;">{len(red_clients)} RED:</strong> {", ".join(html_escape(r["display_name"]) for r in red_clients)} — investigate this week.</p>'
    if amber_clients:
        issues_block += f'<p style="margin:6px 0;"><strong style="color:#f59e0b;">{len(amber_clients)} AMBER:</strong> {", ".join(html_escape(r["display_name"]) for r in amber_clients)} — schedule fixes next sprint.</p>'
    if not red_clients and not amber_clients:
        issues_block = '<p style="margin:6px 0;color:#16a34a;"><strong>All clients green.</strong> No urgent action required.</p>'

    html = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Rank AI Portfolio Digest - {html_escape(label)}</title>
<style>
  body {{ margin:0; padding:0; background:#f3f4f6; font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif; color:#111827; }}
  .container {{ max-width:920px; margin:0 auto; background:#fff; }}
  .header {{ background:#0D1B3E; color:#fff; padding:36px 32px; }}
  .header h1 {{ margin:0; font-size:28px; font-weight:900; text-transform:uppercase; letter-spacing:-0.02em; line-height:1; }}
  .header .meta {{ margin-top:8px; font-size:13px; opacity:0.7; text-transform:uppercase; letter-spacing:0.08em; }}
  .strip {{ background:#1E5AD4; color:#fff; padding:20px 32px; display:flex; gap:32px; flex-wrap:wrap; }}
  .strip .stat {{ }}
  .strip .stat .num {{ font-size:26px; font-weight:900; line-height:1; }}
  .strip .stat .label {{ font-size:11px; opacity:0.9; text-transform:uppercase; letter-spacing:0.08em; margin-top:4px; }}
  section {{ padding:28px 32px; border-bottom:1px solid #e5e7eb; }}
  section h2 {{ margin:0 0 12px; font-size:16px; font-weight:900; text-transform:uppercase; letter-spacing:0.04em; color:#0D1B3E; }}
  table {{ width:100%; border-collapse:collapse; font-size:14px; }}
  th {{ text-align:left; padding:10px 12px; background:#f9fafb; font-weight:700; font-size:11px; color:#6b7280; letter-spacing:0.08em; text-transform:uppercase; border-bottom:2px solid #e5e7eb; }}
  th.r {{ text-align:right; }}
  .footer {{ padding:20px 32px; font-size:12px; color:#6b7280; background:#f9fafb; }}
</style></head><body>
<div class="container">
  <div class="header">
    <h1>Rank AI Portfolio Digest</h1>
    <div class="meta">{html_escape(label)} - internal use only - {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}</div>
  </div>
  <div class="strip">
    <div class="stat"><div class="num">{len(rows_data)}</div><div class="label">Active Clients</div></div>
    <div class="stat"><div class="num">{total_posts}</div><div class="label">Posts Written</div></div>
    <div class="stat"><div class="num">{len(red_clients)}</div><div class="label">Red Sites</div></div>
    <div class="stat"><div class="num">{len(amber_clients)}</div><div class="label">Amber Sites</div></div>
    <div class="stat"><div class="num">{total_alerts}</div><div class="label">Money-Page Alerts</div></div>
  </div>
  <section>
    <h2>Action Items</h2>
    {issues_block}
  </section>
  <section>
    <h2>Per-Client Summary</h2>
    <table>
      <thead><tr>
        <th>Client</th>
        <th>Health</th>
        <th class="r">Perf</th>
        <th class="r">Posts</th>
        <th class="r">Refresh</th>
        <th class="r">Queue</th>
        <th class="r">Alerts</th>
        <th class="r"></th>
      </tr></thead>
      <tbody>{tbody}</tbody>
    </table>
  </section>
  <div class="footer">
    Click "Open report" to view the per-client full HTML report (local file). Reply if you want to change which clients appear here or what the digest shows.
  </div>
</div>
</body></html>'''

    # Save to disk
    out_dir = CLIENTS_DIR.parent / "portfolio" / "digests"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{start.strftime('%Y-%m')}-digest.html"
    out_path.write_text(html)
    print(f"==> Wrote portfolio digest: {out_path}")
    print(f"    Clients summarized: {len(rows_data)}")
    print(f"    Red: {len(red_clients)}  Amber: {len(amber_clients)}  Green: {len(rows_data) - len(red_clients) - len(amber_clients)}")

    if not args.send:
        print(f"\n    Open in browser:  file://{out_path}")
        print(f"    To send to contact@restorationai.io: re-run with --send")
        return 0

    # Send via SendGrid
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        sys.stderr.write("ERROR: SENDGRID_API_KEY not in env.\n")
        return 1
    body = {
        "personalizations": [{
            "to": [{"email": "contact@restorationai.io", "name": "Santino"}],
            "subject": f"Rank AI portfolio digest - {label}",
        }],
        "from": {"email": "no-reply@restorationai.io", "name": "Rank AI"},
        "content": [{"type": "text/html", "value": html}],
    }
    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            msg_id = resp.headers.get("X-Message-Id", "")
            print(f"\n==> Sent: HTTP {resp.status}  X-Message-Id: {msg_id}")
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"SendGrid HTTP {e.code}: {e.read().decode()}\n")
        return 4

    deliveries = out_dir / "_deliveries.jsonl"
    record = {
        "sent_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "period": start.strftime("%Y-%m"),
        "to": "contact@restorationai.io",
        "subject": f"Rank AI portfolio digest - {label}",
        "x_message_id": msg_id,
        "clients_summarized": len(rows_data),
    }
    with open(deliveries, "a") as f:
        f.write(json.dumps(record) + "\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Rank AI — monthly client report generator")
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("preview", help="Generate the HTML report locally")
    pp.add_argument("--slug", required=True)
    pp.add_argument("--period", help="YYYY-MM (defaults to current month)")
    pp.set_defaults(func=cmd_preview)

    pd = sub.add_parser("portfolio", help="Generate a portfolio digest summarizing ALL active clients (internal-only)")
    pd.add_argument("--period", help="YYYY-MM (defaults to current month)")
    pd.add_argument("--send", action="store_true",
                    help="Send the digest to contact@restorationai.io via SendGrid")
    pd.set_defaults(func=cmd_portfolio)
    ps = sub.add_parser("send", help="Send the report via SendGrid REST API")
    ps.add_argument("--slug", required=True)
    ps.add_argument("--period", help="YYYY-MM (defaults to current month)")
    ps.add_argument("--test", action="store_true",
                    help="Override recipient to contact@restorationai.io + prepend TEST banner. "
                         "Bypasses client.report_email_enabled.")
    ps.set_defaults(func=cmd_send)

    pub = sub.add_parser("publish", help="Render + upsert the report (metrics + HTML) to Supabase for the app's Reports tab")
    grp = pub.add_mutually_exclusive_group(required=True)
    grp.add_argument("--slug")
    grp.add_argument("--all", action="store_true")
    pub.add_argument("--period", help="YYYY-MM (defaults to current month)")
    pub.set_defaults(func=cmd_publish)
    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
