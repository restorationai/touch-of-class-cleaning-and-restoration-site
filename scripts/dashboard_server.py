#!/usr/bin/env python3
"""
Rank AI — Web Dashboard Server

Usage:
  python3 scripts/dashboard_server.py          # opens at http://localhost:5050
  python3 scripts/dashboard_server.py --port 8080
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from threading import Timer

from flask import Flask, render_template_string, redirect, url_for

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT   = SCRIPT_DIR.parent
CLIENTS_DIR = REPO_ROOT / "clients"
SITES_DIR   = REPO_ROOT / "sites"

# Source .env
env_path = REPO_ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Data helpers (mirrors dashboard.py logic)
# ---------------------------------------------------------------------------

def days_ago(ts: str | None) -> str:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        days = (datetime.now(timezone.utc) - dt).days
        if days == 0:
            return "today"
        if days == 1:
            return "1d ago"
        return f"{days}d ago"
    except Exception:
        return None


def list_client_slugs() -> list[str]:
    return sorted(p.stem for p in CLIENTS_DIR.glob("*.json") if p.is_file())


def load_client(slug: str) -> dict:
    path = CLIENTS_DIR / f"{slug}.json"
    return json.loads(path.read_text()) if path.exists() else {}


def load_onsite_audit(slug: str) -> dict:
    path = CLIENTS_DIR / slug / "onsite-audit.json"
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        return {}


def load_content_queue(slug: str) -> dict:
    path = CLIENTS_DIR / slug / "content-queue.json"
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        return {}


def load_keyword_bank(slug: str) -> dict:
    path = CLIENTS_DIR / slug / "keyword-bank.json"
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        return {}


def count_blog_posts(slug: str) -> tuple[int, int]:
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
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        return {}


def load_refresh_queue(slug: str) -> dict:
    path = CLIENTS_DIR / slug / "refresh-queue.json"
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        return {}


def read_frontmatter(path: Path) -> dict:
    """Parse YAML frontmatter from a markdown file (key: value pairs only)."""
    result = {}
    try:
        text = path.read_text(errors="replace")
        if not text.startswith("---"):
            return result
        end = text.find("\n---", 3)
        if end == -1:
            return result
        fm = text[3:end]
        for line in fm.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                result[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return result


def load_blog_posts(slug: str) -> list[dict]:
    blog_dir = SITES_DIR / slug / "src" / "content" / "blog"
    if not blog_dir.exists():
        return []
    posts = []
    for p in sorted(blog_dir.glob("*.md"), reverse=True):
        fm = read_frontmatter(p)
        published_at = (
            fm.get("published_at")
            or fm.get("pubDate")
            or fm.get("date")
            or fm.get("publishDate", "")
        )
        posts.append({
            "filename": p.name,
            "slug": p.stem,
            "title": fm.get("title", p.stem),
            "published_at": published_at,
            "rendered": fm.get("rendered", "false").lower() == "true",
            "youtube_id": fm.get("youtube_id", "").strip(),
            "word_count": len(p.read_text(errors="replace").split()),
            "primary_keyword": fm.get("primary_keyword", ""),
            "search_intent": fm.get("search_intent", ""),
        })
    return posts


def build_status_info(status: str | None) -> tuple[str, str]:
    """Returns (label, css_class)."""
    m = {
        "cut_over":        ("Live",      "status-live"),
        "pushed_main":     ("pages.dev", "status-pages"),
        "pushed_staging":  ("Staging",   "status-staging"),
        "content_rendered":("Rendered",  "status-dim"),
        "scaffolded":      ("Scaffolded","status-dim"),
    }
    return m.get(status or "", ("Pending", "status-dim"))


def verdict_info(verdict: str | None) -> tuple[str, str]:
    """Returns (label, css_class)."""
    if verdict == "green": return ("Green",  "verdict-green")
    if verdict == "amber": return ("Amber",  "verdict-amber")
    if verdict == "red":   return ("Red",    "verdict-red")
    return ("-", "verdict-none")


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

BASE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Rank AI Dashboard</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #0f1117;
      --surface: #1a1d27;
      --surface2: #21253a;
      --border: #2e3347;
      --text: #e2e8f0;
      --text-dim: #64748b;
      --text-muted: #475569;
      --blue: #3b82f6;
      --blue-dim: #1d4ed8;
      --green: #22c55e;
      --yellow: #eab308;
      --red: #ef4444;
      --cyan: #22d3ee;
      --purple: #a78bfa;
    }
    body { background: var(--bg); color: var(--text); font-family: 'Inter', system-ui, -apple-system, sans-serif; font-size: 14px; min-height: 100vh; }

    /* Nav */
    nav { background: var(--surface); border-bottom: 1px solid var(--border); padding: 0 24px; display: flex; align-items: center; height: 52px; gap: 16px; }
    nav .brand { font-size: 15px; font-weight: 700; color: var(--blue); letter-spacing: 0.05em; flex: 1; }
    nav .nav-link { color: var(--text-dim); text-decoration: none; padding: 6px 12px; border-radius: 6px; font-size: 13px; transition: all 0.15s; }
    nav .nav-link:hover, nav .nav-link.active { background: var(--surface2); color: var(--text); }
    nav .refresh-btn { background: var(--blue-dim); color: white; border: none; padding: 6px 14px; border-radius: 6px; font-size: 12px; cursor: pointer; font-weight: 600; }
    nav .refresh-btn:hover { background: var(--blue); }

    /* Page */
    .page { max-width: 1400px; margin: 0 auto; padding: 28px 24px; }
    h1 { font-size: 20px; font-weight: 700; color: var(--text); margin-bottom: 6px; }
    .subtitle { color: var(--text-dim); font-size: 13px; margin-bottom: 28px; }

    /* Table */
    .data-table { width: 100%; border-collapse: collapse; background: var(--surface); border-radius: 10px; overflow: hidden; border: 1px solid var(--border); }
    .data-table th { background: var(--surface2); color: var(--text-dim); font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); }
    .data-table td { padding: 12px 14px; border-bottom: 1px solid var(--border); vertical-align: middle; }
    .data-table tr:last-child td { border-bottom: none; }
    .data-table tr:hover td { background: var(--surface2); }
    .data-table a { color: var(--blue); text-decoration: none; }
    .data-table a:hover { text-decoration: underline; }

    /* Status badges */
    .badge { display: inline-flex; align-items: center; gap: 5px; padding: 3px 9px; border-radius: 99px; font-size: 12px; font-weight: 600; white-space: nowrap; }
    .status-live    { background: rgba(34,197,94,.15); color: var(--green); }
    .status-pages   { background: rgba(34,211,238,.12); color: var(--cyan); }
    .status-staging { background: rgba(234,179,8,.12); color: var(--yellow); }
    .status-dim     { background: rgba(100,116,139,.12); color: var(--text-dim); }
    .verdict-green  { background: rgba(34,197,94,.15); color: var(--green); }
    .verdict-amber  { background: rgba(234,179,8,.12); color: var(--yellow); }
    .verdict-red    { background: rgba(239,68,68,.15); color: var(--red); }
    .verdict-none   { color: var(--text-dim); }
    .dot { font-size: 8px; }

    /* Checks */
    .check-yes { color: var(--green); font-size: 15px; }
    .check-no  { color: var(--text-muted); }
    .check-warn { color: var(--yellow); }

    /* Numbers */
    .num { font-variant-numeric: tabular-nums; font-weight: 500; }
    .num-zero { color: var(--text-muted); }

    /* Client grid */
    .client-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
    @media (max-width: 1100px) { .client-grid { grid-template-columns: repeat(2,1fr); } }
    @media (max-width: 700px)  { .client-grid { grid-template-columns: 1fr; } }

    /* Cards */
    .card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
    .card-header { background: var(--surface2); padding: 12px 16px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border); }
    .card-title { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-dim); }
    .card-body { padding: 14px 16px; }
    .kv { display: flex; gap: 10px; padding: 4px 0; border-bottom: 1px solid rgba(46,51,71,.5); font-size: 13px; }
    .kv:last-child { border-bottom: none; }
    .kv-label { color: var(--text-dim); min-width: 130px; flex-shrink: 0; }
    .kv-value { color: var(--text); word-break: break-word; }
    .kv-value a { color: var(--blue); text-decoration: none; }
    .kv-value a:hover { text-decoration: underline; }

    /* Wide card (full row) */
    .card-wide { grid-column: 1 / -1; }

    /* Client header */
    .client-header { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 20px 24px; margin-bottom: 24px; display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
    .client-header h1 { margin-bottom: 2px; }
    .client-meta { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }

    /* Breadcrumb */
    .breadcrumb { font-size: 13px; color: var(--text-dim); margin-bottom: 20px; }
    .breadcrumb a { color: var(--blue); text-decoration: none; }
    .breadcrumb a:hover { text-decoration: underline; }

    /* Alert strip */
    .alert { padding: 10px 16px; border-radius: 8px; font-size: 13px; margin-bottom: 16px; display: flex; align-items: center; gap: 10px; }
    .alert-red  { background: rgba(239,68,68,.1); border: 1px solid rgba(239,68,68,.3); color: var(--red); }
    .alert-amber{ background: rgba(234,179,8,.1); border: 1px solid rgba(234,179,8,.3); color: var(--yellow); }

    /* Dim text */
    .dim { color: var(--text-dim); }
    .muted { color: var(--text-muted); }

    /* Detail pages */
    .detail-table { width: 100%; border-collapse: collapse; background: var(--surface); border-radius: 10px; overflow: hidden; border: 1px solid var(--border); margin-top: 16px; }
    .detail-table th { background: var(--surface2); color: var(--text-dim); font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); cursor: pointer; user-select: none; }
    .detail-table th:hover { color: var(--text); }
    .detail-table td { padding: 10px 14px; border-bottom: 1px solid var(--border); font-size: 13px; vertical-align: middle; }
    .detail-table tr:last-child td { border-bottom: none; }
    .detail-table tr:hover td { background: var(--surface2); }
    .tag { display: inline-block; padding: 2px 8px; border-radius: 99px; font-size: 11px; font-weight: 600; }
    .tag-p1 { background: rgba(239,68,68,.15); color: var(--red); }
    .tag-p2 { background: rgba(234,179,8,.12); color: var(--yellow); }
    .tag-p3 { background: rgba(100,116,139,.12); color: var(--text-dim); }
    .tag-transactional { background: rgba(34,197,94,.12); color: var(--green); }
    .tag-commercial    { background: rgba(59,130,246,.12); color: var(--blue); }
    .tag-informational { background: rgba(167,139,250,.12); color: var(--purple); }
    .tag-navigational  { background: rgba(100,116,139,.12); color: var(--text-dim); }
    .tag-done   { background: rgba(34,197,94,.12); color: var(--green); }
    .tag-queued { background: rgba(234,179,8,.12); color: var(--yellow); }
    .tag-video  { background: rgba(239,68,68,.15); color: var(--red); }
    .section-title { font-size: 16px; font-weight: 700; margin-top: 28px; margin-bottom: 4px; }
    .section-sub { font-size: 13px; color: var(--text-dim); margin-bottom: 4px; }
    .search-box { background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 8px 12px; border-radius: 8px; font-size: 13px; width: 280px; outline: none; }
    .search-box:focus { border-color: var(--blue); }
    .filters { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
    .filter-btn { background: var(--surface2); border: 1px solid var(--border); color: var(--text-dim); padding: 5px 12px; border-radius: 6px; font-size: 12px; cursor: pointer; transition: all 0.15s; }
    .filter-btn:hover, .filter-btn.active { background: var(--blue-dim); border-color: var(--blue); color: white; }
    .card-link { text-decoration: none; color: inherit; display: flex; align-items: center; justify-content: space-between; }
    .card-link:hover .card-title { color: var(--blue); }
    .card-link .arrow { color: var(--text-muted); font-size: 12px; }
    .card-link:hover .arrow { color: var(--blue); }
  </style>
</head>
<body>
<nav>
  <span class="brand">RANK AI</span>
  {% for s in all_slugs %}
  <a href="/{{ s }}" class="nav-link {% if current == s %}active{% endif %}">{{ s }}</a>
  {% endfor %}
  <a href="/" class="nav-link {% if current == '__admin__' %}active{% endif %}">All Clients</a>
  <button class="refresh-btn" onclick="location.reload()">Refresh</button>
</nav>
{% block content %}{% endblock %}
</body>
</html>
"""

