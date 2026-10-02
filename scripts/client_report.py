#!/usr/bin/env python3
"""client_report.py — the fleet-wide monthly results pack (Santino 2026-08-30:
"I love this and I think it should be in the app just as it is. It needs to
happen systematically for every client instead of just being on my machine
when I ask").

Per active client, one self-contained HTML page in the style of the TRG
growth review: Google Search 28-day comparison, review-campaign progress,
the work we shipped (from the ledgers that every pipeline already writes),
and live business listings. Uploaded to the public `client-reports` bucket
under an unguessable tokened path, recorded in marketing_client_reports
(upsert per company+period, so a month regenerates in place), and one
client-visible work_log line so Reports shows the report itself.

Sections render only when their data exists — a client with no GSC property
gets no empty search section, a client with no campaign gets no review block.
No em dashes anywhere in the output (house law).

Usage:
  python3 scripts/client_report.py --all
  python3 scripts/client_report.py --slug narestco
  python3 scripts/client_report.py --all --period 2026-08
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import secrets
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
HDR = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
       "Content-Type": "application/json"}
BUCKET = "client-reports"
# Supabase public storage refuses to RENDER html (text/plain + nosniff),
# so reports are served through the Railway API front door instead.
REPORT_BASE = "https://rank-ai-api-production.up.railway.app/report"

_INACTIVE = {"paused", "suspended", "cancelled", "canceled", "churned", "inactive", "archived",
             "suspended"}


def _sb(path: str):
    r = requests.get(f"{SB_URL}/rest/v1/{path}", headers=HDR, timeout=30)
    return r.json() if r.ok else []


def _count(path: str) -> int:
    r = requests.get(f"{SB_URL}/rest/v1/{path}",
                     headers=HDR | {"Prefer": "count=exact", "Range": "0-0"},
                     timeout=20)
    cr = r.headers.get("content-range", "")
    return int(cr.split("/")[-1]) if r.ok and "/" in cr else 0


# ----------------------------------------------------------------- GSC pull
def _gsc_token() -> str | None:
    try:
        from gsc_setup import AGENCY_TOKEN_PATH, OAUTH_CLIENT_PATH
        tok = json.load(open(AGENCY_TOKEN_PATH))
        oc = json.load(open(OAUTH_CLIENT_PATH))
        cfg = oc.get("installed") or oc.get("web") or oc
        r = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
            "refresh_token": tok["refresh_token"],
            "grant_type": "refresh_token"}, timeout=30)
        return r.json().get("access_token") if r.ok else None
    except Exception:  # noqa: BLE001
        return None


def gsc_section(domain: str, at: str) -> dict | None:
    """28d vs prior-28d totals + top queries for sc-domain:{domain}."""
    site = requests.utils.quote(f"sc-domain:{domain}", safe="")
    end = dt.date.today() - dt.timedelta(days=2)   # GSC lags ~2 days
    start = end - dt.timedelta(days=27)
    p_end = start - dt.timedelta(days=1)
    p_start = p_end - dt.timedelta(days=27)

    def q(s, e, dims=None, limit=8):
        body = {"startDate": str(s), "endDate": str(e), "rowLimit": limit}
        if dims:
            body["dimensions"] = dims
        r = requests.post(
            f"https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query",
            headers={"Authorization": f"Bearer {at}"}, json=body, timeout=30)
        return r.json() if r.ok else None

    cur = q(start, end)
    if cur is None:          # property not in the agency account
        return None
    prev = q(p_start, p_end) or {}

    def tot(x):
        rows = (x or {}).get("rows") or [{}]
        return int(rows[0].get("impressions", 0)), int(rows[0].get("clicks", 0))

    ci, cc = tot(cur)
    pi, pc = tot(prev)
    if ci == 0 and pi == 0:
        return None          # brand-new property, nothing to show yet
    daily = q(p_start, end, ["date"], 60) or {}
    series = [int(r.get("impressions", 0)) for r in (daily.get("rows") or [])]
    top = q(start, end, ["query"], 6) or {}
    queries = [{"q": r["keys"][0], "impr": int(r["impressions"]),
                "clicks": int(r["clicks"]), "pos": round(r["position"], 1)}
               for r in (top.get("rows") or [])
               if r.get("impressions", 0) >= 5]
    return {"impr": ci, "clicks": cc, "impr_prev": pi, "clicks_prev": pc,
            "start": str(start), "end": str(end), "queries": queries[:5],
            "series": series}


def rankings_section(cid: str, domain: str | None, at: str | None) -> dict | None:
    """Where the client ranks (Santino 2026-08-31: 'ai search rankings and any
    other outstanding rankings'). Three measured sources, zero estimates:
      - GSC: search terms on page 1 (position <= 10, 5+ impressions) and count
        of site pages Google actually showed searchers, each vs prior 28 days
      - marketing_geogrid_scans: live map-pack position per keyword per grid
        city (latest scan per pair, 60-day recency) + the rendered heat map PNG
      - marketing_ai_search_history/-scans: share of AI-assistant answers that
        cite the client, plus real example queries where they were recommended
    Every subpart is optional; returns None when no source has data."""
    out: dict = {}
    if domain and at:
        site = requests.utils.quote(f"sc-domain:{domain}", safe="")
        end = dt.date.today() - dt.timedelta(days=2)
        start = end - dt.timedelta(days=27)
        p_end = start - dt.timedelta(days=1)
        p_start = p_end - dt.timedelta(days=27)

        def q(s, e, dims, limit):
            r = requests.post(
                f"https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query",
                headers={"Authorization": f"Bearer {at}"},
                json={"startDate": str(s), "endDate": str(e),
                      "dimensions": dims, "rowLimit": limit}, timeout=30)
            return (r.json().get("rows") or []) if r.ok else []

        def page1(rows):
            return sum(1 for r in rows
                       if r.get("position", 99) <= 10.5 and r.get("impressions", 0) >= 5)

        qc = q(start, end, ["query"], 1000)
        pc = q(start, end, ["page"], 2000)
        if qc or pc:
            out["page1"] = {"cur": page1(qc),
                            "prev": page1(q(p_start, p_end, ["query"], 1000))}
            out["pages"] = {"cur": len(pc),
                            "prev": len(q(p_start, p_end, ["page"], 2000))}

    cutoff = (dt.datetime.now(dt.timezone.utc) -
              dt.timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scans = _sb(f"marketing_geogrid_scans?company_id=eq.{cid}"
                f"&scanned_at=gte.{cutoff}&avg_rank=not.is.null"
                f"&order=scanned_at.desc&limit=60"
                f"&select=keyword,city_label,avg_rank,pct_in_top3,scanned_at,image_url")
    seen: set = set()
    grid: list[dict] = []
    for s in scans:
        k = (s["keyword"], s.get("city_label"))
        if k in seen:
            continue
        seen.add(k)
        prev = next((r for r in scans
                     if (r["keyword"], r.get("city_label")) == k
                     and (r["scanned_at"] or "")[:10] < (s["scanned_at"] or "")[:10]),
                    None)
        grid.append({"kw": s["keyword"], "city": s.get("city_label") or "",
                     "rank": float(s["avg_rank"]),
                     "top3": float(s["pct_in_top3"] or 0),
                     "prev_rank": float(prev["avg_rank"]) if prev else None,
                     "date": (s["scanned_at"] or "")[:10],
                     "img": s.get("image_url")})
    if grid:
        grid.sort(key=lambda g: g["rank"])
        out["grid"] = grid[:8]

    hist = _sb(f"marketing_ai_search_history?company_id=eq.{cid}"
               f"&order=scanned_at.desc&limit=12")
    if hist:
        cur = hist[0]
        base = next((h for h in hist[1:]
                     if (cur["scanned_at"] or "")[:10] > (h["scanned_at"] or "")[:10]
                     and (dt.date.fromisoformat((cur["scanned_at"] or "")[:10]) -
                          dt.date.fromisoformat((h["scanned_at"] or "")[:10])).days >= 14),
                    None)
        cited_rows = _sb(f"marketing_ai_search_scans?company_id=eq.{cid}"
                         f"&cited=eq.true&order=scanned_at.desc&limit=20"
                         f"&select=query,engine,client_rank")
        ex, seen_q = [], set()
        for r in cited_rows:
            qq = (r.get("query") or "").strip()
            if not qq or qq.lower() in seen_q:
                continue
            seen_q.add(qq.lower())
            ex.append({"q": qq, "engine": r.get("engine") or "",
                       "rank": r.get("client_rank")})
        ex.sort(key=lambda x: (x["rank"] is None, x["rank"] or 99))
        out["ai"] = {"pct": int(cur.get("visibility_pct") or 0),
                     "cited": int(cur.get("cited") or 0),
                     "total": int(cur.get("total") or 0),
                     "top": int(cur.get("top_picks") or 0),
                     "date": (cur.get("scanned_at") or "")[:10],
                     "prev_pct": int(base["visibility_pct"]) if base else None,
                     "examples": ex[:4]}

    return out or None


# ------------------------------------------------------------- data gathers
def review_section(cid: str) -> dict | None:
    total = _count(f"review_requests?company_id=eq.{cid}&select=id&limit=1")
    if not total:
        return None
    unproc = _count(f"review_requests?company_id=eq.{cid}&select=id"
                    "&status=in.(pending,staged)&last_sent_at=is.null&limit=1")
    clicked = _count(f"review_requests?company_id=eq.{cid}&select=id"
                     "&status=in.(clicked,reviewed,feedback_given)&limit=1")
    processed = max(total - unproc, 0)
    if not processed:
        return None
    return {"total": total, "processed": processed, "clicked": clicked,
            "pct": round(processed / total * 100),
            "click_rate": round(clicked / processed * 100, 1)}


def work_section(cid: str, days: int = 31) -> dict:
    # Z-format, never isoformat(): '+00:00' reads as a space in a URL query
    # and PostgREST 400s the filter (the whole section silently vanished).
    since = (dt.datetime.now(dt.timezone.utc)
             - dt.timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
    logs = _sb(f"marketing_work_log?company_id=eq.{cid}"
               f"&ts=gte.{since}&order=ts.desc"
               # never the report itself, never outreach — "Texted Bobby..."
               # is conversation, not delivered work (Santino 2026-08-31)
               "&category=not.in.(reporting,outreach)"
               "&select=detail,category,ts&limit=60")
    changes = _sb(f"marketing_gbp_changes?company_id=eq.{cid}"
                  f"&changed_at=gte.{since}&select=change_type&limit=1000")
    by_type: dict[str, int] = {}
    for c in changes:
        t = c.get("change_type") or "other"
        by_type[t] = by_type.get(t, 0) + 1
    # de-dupe near-identical ledger lines (daily crons repeat phrasing)
    seen, items = set(), []
    for lg in logs:
        if re.match(r"\s*(texted|messaged|emailed)\b", str(lg.get("detail") or ""), re.I):
            continue
        key = re.sub(r"\d+", "#", str(lg.get("detail") or ""))[:80]
        if key in seen:
            continue
        seen.add(key)
        items.append({"msg": str(lg.get("detail") or "").strip(),
                      "when": str(lg.get("ts") or "")[:10]})
        if len(items) >= 10:
            break
    return {"items": items, "gbp_counts": by_type}


def gbp_section(cid: str, days: int = 31) -> dict | None:
    """Google Business Profile stats (Santino 2026-08-31): rating, reviews,
    and what we published to the profile this period."""
    prof = _sb(f"marketing_gbp_profiles?company_id=eq.{cid}"
               "&select=rating,review_count&limit=1")
    since = (dt.datetime.now(dt.timezone.utc)
             - dt.timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
    posts = _count(f"marketing_gbp_posts?company_id=eq.{cid}&select=id"
                   f"&posted_at=gte.{since}&limit=1")
    changes = _sb(f"marketing_gbp_changes?company_id=eq.{cid}"
                  f"&changed_at=gte.{since}&select=change_type&limit=1000")
    photos = sum(1 for c in changes if c.get("change_type") == "photo")
    svc_adds = sum(1 for c in changes if c.get("change_type") == "service_add")
    r = (prof[0] if prof else {}) or {}
    if not (r.get("rating") or posts or photos or svc_adds):
        return None
    return {"rating": r.get("rating"), "reviews": r.get("review_count"),
            "posts": posts, "photos": photos, "svc_adds": svc_adds}


def _outcomes_stat(outcomes: dict) -> str:
    """One report card summarizing what the calls turned into (queue #6:
    booked / quotes / missed opportunities / callbacks surfaced monthly)."""
    if not outcomes:
        return ""
    label = {"booked": "booked", "quote_requested": "quote requests",
             "missed_opportunity": "missed opportunities",
             "callback_needed": "callbacks requested",
             "info_only": "questions"}
    bits = [f"{n} {label[k]}" for k, n in sorted(
        outcomes.items(), key=lambda kv: -kv[1]) if k in label and n]
    if not bits:
        return ""
    return ('<div class="stat"><div class="lbl">What the calls turned into'
            '</div><div class="num" style="font-size:1.05rem">'
            + " &#183; ".join(bits[:4])
            + '</div><div class="from">we text you the moment a call is '
              'labeled a missed opportunity or callback</div></div>')


def _spam_blocked_stat(n: int) -> str:
    """E3: spam is a POSITIVE line, not noise (Roy: dozens of lead-farm
    robocalls made the call report look broken)."""
    if not n:
        return ""
    return ('<div class="stat"><div class="lbl">Spam calls blocked</div>'
            f'<div class="num">{_fmt(n)}</div>'
            '<div class="from">robocalls and solicitors we filtered so they '
            'never rang your line or counted above</div></div>')


def _answer_rate_stat(calls: dict) -> str:
    """E4: answer rate on real calls. Voicemail is the silent leak (RX:
    105 of 200 calls ended in voicemail) — clients should see it monthly."""
    total = calls.get("total") or 0
    if total < 10:
        return ""
    pct = round(100 * (calls.get("answered_live") or 0) / total)
    return ('<div class="stat"><div class="lbl">Answered live</div>'
            f'<div class="num">{pct}%</div>'
            '<div class="from">calls reaching a person, not voicemail'
            + ('. Answering faster is the cheapest way to win more jobs'
               if pct < 70 else '') + '</div></div>')


def calls_section(cid: str, days: int = 31) -> dict | None:
    """Tracked phone calls (Santino 2026-08-31: "add the ability to see how
    many calls happen and the list of calls from both Google and the
    website"). Only exists once call tracking is provisioned."""
    since = (dt.datetime.now(dt.timezone.utc)
             - dt.timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
    rows = _sb(f"marketing_tracked_calls?company_id=eq.{cid}"
               f"&started_at=gte.{since}&order=started_at.desc"
               "&select=source,from_number,status,duration_seconds,started_at,analysis&limit=200")
    if not rows:
        return None
    # E3 (2026-09-18, Roy's "cleaned call report"): spam never counts as a
    # tracked call in anything client-facing. Calls the AI classified spam
    # or the router dead-ended are pulled out and reported as ONE positive
    # number ("N spam calls blocked") instead of polluting every stat.
    def _is_spam(r: dict) -> bool:
        a = r.get("analysis")
        return (r.get("status") == "blocked_spam"
                or (isinstance(a, dict) and a.get("outcome") == "spam"))
    spam = sum(1 for r in rows if _is_spam(r))
    rows = [r for r in rows if not _is_spam(r)]
    by_src = {"gbp": 0, "website": 0}
    answered = 0
    answered_live = 0   # E4: connected to a human, not voicemail
    outcomes: dict[str, int] = {}
    for r in rows:
        by_src[r.get("source") or "gbp"] = by_src.get(r.get("source") or "gbp", 0) + 1
        a = r.get("analysis")
        oc = a.get("outcome") if isinstance(a, dict) else None
        if (r.get("duration_seconds") or 0) >= 20:
            answered += 1
        if oc != "voicemail" and (r.get("duration_seconds") or 0) >= 20:
            answered_live += 1
        if oc:
            outcomes[oc] = outcomes.get(oc, 0) + 1
    for r in rows:
        r.pop("analysis", None)   # the table renderer never needs it
    return {"total": len(rows), "gbp": by_src.get("gbp", 0),
            "website": by_src.get("website", 0), "answered": answered,
            "answered_live": answered_live, "spam_blocked": spam,
            "outcomes": outcomes, "recent": rows[:20]}


def activity_section(cid: str, period: str) -> list[dict]:
    """The full month-to-date action log (monthly_summaries.items) — same
    lines the app shows, tucked into a collapsed block at the report's end."""
    rows = _sb(f"monthly_summaries?company_id=eq.{cid}&month=eq.{period}"
               "&select=items&limit=1")
    items = (rows[0].get("items") or []) if rows else []
    return items[:200]


def pages_section(cid: str, slug: str | None, days: int = 31) -> dict | None:
    """New website pages, itemized per service (Santino 2026-08-31: "itemize
    that out a little bit more"). Page counts derive from the client's own
    service-area ring: one dedicated page per area plus the service page."""
    since = (dt.datetime.now(dt.timezone.utc)
             - dt.timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
    rows = _sb(f"marketing_page_requests?company_id=eq.{cid}&status=eq.built"
               f"&built_at=gte.{since}&select=service,service_slug")
    if not rows:
        return None
    ring = 0
    if slug:
        try:
            pi = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text())
            ring = sum(1 for a in (pi.get("service_areas") or []) if not a.get("primary"))
        except Exception:  # noqa: BLE001
            pass
    per = 1 + ring
    # dedupe on service_slug — "Water Removal" and "Water Cleanup" resolve to
    # the SAME page set, and double-counting overstates the total (TRG showed
    # 318 for what is 6 unique services; accuracy beats impressiveness).
    by_slug: dict[str, str] = {}
    for r in rows:
        sl = (r.get("service_slug") or r.get("service") or "").strip()
        if sl and sl not in by_slug:
            by_slug[sl] = (r.get("service") or sl).strip()
    svcs = sorted(by_slug.values())
    return {"services": svcs, "per": per, "total": per * len(svcs), "ring": ring}


def listings_section(cid: str) -> dict | None:
    rows = _sb(f"citation_listings?company_id=eq.{cid}&select=directory,status,listing_url")
    live = [r for r in rows if r.get("status") in ("live", "created")]
    if not rows:
        return None
    entries = sorted({(r["directory"].replace("_", " ").title(),
                       (r.get("listing_url") or "").strip()) for r in live})
    return {"live": len(live), "total": len(rows), "entries": entries}


# ------------------------------------------------------------------ render
_GBP_LABELS = {
    "post": "Google Business posts published",
    "service_add": "services added to your Google listing",
    "service_remove": "services cleaned off your Google listing",
    "description": "service descriptions written",
    "photo": "photos added to your Google listing",
}


def _fmt(n) -> str:
    return f"{n:,}"


def _sparkline(series: list[int], width: int = 720, height: int = 64) -> str:
    """Inline SVG area sparkline of daily impressions (8 weeks). Simple,
    self-contained, theme-safe via currentColor-independent fill."""
    pts = [v for v in series if v >= 0]
    if len(pts) < 8:
        return ""
    mx = max(pts) or 1
    step = width / (len(pts) - 1)
    coords = [(round(i * step, 1), round(height - (v / mx) * (height - 6) - 2, 1))
              for i, v in enumerate(pts)]
    line = " ".join(f"{x},{y}" for x, y in coords)
    area = f"0,{height} " + line + f" {width},{height}"
    return (f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" '
            f'style="width:100%;height:{height}px;display:block;margin:.4rem 0 .2rem">'
            f'<polygon points="{area}" fill="#1863A8" opacity="0.14"/>'
            f'<polyline points="{line}" fill="none" stroke="#1863A8" stroke-width="2"/>'
            f'<circle cx="{coords[-1][0]}" cy="{coords[-1][1]}" r="3" fill="#1863A8"/></svg>')


def _delta_chip(cur: int, prev: int) -> str:
    if prev <= 0:
        return ""
    x = cur / prev
    if x >= 1.05:
        return f'<span class="delta">{x:.1f}x</span>'
    if x <= 0.95:
        return f'<span class="delta down">{round((1 - x) * 100)}% down</span>'
    return '<span class="delta flat">steady</span>'


def _mask(num: str) -> str:
    d = re.sub(r"\D", "", num or "")[-10:]
    return f"({d[:3]}) ***-{d[6:]}" if len(d) == 10 else "unknown"


def _dur(sec) -> str:
    sec = int(sec or 0)
    return f"{sec // 60}:{sec % 60:02d}"


_ENGINE_LABELS = {"chatgpt": "ChatGPT", "gemini": "Google Gemini",
                  "perplexity": "Perplexity", "google_ai": "Google AI Overviews",
                  "ai_overview": "Google AI Overviews", "copilot": "Bing Copilot"}


def render_html(name: str, period: str, gsc: dict | None, rev: dict | None,
                work: dict, lst: dict | None, calls: dict | None = None,
                activity: list[dict] | None = None, gbp: dict | None = None,
                pages: dict | None = None, rank: dict | None = None) -> str:
    e = html.escape
    parts: list[str] = []
    month_label = dt.datetime.strptime(period, "%Y-%m").strftime("%B %Y")

    if gsc:
        qrows = "".join(
            f"<tr><td>{e(q['q'])}</td><td class='n'>{_fmt(q['impr'])}</td>"
            f"<td class='n'>{_fmt(q['clicks'])}</td><td class='n'>{q['pos']:.0f}</td></tr>"
            for q in gsc["queries"])
        qtable = (f"<div class='twrap'><table><tr><th>Search term</th>"
                  f"<th class='n'>Times shown</th><th class='n'>Clicks</th>"
                  f"<th class='n'>Position</th></tr>{qrows}</table></div>"
                  if qrows else "")
        parts.append(f"""
<section><h2>Google Search</h2>
<div class="stats">
  <div class="stat"><div class="lbl">Times shown in Google</div>
    <div class="num">{_fmt(gsc['impr'])}{_delta_chip(gsc['impr'], gsc['impr_prev'])}</div>
    <div class="from">previous four weeks: {_fmt(gsc['impr_prev'])}</div></div>
  <div class="stat"><div class="lbl">Clicks to your website</div>
    <div class="num">{_fmt(gsc['clicks'])}{_delta_chip(gsc['clicks'], gsc['clicks_prev'])}</div>
    <div class="from">previous four weeks: {_fmt(gsc['clicks_prev'])}</div></div>
</div><p class="lbl" style="margin:.9rem 0 0">DAILY TIMES SHOWN IN GOOGLE, LAST 8 WEEKS</p>{_sparkline(gsc.get("series") or [])}{qtable}
<p class="note">Daily impressions over the last eight weeks, then the four weeks ending {e(gsc['end'])} compared with the four weeks before. Source: Google Search Console.</p>
</section>""")

    if rank:
        rstats = []
        if "page1" in rank:
            p1 = rank["page1"]
            rstats.append(
                f"<div class='stat'><div class='lbl'>Search terms on page 1</div>"
                f"<div class='num'>{_fmt(p1['cur'])}{_delta_chip(p1['cur'], p1['prev'])}</div>"
                f"<div class='from'>ranking in Google's top 10, previous four weeks: {_fmt(p1['prev'])}</div></div>")
        if "pages" in rank:
            pg = rank["pages"]
            rstats.append(
                f"<div class='stat'><div class='lbl'>Pages shown in Google</div>"
                f"<div class='num'>{_fmt(pg['cur'])}{_delta_chip(pg['cur'], pg['prev'])}</div>"
                f"<div class='from'>pages of your site Google put in front of searchers</div></div>")
        ai = rank.get("ai")
        if ai:
            top_bit = f", the #1 pick in {ai['top']}" if ai["top"] else ""
            trend = ""
            if ai.get("prev_pct") is not None:
                d = ai["pct"] - ai["prev_pct"]
                if d > 0:
                    trend = f'<span class="delta">up {d} pts</span>'
                elif d < 0:
                    trend = f'<span class="delta down">down {abs(d)} pts</span>'
            rstats.append(
                f"<div class='stat'><div class='lbl'>AI assistant visibility</div>"
                f"<div class='num'>{ai['pct']}<span class='of'>%</span>{trend}</div>"
                f"<div class='from'>named in {ai['cited']} of {ai['total']} AI answers "
                f"we tested{top_bit}</div></div>")
        grid_html = ""
        if rank.get("grid"):
            grows = []
            for g in rank["grid"]:
                if g["prev_rank"] is None:
                    tr = "<span class='of'>first scan</span>"
                elif g["prev_rank"] - g["rank"] >= 0.5:
                    tr = "<span style='color:var(--good);font-weight:700'>&#9650; improved</span>"
                elif g["rank"] - g["prev_rank"] >= 0.5:
                    tr = "<span style='color:var(--bad);font-weight:700'>&#9660; slipped</span>"
                else:
                    tr = "<span class='of'>steady</span>"
                grows.append(
                    f"<tr><td>{e(g['kw'])}</td><td>{e(g['city'])}</td>"
                    f"<td class='n'>#{g['rank']:.0f}</td>"
                    f"<td class='n'>{g['top3']:.0f}%</td><td>{tr}</td></tr>")
            grid_html = (
                f"<p class='lbl' style='margin:1rem 0 .4rem'>GOOGLE MAPS POSITIONS ACROSS YOUR SERVICE AREA</p>"
                f"<div class='twrap'><table><tr><th>Keyword</th><th>Scanned around</th>"
                f"<th class='n'>Average map position</th><th class='n'>Area in top 3</th>"
                f"<th>Trend</th></tr>{''.join(grows)}</table></div>")
        ai_html = ""
        if ai and ai.get("examples"):
            ex_parts = []
            for x in ai["examples"]:
                eng = _ENGINE_LABELS.get((x["engine"] or "").lower(),
                                         (x["engine"] or "").title())
                suffix = f", recommended #{int(x['rank'])}" if x.get("rank") else ""
                ex_parts.append(f"<li>&ldquo;{e(x['q'])}&rdquo; "
                                f"<span class='when'>{e(eng + suffix)}</span></li>")
            ex_lines = "".join(ex_parts)
            ai_html = (
                f"<p class='lbl' style='margin:1rem 0 .4rem'>AI ASSISTANTS RECOMMENDED YOU FOR</p>"
                f"<ul class='worklist'>{ex_lines}</ul>")
        if rstats or grid_html or ai_html:
            parts.append(f"""
<section><h2>Where you rank</h2>
{f'<div class="stats">{"".join(rstats)}</div>' if rstats else ''}
{grid_html}
{ai_html}
<p class="note">Map positions come from live scans of Google Maps results at a grid of points around your service area. AI visibility is measured by asking ChatGPT, Gemini and other assistants the questions your customers actually ask, then checking whether they name your business.</p>
</section>""")

    if rev:
        parts.append(f"""
<section><h2>Review campaign</h2>
<div class="stats">
  <div class="stat"><div class="lbl">Past customers messaged</div>
    <div class="num">{_fmt(rev['processed'])}<span class="of"> of {_fmt(rev['total'])}</span></div>
    <div class="from">{rev['pct']}% of your list, drip in progress</div></div>
  <div class="stat"><div class="lbl">Clicked your review link</div>
    <div class="num">{_fmt(rev['clicked'])}</div>
    <div class="from">{rev['click_rate']}% of those messaged</div></div>
</div></section>""")

    if gbp:
        bits = []
        if gbp.get("rating"):
            bits.append(f"<div class='stat'><div class='lbl'>Google rating</div>"
                        f"<div class='num'>{gbp['rating']}<span class='of'> stars</span></div>"
                        f"<div class='from'>{_fmt(gbp.get('reviews') or 0)} public reviews</div></div>")
        pub = []
        if gbp.get("posts"):
            pub.append(f"{gbp['posts']} Google posts")
        if gbp.get("photos"):
            pub.append(f"{gbp['photos']} photos")
        if gbp.get("svc_adds"):
            pub.append(f"{gbp['svc_adds']} services added")
        if pub:
            bits.append(f"<div class='stat'><div class='lbl'>Published to your profile</div>"
                        f"<div class='num'>{_fmt(gbp.get('posts') or 0) if gbp.get('posts') else ''}"
                        f"<span class='of'>{' posts this month' if gbp.get('posts') else ''}</span></div>"
                        f"<div class='from'>{e(', '.join(pub))}</div></div>")
        if bits:
            parts.append(f"""
<section><h2>Google Business Profile</h2>
<div class="stats">{''.join(bits)}</div></section>""")

    if calls:
        rows_html = "".join(
            f"<tr><td>{str(r.get('started_at') or '')[:10]}</td>"
            f"<td>{'Google listing' if (r.get('source') or 'gbp') == 'gbp' else 'Website'}</td>"
            f"<td class='n'>{e(_mask(r.get('from_number') or ''))}</td>"
            f"<td class='n'>{_dur(r.get('duration_seconds'))}</td></tr>"
            for r in calls["recent"])
        parts.append(f"""
<section><h2>Phone calls</h2>
<div class="stats">
  <div class="stat"><div class="lbl">Tracked calls, last 30 days</div>
    <div class="num">{_fmt(calls['total'])}</div>
    <div class="from">{calls['answered_live']} reached a person live</div></div>
  <div class="stat"><div class="lbl">Where they came from</div>
    <div class="num">{_fmt(calls['gbp'])}<span class="of"> Google</span> &#183; {_fmt(calls['website'])}<span class="of"> website</span></div>
    <div class="from">every call rings straight to your line and is recorded</div></div>
  {_answer_rate_stat(calls)}
  {_spam_blocked_stat(calls.get('spam_blocked') or 0)}
  {_outcomes_stat(calls.get('outcomes') or {})}
</div>
<div class='twrap'><table><tr><th>Date</th><th>Source</th><th class='n'>Caller</th><th class='n'>Length</th></tr>{rows_html}</table></div>
<p class="note">Call recordings are available any time in your account at app.restorationai.io.</p>
</section>""")

    gbp_lines = "".join(
        f"<li><b>{cnt}</b> {e(_GBP_LABELS.get(t, t.replace('_', ' ') + ' updates'))}</li>"
        for t, cnt in sorted(work["gbp_counts"].items(), key=lambda kv: -kv[1]) if cnt)
    rich = []
    if pages and pages["services"]:
        svc_bullets = "".join(
            f"<li>{e(sv)}: <b>{_fmt(pages['per'])}</b> pages, one for every service area</li>"
            for sv in pages["services"])
        rich.append(
            f"<li><b>{_fmt(pages['total'])} website pages published</b> across "
            f"{len(pages['services'])} services, every page with full on-page SEO: "
            f"structured data (JSON-LD), AI-assistant files (llms.txt), instant "
            f"search-engine submission (IndexNow + sitemaps), and internal linking."
            f"<ul style='margin:.5rem 0 0;padding-left:1.1rem'>{svc_bullets}</ul></li>")
    if lst and lst["live"]:
        bullets = "".join(
            (f"<li>{e(n)}" + (f" &#183; <a href='{e(u)}' target='_blank' rel='noopener'>view listing</a>" if u else "")
             + "</li>") for n, u in lst["entries"])
        rich.append(
            f"<li><b>{lst['live']} business listings live</b> on tracked directories "
            f"(consistent listings are how Google and AI assistants verify your business)."
            f"<ul style='margin:.5rem 0 0;padding-left:1.1rem'>{bullets}</ul></li>")
    work_lines = "".join(rich) + "".join(
        f"<li>{e(w['msg'])} <span class='when'>{e(w['when'])}</span></li>"
        for w in work["items"])
    if gbp_lines or work_lines:
        parts.append(f"""
<section><h2>Work delivered</h2>
{f"<ul class='counts'>{gbp_lines}</ul>" if gbp_lines else ""}
{f"<ul class='worklist'>{work_lines}</ul>" if work_lines else ""}
</section>""")



    if activity:
        act_lines = "".join(
            f"<li>{e(str(a.get('line') or ''))} <span class='when'>{e(str(a.get('date') or '')[:10])}</span></li>"
            for a in activity)
        parts.append(f"""
<section><h2>Every action, day by day</h2>
<details><summary>{len(activity)} logged actions this month, tap to expand</summary>
<ul class="worklist" style="margin-top:.8rem">{act_lines}</ul></details>
</section>""")

    body = "".join(parts) or "<section><p>Your campaign is just getting started. The first full month of results lands here.</p></section>"
    return f"""<meta charset="utf-8"><title>{e(name)} Results</title>
<style>
:root{{--paper:#FAFCFD;--panel:#FFF;--ink:#17222B;--sub:#5E707C;--line:#DCE6EC;
--blue:#1863A8;--navy:#0E3A5C;--good:#1E7D4E;--good-bg:#E7F4EC;--bad:#A33;--bad-bg:#F7ECEC}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--paper:#0D161C;--panel:#142129;
--ink:#E8F0F5;--sub:#9AAEBB;--line:#24363F;--blue:#5CA8E8;--navy:#BFDDF5;--good:#5BC98B;--good-bg:#173328;--bad:#E09;--bad-bg:#331722}}}}
:root[data-theme="dark"]{{--paper:#0D161C;--panel:#142129;--ink:#E8F0F5;--sub:#9AAEBB;--line:#24363F;
--blue:#5CA8E8;--navy:#BFDDF5;--good:#5BC98B;--good-bg:#173328;--bad:#E09;--bad-bg:#331722}}
*{{box-sizing:border-box}}body{{background:var(--paper);color:var(--ink);margin:0;
font:16px/1.55 -apple-system,"Segoe UI",Helvetica,Arial,sans-serif;padding:2.2rem 1.2rem 4rem}}
main{{max-width:820px;margin:0 auto;display:flex;flex-direction:column;gap:2rem}}
.kicker{{font-size:.75rem;letter-spacing:.14em;text-transform:uppercase;color:var(--blue);font-weight:700}}
h1{{font-size:1.7rem;color:var(--navy);margin:.1rem 0;text-wrap:balance}}
.meta{{color:var(--sub);font-size:.9rem}}
h2{{font-size:1.1rem;color:var(--navy);margin:0 0 .7rem}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem;margin-bottom:.8rem}}
.stat{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:1rem 1.15rem}}
.lbl{{font-size:.75rem;letter-spacing:.1em;text-transform:uppercase;color:var(--sub);font-weight:600}}
.num{{font-size:2rem;font-weight:700;font-variant-numeric:tabular-nums;margin:.2rem 0}}
.of{{font-size:1.05rem;color:var(--sub);font-weight:500}}
.from{{color:var(--sub);font-size:.88rem}}
.delta{{display:inline-block;background:var(--good-bg);color:var(--good);border-radius:999px;
padding:.1rem .55rem;font-size:.8rem;font-weight:700;margin-left:.4rem;vertical-align:middle}}
.delta.down{{background:var(--bad-bg);color:var(--bad)}}.delta.flat{{background:var(--line);color:var(--sub)}}
.twrap{{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--panel)}}
table{{border-collapse:collapse;width:100%;min-width:460px;font-size:.92rem}}
th{{font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;color:var(--sub);text-align:left;font-weight:600}}
th,td{{padding:.55rem .85rem;border-bottom:1px solid var(--line)}}tr:last-child td{{border-bottom:none}}
td.n,th.n{{text-align:right;font-variant-numeric:tabular-nums}}
ul.counts{{list-style:none;margin:0 0 .8rem;padding:0;display:flex;flex-wrap:wrap;gap:.5rem}}
ul.counts li{{background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:.35rem .85rem;font-size:.9rem}}
ul.worklist{{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:.5rem}}
ul.worklist li{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:.6rem .9rem;font-size:.93rem}}
.when{{color:var(--sub);font-size:.8rem;white-space:nowrap;margin-left:.4rem}}
.note{{color:var(--sub);font-size:.83rem}}
footer{{color:var(--sub);font-size:.83rem;border-top:1px solid var(--line);padding-top:.9rem}}
</style>
<main>
<header>
  <div class="kicker">Monthly Results</div>
  <h1>{e(name)}</h1>
  <div class="meta">{e(month_label)}. Prepared by Rank AI.</div>
</header>
{body}
<footer>Questions? Text us any time. This page updates monthly and the numbers come straight from Google Search Console, live map scans, AI assistant checks, your review campaign, and our work ledger.</footer>
</main>
"""


# ------------------------------------------------------------------- main
def notify_client(co: dict, url: str, period: str) -> str:
    """Monthly distribution (Santino 2026-08-31): one email with the report
    link + one [FOR MONICA] note so the text goes out through her guards and
    quiet windows. Called only with --notify (the monthly cron), never on
    manual regenerations."""
    month = dt.datetime.strptime(period, "%Y-%m").strftime("%B")
    # GREETING NAME LAW (Santino 2026-10-01): the September emails opened
    # "Hi California," / "Hi DRYCOR," because this took the first word of the
    # COMPANY name. Greet the person, via the same resolver Monica uses
    # (preferred contact -> owner -> "there"), never the business name.
    try:
        import client_concierge as _cc
        full = _cc.fetch_companies([co["id"]]).get(co["id"]) or co
        first = _cc.contact_first_name(None, full)
    except Exception:  # noqa: BLE001
        owner = (co.get("account_owner_name") or "").strip()
        first = owner.split()[0].title() if owner else "there"
    sent = []
    email = (co.get("email") or "").strip()
    sg = os.environ.get("SENDGRID_API_KEY") or ""
    if email and sg:
        r = requests.post("https://api.sendgrid.com/v3/mail/send",
                          headers={"Authorization": f"Bearer {sg}",
                                   "Content-Type": "application/json"},
                          json={"personalizations": [{"to": [{"email": email}]}],
                                "from": {"email": "contact@restorationai.io",
                                         "name": "Rank AI"},
                                "reply_to": {"email": "contact@restorationai.io"},
                                "subject": f"Your {month} results are ready",
                                "content": [{"type": "text/plain", "value":
                                    f"Hi {first},\n\nYour {month} results page is ready: "
                                    f"what showed up in Google, calls, your review "
                                    f"campaign, and everything we shipped for you, all "
                                    f"in one place.\n\n{url}\n\nQuestions? Just reply "
                                    f"to this email or text us.\n\nRank AI"}]},
                          timeout=30)
        sent.append(f"email {'ok' if r.ok else r.status_code}")
    requests.post(f"{SB_URL}/rest/v1/marketing_ops_notes",
                  headers=HDR | {"Prefer": "return=minimal"},
                  json={"company_id": co["id"], "status": "open", "body":
                        f"[FOR MONICA] Their {month} results page is ready. Send them "
                        f"the link with one warm line, e.g. 'your {month} results "
                        f"are in, here is everything in one page'. LINK (share "
                        f"exactly): {url}"},
                  timeout=30)
    sent.append("monica note filed")
    return ", ".join(sent)


def build_one(co: dict, slug: str | None, period: str, at: str | None,
              dry: bool, notify: bool = False) -> str:
    cid, name = co["id"], (co.get("name") or "").strip()
    domain = None
    if slug:
        try:
            cj = json.loads((ROOT / "clients" / f"{slug}.json").read_text())
            domain = (cj.get("domain") or "").strip() or None
        except Exception:  # noqa: BLE001
            pass
    gsc = gsc_section(domain, at) if (domain and at) else None
    rev = review_section(cid)
    work = work_section(cid)
    lst = listings_section(cid)
    calls = calls_section(cid)
    activity = activity_section(cid, period)
    gbp = gbp_section(cid)
    pages = pages_section(cid, slug)
    rank = rankings_section(cid, domain, at)
    if not (gsc or rev or calls or gbp or rank or work["items"] or work["gbp_counts"] or (lst and lst["live"])):
        return f"{name}: nothing reportable yet, skipped"
    page = render_html(name, period, gsc, rev, work, lst, calls, activity, gbp, pages, rank)
    if dry:
        return f"{name}: would publish ({len(page)} bytes; gsc={'y' if gsc else 'n'} rev={'y' if rev else 'n'} work={len(work['items'])})"

    # keep the same tokened URL across regenerations of the same period
    existing = _sb(f"marketing_client_reports?company_id=eq.{cid}&period=eq.{period}&select=url")
    if existing:
        key = "/".join(existing[0]["url"].rstrip("/").split("/")[-2:])
    else:
        key = f"{cid}/{period}-{secrets.token_hex(5)}.html"
    up = requests.post(f"{SB_URL}/storage/v1/object/{BUCKET}/{key}",
                       headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                                "Content-Type": "text/html; charset=utf-8",
                                "x-upsert": "true"},
                       data=page.encode(), timeout=60)
    if not up.ok:
        return f"{name}: UPLOAD FAILED {up.status_code} {up.text[:120]}"
    url = f"{REPORT_BASE}/{key}"
    requests.post(f"{SB_URL}/rest/v1/marketing_client_reports?on_conflict=company_id,period",
                  headers=HDR | {"Prefer": "resolution=merge-duplicates,return=minimal"},
                  json={"company_id": cid, "period": period, "url": url,
                        "stats": {"gsc": bool(gsc), "reviews": bool(rev),
                                  "work_items": len(work["items"])}},
                  timeout=30)
    if existing:
        if notify:
            return f"{name}: refreshed {url} [{notify_client(co, url, period)}]"
        return f"{name}: refreshed {url}"
    try:
        from work_log import work_log
        work_log(cid, "reporting", "monthly-report",
                 f"Your {dt.datetime.strptime(period, '%Y-%m').strftime('%B')} "
                 f"results report is ready: {url}",
                 evidence={"url": url, "period": period},
                 actor="automation", source="client_report.py")
    except Exception as ex:  # noqa: BLE001
        print(f"  [work-log] warn {name}: {str(ex)[:80]}")
    if notify:
        return f"{name}: published {url} [{notify_client(co, url, period)}]"
    return f"{name}: published {url}"


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--period", default=dt.date.today().strftime("%Y-%m"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--notify", action="store_true",
                    help="Also email each client their report link + file the "
                         "Monica SMS note (monthly cron only)")
    args = ap.parse_args()

    cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
    slug_by_cid = {v: k for k, v in cmap.items()}
    cos = _sb("companies?select=id,name,status,plan,email&plan=ilike.rank%20ai")
    cos = [c for c in cos
           if str(c.get("status") or "").strip().lower() not in _INACTIVE
           and not re.match(r"^\s*(test\b|rank\s*ai\b|restoration\s*ai\b)",
                            c.get("name") or "", re.I)]
    if args.slug:
        cos = [c for c in cos if slug_by_cid.get(c["id"]) == args.slug]
        if not cos:
            print(f"no active company for slug {args.slug}")
            return 1
    at = _gsc_token()
    if not at:
        print("  (no GSC token; search sections skipped)")
    for co in sorted(cos, key=lambda c: c.get("name") or ""):
        try:
            print("  " + build_one(co, slug_by_cid.get(co["id"]), args.period,
                                   at, args.dry_run, notify=args.notify))
        except Exception as ex:  # noqa: BLE001 — one client never sinks the fleet
            print(f"  {co.get('name')}: ERROR {type(ex).__name__}: {str(ex)[:140]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
