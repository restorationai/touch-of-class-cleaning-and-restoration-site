#!/usr/bin/env python3
"""
Rank AI — Terminal Dashboard

Usage:
  python3 scripts/dashboard.py                         # admin: all clients
  python3 scripts/dashboard.py --slug narestco         # client: individual view
  python3 scripts/dashboard.py --slug narestco --live  # client view + live Ads + GBP
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CLIENTS_DIR = REPO_ROOT / "clients"
SITES_DIR = REPO_ROOT / "sites"

console = Console(width=160)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def days_ago(ts: str | None) -> str:
    if not ts:
        return "-"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        days = (datetime.now(timezone.utc) - dt).days
        if days == 0:
            return "today"
        if days == 1:
            return "1d ago"
        return f"{days}d ago"
    except Exception:
        return "-"


def verdict_text(verdict: str | None, include_label: bool = True) -> Text:
    if verdict == "green":
        return Text(("● green" if include_label else "●"), style="bold green")
    if verdict == "amber":
        return Text(("● amber" if include_label else "●"), style="bold yellow")
    if verdict == "red":
        return Text(("● RED" if include_label else "●"), style="bold red")
    return Text("-", style="dim")


def build_text(status: str | None) -> Text:
    m = {
        "cut_over":      Text("● live",       style="bold green"),
        "pushed_main":   Text("● pages.dev",  style="cyan"),
        "pushed_staging":Text("● staging",    style="yellow"),
        "content_rendered": Text("○ rendered",style="dim yellow"),
        "scaffolded":    Text("○ scaffolded", style="dim"),
    }
    return m.get(status or "", Text("○ pending", style="dim"))


def status_text(status: str | None) -> Text:
    if status == "active":
        return Text("active", style="green")
    if status == "pending_ns":
        return Text("pending NS", style="yellow")
    return Text(status or "unknown", style="dim")


def check(val: bool) -> str:
    return "[green]✓[/green]" if val else "[dim]-[/dim]"


def money(amount: float) -> str:
    return f"${amount:,.2f}"


def na(val, fmt=None) -> str:
    if val is None:
        return "[dim]-[/dim]"
    if fmt:
        return fmt.format(val)
    return str(val)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def list_client_slugs() -> list[str]:
    return sorted(
        p.stem for p in CLIENTS_DIR.glob("*.json")
        if p.is_file()
    )


def load_client(slug: str) -> dict:
    path = CLIENTS_DIR / f"{slug}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def load_onsite_audit(slug: str) -> dict:
    path = CLIENTS_DIR / slug / "onsite-audit.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def load_content_queue(slug: str) -> dict:
    path = CLIENTS_DIR / slug / "content-queue.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def load_keyword_bank(slug: str) -> dict:
    path = CLIENTS_DIR / slug / "keyword-bank.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def count_blog_posts(slug: str) -> tuple[int, int]:
    """Returns (total_posts, videos_published)."""
    blog_dir = SITES_DIR / slug / "src" / "content" / "blog"
    if not blog_dir.exists():
        return 0, 0
    posts = list(blog_dir.glob("*.md"))
    videos = sum(
        1 for p in posts
        if "youtube_id:" in p.read_text()
        and 'youtube_id: ""' not in p.read_text()
    )
    return len(posts), videos


def load_ads_structure(slug: str) -> dict:
    path = CLIENTS_DIR / slug / "ads-structure.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Live data loaders (optional, require API tokens)
# ---------------------------------------------------------------------------

def _ads_client(slug: str):
    try:
        from google.ads.googleads.client import GoogleAdsClient
    except ImportError:
        return None, "google-ads not installed"

    t_path = CLIENTS_DIR / slug / ".ads-token.json"
    if not t_path.exists():
        return None, "auth required (run ads_manager.py auth)"

    dev_token = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
    if not dev_token:
        return None, "GOOGLE_ADS_DEVELOPER_TOKEN not set"

    try:
        token_data = json.loads(t_path.read_text())
        mcc_id = os.environ.get("GOOGLE_ADS_MCC_CUSTOMER_ID", "").replace("-", "")
        ads_client = GoogleAdsClient.load_from_dict({
            "developer_token": dev_token,
            "client_id": token_data["client_id"],
            "client_secret": token_data["client_secret"],
            "refresh_token": token_data["refresh_token"],
            "login_customer_id": mcc_id,
            "use_proto_plus": True,
        })
        return ads_client, None
    except Exception as exc:
        return None, str(exc)[:80]


def load_live_ads(slug: str, days: int = 7) -> dict:
    client_rec = load_client(slug)
    customer_id = (
        client_rec.get("brand", {}).get("google_ads_customer_id")
        or client_rec.get("google_ads", {}).get("customer_id")
    )
    if not customer_id:
        return {"error": "no customer ID in client record"}

    ads_client, err = _ads_client(slug)
    if err:
        return {"error": err}

    from datetime import date, timedelta
    end = date.today()
    start = end - timedelta(days=days - 1)

    try:
        ga = ads_client.get_service("GoogleAdsService")
        query = f"""
            SELECT
              campaign.name, campaign.status,
              metrics.impressions, metrics.clicks,
              metrics.cost_micros, metrics.conversions,
              metrics.ctr, metrics.average_cpc
            FROM campaign
            WHERE segments.date BETWEEN '{start}' AND '{end}'
              AND campaign.status != 'REMOVED'
            ORDER BY metrics.cost_micros DESC
        """
        stream = ga.search_stream(
            customer_id=customer_id.replace("-", ""), query=query
        )
        campaigns = []
        for batch in stream:
            for row in batch.results:
                m = row.metrics
                campaigns.append({
                    "name": row.campaign.name,
                    "status": row.campaign.status.name,
                    "impressions": m.impressions,
                    "clicks": m.clicks,
                    "cost_usd": m.cost_micros / 1_000_000,
                    "conversions": m.conversions,
                    "ctr": m.ctr,
                })
        total_spend = sum(c["cost_usd"] for c in campaigns)
        total_clicks = sum(c["clicks"] for c in campaigns)
        total_impr = sum(c["impressions"] for c in campaigns)
        total_conv = sum(c["conversions"] for c in campaigns)
        return {
            "spend": total_spend,
            "clicks": total_clicks,
            "impressions": total_impr,
            "conversions": total_conv,
            "ctr": total_clicks / total_impr if total_impr else 0,
            "cpc": total_spend / total_clicks if total_clicks else 0,
            "campaigns": campaigns,
            "days": days,
        }
    except Exception as exc:
        return {"error": str(exc)[:120]}


def load_live_gbp(slug: str, days: int = 7) -> dict:
    t_path = CLIENTS_DIR / slug / ".gbp-token.json"
    if not t_path.exists():
        return {"error": "auth required (run gbp_manager.py auth)"}
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        import urllib.request as ureq
        import urllib.parse

        data = json.loads(t_path.read_text())
        creds = Credentials(
            token=data.get("token"),
            refresh_token=data["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=data["client_id"],
            client_secret=data["client_secret"],
        )
        if not creds.valid:
            creds.refresh(Request())

        client_rec = load_client(slug)
        location_name = client_rec.get("gbp_location_name")
        if not location_name:
            return {"error": "no gbp_location_name in client record"}

        from datetime import date, timedelta
        end = date.today()
        start = end - timedelta(days=days - 1)
        metrics_list = [
            "BUSINESS_IMPRESSIONS_DESKTOP_MAPS",
            "BUSINESS_IMPRESSIONS_MOBILE_SEARCH",
            "BUSINESS_DIRECTION_REQUESTS",
            "CALL_CLICKS",
            "WEBSITE_CLICKS",
        ]
        results = {}
        perf_api = "https://businessprofileperformance.googleapis.com/v1"
        for metric in metrics_list:
            params = urllib.parse.urlencode({
                "dailyMetric": metric,
                "dailyRange.start_date.year": start.year,
                "dailyRange.start_date.month": start.month,
                "dailyRange.start_date.day": start.day,
                "dailyRange.end_date.year": end.year,
                "dailyRange.end_date.month": end.month,
                "dailyRange.end_date.day": end.day,
            })
            url = f"{perf_api}/{location_name}:getDailyMetricsTimeSeries?{params}"
            req = ureq.Request(url, headers={"Authorization": f"Bearer {creds.token}"})
            try:
                with ureq.urlopen(req, timeout=15) as resp:
                    payload = json.loads(resp.read().decode())
                total = sum(
                    int(d.get("value", 0))
                    for d in payload.get("timeSeries", {}).get("datedValues", [])
                    if d.get("value")
                )
                results[metric] = total
            except Exception:
                results[metric] = None

        impressions = (results.get("BUSINESS_IMPRESSIONS_DESKTOP_MAPS") or 0) + \
                      (results.get("BUSINESS_IMPRESSIONS_MOBILE_SEARCH") or 0)
        return {
            "impressions": impressions,
            "direction_requests": results.get("BUSINESS_DIRECTION_REQUESTS"),
            "call_clicks": results.get("CALL_CLICKS"),
            "website_clicks": results.get("WEBSITE_CLICKS"),
            "days": days,
        }
    except Exception as exc:
        return {"error": str(exc)[:120]}


# ---------------------------------------------------------------------------
# Admin view
# ---------------------------------------------------------------------------

def render_admin() -> None:
    slugs = list_client_slugs()

    console.print()
    console.rule(
        Text("  RANK AI — CLIENT PORTFOLIO  ", style="bold white"),
        style="bright_blue"
    )
    console.print()

    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold bright_blue",
        border_style="bright_blue",
        padding=(0, 1),
    )
    table.add_column("#",        width=3,  justify="right", style="dim")
    table.add_column("Client",   min_width=22)
    table.add_column("Domain",   min_width=18)
    table.add_column("Site",     width=14)
    table.add_column("Audit",    width=14)
    table.add_column("Queue",    width=7,  justify="center")
    table.add_column("Posts",    width=7,  justify="center")
    table.add_column("Videos",   width=7,  justify="center")
    table.add_column("Ads token",width=10, justify="center")
    table.add_column("GBP token",width=10, justify="center")

    for i, slug in enumerate(slugs, 1):
        rec = load_client(slug)
        audit = load_onsite_audit(slug)
        queue = load_content_queue(slug)
        posts, videos = count_blog_posts(slug)

        display = rec.get("display_name", slug)
        if len(display) > 24:
            display = display[:22] + ".."
        domain = rec.get("domain", "-")

        verdict = rec.get("audit", {}).get("last_audit_verdict")
        audit_ts = rec.get("audit", {}).get("last_audit_at")
        audit_cell = Text()
        if verdict:
            vt = verdict_text(verdict)
            audit_cell.append_text(vt)
            audit_cell.append(f"  {days_ago(audit_ts)}", style="dim")
        else:
            audit_cell = Text("-", style="dim")

        queue_count = len(queue.get("items", []))
        has_ads = (CLIENTS_DIR / slug / ".ads-token.json").exists()
        has_gbp = (CLIENTS_DIR / slug / ".gbp-token.json").exists()

        table.add_row(
            str(i),
            display,
            domain,
            build_text(rec.get("build_status")),
            audit_cell,
            str(queue_count) if queue_count else "[dim]-[/dim]",
            str(posts) if posts else "[dim]-[/dim]",
            str(videos) if videos else "[dim]-[/dim]",
            "[green]✓[/green]" if has_ads else "[dim]-[/dim]",
            "[green]✓[/green]" if has_gbp else "[dim]-[/dim]",
        )

    console.print(table)
    console.print()
    console.print(
        f"  [dim]{len(slugs)} client(s) — "
        f"run [white]python3 scripts/dashboard.py --slug <slug>[/white] "
        f"for individual view[/dim]"
    )
    console.print()


# ---------------------------------------------------------------------------
# Client view
# ---------------------------------------------------------------------------

def _panel(title: str, content: str, style: str = "bright_blue") -> Panel:
    return Panel(
        content,
        title=f"[bold]{title}[/bold]",
        title_align="left",
        border_style=style,
        padding=(0, 1),
    )


def _kv(label: str, value, label_width: int = 18) -> str:
    label_str = f"[dim]{label:<{label_width}}[/dim]"
    if isinstance(value, Text):
        return label_str + value.markup
    return f"{label_str}{value}"


def render_client(slug: str, live: bool = False) -> None:
    rec = load_client(slug)
    if not rec:
        console.print(f"[red]Client not found: {slug}[/red]")
        sys.exit(1)

    audit = load_onsite_audit(slug)
    queue = load_content_queue(slug)
    kb = load_keyword_bank(slug)
    posts, videos = count_blog_posts(slug)
    ads_structure = load_ads_structure(slug)

    live_ads: dict = {}
    live_gbp: dict = {}
    if live:
        console.print("[dim]  Loading live data...[/dim]", end="")
        live_ads = load_live_ads(slug, days=7)
        live_gbp = load_live_gbp(slug, days=7)
        console.print("\r                        \r", end="")

    display_name = rec.get("display_name", slug)
    domain = rec.get("domain", "-")
    build_status = rec.get("build_status")

    # ── Header ───────────────────────────────────────────────────────────────
    console.print()
    console.rule(
        Text(f"  {display_name}  ", style="bold white"),
        style="bright_blue"
    )
    header_lines = [
        _kv("Slug",       f"[cyan]{slug}[/cyan]"),
        _kv("Domain",     f"[link=https://{domain}]{domain}[/link]"),
        _kv("Status",     status_text(rec.get("status")).markup),
        _kv("Tier",       rec.get("tier", "-")),
        _kv("Site",       build_text(build_status).markup),
    ]
    if rec.get("apex_cutover"):
        header_lines.append(_kv("Live since", days_ago(rec["apex_cutover"].get("completed_at"))))
    console.print(Panel(
        "\n".join(header_lines),
        border_style="bright_blue",
        padding=(0, 2),
    ))
    console.print()

    # ── Row 1: Website + Audit ────────────────────────────────────────────────
    # Website
    build = rec.get("build", {})
    plan = rec.get("plan", {})
    pages_proj = build.get("pages_project", "-")
    pages_url = f"https://{pages_proj}.pages.dev" if pages_proj != "-" else "-"
    live_url = f"https://{domain}/" if build_status == "cut_over" else pages_url

    website_lines = [
        _kv("URL",          f"[link={live_url}]{live_url}[/link]"),
        _kv("GitHub repo",  build.get("github_repo", "-")),
        _kv("Pages project",pages_proj),
        _kv("Page count",   str(plan.get("url_count", "-"))),
        _kv("Last deploy",  days_ago(build.get("last_pushed_main_at"))),
        _kv("Scaffolded",   days_ago(build.get("scaffolded_at"))),
        _kv("Template",     f"{plan.get('template', '-')} v{plan.get('template_version', '-')}"),
    ]

    # Audit
    audit_rec = rec.get("audit", {})
    verdict = audit_rec.get("last_audit_verdict")
    audit_report = audit_rec.get("last_audit_report_path", "-")

    url_scores = audit.get("url_scores", {})
    issue_counts: dict[str, int] = {}
    for url_data in url_scores.values():
        for issue in url_data.get("issues", []):
            sev = issue.get("severity", "low")
            issue_counts[sev] = issue_counts.get(sev, 0) + 1

    audit_lines = [
        _kv("Verdict",      verdict_text(verdict).markup if verdict else "[dim]-[/dim]"),
        _kv("Last run",     days_ago(audit_rec.get("last_audit_at"))),
        _kv("Report",       audit_report.split("/")[-1] if audit_report != "-" else "-"),
        _kv("Critical",     f"[red]{issue_counts.get('critical', 0)}[/red]" if issue_counts.get('critical') else "[dim]0[/dim]"),
        _kv("High",         f"[yellow]{issue_counts.get('high', 0)}[/yellow]" if issue_counts.get('high') else "[dim]0[/dim]"),
        _kv("Medium",       str(issue_counts.get("medium", 0))),
        _kv("Audited at",   audit_rec.get("live_origin_audited", "-")),
    ]

    console.print(Columns([
        _panel("WEBSITE", "\n".join(website_lines)),
        _panel("ONSITE AUDIT", "\n".join(audit_lines),
               style="green" if verdict == "green" else "yellow" if verdict == "amber" else "red" if verdict == "red" else "bright_blue"),
    ], equal=True, expand=True))
    console.print()

    # ── Row 2: Blog + Keywords ────────────────────────────────────────────────
    queue_items = queue.get("items", [])
    next_item = queue_items[0] if queue_items else None
    next_title = (next_item.get("title") or next_item.get("keyword", ""))[:40] if next_item else "-"

    refresh_rec = rec.get("refresh", {})
    blog_lines = [
        _kv("Posts live",   str(posts) if posts else "[dim]0[/dim]"),
        _kv("Videos live",  str(videos) if videos else "[dim]0[/dim]"),
        _kv("Queue depth",  f"[yellow]{len(queue_items)}[/yellow]" if queue_items else "[dim]0[/dim]"),
        _kv("Next to write", next_title),
        _kv("Last refresh",  days_ago(refresh_rec.get("last_run_at"))),
        _kv("Last action",   refresh_rec.get("last_run_top_action", "-")),
    ]

    kb_keywords = kb.get("keywords", [])
    seeds_done = kb.get("seeds_researched", [])
    last_kw = max((s.get("last_researched", "") for s in seeds_done), default=None) if seeds_done else None

    kw_lines = [
        _kv("Bank size",    f"{len(kb_keywords):,} keywords" if kb_keywords else "[dim]0[/dim]"),
        _kv("Seeds done",   str(len(seeds_done)) if seeds_done else "[dim]0[/dim]"),
        _kv("Last run",     days_ago(last_kw)),
        _kv("P1 in queue",  str(sum(1 for k in kb_keywords if k.get("priority") == 1)) if kb_keywords else "[dim]-[/dim]"),
        _kv("P2 in bank",   str(sum(1 for k in kb_keywords if k.get("priority") == 2)) if kb_keywords else "[dim]-[/dim]"),
    ]

    console.print(Columns([
        _panel("BLOG & CONTENT", "\n".join(blog_lines)),
        _panel("KEYWORD RESEARCH", "\n".join(kw_lines)),
    ], equal=True, expand=True))
    console.print()

    # ── Row 3: GSC + GBP Auth ─────────────────────────────────────────────────
    gsc = rec.get("gsc", {})
    gsc_lines = [
        _kv("Property",     gsc.get("property_url", "[dim]not set[/dim]")),
        _kv("Verified",     "[green]✓[/green]" if gsc.get("verified_at") else "[dim]-[/dim]"),
        _kv("Verified at",  days_ago(gsc.get("verified_at"))),
        _kv("Sitemap",      gsc.get("sitemap_url", "[dim]-[/dim]")),
    ]

    gbp_location = rec.get("gbp_location_name")
    has_gbp_token = (CLIENTS_DIR / slug / ".gbp-token.json").exists()
    gbp_auth_lines = [
        _kv("Location pinned", "[green]✓[/green]" if gbp_location else "[yellow]not set[/yellow]"),
        _kv("Location name",  gbp_location or "[dim]run gbp_manager.py locations[/dim]"),
        _kv("Auth token",     "[green]✓[/green]" if has_gbp_token else "[yellow]run gbp_manager.py auth[/yellow]"),
    ]

    console.print(Columns([
        _panel("GOOGLE SEARCH CONSOLE", "\n".join(gsc_lines)),
        _panel("GOOGLE BUSINESS PROFILE", "\n".join(gbp_auth_lines)),
    ], equal=True, expand=True))
    console.print()

    # ── Google Ads ────────────────────────────────────────────────────────────
    has_ads_token = (CLIENTS_DIR / slug / ".ads-token.json").exists()
    ads_cid = (
        rec.get("brand", {}).get("google_ads_customer_id")
        or rec.get("google_ads", {}).get("customer_id")
    )
    campaigns_in_structure = len(ads_structure.get("campaigns", {}))
    ad_groups_in_structure = len(ads_structure.get("ad_groups", {}))

    if live and live_ads and "error" not in live_ads:
        ads_lines = [
            _kv("Period",       f"last {live_ads['days']} days  [dim](live)[/dim]"),
            _kv("Spend",        f"[bold]{money(live_ads['spend'])}[/bold]"),
            _kv("Clicks",       f"{live_ads['clicks']:,}"),
            _kv("Impressions",  f"{live_ads['impressions']:,}"),
            _kv("CTR",          f"{live_ads['ctr']*100:.2f}%"),
            _kv("Avg CPC",      money(live_ads['cpc'])),
            _kv("Conversions",  f"{live_ads['conversions']:.1f}"),
            _kv("Campaigns",    str(len(live_ads.get("campaigns", [])))),
        ]
        if live_ads.get("campaigns"):
            top = live_ads["campaigns"][0]
            ads_lines.append(_kv("Top campaign", f"{top['name'][:30]}  {money(top['cost_usd'])}"))
    elif live and "error" in live_ads:
        ads_lines = [
            _kv("Status", f"[yellow]{live_ads['error']}[/yellow]"),
        ]
    else:
        ads_lines = [
            _kv("Auth token",   "[green]✓[/green]" if has_ads_token else "[yellow]run ads_manager.py auth[/yellow]"),
            _kv("Customer ID",  ads_cid or "[dim]not set[/dim]"),
            _kv("Campaigns",    str(campaigns_in_structure) if campaigns_in_structure else "[dim]run ads_manager.py scaffold[/dim]"),
            _kv("Ad groups",    str(ad_groups_in_structure) if ad_groups_in_structure else "[dim]-[/dim]"),
            _kv("Live data",    "[dim]add --live flag for 7-day metrics[/dim]"),
        ]

    ads_style = "green" if (live and live_ads and "error" not in live_ads) else "bright_blue"
    console.print(_panel(
        "GOOGLE ADS" + (" — 7 days" if live else ""),
        "\n".join(ads_lines),
        style=ads_style,
    ))
    console.print()

    # ── GBP Insights ─────────────────────────────────────────────────────────
    if live and live_gbp and "error" not in live_gbp:
        gbp_lines = [
            _kv("Period",           f"last {live_gbp['days']} days  [dim](live)[/dim]"),
            _kv("Impressions",      f"{live_gbp.get('impressions', '-'):,}" if live_gbp.get('impressions') is not None else "[dim]-[/dim]"),
            _kv("Direction requests", na(live_gbp.get("direction_requests"), "{:,}")),
            _kv("Call clicks",      na(live_gbp.get("call_clicks"), "{:,}")),
            _kv("Website clicks",   na(live_gbp.get("website_clicks"), "{:,}")),
        ]
        gbp_style = "green"
    elif live and "error" in live_gbp:
        gbp_lines = [_kv("Status", f"[yellow]{live_gbp['error']}[/yellow]")]
        gbp_style = "yellow"
    else:
        gbp_lines = [
            _kv("Auth token",   "[green]✓[/green]" if has_gbp_token else "[yellow]run gbp_manager.py auth[/yellow]"),
            _kv("Location",     gbp_location or "[dim]not pinned[/dim]"),
            _kv("Live data",    "[dim]add --live flag for 7-day metrics[/dim]"),
        ]
        gbp_style = "bright_blue"

    console.print(_panel(
        "GOOGLE BUSINESS PROFILE" + (" — 7 days" if live else ""),
        "\n".join(gbp_lines),
        style=gbp_style,
    ))
    console.print()

    # ── Footer ────────────────────────────────────────────────────────────────
    hints = []
    if not live:
        hints.append("add [white]--live[/white] for real-time Ads + GBP data")
    if verdict in ("amber", "red"):
        hints.append("run [white]rank-ai-onsite-audit[/white] to diagnose issues")
    if len(queue_items) < 3:
        hints.append("run [white]rank-ai-keyword-researcher[/white] to fill the content queue")
    if hints:
        console.print(f"  [dim]Hints: {' | '.join(hints)}[/dim]")
    console.print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Rank AI Terminal Dashboard")
    parser.add_argument("--slug", help="Individual client slug (omit for admin view)")
    parser.add_argument("--live", action="store_true",
                        help="Pull live data from Google Ads + GBP APIs")
    args = parser.parse_args()

    # Source .env if available
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                if key not in os.environ:
                    os.environ[key] = val

    if args.slug:
        render_client(args.slug.lower(), live=args.live)
    else:
        render_admin()


if __name__ == "__main__":
    main()
