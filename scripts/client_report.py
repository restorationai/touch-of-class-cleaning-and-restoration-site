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
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = ROOT / "clients"


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


def build_report_data(slug: str, period: str | None) -> ReportData:
    client = load_client(slug)
    start, end, label = parse_period(period)
    posts = collect_posts_this_month(slug, start, end)
    audit, refresh, queue_depth = collect_state(slug)
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

    <section>
      <div class="eyebrow">Section 1</div>
      <h2>Content Delivered</h2>
      <p>Below is the SEO content we wrote, published, and indexed on your site in {html_escape(r.period_label)}.</p>
      <table style="width:100%;border-collapse:collapse;margin-top:16px;">{posts_html}</table>
    </section>

    <section>
      <div class="eyebrow">Section 2</div>
      <h2>Site Health &nbsp; {verdict_badge(audit_verdict)}</h2>
      <p>Monthly technical audit of your site's core SEO health (performance, accessibility, on-page signals).</p>
      {audit_html}
    </section>

    <section>
      <div class="eyebrow">Section 3</div>
      <h2>Content Refresh Activity</h2>
      <p>Existing pages we identified as needing refresh, fix, or re-indexing.</p>
      {refresh_html}
    </section>

    <section>
      <div class="eyebrow">Section 4</div>
      <h2>Coming Up Next Month</h2>
      <p>Scheduled work + the queue we're drawing from to write next.</p>
      {coming_html}
    </section>

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
    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
