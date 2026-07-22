#!/usr/bin/env python3
"""progress_report.py — weekly baseline-vs-now progress reports (churn killer).

For every Active 'Rank AI'-plan company with integration_settings.
baseline_audit_id (the funnel audit = their permanent day-0 record), this
re-measures the SAME probes the audit ran — Google rankings for the same
keyword set, the same live AI-search questions, GBP review count — plus
content shipped, renders a compact before/after HTML report, uploads it to
R2, and inserts a marketing_reports row so it appears in the app's Reports
tab next to the baseline.

Self-gating: skips any company whose last progress report is younger than
6 days, so the ops scheduler can run it daily and each client still gets
exactly one report per week. Costs ~$0.20-0.50/client/week (DataForSEO
only — no LLM calls; every number is measured, never written).

Usage:
  python3 scripts/progress_report.py --all [--force] [--dry-run]
  python3 scripts/progress_report.py --company-id CO-... [--force]
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

import lead_audit as la  # noqa: E402  run_rankings / run_ai_search / r2 helpers

PETROL = "#0E5874"
PETROL_DK = "#0A3A52"


def sb(method, path, body=None, prefer="return=representation"):
    url = os.environ["SUPABASE_URL"] + path
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    req = urllib.request.Request(url, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"apikey": key, "Authorization": "Bearer " + key,
                 "Content-Type": "application/json", "Prefer": prefer})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


def _esc(s):
    return html.escape(str(s if s is not None else ""))


def _pos(p):
    return "#{}".format(p) if p else "not in top 20"


def _delta_arrow(before, after, lower_is_better=True):
    if before is None and after is None:
        return ""
    if before == after:
        return "→"
    if before is None:
        return "▲"          # unranked -> ranked
    if after is None:
        return "▼"
    improved = (after < before) if lower_is_better else (after > before)
    return "▲" if improved else "▼"


def measure(company, baseline):
    """Re-run the audit's own probes; every metric measured, none invented."""
    data = baseline["data"]
    biz = data["business"]
    domain = data["domain"]
    service = (biz.get("services") or ["water damage restoration"])[0]
    cities = biz.get("cities") or []
    auth = la._dfs_auth()

    rankings_now, _ = la.run_rankings(auth, domain, service, cities)
    ai_now, _ = la.run_ai_search(auth, domain, biz.get("business_name"), service, cities)

    reviews_now = {}
    prof = sb("GET", "/rest/v1/marketing_gbp_profiles?company_id=eq.{}"
              "&select=rating,review_count".format(company["id"]))
    if prof and prof[0].get("review_count") is not None:
        reviews_now = {"rating": prof[0].get("rating"),
                       "count": prof[0].get("review_count")}
    else:
        place = (data.get("gbp") or {}).get("place_id")
        if place:
            try:
                g, _ = la.gbp_by_id(auth, place_id=place)
                if g.get("found"):
                    reviews_now = {"rating": g.get("rating"), "count": g.get("reviews")}
            except Exception:
                pass

    content_published = 0
    try:
        rows = sb("GET", "/rest/v1/marketing_content?company_id=eq.{}"
                  "&status=eq.published&select=id".format(company["id"]))
        content_published = len(rows or [])
    except Exception:
        pass

    return {"rankings": rankings_now, "ai": ai_now, "reviews": reviews_now,
            "content_published": content_published}