ADMIN_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
{% block content %}
<div class="page">
  <h1>Client Portfolio</h1>
  <p class="subtitle">{{ clients|length }} clients &mdash; click a row to view details</p>

  <table class="data-table">
    <thead>
      <tr>
        <th>#</th>
        <th>Client</th>
        <th>Domain</th>
        <th>Site</th>
        <th>Audit</th>
        <th style="text-align:center">Last Audit</th>
        <th style="text-align:center">Queue</th>
        <th style="text-align:center">Posts</th>
        <th style="text-align:center">Videos</th>
        <th style="text-align:center">Ads</th>
        <th style="text-align:center">GBP</th>
      </tr>
    </thead>
    <tbody>
    {% for c in clients %}
      <tr style="cursor:pointer" onclick="location.href='/{{ c.slug }}'">
        <td class="dim">{{ loop.index }}</td>
        <td><a href="/{{ c.slug }}">{{ c.display_name }}</a></td>
        <td class="dim">{{ c.domain }}</td>
        <td><span class="badge {{ c.site_class }}"><span class="dot">●</span> {{ c.site_label }}</span></td>
        <td>
          {% if c.verdict_label != '-' %}
          <span class="badge {{ c.verdict_class }}"><span class="dot">●</span> {{ c.verdict_label }}</span>
          {% else %}
          <span class="muted">—</span>
          {% endif %}
        </td>
        <td style="text-align:center" class="dim">{{ c.audit_age or '—' }}</td>
        <td style="text-align:center">
          {% if c.queue_count %}<span class="num">{{ c.queue_count }}</span>{% else %}<span class="num-zero">0</span>{% endif %}
        </td>
        <td style="text-align:center">
          {% if c.posts %}<span class="num">{{ c.posts }}</span>{% else %}<span class="num-zero">0</span>{% endif %}
        </td>
        <td style="text-align:center">
          {% if c.videos %}<span class="num">{{ c.videos }}</span>{% else %}<span class="num-zero">0</span>{% endif %}
        </td>
        <td style="text-align:center">
          {% if c.has_ads %}<span class="check-yes">✓</span>{% else %}<span class="check-no">—</span>{% endif %}
        </td>
        <td style="text-align:center">
          {% if c.has_gbp %}<span class="check-yes">✓</span>{% else %}<span class="check-no">—</span>{% endif %}
        </td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
