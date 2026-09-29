#!/usr/bin/env python3
"""monthly_summary.py — the per-client monthly line-item summary (the owner's
answer to "what have you done for me this month?").

Compiles every client-visible action our systems took in one calendar month
into a normalized list of line items and stores it in Supabase
monthly_summaries (one row per company per month; recompiling refreshes the
row in place). The app renders the row as the Marketing -> Monthly Summary
tab, visible to the client's own users.

Item shape (stored in the row's items jsonb array):
  { "date": "YYYY-MM-DD",
    "category": website|google-profile|reviews|ads|citations|content|other,
    "line": plain client-readable English (no jargon, no internal codenames),
    "detail": optional supporting text or URL,
    "count": optional int (aggregated lines: review sends per day, ...) }

The row's stats jsonb carries the roll-up header numbers the app shows as
chips: texts_sent, review_clicks, pages_published, profile_edits,
listings_added, total_actions, by_category.

Sources (each fail-soft; one broken table never kills the compile):
  marketing_work_log            everything work_log() records (site work,
                                citations syncs, keyword research, dev-agent
                                completions, LSA lead reviews + LSA changes,
                                AI-answer/award site updates, render-sweep
                                pages, research delivered in the app). Dev
                                rows prefer the evidence.client_line written
                                by dev_inbox.py. Category map: _WORKLOG_CAT.

RULE (2026-09-29, "every client action logs"): any system that changes a
client's Google profile, site, listings or ads, or delivers research to them,
writes one plain client-readable line via gbp.log_change (Google profile
edits) or work_log.work_log (everything else). This compiler only reads.
  marketing_ops_notes           resolved [DEV] notes with no work_log twin
                                (pre-client_line history), cleaned for clients
  marketing_gbp_changes         GBP optimization edits (services, description,
                                phone, cover, service areas ...; change_type=
                                post excluded, those mirror marketing_gbp_posts;
                                review_reply lands under Reviews)
  marketing_gbp_posts           GBP posts published
  review_requests               review texts sent (per-day roll-up) + clicked
  clients/{slug}/ads-journal.md Google Ads changes (budget, negatives, pause,
                                tracking; internal note/watch entries skipped)
  browser_agent_actions         directory listings the browser agent created
  user_integrations             provider=citations connection_metadata
                                .nap_audit: listings verified live this month
  marketing_backlinks           backlinks confirmed live
  marketing_content_items       blog posts published
  marketing_page_requests       service pages built from the app's queue
  marketing_videos              YouTube videos published
  marketing_press_releases      press releases drafted/published
  marketing_setup_ledger        setup milestones (done_at in month)
  clients/{slug}.json           build/scaffold + go-live timestamps (only when
                                the setup ledger did not already record them)
  git log sites/{slug}/         site work shipped, rolled up per day (content
                                writer + [automated] chore commits excluded;
                                DEV AGENT commits excluded, the dev items
                                above already tell that story)
  marketing_geogrid_scans       local map-rank scans, rolled up per day

Deliberately NOT included: gsc_sync analytics refreshes (data plumbing, not
client-visible work) and marketing_work_log production-deploy rows (the git
day roll-up describes the same shipped work with actual substance).

Usage:
  python3 scripts/monthly_summary.py compile --slug narestco
  python3 scripts/monthly_summary.py compile --slug narestco --month 2026-07
  python3 scripts/monthly_summary.py compile --all [--month YYYY-MM] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
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
from work_report import (_MILESTONE_COPY, _MILESTONE_SKIP, _parse_ts,  # noqa: E402
                         _range_filter, _rows, clean)

CATEGORIES = ["website", "google-profile", "reviews", "ads", "citations",
              "content", "other"]

# Clients whose summaries we compile with --all: everyone we are actively
# working for. Paused/archived clients keep their historical rows but stop
# accruing new ones.
_COMPILE_STATUSES = {"active", "live", "pending", "onboarding"}


# ---------------------------------------------------------------- utilities


def month_bounds(month: str) -> tuple[date, date]:
    """'YYYY-MM' -> (first day, last day) of that calendar month."""
    y, m = int(month[:4]), int(month[5:7])
    since = date(y, m, 1)
    until = (date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)) - timedelta(days=1)
    return since, until


_CODE_FILE_RE = re.compile(
    r"\b(?:sites|scripts|clients|src|templates|workers)/[\w./-]+"
    r"|\b[\w-]+\.(?:py|ts|tsx|js|mjs|json|md|astro|yml|sql)\b")


def plainify(text: str) -> str:
    """Best-effort client-readable cleanup of an engineer-written sentence:
    strip code ticks, file paths, bracket tags and URLs; keep the words."""
    t = re.sub(r"`+", "", str(text or ""))
    t = re.sub(r"\[[A-Z][A-Z -]*\]", "", t)
    t = _CODE_FILE_RE.sub("", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"\s*[—–]\s*", ", ", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" ,;:.")
    return t


def item(when, category: str, line: str, detail: str | None = None,
         count: int | None = None, kind: str = "") -> dict | None:
    """Normalize one line item; kind is an internal marker for the stats
    roll-up, stripped before storage. Returns None when the date is missing."""
    d = when.date() if isinstance(when, datetime) else when
    if not d or not line:
        return None
    out = {"date": d.isoformat(), "category": category, "line": line, "_k": kind}
    if detail:
        out["detail"] = detail
    if count is not None:
        out["count"] = count
    return out


# ---------------------------------------------------------------- collectors
# Each returns a list of items. Orchestrated by compile_month(), which wraps
# every call so one bad source degrades to a printed warning.

# "note" rows are operator analysis (ads audits, watch notes), never a
# client line; the ads journal skips its note entries for the same reason.
_WORKLOG_SKIP_ACTIONS = {"production-deploy", "staging-deploy",
                         "client-feedback-notified", "note"}
# work_log category -> report category. Anything unmapped lands in "other".
# gbp/ads/content added 2026-09-29 ("every client action logs"): gbp_auto_apply
# and friends wrote category "gbp", LSA work writes "ads", and both used to
# fall through to "other".
_WORKLOG_CAT = {"site": "website", "citations": "citations",
                "keyword-research": "content", "content": "content",
                "reviews": "reviews", "gbp": "google-profile", "ads": "ads",
                "outreach": "other", "routine": "other", "research": "other"}
# gbp work_log summaries whose per-change rows already land in
# marketing_gbp_changes (add_services / log_change): the change-log row is the
# client line, the work_log twin would double-count the same edit.
_WORKLOG_GBP_TWINS = {"optimizer-auto-apply", "services-applied",
                      "services-auto-applied", "services-auto-trimmed",
                      "service-trim"}
# recurring checks/refreshes: identical lines roll up into one item with a
# count (like category "routine") instead of one line per night.
_WORKLOG_ROLLUP_ACTIONS = {"parity-check", "ai-answers-refresh",
                           "review-snippets-sync", "location-scout"}


def from_work_log(cid: str, since: date, until: date,
                  seen_note_ids: set) -> list[dict]:
    out = []
    # routine sweeps run nightly; a line per night drowns the month, so
    # identical routine lines roll up into one item with a count
    routine: dict[tuple[str, str], tuple[date, int]] = {}
    for r in _rows(f"/rest/v1/marketing_work_log?company_id=eq.{cid}"
                   "&select=ts,category,action,detail,evidence"
                   f"{_range_filter('ts', since, until)}&order=ts.asc&limit=1000"):
        evidence = r.get("evidence") or {}
        if isinstance(evidence, dict) and evidence.get("note_id"):
            seen_note_ids.add(str(evidence["note_id"]))
        action = r.get("action") or ""
        if action in _WORKLOG_SKIP_ACTIONS:
            continue
        if (r.get("category") or "") == "gbp" and action in _WORKLOG_GBP_TWINS:
            continue
        ts = _parse_ts(r.get("ts"))
        line = clean(evidence.get("client_line") if isinstance(evidence, dict)
                     else None, 180) or clean(r.get("detail") or r.get("action"), 180)
        # a trailing ": https://..." belongs in detail, not the line (also
        # lets the dedupe pass match the browser agent's version of the event)
        detail = None
        m = re.search(r":?\s*\(?(https?://\S+?)\)?\s*$", line)
        if m:
            detail = m.group(1)
            line = line[:m.start()].rstrip(" :,") + "."
        cat = _WORKLOG_CAT.get(r.get("category") or "", "other")
        if (r.get("category") or "") == "routine" or action in _WORKLOG_ROLLUP_ACTIONS:
            if ts:
                prev = routine.get((cat, line))
                routine[(cat, line)] = (
                    max(ts.date(), prev[0]) if prev else ts.date(),
                    prev[1] + 1 if prev else 1)
            continue
        e = item(ts, cat, line, detail=detail, kind="work-log")
        if e:
            out.append(e)
    for (cat, line), (d, n) in routine.items():
        e = item(d, cat, line, count=n if n > 1 else None, kind="work-log")
        if e:
            out.append(e)
    return out


def _dev_line(body: str) -> str:
    t = re.sub(r"^\[DEV\]\s*", "", body or "").strip()
    if t.startswith("CLIENT FEEDBACK"):
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
        req = lines[1] if len(lines) > 1 else lines[0]
        return "Website change you asked for was completed: " + clean(plainify(req), 130)
    t = re.sub(r"\(from call:.*?\)", "", t.splitlines()[0])
    return "Website task completed: " + clean(plainify(t), 140)


def from_dev_notes(cid: str, since: date, until: date,
                   seen_note_ids: set) -> list[dict]:
    """Resolved [DEV] completions that never landed a work_log row (history
    from before dev_inbox.py wrote client_line ledger rows for every task)."""
    out = []
    for r in _rows(f"/rest/v1/marketing_ops_notes?company_id=eq.{cid}"
                   "&status=eq.resolved&body=like.%5BDEV%5D*"
                   "&select=id,body,resolved_at"
                   f"{_range_filter('resolved_at', since, until)}"
                   "&order=resolved_at.asc&limit=300"):
        if str(r.get("id")) in seen_note_ids:
            continue
        e = item(_parse_ts(r.get("resolved_at")), "website",
                 _dev_line(r.get("body") or ""), kind="dev-note")
        if e:
            out.append(e)
    return out


# change_types that are not profile EDITS: review replies are review work
# (reported under Reviews, not counted as profile edits).
_GBP_CHANGE_CAT = {"review_reply": ("reviews", "review-reply")}


def from_gbp_changes(cid: str, since: date, until: date) -> list[dict]:
    out = []
    for r in _rows(f"/rest/v1/marketing_gbp_changes?company_id=eq.{cid}"
                   "&change_type=neq.post"
                   "&select=changed_at,change_type,summary"
                   f"{_range_filter('changed_at', since, until)}"
                   "&order=changed_at.asc&limit=500"):
        cat, kind = _GBP_CHANGE_CAT.get(r.get("change_type") or "",
                                        ("google-profile", "gbp-change"))
        e = item(_parse_ts(r.get("changed_at")), cat,
                 clean(r.get("summary") or r.get("change_type"), 170),
                 kind=kind)
        if e:
            out.append(e)
    return out


def from_gbp_posts(cid: str, since: date, until: date) -> list[dict]:
    out = []
    for r in _rows(f"/rest/v1/marketing_gbp_posts?company_id=eq.{cid}"
                   "&select=posted_at,topic,summary"
                   f"{_range_filter('posted_at', since, until)}"
                   "&order=posted_at.asc&limit=500"):
        topic = (r.get("topic") or "update").replace("_", " ")
        e = item(_parse_ts(r.get("posted_at")), "google-profile",
                 f"Post published on your Google Business Profile ({topic}): "
                 f"\"{clean(r.get('summary'), 100)}\"", kind="gbp-post")
        if e:
            out.append(e)
    return out


def from_reviews(cid: str, since: date, until: date) -> list[dict]:
    """Sends rolled up per day; clicks as one month line (people who tapped
    through to leave a review)."""
    per_day: dict[date, int] = {}
    for r in _rows(f"/rest/v1/review_requests?company_id=eq.{cid}"
                   f"&select=last_sent_at{_range_filter('last_sent_at', since, until)}"
                   "&limit=2000"):
        ts = _parse_ts(r.get("last_sent_at"))
        if ts:
            per_day[ts.date()] = per_day.get(ts.date(), 0) + 1
    out = []
    for d, n in sorted(per_day.items()):
        out.append(item(d, "reviews",
                        f"Review invitation{'s' if n != 1 else ''} texted to "
                        f"{n} past customer{'s' if n != 1 else ''}.",
                        count=n, kind="review-sent"))
    clicks = 0
    last_click: date | None = None
    for r in _rows(f"/rest/v1/review_requests?company_id=eq.{cid}"
                   f"&select=last_clicked_at{_range_filter('last_clicked_at', since, until)}"
                   "&limit=2000"):
        ts = _parse_ts(r.get("last_clicked_at"))
        if ts:
            clicks += 1
            last_click = max(last_click, ts.date()) if last_click else ts.date()
    if clicks and last_click:
        out.append(item(last_click, "reviews",
                        f"{clicks} customer{'s' if clicks != 1 else ''} opened "
                        "their review link this month.",
                        count=clicks, kind="review-clicked"))
    return [e for e in out if e]


# Ads journal: `## YYYY-MM-DD HH:MMZ · kind · target` headers written by
# ads_manager.py. kind -> (roll-up group, client line). note/watch/review
# entries are internal analysis and never shown to clients.
_ADS_HEAD = re.compile(r"^## (\d{4}-\d{2}-\d{2}) \d{2}:\d{2}Z\s*·\s*([a-z-]+)\s*·", re.M)
_ADS_KINDS = {
    "budget":           ("budget", "Advertising budget adjusted."),
    "set-budget":       ("budget", "Advertising budget adjusted."),
    "bid":              ("bidding", "Ad bidding strategy tuned."),
    "set-bid-strategy": ("bidding", "Ad bidding strategy tuned."),
    "pause":            ("paused", "Ad campaign paused while we optimize."),
    "enable":           ("enabled", "Ad campaign turned on."),
    "add-negatives":    ("negatives", "Junk search terms blocked from triggering your ads, cutting wasted spend."),
    "apply-negatives":  ("negatives", "Junk search terms blocked from triggering your ads, cutting wasted spend."),
    "negatives":        ("negatives", "Junk search terms blocked from triggering your ads, cutting wasted spend."),
    "tracking":         ("tracking", "Call tracking on your ads checked and improved."),
    "location":         ("targeting", "Ad location targeting updated."),
    "launch":           ("launch", "Ad campaign launched."),
    "create":           ("launch", "Ad campaign created."),
    "action":           ("maintenance", "Ad account maintenance performed."),
}


def from_ads_journal(slug: str, since: date, until: date) -> list[dict]:
    path = CLIENTS_DIR / slug / "ads-journal.md"
    if not path.exists():
        return []
    groups: dict[tuple[date, str], int] = {}
    lines: dict[str, str] = {}
    for m in _ADS_HEAD.finditer(path.read_text()):
        try:
            d = date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if not (since <= d <= until):
            continue
        mapped = _ADS_KINDS.get(m.group(2))
        if not mapped:
            continue
        group, line = mapped
        groups[(d, group)] = groups.get((d, group), 0) + 1
        lines[group] = line
    out = []
    for (d, group), n in sorted(groups.items()):
        out.append(item(d, "ads", lines[group],
                        count=n if n > 1 else None, kind="ads"))
    return [e for e in out if e]


_PLATFORM_PRETTY = {"houzz": "Houzz", "porch": "Porch", "homeguide": "HomeGuide",
                    "bbb": "the BBB", "bing": "Bing Places", "apple": "Apple Maps",
                    "nextdoor": "Nextdoor", "yelp": "Yelp", "facebook": "Facebook"}


def from_browser_agent(cid: str, since: date, until: date) -> list[dict]:
    out = []
    for r in _rows(f"/rest/v1/browser_agent_actions?company_id=eq.{cid}"
                   "&outcome=eq.done&live=is.true"
                   "&select=created_at,playbook,action,detail"
                   f"{_range_filter('created_at', since, until)}"
                   "&order=created_at.asc&limit=500"):
        action = r.get("action") or ""
        playbook = r.get("playbook") or ""
        platform = _PLATFORM_PRETTY.get(action.split("-")[0].lower())
        created = playbook == "bing-places" or action.endswith("-create")
        if playbook == "bing-places":
            text = "New business listing created for you on Bing Places, synced from your Google listing."
        elif created and platform:
            text = f"New business listing created for you on {platform}."
        else:
            text = clean(plainify(r.get("detail") or f"{playbook} {action}"), 160)
        e = item(_parse_ts(r.get("created_at")), "citations", text,
                 kind="listing-created" if created else "listing-work")
        if e:
            out.append(e)
    return out


_NAP_PRETTY = {"google_listing": "Google", "bing_places": "Bing Places",
               "apple_maps": "Apple Maps", "yellowpages": "Yellow Pages",
               "homeadvisor": "HomeAdvisor", "homeguide": "HomeGuide",
               "bbb": "BBB", "angi": "Angi", "yelp": "Yelp", "houzz": "Houzz",
               "porch": "Porch", "facebook": "Facebook", "nextdoor": "Nextdoor",
               "thumbtack": "Thumbtack", "expertise": "Expertise"}


def from_nap_audit(cid: str, since: date, until: date) -> list[dict]:
    """user_integrations provider=citations connection_metadata.nap_audit:
    one roll-up line for the listings verified live this month."""
    rows = _rows(f"/rest/v1/user_integrations?client_id=eq.{cid}"
                 "&provider=eq.citations&select=connection_metadata&limit=1")
    if not rows:
        return []
    audit = ((rows[0].get("connection_metadata") or {}).get("nap_audit")) or {}
    if not isinstance(audit, dict):
        return []
    live, latest = [], None
    for key, entry in audit.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("status") not in ("found", "discrepancy"):
            continue
        ts = _parse_ts(entry.get("checked_at"))
        if not ts or not (since <= ts.date() <= until):
            continue
        live.append(_NAP_PRETTY.get(key, key.replace("_", " ").title()))
        latest = max(latest, ts.date()) if latest else ts.date()
    if not live:
        return []
    names = ", ".join(sorted(live))
    e = item(latest, "citations",
             f"Business listings check completed: {len(live)} of your "
             f"directory listings verified live across the web.",
             detail=names, count=len(live), kind="listing-live")
    return [e] if e else []


def from_backlinks(cid: str, since: date, until: date) -> list[dict]:
    out = []
    for r in _rows(f"/rest/v1/marketing_backlinks?company_id=eq.{cid}"
                   "&status=eq.live&select=label,last_checked_at"
                   f"{_range_filter('last_checked_at', since, until)}"
                   "&order=last_checked_at.asc&limit=200"):
        e = item(_parse_ts(r.get("last_checked_at")), "citations",
                 f"New link to your website confirmed live: {clean(r.get('label'), 90)}.",
                 kind="backlink")
        if e:
            out.append(e)
    return out


def from_content_items(cid: str, since: date, until: date) -> list[dict]:
    out = []
    for r in _rows(f"/rest/v1/marketing_content_items?company_id=eq.{cid}"
                   "&status=eq.published&select=title,live_url,published_at"
                   f"{_range_filter('published_at', since, until)}"
                   "&order=published_at.asc&limit=200"):
        e = item(_parse_ts(r.get("published_at")), "content",
                 f"New article published on your website: \"{clean(r.get('title'), 100)}\"",
                 detail=r.get("live_url") or None, kind="content-item")
        if e:
            out.append(e)
    return out


def from_page_requests(cid: str, since: date, until: date) -> list[dict]:
    out = []
    for r in _rows(f"/rest/v1/marketing_page_requests?company_id=eq.{cid}"
                   "&select=service,page_url,built_at"
                   f"{_range_filter('built_at', since, until)}"
                   "&order=built_at.asc&limit=100"):
        e = item(_parse_ts(r.get("built_at")), "content",
                 f"New service page published: {clean(r.get('service'), 90)}.",
                 detail=r.get("page_url") or None, kind="page-request")
        if e:
            out.append(e)
    return out


def from_videos(cid: str, since: date, until: date) -> list[dict]:
    out = []
    for r in _rows(f"/rest/v1/marketing_videos?company_id=eq.{cid}"
                   "&select=title,url,created_at"
                   f"{_range_filter('created_at', since, until)}"
                   "&order=created_at.asc&limit=100"):
        e = item(_parse_ts(r.get("created_at")), "content",
                 f"YouTube video published for your business: \"{clean(r.get('title'), 100)}\"",
                 detail=r.get("url") or None, kind="video")
        if e:
            out.append(e)
    return out


def from_press_releases(cid: str, since: date, until: date) -> list[dict]:
    out = []
    for r in _rows(f"/rest/v1/marketing_press_releases?company_id=eq.{cid}"
                   "&select=title,quarter,status,published_url,created_at"
                   f"{_range_filter('created_at', since, until)}&limit=20"):
        verb = "published" if r.get("status") == "published" else "prepared"
        e = item(_parse_ts(r.get("created_at")), "content",
                 f"Press release {verb} for your business: \"{clean(r.get('title'), 100)}\"",
                 detail=r.get("published_url") or None, kind="press")
        if e:
            out.append(e)
    return out


_LEDGER_CAT = {"site-built": "website", "site-live": "website",
               "site-imagery": "website", "gsc-indexnow": "website",
               "google-connected": "google-profile",
               "gbp-verified": "google-profile",
               "lsa-setup": "ads", "citations-build": "citations"}


def from_setup_ledger(cid: str, slug: str, since: date, until: date,
                      ledger_keys: set) -> list[dict]:
    # the ledger's done_at is the flip-to-done stamp; for milestones whose
    # REAL date the client record knows (build, go-live), a stamp inside the
    # month with a real date outside it is a backfill artifact, not news
    real_dates: dict[str, date | None] = {}
    try:
        rec = json.loads((CLIENTS_DIR / f"{slug}.json").read_text())
        scaffolded = _parse_ts((rec.get("build") or {}).get("scaffolded_at"))
        cutover = _parse_ts(rec.get("cut_over_at")
                            or (rec.get("apex_cutover") or {}).get("completed_at"))
        real_dates = {"site-built": scaffolded.date() if scaffolded else None,
                      "site-live": cutover.date() if cutover else None}
    except (json.JSONDecodeError, OSError):
        pass
    out = []
    for r in _rows(f"/rest/v1/marketing_setup_ledger?company_id=eq.{cid}"
                   "&status=eq.done&select=item_key,title,evidence,done_at"
                   f"{_range_filter('done_at', since, until)}"
                   "&order=done_at.asc&limit=100"):
        key = r.get("item_key") or ""
        if key in _MILESTONE_SKIP:
            continue
        ledger_keys.add(key)
        real = real_dates.get(key)
        if real and not (since <= real <= until):
            continue
        text = _MILESTONE_COPY.get(key)
        if text:
            try:
                text = text.format(**{k: clean(str(v), 60) for k, v in
                                      (r.get("evidence") or {}).items()
                                      if isinstance(v, (str, int, float))})
            except (KeyError, IndexError):
                text = None
        if not text or "{" in text:
            text = clean(plainify(r.get("title") or key.replace("-", " ")), 140)
            text = text[:1].upper() + text[1:] if text else text
        e = item(_parse_ts(r.get("done_at")), _LEDGER_CAT.get(key, "other"),
                 text, kind="milestone")
        if e:
            out.append(e)
    return out


def from_client_record(slug: str, since: date, until: date,
                       ledger_keys: set) -> list[dict]:
    """Build/go-live timestamps from clients/{slug}.json, only when the setup
    ledger did not already record the same milestone this month."""
    try:
        rec = json.loads((CLIENTS_DIR / f"{slug}.json").read_text())
    except (json.JSONDecodeError, OSError):
        return []
    out = []
    build = rec.get("build") or {}
    scaffolded = _parse_ts(build.get("scaffolded_at"))
    if (scaffolded and since <= scaffolded.date() <= until
            and "site-built" not in ledger_keys):
        n = build.get("url_count")
        text = (f"Your new website was built: {n} pages created and staged "
                "for preview." if n else
                "Your new website was built and staged for preview.")
        out.append(item(scaffolded, "website", text, kind="milestone"))
    cutover = _parse_ts(rec.get("cut_over_at")
                        or (rec.get("apex_cutover") or {}).get("completed_at"))
    if (cutover and since <= cutover.date() <= until
            and "site-live" not in ledger_keys):
        domain = rec.get("domain")
        text = (f"Your website went live at https://{domain}." if domain
                else "Your website went live on your own domain.")
        out.append(item(cutover, "website", text, kind="milestone"))
    return [e for e in out if e]


_COMMIT_SKIP = re.compile(r"^(?:Content writer:|DEV AGENT:)|\[automated\]")


def from_git(slug: str, since: date, until: date) -> list[dict]:
    """Site work shipped, one roll-up line per day. Content-writer commits are
    excluded (marketing_content_items already reports the article) and DEV
    AGENT commits are excluded (the dev items already tell that story)."""
    site_dir = ROOT / "sites" / slug
    if not site_dir.exists():
        return []
    try:
        raw = subprocess.run(
            ["git", "-C", str(ROOT), "log", "--pretty=%ad|%s", "--date=short",
             f"--since={since.isoformat()}T00:00:00",
             f"--until={(until + timedelta(days=1)).isoformat()}T00:00:00",
             "--", f"sites/{slug}/"],
            capture_output=True, text=True, timeout=60).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    per_day: dict[date, list[str]] = {}
    for row in raw.splitlines():
        if "|" not in row:
            continue
        day_s, subject = row.split("|", 1)
        subject = subject.strip()
        if _COMMIT_SKIP.search(subject):
            continue
        try:
            d = date.fromisoformat(day_s.strip())
        except ValueError:
            continue
        if since <= d <= until:
            # strip a leading "slug:"/"fleet:" style prefix, then de-jargon
            subject = re.sub(r"^[\w .+-]{1,40}:\s*", "", subject)
            per_day.setdefault(d, []).append(clean(plainify(subject), 90))
    out = []
    for d, subjects in sorted(per_day.items()):
        n = len(subjects)
        e = item(d, "website",
                 f"Website improvement{'s' if n != 1 else ''} shipped to your "
                 f"site ({n} update{'s' if n != 1 else ''}).",
                 detail="; ".join(s for s in subjects if s)[:300] or None,
                 count=n if n > 1 else None, kind="git")
        if e:
            out.append(e)
    return out


def from_geogrid(cid: str, since: date, until: date) -> list[dict]:
    per_day: dict[date, tuple[set, set]] = {}
    for r in _rows(f"/rest/v1/marketing_geogrid_scans?company_id=eq.{cid}"
                   "&select=scanned_at,keyword,city_label"
                   f"{_range_filter('scanned_at', since, until)}&limit=2000"):
        ts = _parse_ts(r.get("scanned_at"))
        if not ts:
            continue
        kws, cities = per_day.setdefault(ts.date(), (set(), set()))
        kws.add(r.get("keyword") or "")
        cities.add(r.get("city_label") or "")
    out = []
    for d, (kws, cities) in sorted(per_day.items()):
        k, c = len(kws - {""}), len(cities - {""})
        e = item(d, "other",
                 f"Local map rankings scanned: {k} search term{'s' if k != 1 else ''} "
                 f"checked across {c} area{'s' if c != 1 else ''}.",
                 kind="geogrid")
        if e:
            out.append(e)
    return out


# ---------------------------------------------------------------- assembly


def compile_month(slug: str, cid: str, since: date, until: date) -> tuple[list[dict], dict]:
    items: list[dict] = []
    seen_note_ids: set = set()
    ledger_keys: set = set()

    steps = [
        ("work_log",      lambda: from_work_log(cid, since, until, seen_note_ids)),
        ("dev_notes",     lambda: from_dev_notes(cid, since, until, seen_note_ids)),
        ("gbp_changes",   lambda: from_gbp_changes(cid, since, until)),
        ("gbp_posts",     lambda: from_gbp_posts(cid, since, until)),
        ("reviews",       lambda: from_reviews(cid, since, until)),
        ("ads_journal",   lambda: from_ads_journal(slug, since, until)),
        ("browser_agent", lambda: from_browser_agent(cid, since, until)),
        ("nap_audit",     lambda: from_nap_audit(cid, since, until)),
        ("backlinks",     lambda: from_backlinks(cid, since, until)),
        ("content_items", lambda: from_content_items(cid, since, until)),
        ("page_requests", lambda: from_page_requests(cid, since, until)),
        ("videos",        lambda: from_videos(cid, since, until)),
        ("press",         lambda: from_press_releases(cid, since, until)),
        ("setup_ledger",  lambda: from_setup_ledger(cid, slug, since, until, ledger_keys)),
        ("client_record", lambda: from_client_record(slug, since, until, ledger_keys)),
        ("git",           lambda: from_git(slug, since, until)),
        ("geogrid",       lambda: from_geogrid(cid, since, until)),
    ]
    for name, fn in steps:
        try:
            items.extend(fn())
        except Exception as e:  # noqa: BLE001 — one source never kills the month
            print(f"  [warn] {name} skipped: {str(e)[:120]}")

    # near-duplicate guard (the same event recorded by two sources, e.g. a
    # listing creation in both marketing_work_log and browser_agent_actions)
    seen, deduped = set(), []
    for e in sorted(items, key=lambda x: (x["date"], CATEGORIES.index(x["category"]))):
        norm = e["line"].lower().rstrip(".! ")
        # a listing is created once; retries on later days are the same event
        key = ((e["category"], norm) if norm.startswith("new business listing created")
               else (e["date"], e["category"], norm))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)

    stats = {"texts_sent": 0, "review_clicks": 0, "pages_published": 0,
             "profile_edits": 0, "listings_added": 0, "total_actions": 0,
             "by_category": {}}
    for e in deduped:
        k, n = e.pop("_k", ""), e.get("count") or 1
        if k == "review-sent":
            stats["texts_sent"] += n
        elif k == "review-clicked":
            stats["review_clicks"] += n
            continue  # informational, not an action we performed
        elif k in ("content-item", "page-request"):
            stats["pages_published"] += 1
        elif k in ("gbp-change", "gbp-post"):
            stats["profile_edits"] += 1
        elif k == "listing-created" or (e["category"] == "citations" and
                                        e["line"].startswith("New business listing created")):
            # the line-prefix check catches the work_log twin of a creation
            # the dedupe pass kept in place of the browser agent's row
            stats["listings_added"] += n
        stats["total_actions"] += n
        cat = e["category"]
        stats["by_category"][cat] = stats["by_category"].get(cat, 0) + n
    return deduped, stats


def upsert_summary(cid: str, since: date, items: list[dict], stats: dict) -> None:
    _sb("POST", "/rest/v1/monthly_summaries?on_conflict=company_id,month",
        body={"company_id": cid, "month": since.isoformat(),
              "stats": stats, "items": items,
              "generated_at": datetime.now(timezone.utc).isoformat()},
        prefer="resolution=merge-duplicates,return=minimal")


# ---------------------------------------------------------------- CLI


def compile_clients() -> list[str]:
    out = []
    for path in sorted(CLIENTS_DIR.glob("*.json")):
        if path.name == "company_map.json":
            continue
        try:
            c = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(c, dict) and c.get("status") in _COMPILE_STATUSES:
            out.append(path.stem)
    return out


def run_one(slug: str, month: str, dry_run: bool) -> None:
    cid = company_id_for_slug(slug)
    if not cid:
        print(f"{slug}: no company_id mapping, skipped")
        return
    since, until = month_bounds(month)
    items, stats = compile_month(slug, cid, since, until)
    if not items:
        print(f"{slug}: {month} has no recorded activity, no row written")
        return
    if dry_run:
        print(f"{slug}: {month} -> {len(items)} items (dry run)")
        print(json.dumps({"stats": stats, "items": items}, indent=1))
        return
    upsert_summary(cid, since, items, stats)
    print(f"{slug}: {month} -> {len(items)} items, "
          f"{stats['total_actions']} actions recorded")


def main() -> int:
    ap = argparse.ArgumentParser(description="Per-client monthly summary compiler")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("compile", help="compile one month into monthly_summaries")
    pc.add_argument("--slug", help="one client")
    pc.add_argument("--all", action="store_true", help="every compile-eligible client")
    pc.add_argument("--month", help="YYYY-MM (default: current month, UTC)")
    pc.add_argument("--dry-run", action="store_true",
                    help="print the compiled JSON, write nothing")
    a = ap.parse_args()
    if not a.slug and not a.all:
        ap.error("pass --slug <slug> or --all")
    month = a.month or datetime.now(timezone.utc).strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        ap.error("--month must be YYYY-MM")
    slugs = compile_clients() if a.all else [a.slug]
    for slug in slugs:
        try:
            run_one(slug, month, a.dry_run)
        except Exception as e:  # noqa: BLE001 — one client never kills --all
            print(f"  FAIL {slug}: {str(e)[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