def build_html(company, baseline, now, baseline_date):
    data = baseline["data"]
    b_rank = {r["keyword"]: r.get("position") for r in (data.get("rankings") or [])}
    n_rank = {r["keyword"]: r.get("position") for r in now["rankings"]}
    kws = list(b_rank.keys()) or list(n_rank.keys())

    b_ranked = sum(1 for p in b_rank.values() if p)
    n_ranked = sum(1 for p in n_rank.values() if p)
    b_ai = data.get("ai_search") or []
    b_cited = sum(1 for r in b_ai if r.get("cited"))
    b_ai_total = sum(1 for r in b_ai if r.get("cited") is not None)
    n_cited = sum(1 for r in now["ai"] if r.get("cited"))
    n_ai_total = sum(1 for r in now["ai"] if r.get("cited") is not None)
    b_reviews = (data.get("gbp") or {}).get("reviews")
    n_reviews = (now.get("reviews") or {}).get("count")

    def chip(label, before, after, arrow):
        return ('<div class="chip"><div class="cl">{}</div>'
                '<div class="cv">{} <span class="ar">{}</span> <b>{}</b></div></div>'
                ).format(_esc(label), _esc(before), arrow, _esc(after))

    chips = [
        chip("Keywords ranked (top 20)", "{}/{}".format(b_ranked, len(kws)),
             "{}/{}".format(n_ranked, len(kws)),
             _delta_arrow(len(kws) - b_ranked, len(kws) - n_ranked)),
        chip("AI answers citing you", "{}/{}".format(b_cited, b_ai_total),
             "{}/{}".format(n_cited, n_ai_total),
             _delta_arrow(b_cited, n_cited, lower_is_better=False)),
    ]
    if b_reviews is not None or n_reviews is not None:
        chips.append(chip("Google reviews", b_reviews if b_reviews is not None else "—",
                          n_reviews if n_reviews is not None else "—",
                          _delta_arrow(b_reviews, n_reviews, lower_is_better=False)))
    if now.get("content_published"):
        chips.append('<div class="chip"><div class="cl">Content pieces live</div>'
                     '<div class="cv"><b>{}</b></div></div>'.format(now["content_published"]))

    rows = []
    for kw in kws:
        b, n = b_rank.get(kw), n_rank.get(kw)
        cls = "up" if _delta_arrow(b, n) == "▲" else ("dn" if _delta_arrow(b, n) == "▼" else "")
        rows.append("<tr><td>{}</td><td>{}</td><td class='{}'>{} {}</td></tr>".format(
            _esc(kw), _esc(_pos(b)), cls, _esc(_pos(n)), _delta_arrow(b, n)))

    today = dt.date.today().strftime("%B %d, %Y")
    return """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Progress Report — {name}</title>
<style>
body{{font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif;background:#f1f5f9;color:#1f2937;margin:0;padding:24px 14px}}
.card{{max-width:760px;margin:0 auto;background:#fff;border-radius:16px;border:1px solid #e2e8f0;padding:32px 28px}}
.k{{color:{petrol};font-weight:700;font-size:12px;letter-spacing:.12em;text-transform:uppercase}}
h1{{margin:6px 0 2px;font-size:26px;color:#0f172a}}
.sub{{color:#64748b;font-size:14px;margin-bottom:22px}}
.chips{{display:flex;flex-wrap:wrap;gap:12px;margin:18px 0 26px}}
.chip{{flex:1 1 200px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:14px 16px}}
.cl{{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}}
.cv{{font-size:20px;color:#0f172a}} .cv b{{color:{petrol}}}
.ar{{color:#94a3b8;font-size:14px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th{{text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.06em;padding:8px 6px;border-bottom:1px solid #e2e8f0}}
td{{padding:9px 6px;border-bottom:1px solid #f1f5f9}}
td.up{{color:#0f766e;font-weight:600}} td.dn{{color:#b91c1c}}
.foot{{margin-top:26px;color:#94a3b8;font-size:12.5px;text-align:center}}
</style></head><body><div class="card">
<div class="k">Restoration AI · Progress Report</div>
<h1>{name}</h1>
<div class="sub">Baseline {bdate} &nbsp;→&nbsp; measured {today}. Same keywords, same live AI questions, same tools as your original report.</div>
<div class="chips">{chips}</div>
<table><tr><th>Search</th><th>Baseline</th><th>Now</th></tr>{rows}</table>
<div class="foot">Every number above is measured live, never estimated. Prepared by Restoration AI · restorationai.io</div>
</div></body></html>""".format(
        name=_esc(company["name"]), bdate=_esc(baseline_date), today=today,
        chips="".join(chips), rows="".join(rows), petrol=PETROL)


def run_company(company, force=False, dry_run=False):
    ints = company.get("integration_settings") or {}
    if isinstance(ints, str):
        try:
            ints = json.loads(ints)
        except Exception:
            ints = {}
    aid = ints.get("baseline_audit_id")
    if not aid:
        return "no baseline_audit_id — skip"

    recent = sb("GET", "/rest/v1/marketing_reports?company_id=eq.{}"
                "&report_month=like.Progress*&order=created_at.desc&limit=1"
                .format(company["id"]))
    if recent and not force:
        age = (dt.datetime.now(dt.timezone.utc)
               - dt.datetime.fromisoformat(recent[0]["created_at"].replace("Z", "+00:00")))
        if age.days < 6:
            return "last progress report {}d old — skip".format(age.days)

    raw = la.r2_get(la.PRIVATE_BUCKET, "lead-audits/{}/audit.json".format(aid))
    if not raw:
        return "baseline audit.json missing — skip"
    baseline = json.loads(raw)
    baseline_date = (baseline.get("created_at") or "")[:10] or "day 0"
    if baseline.get("created_at") and not force:
        b_age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(
            baseline["created_at"].replace("Z", "+00:00")))
        if b_age.days < 6:
            return "baseline only {}d old — first report at day 7".format(b_age.days)

    now = measure(company, baseline)
    html_out = build_html(company, baseline, now, baseline_date)
    if dry_run:
        out = "/tmp/progress-{}.html".format(company["id"])
        Path(out).write_text(html_out)
        return "dry run — wrote " + out

    key = "lead-audits/{}/progress-{}.html".format(aid, dt.date.today().strftime("%Y%m%d"))
    if not la.r2_put(la.BUCKET, key, html_out.encode(), "text/html; charset=utf-8"):
        return "R2 upload failed"
    url = "{}/{}".format(la.PUBLIC_BASE, key)

    sb("POST", "/rest/v1/marketing_reports", body={
        "company_id": company["id"],
        "report_month": "Progress — {}".format(dt.date.today().strftime("%b %d, %Y")),
        "report_url": url, "status": "completed",
        "posts_published": now.get("content_published") or 0,
        "videos_created": 0, "avg_lighthouse_score": 0,
    }, prefer="return=minimal")
    return "report published: " + url


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--company-id")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.company_id:
        cos = sb("GET", "/rest/v1/companies?id=eq.{}&select=id,name,integration_settings"
                 .format(args.company_id))
    elif args.all:
        cos = sb("GET", "/rest/v1/companies?status=eq.Active&plan=eq.Rank%20AI"
                 "&select=id,name,integration_settings")
    else:
        sys.exit("pass --company-id or --all")

    for co in cos or []:
        try:
            print("{}: {}".format(co["name"], run_company(co, args.force, args.dry_run)))
        except Exception as e:
            print("{}: ERROR {}".format(co["name"], str(e)[:200]))


if __name__ == "__main__":
    main()