""")

CLIENT_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
{% block content %}
<div class="page">
  <div class="breadcrumb"><a href="/">All Clients</a> / {{ c.display_name }}</div>

  {% if c.verdict == 'red' %}
  <div class="alert alert-red">&#9888; Audit verdict is RED — site has critical issues that need attention.</div>
  {% elif c.verdict == 'amber' %}
  <div class="alert alert-amber">&#9888; Audit verdict is Amber — some issues detected. Run an onsite audit for details.</div>
  {% endif %}

  <div class="client-header">
    <div>
      <h1>{{ c.display_name }}</h1>
      <div class="dim" style="margin-top:4px;font-size:13px">{{ c.domain }}</div>
      <div class="client-meta">
        <span class="badge {{ c.site_class }}"><span class="dot">●</span> {{ c.site_label }}</span>
        {% if c.verdict != None %}<span class="badge {{ c.verdict_class }}"><span class="dot">●</span> {{ c.verdict_label }}</span>{% endif %}
        <span class="badge status-dim">{{ c.tier }}</span>
      </div>
    </div>
  </div>

  <div class="client-grid">

    <!-- Website -->
    <div class="card">
      <div class="card-header"><span class="card-title">Website</span></div>
      <div class="card-body">
        <div class="kv"><span class="kv-label">URL</span><span class="kv-value"><a href="{{ c.live_url }}" target="_blank">{{ c.live_url }}</a></span></div>
        <div class="kv"><span class="kv-label">GitHub</span><span class="kv-value"><a href="https://github.com/{{ c.github_repo }}" target="_blank">{{ c.github_repo or '—' }}</a></span></div>
        <div class="kv"><span class="kv-label">Pages project</span><span class="kv-value">{{ c.pages_project or '—' }}</span></div>
        <div class="kv"><span class="kv-label">Pages count</span><span class="kv-value">{{ c.url_count or '—' }}</span></div>
        <div class="kv"><span class="kv-label">Last deploy</span><span class="kv-value">{{ c.last_deploy or '—' }}</span></div>
        <div class="kv"><span class="kv-label">Scaffolded</span><span class="kv-value">{{ c.scaffolded_at or '—' }}</span></div>
        <div class="kv"><span class="kv-label">Template</span><span class="kv-value">{{ c.template or '—' }}</span></div>
      </div>
    </div>

    <!-- Onsite Audit -->
    <div class="card">
      <div class="card-header">
        <a href="/{{ c.slug }}/audit" class="card-link"><span class="card-title">Onsite Audit</span><span class="arrow">View →</span></a>
        {% if c.verdict != None %}<span class="badge {{ c.verdict_class }}">{{ c.verdict_label }}</span>{% endif %}
      </div>
      <div class="card-body">
        <div class="kv"><span class="kv-label">Last run</span><span class="kv-value">{{ c.audit_age or '—' }}</span></div>
        <div class="kv"><span class="kv-label">Report</span><span class="kv-value">{{ c.audit_report or '—' }}</span></div>
        <div class="kv"><span class="kv-label">Critical issues</span><span class="kv-value" style="color:{% if c.critical_issues %}var(--red){% else %}var(--text-dim){% endif %}">{{ c.critical_issues }}</span></div>
        <div class="kv"><span class="kv-label">High issues</span><span class="kv-value" style="color:{% if c.high_issues %}var(--yellow){% else %}var(--text-dim){% endif %}">{{ c.high_issues }}</span></div>
        <div class="kv"><span class="kv-label">Medium issues</span><span class="kv-value">{{ c.medium_issues }}</span></div>
        <div class="kv"><span class="kv-label">Audited origin</span><span class="kv-value">{% if c.audited_origin %}<a href="{{ c.audited_origin }}" target="_blank">{{ c.audited_origin }}</a>{% else %}—{% endif %}</span></div>
      </div>
    </div>

    <!-- Blog & Content -->
    <div class="card">
      <div class="card-header"><a href="/{{ c.slug }}/blog" class="card-link"><span class="card-title">Blog &amp; Content</span><span class="arrow">View all →</span></a></div>
      <div class="card-body">
        <div class="kv"><span class="kv-label">Posts live</span><span class="kv-value num">{{ c.posts }}</span></div>
        <div class="kv"><span class="kv-label">Videos live</span><span class="kv-value num">{{ c.videos }}</span></div>
        <div class="kv"><span class="kv-label">Queue depth</span><span class="kv-value num" style="color:{% if c.queue_count > 0 %}var(--yellow){% else %}var(--text-dim){% endif %}">{{ c.queue_count }}</span></div>
        <div class="kv"><span class="kv-label">Next to write</span><span class="kv-value">{{ c.next_to_write or '—' }}</span></div>
        <div class="kv"><span class="kv-label">Last refresh</span><span class="kv-value">{{ c.last_refresh or '—' }}</span></div>
        <div class="kv"><span class="kv-label">Last action</span><span class="kv-value">{{ c.refresh_action or '—' }}</span></div>
      </div>
    </div>

    <!-- Keyword Research -->
    <div class="card">
      <div class="card-header"><a href="/{{ c.slug }}/keywords" class="card-link"><span class="card-title">Keyword Research</span><span class="arrow">View all →</span></a></div>
      <div class="card-body">
        <div class="kv"><span class="kv-label">Bank size</span><span class="kv-value num">{{ c.kw_bank_size }} keywords</span></div>
        <div class="kv"><span class="kv-label">Seeds researched</span><span class="kv-value num">{{ c.kw_seeds_done }}</span></div>
        <div class="kv"><span class="kv-label">Last run</span><span class="kv-value">{{ c.kw_last_run or '—' }}</span></div>
        <div class="kv"><span class="kv-label">Priority 1 in queue</span><span class="kv-value num">{{ c.kw_p1 }}</span></div>
        <div class="kv"><span class="kv-label">Priority 2 in bank</span><span class="kv-value num">{{ c.kw_p2 }}</span></div>
      </div>
    </div>

    <!-- GSC -->
    <div class="card">
      <div class="card-header"><span class="card-title">Google Search Console</span></div>
      <div class="card-body">
        <div class="kv"><span class="kv-label">Property</span><span class="kv-value">{{ c.gsc_property or '—' }}</span></div>
        <div class="kv"><span class="kv-label">Verified</span><span class="kv-value">{% if c.gsc_verified %}<span class="check-yes">✓</span>{% else %}<span class="check-no">—</span>{% endif %}</span></div>
        <div class="kv"><span class="kv-label">Verified at</span><span class="kv-value">{{ c.gsc_verified_at or '—' }}</span></div>
        <div class="kv"><span class="kv-label">Sitemap</span><span class="kv-value">{% if c.gsc_sitemap %}<a href="{{ c.gsc_sitemap }}" target="_blank">{{ c.gsc_sitemap }}</a>{% else %}—{% endif %}</span></div>
      </div>
    </div>

    <!-- GBP Auth -->
    <div class="card">
      <div class="card-header"><span class="card-title">Google Business Profile</span></div>
      <div class="card-body">
        <div class="kv"><span class="kv-label">Auth token</span><span class="kv-value">{% if c.has_gbp %}<span class="check-yes">✓ Connected</span>{% else %}<span class="check-warn">run gbp_manager.py auth</span>{% endif %}</span></div>
        <div class="kv"><span class="kv-label">Location pinned</span><span class="kv-value">{% if c.gbp_location %}<span class="check-yes">✓</span>{% else %}<span class="check-warn">run gbp_manager.py locations</span>{% endif %}</span></div>
        <div class="kv"><span class="kv-label">Location name</span><span class="kv-value">{{ c.gbp_location or '—' }}</span></div>
      </div>
    </div>

    <!-- Google Ads (wide) -->
    <div class="card card-wide">
      <div class="card-header">
        <span class="card-title">Google Ads</span>
        {% if c.has_ads %}<span class="badge status-live">Connected</span>{% else %}<span class="badge status-dim">Not connected</span>{% endif %}
      </div>
      <div class="card-body" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:0">
        <div class="kv"><span class="kv-label">Auth token</span><span class="kv-value">{% if c.has_ads %}<span class="check-yes">✓</span>{% else %}<span class="check-warn">run ads_manager.py auth</span>{% endif %}</span></div>
        <div class="kv"><span class="kv-label">Customer ID</span><span class="kv-value">{{ c.ads_cid or '—' }}</span></div>
        <div class="kv"><span class="kv-label">Campaigns</span><span class="kv-value">{% if c.ads_campaigns %}<span class="num">{{ c.ads_campaigns }}</span>{% else %}<span class="dim">run ads_manager.py scaffold</span>{% endif %}</span></div>
        <div class="kv"><span class="kv-label">Ad groups</span><span class="kv-value num">{{ c.ads_ad_groups or '—' }}</span></div>
        <div class="kv" style="grid-column:1/-1"><span class="kv-label">Live metrics</span><span class="kv-value dim">Use <code>--live</code> flag in terminal for 7-day data</span></div>
      </div>
    </div>

  </div>
</div>
{% endblock %}
""")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def admin():
    slugs = list_client_slugs()
    clients = []
    for slug in slugs:
        rec = load_client(slug)
        queue = load_content_queue(slug)
        posts, videos = count_blog_posts(slug)
        site_label, site_class = build_status_info(rec.get("build_status"))
        verdict_label, verdict_class = verdict_info(rec.get("audit", {}).get("last_audit_verdict"))
        clients.append({
            "slug": slug,
            "display_name": rec.get("display_name", slug),
            "domain": rec.get("domain", "-"),
            "site_label": site_label,
            "site_class": site_class,
            "verdict_label": verdict_label,
            "verdict_class": verdict_class,
            "audit_age": days_ago(rec.get("audit", {}).get("last_audit_at")),
            "queue_count": len(queue.get("items", [])),
            "posts": posts,
            "videos": videos,
            "has_ads": (CLIENTS_DIR / slug / ".ads-token.json").exists(),
            "has_gbp": (CLIENTS_DIR / slug / ".gbp-token.json").exists(),
        })
    return render_template_string(ADMIN_HTML,
        clients=clients,
        all_slugs=slugs,
        current="__admin__",
    )


