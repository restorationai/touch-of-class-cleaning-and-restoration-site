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

_INACTIVE = {"paused", "cancelled", "canceled", "churned", "inactive", "archived"}


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
    top = q(start, end, ["query"], 6) or {}
    queries = [{"q": r["keys"][0], "impr": int(r["impressions"]),
                "clicks": int(r["clicks"]), "pos": round(r["position"], 1)}
               for r in (top.get("rows") or [])
               if r.get("impressions", 0) >= 5]
    return {"impr": ci, "clicks": cc, "impr_prev": pi, "clicks_prev": pc,
            "start": str(start), "end": str(end), "queries": queries[:5]}


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
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat()
    logs = _sb(f"marketing_work_log?company_id=eq.{cid}"
               f"&ts=gte.{since}&order=ts.desc"
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
        key = re.sub(r"\d+", "#", str(lg.get("detail") or ""))[:80]
        if key in seen:
            continue
        seen.add(key)
        items.append({"msg": str(lg.get("detail") or "").strip(),
                      "when": str(lg.get("ts") or "")[:10]})
        if len(items) >= 10:
            break
    return {"items": items, "gbp_counts": by_type}


def listings_section(cid: str) -> dict | None:
    rows = _sb(f"citation_listings?company_id=eq.{cid}&select=directory,status,listing_url")
    live = [r for r in rows if r.get("status") == "live"]
    if not rows:
        return None
    return {"live": len(live), "total": len(rows),
            "names": sorted({r["directory"].replace("_", " ").title() for r in live})[:10]}


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


def _delta_chip(cur: int, prev: int) -> str:
    if prev <= 0:
        return ""
    x = cur / prev
    if x >= 1.05:
        return f'<span class="delta">{x:.1f}x</span>'
    if x <= 0.95:
        return f'<span class="delta down">{round((1 - x) * 100)}% down</span>'
    return '<span class="delta flat">steady</span>'


def render_html(name: str, period: str, gsc: dict | None, rev: dict | None,
                work: dict, lst: dict | None) -> str:
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
</div>{qtable}
<p class="note">Four weeks ending {e(gsc['end'])}, compared with the four weeks before. Source: Google Search Console.</p>
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

    gbp_lines = "".join(
        f"<li><b>{cnt}</b> {e(_GBP_LABELS.get(t, t.replace('_', ' ') + ' updates'))}</li>"
        for t, cnt in sorted(work["gbp_counts"].items(), key=lambda kv: -kv[1]) if cnt)
    work_lines = "".join(
        f"<li>{e(w['msg'])} <span class='when'>{e(w['when'])}</span></li>"
        for w in work["items"])
    if gbp_lines or work_lines:
        parts.append(f"""
<section><h2>Work delivered</h2>
{f"<ul class='counts'>{gbp_lines}</ul>" if gbp_lines else ""}
{f"<ul class='worklist'>{work_lines}</ul>" if work_lines else ""}
</section>""")

    if lst and lst["live"]:
        names = ", ".join(html.escape(n) for n in lst["names"])
        parts.append(f"""
<section><h2>Business listings</h2>
<p>Your business is live on <b>{lst['live']}</b> tracked directories{f" including {names}" if names else ""}. Consistent listings strengthen how Google and AI assistants verify your business.</p>
</section>""")

    body = "".join(parts) or "<section><p>Your campaign is just getting started. The first full month of results lands here.</p></section>"
    return f"""<title>{e(name)} Results</title>
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
<footer>Questions? Text us any time. This page updates monthly and the numbers come straight from Google Search Console, your review campaign, and our work ledger.</footer>
</main>
"""


# ------------------------------------------------------------------- main
def build_one(co: dict, slug: str | None, period: str, at: str | None,
              dry: bool) -> str:
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
    if not (gsc or rev or work["items"] or work["gbp_counts"] or (lst and lst["live"])):
        return f"{name}: nothing reportable yet, skipped"
    page = render_html(name, period, gsc, rev, work, lst)
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
    try:
        from work_log import work_log
        work_log(cid, "reporting", "monthly-report",
                 f"Your {dt.datetime.strptime(period, '%Y-%m').strftime('%B')} "
                 f"results report is ready: {url}",
                 evidence={"url": url, "period": period},
                 actor="automation", source="client_report.py")
    except Exception as ex:  # noqa: BLE001
        print(f"  [work-log] warn {name}: {str(ex)[:80]}")
    return f"{name}: published {url}"


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--period", default=dt.date.today().strftime("%Y-%m"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
    slug_by_cid = {v: k for k, v in cmap.items()}
    cos = _sb("companies?select=id,name,status,plan&plan=ilike.rank%20ai")
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
                                   at, args.dry_run))
        except Exception as ex:  # noqa: BLE001 — one client never sinks the fleet
            print(f"  {co.get('name')}: ERROR {type(ex).__name__}: {str(ex)[:140]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
