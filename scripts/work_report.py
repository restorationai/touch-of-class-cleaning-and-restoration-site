#!/usr/bin/env python3
"""work_report.py — the client-facing work report (Santino 2026-08-01:
"every action we take is being documented ... every tiny movement we make
should be recorded as a line item").

Aggregates EVERYTHING we did for a client in a date range into one
plain-English markdown report, grouped by week then by category, with a
counts summary at the top. Written in a voice the CLIENT can read directly.

Sources (one query per table, each fail-soft so a schema drift in one table
never kills the whole report):
  marketing_work_log          site deploys, keyword research, citations
                              audits, nightly routine sweeps, outreach texts
  marketing_gbp_posts         Google Business Profile posts (company_id)
  marketing_gbp_changes       GBP optimization changes (services, categories,
                              description, cover photo ...)
  browser_agent_actions       directory listings the browser agent created
                              (outcome='done' + live=true only)
  marketing_backlinks         backlinks that flipped to live in range
  review_requests             review invitations sent (last_sent_at in range,
                              aggregated per day)
  marketing_content_items     blog posts published (status='published')
  marketing_videos            YouTube videos published
  marketing_press_releases    quarterly press releases drafted/published

Deliberately NOT aggregated:
  marketing_setup_ledger      setup_ledger._upsert re-stamps updated_at on
                              EVERY nightly sweep, so "flipped to done in
                              range" is unrecoverable — done items would
                              replay in every monthly report. If a done_at
                              column ever lands, add it back.
  marketing_gbp_changes rows with change_type='post' — those mirror
                              marketing_gbp_posts (double write on the read
                              side).

Usage:
  python3 scripts/work_report.py --slug narestco
  python3 scripts/work_report.py --slug narestco --since 2026-07-01 --until 2026-07-31
  python3 scripts/work_report.py --all

Output: clients/{slug}/reports/work-report-{since}-to-{until}.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = ROOT / "clients"
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from client_ops_sync import _sb  # noqa: E402
from work_log import company_id_for_slug  # noqa: E402


# ---------------------------------------------------------------- categories
# internal key -> (display label, display order, at-a-glance noun template)
CATEGORIES: dict[str, tuple[str, int, str]] = {
    "site":             ("Website",                              1, "website build and deploy action{s}"),
    "content":          ("Content published",                    2, "blog post{s} published"),
    "video":            ("Videos",                               3, "YouTube video{s} published"),
    "gbp-post":         ("Google Business Profile posts",        4, "Google Business Profile post{s} published"),
    "gbp-change":       ("Google Business Profile optimization", 5, "Google listing optimization{s}"),
    "citations":        ("Directory listings and citations",     6, "directory listing action{s}"),
    "backlinks":        ("Backlinks",                            7, "new backlink{s} confirmed live"),
    "keyword-research": ("Keyword research",                     8, "keyword research refresh{es}"),
    "press":            ("Press releases",                       9, "press release{s} prepared"),
    "reviews":          ("Review campaign",                     10, "review invitation{s} sent"),
    "outreach":         ("Communication",                       11, "coordination message{s} from our team"),
    "setup":            ("Account setup",                       12, "setup item{s} completed"),
    "routine":          ("Routine monitoring",                  13, "automated account checkup{s}"),
}


def clean(text: str, limit: int = 140) -> str:
    """House style for client-facing text: no em/en dashes, single-line,
    truncated on a word boundary."""
    text = re.sub(r"\s*[—–]\s*", ", ", str(text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + " ..."
    return text


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    # Python 3.9 fromisoformat requires exactly 3 or 6 fractional digits;
    # Postgres emits 1-6 (browser_agent rows carry 5). Pad to 6.
    s = re.sub(r"\.(\d{1,6})", lambda m: "." + m.group(1).ljust(6, "0"), s, count=1)
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _rows(path: str) -> list[dict]:
    return _sb("GET", path, prefer="return=representation") or []


def _range_filter(col: str, since: date, until: date) -> str:
    """PostgREST range filter, until-inclusive."""
    lo = f"{since.isoformat()}T00:00:00Z"
    hi = f"{(until + timedelta(days=1)).isoformat()}T00:00:00Z"
    return f"&{col}=gte.{lo}&{col}=lt.{hi}"


# ---------------------------------------------------------------- collectors
# Each returns a list of events: {"when": datetime, "cat": key, "text": str}.
# Wrapped by collect() so one bad query (wrong column, RLS drift) degrades to
# a printed warning, never a dead report.


def ev(when: datetime | None, cat: str, text: str) -> dict | None:
    return {"when": when, "cat": cat, "text": text} if when else None


def from_work_log(cid: str, since: date, until: date) -> list[dict]:
    out = []
    for r in _rows(f"/rest/v1/marketing_work_log?company_id=eq.{cid}"
                   f"&select=ts,category,action,detail{_range_filter('ts', since, until)}"
                   "&order=ts.asc&limit=1000"):
        e = ev(_parse_ts(r.get("ts")), r.get("category") or "other",
               clean(r.get("detail") or r.get("action") or "", 200))
        if e:
            out.append(e)
    return out


def from_gbp_posts(cid: str, since: date, until: date) -> list[dict]:
    out = []
    for r in _rows(f"/rest/v1/marketing_gbp_posts?company_id=eq.{cid}"
                   f"&select=posted_at,topic,summary{_range_filter('posted_at', since, until)}"
                   "&order=posted_at.asc&limit=500"):
        topic = (r.get("topic") or "update").replace("_", " ")
        e = ev(_parse_ts(r.get("posted_at")), "gbp-post",
               f"Google post published ({topic}): \"{clean(r.get('summary'), 110)}\"")
        if e:
            out.append(e)
    return out


def from_gbp_changes(cid: str, since: date, until: date) -> list[dict]:
    out = []
    # change_type=post rows mirror marketing_gbp_posts — excluded here so a
    # post never shows up twice in the same report.
    for r in _rows(f"/rest/v1/marketing_gbp_changes?company_id=eq.{cid}"
                   "&change_type=neq.post"
                   f"&select=changed_at,change_type,summary{_range_filter('changed_at', since, until)}"
                   "&order=changed_at.asc&limit=500"):
        e = ev(_parse_ts(r.get("changed_at")), "gbp-change",
               clean(r.get("summary") or r.get("change_type"), 160))
        if e:
            out.append(e)
    return out


_PLATFORM_PRETTY = {"houzz": "Houzz", "porch": "Porch", "homeguide": "HomeGuide",
                    "bbb": "the BBB", "bing": "Bing Places", "apple": "Apple Maps",
                    "nextdoor": "Nextdoor", "yelp": "Yelp", "facebook": "Facebook"}


def from_browser_agent(cid: str, since: date, until: date) -> list[dict]:
    out = []
    for r in _rows(f"/rest/v1/browser_agent_actions?company_id=eq.{cid}"
                   "&outcome=eq.done&live=is.true"
                   f"&select=created_at,playbook,action,detail{_range_filter('created_at', since, until)}"
                   "&order=created_at.asc&limit=500"):
        action = r.get("action") or ""
        playbook = r.get("playbook") or ""
        platform = _PLATFORM_PRETTY.get(action.split("-")[0].lower())
        if playbook == "bing-places":
            text = "Bing Places business listing created and synced from your Google listing."
        elif action.endswith("-create") and platform:
            text = f"New business listing created for you on {platform}."
        else:
            text = clean(r.get("detail") or f"{playbook}: {action}", 160)
        e = ev(_parse_ts(r.get("created_at")), "citations", text)
        if e:
            out.append(e)
    return out


def from_backlinks(cid: str, since: date, until: date) -> list[dict]:
    out = []
    for r in _rows(f"/rest/v1/marketing_backlinks?company_id=eq.{cid}"
                   "&status=eq.live"
                   f"&select=label,last_checked_at{_range_filter('last_checked_at', since, until)}"
                   "&order=last_checked_at.asc&limit=200"):
        e = ev(_parse_ts(r.get("last_checked_at")), "backlinks",
               f"Backlink confirmed live: {clean(r.get('label'), 90)} now links to your website.")
        if e:
            out.append(e)
    return out


def from_review_requests(cid: str, since: date, until: date) -> list[dict]:
    """One aggregated line per day (individual sends would drown the report)."""
    per_day: dict[date, int] = {}
    for r in _rows(f"/rest/v1/review_requests?company_id=eq.{cid}"
                   f"&select=last_sent_at{_range_filter('last_sent_at', since, until)}"
                   "&limit=2000"):
        ts = _parse_ts(r.get("last_sent_at"))
        if ts:
            per_day[ts.date()] = per_day.get(ts.date(), 0) + 1
    out = []
    for d, n in sorted(per_day.items()):
        when = datetime(d.year, d.month, d.day, 12, tzinfo=timezone.utc)
        out.append({"when": when, "cat": "reviews", "n": n,
                    "text": f"Review invitation{'s' if n != 1 else ''} sent to "
                            f"{n} past customer{'s' if n != 1 else ''}."})
    return out


def from_content_items(cid: str, since: date, until: date) -> list[dict]:
    out = []
    for r in _rows(f"/rest/v1/marketing_content_items?company_id=eq.{cid}"
                   "&status=eq.published"
                   f"&select=title,live_url,published_at{_range_filter('published_at', since, until)}"
                   "&order=published_at.asc&limit=200"):
        text = f"Blog post published: \"{clean(r.get('title'), 100)}\""
        if r.get("live_url"):
            text += f" ({r['live_url']})"
        e = ev(_parse_ts(r.get("published_at")), "content", text)
        if e:
            out.append(e)
    return out


def from_videos(cid: str, since: date, until: date) -> list[dict]:
    out = []
    for r in _rows(f"/rest/v1/marketing_videos?company_id=eq.{cid}"
                   f"&select=title,url,created_at{_range_filter('created_at', since, until)}"
                   "&order=created_at.asc&limit=100"):
        text = f"YouTube video published: \"{clean(r.get('title'), 100)}\""
        if r.get("url"):
            text += f" ({r['url']})"
        e = ev(_parse_ts(r.get("created_at")), "video", text)
        if e:
            out.append(e)
    return out


def from_press_releases(cid: str, since: date, until: date) -> list[dict]:
    out = []
    for r in _rows(f"/rest/v1/marketing_press_releases?company_id=eq.{cid}"
                   f"&select=title,quarter,status,published_url,created_at"
                   f"{_range_filter('created_at', since, until)}&limit=20"):
        verb = "published" if r.get("status") == "published" else "drafted"
        text = (f"Quarterly press release {verb} ({r.get('quarter')}): "
                f"\"{clean(r.get('title'), 100)}\"")
        if r.get("published_url"):
            text += f" ({r['published_url']})"
        e = ev(_parse_ts(r.get("created_at")), "press", text)
        if e:
            out.append(e)
    return out


COLLECTORS = [from_work_log, from_gbp_posts, from_gbp_changes,
              from_browser_agent, from_backlinks,
              from_review_requests, from_content_items, from_videos,
              from_press_releases]


def collect(cid: str, since: date, until: date) -> list[dict]:
    events: list[dict] = []
    for fn in COLLECTORS:
        try:
            events.extend(fn(cid, since, until))
        except Exception as e:  # noqa: BLE001 — one table must not kill the report
            print(f"  [warn] {fn.__name__} skipped: {str(e)[:120]}")
    events.sort(key=lambda e: e["when"])
    return events


# ---------------------------------------------------------------- rendering


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def fmt_day(d: date) -> str:
    return d.strftime("%b %-d")


def fmt_long(d: date) -> str:
    return d.strftime("%B %-d, %Y")


def plural(n: int, template: str) -> str:
    s = "s" if n != 1 else ""
    es = "es" if n != 1 else ""
    return template.replace("{s}", s).replace("{es}", es)


def render(display_name: str, since: date, until: date,
           events: list[dict]) -> str:
    lines = [f"# Work Report: {display_name}", "",
             f"**{fmt_long(since)} to {fmt_long(until)}**  ",
             "Prepared by your team at Rank AI (by Restoration AI). Every line "
             "below is an action we performed on your account, with the date "
             "it happened.", ""]

    if not events:
        lines += ["_No recorded activity in this period._", ""]
        return "\n".join(lines)

    # At-a-glance counts (review invitations count people, not lines).
    counts: dict[str, int] = {}
    for e in events:
        counts[e["cat"]] = counts.get(e["cat"], 0) + e.get("n", 1)
    lines += ["## At a glance", ""]
    for key, (_label, _order, noun) in sorted(CATEGORIES.items(),
                                              key=lambda kv: kv[1][1]):
        n = counts.get(key)
        if n:
            lines.append(f"- **{n}** {plural(n, noun)}")
    for key in sorted(k for k in counts if k not in CATEGORIES):
        lines.append(f"- **{counts[key]}** "
                     f"{plural(counts[key], key.replace('-', ' ') + ' action{s}')}")
    total = sum(counts.values())
    lines += ["", f"**{total} recorded actions in total.**", ""]

    # Weekly sections, oldest first, category-grouped inside each week.
    by_week: dict[date, list[dict]] = {}
    for e in events:
        by_week.setdefault(week_start(e["when"].date()), []).append(e)

    for wk in sorted(by_week):
        lines += [f"## Week of {fmt_long(wk)}", ""]
        wk_events = by_week[wk]
        by_cat: dict[str, list[dict]] = {}
        for e in wk_events:
            by_cat.setdefault(e["cat"], []).append(e)
        for key in sorted(by_cat, key=lambda k: CATEGORIES.get(k, ("", 99, ""))[1]):
            label = CATEGORIES.get(key, (key.title(), 99, ""))[0]
            lines.append(f"### {label}")
            lines.append("")
            for e in by_cat[key]:
                lines.append(f"- {fmt_day(e['when'].date())}: {e['text']}")
            lines.append("")

    lines += ["---", "",
              "Questions about anything on this report? Reply to your team "
              "any time. We keep this ledger running every day, so next "
              "month's report builds automatically from the same record.", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI


def active_clients() -> list[dict]:
    out = []
    for path in sorted(CLIENTS_DIR.glob("*.json")):
        if path.name == "company_map.json":
            continue
        try:
            c = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(c, dict) and c.get("status") == "active":
            c.setdefault("slug", path.stem)
            out.append(c)
    return out


def run_one(slug: str, since: date, until: date) -> Path | None:
    cid = company_id_for_slug(slug)
    if not cid:
        print(f"{slug}: no company_id mapping — skipped")
        return None
    try:
        client = json.loads((CLIENTS_DIR / f"{slug}.json").read_text())
    except (json.JSONDecodeError, OSError):
        client = {}
    display = client.get("display_name") or slug
    print(f"==> {slug} ({cid}) {since} .. {until}")
    events = collect(cid, since, until)
    print(f"    {len(events)} event line(s) collected")
    md = render(display, since, until, events)
    out_dir = CLIENTS_DIR / slug / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"work-report-{since.isoformat()}-to-{until.isoformat()}.md"
    out_path.write_text(md)
    print(f"    wrote {out_path.relative_to(ROOT)}")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Client-facing work report")
    ap.add_argument("--slug", help="One client")
    ap.add_argument("--all", action="store_true",
                    help="Every active Rank AI client")
    ap.add_argument("--since", help="YYYY-MM-DD (default: until minus 30 days)")
    ap.add_argument("--until", help="YYYY-MM-DD (default: today)")
    a = ap.parse_args()
    if not a.slug and not a.all:
        ap.error("pass --slug <slug> or --all")
    until = date.fromisoformat(a.until) if a.until else datetime.now(timezone.utc).date()
    since = date.fromisoformat(a.since) if a.since else until - timedelta(days=30)
    if since > until:
        ap.error("--since is after --until")
    slugs = ([c["slug"] for c in active_clients()] if a.all else [a.slug])
    for slug in slugs:
        try:
            run_one(slug, since, until)
        except Exception as e:  # noqa: BLE001 — one client never kills --all
            print(f"  FAIL {slug}: {str(e)[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