@app.route("/<slug>")
def client_view(slug: str):
    slugs = list_client_slugs()
    if slug not in slugs:
        return redirect(url_for("admin"))

    rec = load_client(slug)
    audit_rec = rec.get("audit", {})
    build = rec.get("build", {})
    plan = rec.get("plan", {})
    gsc = rec.get("gsc", {})
    audit = load_onsite_audit(slug)
    queue = load_content_queue(slug)
    kb = load_keyword_bank(slug)
    ads_structure = load_ads_structure(slug)
    posts, videos = count_blog_posts(slug)

    # Audit issues
    url_scores = audit.get("url_scores", {})
    issue_counts: dict[str, int] = {}
    for url_data in url_scores.values():
        for issue in url_data.get("issues", []):
            sev = issue.get("severity", "low")
            issue_counts[sev] = issue_counts.get(sev, 0) + 1

    # Site URL
    build_status = rec.get("build_status")
    domain = rec.get("domain", "-")
    pages_proj = build.get("pages_project", "-")
    pages_url = f"https://{pages_proj}.pages.dev" if pages_proj != "-" else "#"
    live_url = f"https://{domain}/" if build_status == "cut_over" else pages_url

    site_label, site_class = build_status_info(build_status)
    verdict = audit_rec.get("last_audit_verdict")
    verdict_label, verdict_class = verdict_info(verdict)

    # Keyword bank
    kb_keywords = kb.get("keywords", [])
    seeds_done = kb.get("seeds_researched", [])
    last_kw = max((s.get("last_researched", "") for s in seeds_done), default=None) if seeds_done else None

    # Queue
    queue_items = queue.get("items", [])
    next_item = queue_items[0] if queue_items else None
    next_title = (next_item.get("title") or next_item.get("keyword", ""))[:50] if next_item else None

    # Ads
    ads_cid = (
        rec.get("brand", {}).get("google_ads_customer_id")
        or rec.get("google_ads", {}).get("customer_id")
    )
    ads_campaigns = len(ads_structure.get("campaigns", {}))
    ads_ad_groups = len(ads_structure.get("ad_groups", {}))

    c = {
        "slug": slug,
        "display_name": rec.get("display_name", slug),
        "domain": domain,
        "tier": rec.get("tier", "-"),
        "site_label": site_label,
        "site_class": site_class,
        "verdict": verdict,
        "verdict_label": verdict_label,
        "verdict_class": verdict_class,
        "live_url": live_url,
        "github_repo": build.get("github_repo"),
        "pages_project": pages_proj,
        "url_count": plan.get("url_count"),
        "last_deploy": days_ago(build.get("last_pushed_main_at")),
        "scaffolded_at": days_ago(build.get("scaffolded_at")),
        "template": f"{plan.get('template', '-')} v{plan.get('template_version', '-')}",
        "audit_age": days_ago(audit_rec.get("last_audit_at")),
        "audit_report": audit_rec.get("last_audit_report_path", "").split("/")[-1] or None,
        "critical_issues": issue_counts.get("critical", 0),
        "high_issues": issue_counts.get("high", 0),
        "medium_issues": issue_counts.get("medium", 0),
        "audited_origin": audit_rec.get("live_origin_audited"),
        "posts": posts,
        "videos": videos,
        "queue_count": len(queue_items),
        "next_to_write": next_title,
        "last_refresh": days_ago(rec.get("refresh", {}).get("last_run_at")),
        "refresh_action": rec.get("refresh", {}).get("last_run_top_action"),
        "kw_bank_size": len(kb_keywords),
        "kw_seeds_done": len(seeds_done),
        "kw_last_run": days_ago(last_kw),
        "kw_p1": sum(1 for k in kb_keywords if k.get("priority") == 1),
        "kw_p2": sum(1 for k in kb_keywords if k.get("priority") == 2),
        "gsc_property": gsc.get("property_url"),
        "gsc_verified": bool(gsc.get("verified_at")),
        "gsc_verified_at": days_ago(gsc.get("verified_at")),
        "gsc_sitemap": gsc.get("sitemap_url"),
        "has_ads": (CLIENTS_DIR / slug / ".ads-token.json").exists(),
        "ads_cid": ads_cid,
        "ads_campaigns": ads_campaigns or None,
        "ads_ad_groups": ads_ad_groups or None,
        "has_gbp": (CLIENTS_DIR / slug / ".gbp-token.json").exists(),
        "gbp_location": rec.get("gbp_location_name"),
    }
    return render_template_string(CLIENT_HTML, c=c, all_slugs=slugs, current=slug)


