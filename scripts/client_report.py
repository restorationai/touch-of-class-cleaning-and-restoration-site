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
    print("Send via SendGrid is task #40 (not yet implemented). Use preview for now.")
    return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Rank AI — monthly client report generator")
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("preview", help="Generate the HTML report locally")
    pp.add_argument("--slug", required=True)
    pp.add_argument("--period", help="YYYY-MM (defaults to current month)")
    pp.set_defaults(func=cmd_preview)
    ps = sub.add_parser("send", help="Send the report via SendGrid (stub — task #40)")
    ps.add_argument("--slug", required=True)
    ps.add_argument("--period", help="YYYY-MM (defaults to current month)")
    ps.set_defaults(func=cmd_send)
    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