# ---------------------------------------------------------------------------
# Detail routes
# ---------------------------------------------------------------------------

DETAIL_BLOG_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
{% block content %}
<div class="page">
  <div class="breadcrumb"><a href="/">All Clients</a> / <a href="/{{ slug }}">{{ display_name }}</a> / Blog &amp; Content</div>
  <h1>Blog &amp; Content</h1>
  <p class="subtitle">{{ pending_items|length }} pending &bull; {{ written_items|length }} written &bull; {{ posts|length }} posts on disk</p>

  <!-- Pending Queue -->
  <div class="section-title">Up Next <span class="dim" style="font-size:13px;font-weight:400">({{ pending_items|length }} to write)</span></div>
  <div class="section-sub">Topics approved for writing, in priority order. Write P1s first.</div>
  {% if pending_items %}
  <div class="filters">
    <input class="search-box" id="q-search" placeholder="Filter..." oninput="filterTable('queue-table','q-search')">
  </div>
  <table class="detail-table" id="queue-table">
    <thead><tr>
      <th onclick="sortTable('queue-table',0)">#</th>
      <th onclick="sortTable('queue-table',1)">Keyword / Topic</th>
      <th onclick="sortTable('queue-table',2)">Suggested Title</th>
      <th onclick="sortTable('queue-table',3)">Intent</th>
      <th onclick="sortTable('queue-table',4)" style="text-align:right">Volume</th>
      <th onclick="sortTable('queue-table',5)" style="text-align:right">KD</th>
      <th onclick="sortTable('queue-table',6)">Added</th>
      <th onclick="sortTable('queue-table',7)">Scheduled</th>
    </tr></thead>
    <tbody>
    {% for item in pending_items %}
    <tr>
      <td class="dim">{{ loop.index }}</td>
      <td style="font-weight:500">{{ item.primary_keyword or '—' }}</td>
      <td style="color:var(--text-dim);font-size:12px">{{ item.suggested_title or '—' }}</td>
      <td>{% if item.intent %}<span class="tag tag-{{ item.intent }}">{{ item.intent }}</span>{% else %}<span class="muted">—</span>{% endif %}</td>
      <td class="num" style="text-align:right">{{ item.volume or '—' }}</td>
      <td class="num" style="text-align:right">{{ item.kd or '—' }}</td>
      <td class="dim">{{ item.queued_at[:10] if item.queued_at else '—' }}</td>
      <td class="dim">{{ item.scheduled_for or '—' }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p class="dim" style="margin-top:12px">Nothing pending — run <code>rank-ai-keyword-researcher</code> to add topics.</p>
  {% endif %}

  <!-- Written (published) -->
  <div class="section-title" style="margin-top:32px">Written Posts <span class="dim" style="font-size:13px;font-weight:400">({{ posts|length }} published)</span></div>
  <div class="section-sub">Posts that have been written and are live on the site.</div>
  {% if posts %}
  <div class="filters">
    <input class="search-box" id="p-search" placeholder="Filter posts..." oninput="filterTable('posts-table','p-search')">
    <button class="filter-btn active" onclick="filterTag('',this)">All</button>
    <button class="filter-btn" onclick="filterTag('video',this)">Has Video</button>
  </div>
  <table class="detail-table" id="posts-table">
    <thead><tr>
      <th onclick="sortTable('posts-table',0)">Title</th>
      <th onclick="sortTable('posts-table',1)">Published</th>
      <th onclick="sortTable('posts-table',2)">Written</th>
      <th onclick="sortTable('posts-table',3)">Intent</th>
      <th onclick="sortTable('posts-table',4)" style="text-align:right">Words</th>
      <th onclick="sortTable('posts-table',5)">Video</th>
      <th onclick="sortTable('posts-table',6)">URL</th>
    </tr></thead>
    <tbody>
    {% for p in posts %}
    <tr>
      <td style="font-weight:500">{{ p.title }}</td>
      <td class="dim">{{ p.published_at or '—' }}</td>
      <td class="dim">{{ p.written_at or '—' }}</td>
      <td>{% if p.search_intent %}<span class="tag tag-{{ p.search_intent }}">{{ p.search_intent }}</span>{% else %}<span class="muted">—</span>{% endif %}</td>
      <td class="num" style="text-align:right">{{ p.word_count }}</td>
      <td>{% if p.youtube_id %}<span class="tag tag-video">▶ {{ p.youtube_id[:11] }}</span>{% else %}<span class="muted">—</span>{% endif %}</td>
      <td style="font-size:11px">{% if p.post_url %}<a href="{{ p.post_url }}" target="_blank">{{ p.post_url }}</a>{% else %}<span class="muted">/blog/{{ p.slug }}/</span>{% endif %}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p class="dim" style="margin-top:12px">No published posts found.</p>
  {% endif %}
</div>
<script>
function filterTable(tableId, inputId) {
  const q = document.getElementById(inputId).value.toLowerCase();
  document.querySelectorAll('#'+tableId+' tbody tr').forEach(r => {
    r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
}
function filterTag(val, btn) {
  document.querySelectorAll('.filters .filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#posts-table tbody tr').forEach(r => {
    if (!val) { r.style.display = ''; return; }
    if (val === 'video') r.style.display = r.textContent.includes('▶') ? '' : 'none';
    else r.style.display = '';
  });
}
function sortTable(tableId, col) {
  const table = document.getElementById(tableId);
  const rows = Array.from(table.querySelectorAll('tbody tr'));
  const asc = table.dataset.sortCol == col && table.dataset.sortDir == 'asc';
  rows.sort((a, b) => {
    const av = a.cells[col]?.textContent.trim() || '';
    const bv = b.cells[col]?.textContent.trim() || '';
    const an = parseFloat(av), bn = parseFloat(bv);
    if (!isNaN(an) && !isNaN(bn)) return asc ? bn - an : an - bn;
    return asc ? bv.localeCompare(av) : av.localeCompare(bv);
  });
  table.dataset.sortCol = col; table.dataset.sortDir = asc ? 'desc' : 'asc';
  rows.forEach(r => table.querySelector('tbody').appendChild(r));
}
</script>
{% endblock %}
""")

DETAIL_KEYWORDS_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
{% block content %}
<div class="page">
  <div class="breadcrumb"><a href="/">All Clients</a> / <a href="/{{ slug }}">{{ display_name }}</a> / Keyword Research</div>
  <h1>Keyword Bank</h1>
  <p class="subtitle">{{ keywords|length }} keywords across {{ seeds_done }} seeds researched</p>

  <div class="filters">
    <input class="search-box" id="kw-search" placeholder="Filter keywords..." oninput="filterTable('kw-table','kw-search')">
    <button class="filter-btn active" onclick="filterCol('kw-table',2,'',this)">All</button>
    <button class="filter-btn" onclick="filterCol('kw-table',2,'P1',this)">P1</button>
    <button class="filter-btn" onclick="filterCol('kw-table',2,'P2',this)">P2</button>
    <button class="filter-btn" onclick="filterCol('kw-table',2,'P3',this)">P3</button>
    <button class="filter-btn" onclick="filterCol('kw-table',3,'transactional',this)">Transactional</button>
    <button class="filter-btn" onclick="filterCol('kw-table',3,'informational',this)">Informational</button>
  </div>
  <table class="detail-table" id="kw-table">
    <thead><tr>
      <th onclick="sortTable(0)">Keyword</th>
      <th onclick="sortTable(1)">City</th>
      <th onclick="sortTable(2)">Priority</th>
      <th onclick="sortTable(3)">Intent</th>
      <th onclick="sortTable(4)" style="text-align:right">Volume</th>
      <th onclick="sortTable(5)" style="text-align:right">Difficulty</th>
      <th onclick="sortTable(6)">Seed</th>
      <th onclick="sortTable(7)">Researched</th>
    </tr></thead>
    <tbody>
    {% for kw in keywords %}
    <tr>
      <td style="font-weight:500">{{ kw.keyword }}</td>
      <td class="dim">{{ kw.city or '—' }}</td>
      <td><span class="tag tag-p{{ kw.priority }}">P{{ kw.priority }}</span></td>
      <td>{% if kw.intent %}<span class="tag tag-{{ kw.intent }}">{{ kw.intent }}</span>{% else %}<span class="muted">—</span>{% endif %}</td>
      <td class="num" style="text-align:right">{{ kw.search_volume or '—' }}</td>
      <td class="num" style="text-align:right">{{ kw.difficulty or '—' }}</td>
      <td class="dim">{{ kw.seed or '—' }}</td>
      <td class="dim">{{ kw.last_researched[:10] if kw.last_researched else '—' }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
<script>
function filterTable(tableId, inputId) {
  const q = document.getElementById(inputId).value.toLowerCase();
  document.querySelectorAll('#'+tableId+' tbody tr').forEach(r => {
    r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
}
function filterCol(tableId, col, val, btn) {
  document.querySelectorAll('.filters .filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#'+tableId+' tbody tr').forEach(r => {
    r.style.display = (!val || r.cells[col]?.textContent.includes(val)) ? '' : 'none';
  });
}
function sortTable(col) {
  const table = document.getElementById('kw-table');
  const rows = Array.from(table.querySelectorAll('tbody tr'));
  const asc = table.dataset.sortCol == col && table.dataset.sortDir == 'asc';
  rows.sort((a, b) => {
    const av = a.cells[col]?.textContent.trim() || '';
    const bv = b.cells[col]?.textContent.trim() || '';
    const an = parseFloat(av), bn = parseFloat(bv);
    if (!isNaN(an) && !isNaN(bn)) return asc ? bn - an : an - bn;
    return asc ? bv.localeCompare(av) : av.localeCompare(bv);
  });
  table.dataset.sortCol = col; table.dataset.sortDir = asc ? 'desc' : 'asc';
  rows.forEach(r => table.querySelector('tbody').appendChild(r));
}
</script>
{% endblock %}
""")

DETAIL_AUDIT_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
{% block content %}
<div class="page">
  <div class="breadcrumb"><a href="/">All Clients</a> / <a href="/{{ slug }}">{{ display_name }}</a> / Onsite Audit</div>
  <h1>Onsite Audit</h1>
  {% if last_run %}
  <p class="subtitle">Last run {{ last_run }} &mdash; verdict: <span class="badge {{ verdict_class }}">{{ verdict_label }}</span></p>
  {% else %}
  <p class="subtitle">No audit run yet. Use <code>rank-ai-onsite-audit</code> to run one.</p>
  {% endif %}

  {% if url_scores %}
  <table class="detail-table" id="audit-table">
    <thead><tr>
      <th>URL</th>
      <th>Verdict</th>
      <th style="text-align:right">Perf</th>
      <th style="text-align:right">SEO</th>
      <th style="text-align:right">A11y</th>
      <th style="text-align:right">Best Practices</th>
      <th>Issues</th>
    </tr></thead>
    <tbody>
    {% for url, data in url_scores.items() %}
    <tr>
      <td style="font-size:12px;color:var(--text-dim)">{{ url }}</td>
      <td>{% set v = data.verdict %}
        <span class="badge {% if v == 'green' %}verdict-green{% elif v == 'amber' %}verdict-amber{% elif v == 'red' %}verdict-red{% else %}status-dim{% endif %}">{{ v or '—' }}</span>
      </td>
      <td class="num" style="text-align:right">{{ data.scores.performance if data.scores else '—' }}</td>
      <td class="num" style="text-align:right">{{ data.scores.seo if data.scores else '—' }}</td>
      <td class="num" style="text-align:right">{{ data.scores.accessibility if data.scores else '—' }}</td>
      <td class="num" style="text-align:right">{{ data.scores.best_practices if data.scores else '—' }}</td>
      <td class="dim">{{ data.issues|length if data.issues else 0 }} issue(s)</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p class="dim" style="margin-top:16px">No URL scores available in audit state file.</p>
  {% endif %}
</div>
{% endblock %}
""")


@app.route("/<slug>/blog")
def blog_detail(slug: str):
    slugs = list_client_slugs()
    if slug not in slugs:
        return redirect(url_for("admin"))
    rec = load_client(slug)
    queue = load_content_queue(slug)
    posts = load_blog_posts(slug)

    all_items = queue.get("items", [])
    pending_items = [i for i in all_items if i.get("status") == "queued"]
    written_items = [i for i in all_items if i.get("status") in ("written", "published")]

    # Build lookup: suggested_slug -> queue item (for written_at + post_url)
    written_lookup: dict[str, dict] = {}
    for item in written_items:
        key = item.get("suggested_slug") or item.get("id", "").split("-", 3)[-1]
        written_lookup[key] = item

    # Enrich posts with queue data
    for post in posts:
        match = written_lookup.get(post["slug"])
        if match:
            post["written_at"] = (match.get("written_at") or "")[:10]
            post["post_url"] = match.get("post_url")
        else:
            post.setdefault("written_at", None)
            post.setdefault("post_url", None)

    return render_template_string(DETAIL_BLOG_HTML,
        slug=slug,
        display_name=rec.get("display_name", slug),
        pending_items=pending_items,
        written_items=written_items,
        posts=posts,
        all_slugs=slugs,
        current=slug,
    )


@app.route("/<slug>/keywords")
def keywords_detail(slug: str):
    slugs = list_client_slugs()
    if slug not in slugs:
        return redirect(url_for("admin"))
    rec = load_client(slug)
    kb = load_keyword_bank(slug)
    keywords = sorted(
        kb.get("keywords", []),
        key=lambda k: (k.get("priority", 9), -(k.get("search_volume") or 0))
    )
    seeds_done = kb.get("seeds_researched", [])
    return render_template_string(DETAIL_KEYWORDS_HTML,
        slug=slug,
        display_name=rec.get("display_name", slug),
        keywords=keywords,
        seeds_done=len(seeds_done),
        all_slugs=slugs,
        current=slug,
    )


@app.route("/<slug>/audit")
def audit_detail(slug: str):
    slugs = list_client_slugs()
    if slug not in slugs:
        return redirect(url_for("admin"))
    rec = load_client(slug)
    audit = load_onsite_audit(slug)
    audit_rec = rec.get("audit", {})
    verdict = audit_rec.get("last_audit_verdict")
    verdict_label, verdict_class = verdict_info(verdict)
    return render_template_string(DETAIL_AUDIT_HTML,
        slug=slug,
        display_name=rec.get("display_name", slug),
        last_run=days_ago(audit_rec.get("last_audit_at")),
        verdict_label=verdict_label,
        verdict_class=verdict_class,
        url_scores=audit.get("url_scores", {}),
        all_slugs=slugs,
        current=slug,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Rank AI Web Dashboard")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--no-open", action="store_true", help="Don't auto-open browser")
    args = parser.parse_args()

    if not args.no_open:
        Timer(0.8, lambda: webbrowser.open(f"http://localhost:{args.port}")).start()

    print(f"  Rank AI Dashboard running at http://localhost:{args.port}")
    print(f"  Press Ctrl+C to stop.\n")
    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
