#!/usr/bin/env python3
"""
ads_dashboard.py — generate a self-contained Google Ads dashboard for a client.

Pulls live data (campaigns, daily trend, ALL search terms with clicks, existing
negatives) + runs the ads_review vetter to flag which search terms are NEW negatives
we haven't applied yet. Writes a single static HTML file (data embedded, no backend)
to ads-dashboard/{slug}.html — open it in a browser.

    python3 scripts/ads_dashboard.py --slug narestco [--days 30]
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import ads_manager as am  # noqa: E402
import ads_review as ar   # noqa: E402


def _norm(t: str) -> str:
    return (t or "").strip().lower()


def gather(slug: str, days: int) -> dict:
    client = am.build_ads_client(slug, login_as_mcc=True)
    cid = am.get_customer_id(am.load_client(slug), slug)
    rec = am.load_client(slug)
    name = rec.get("display_name", slug)
    win = f"DURING LAST_{days}_DAYS" if days in (7, 14, 30) else "DURING LAST_30_DAYS"

    # Campaigns
    campaigns = []
    for r in am.gaql(client, cid, f"""
        SELECT campaign.name, campaign.status, metrics.cost_micros, metrics.clicks,
          metrics.impressions, metrics.conversions, metrics.conversions_value,
          metrics.search_impression_share, metrics.search_rank_lost_impression_share,
          metrics.search_budget_lost_impression_share
        FROM campaign WHERE segments.date {win}
          AND campaign.advertising_channel_type IN ('SEARCH','LOCAL_SERVICES')
        ORDER BY metrics.cost_micros DESC"""):
        c, m = r.campaign, r.metrics
        campaigns.append({
            "name": c.name, "status": c.status.name, "cost": m.cost_micros / 1e6,
            "clicks": m.clicks, "impr": m.impressions, "conv": round(m.conversions, 1),
            "value": round(m.conversions_value), "is": round((m.search_impression_share or 0) * 100),
            "lost_rank": round((m.search_rank_lost_impression_share or 0) * 100),
            "lost_budget": round((m.search_budget_lost_impression_share or 0) * 100),
        })

    # Daily (last 14d)
    daily = []
    for r in am.gaql(client, cid, """
        SELECT segments.date, metrics.cost_micros, metrics.clicks, metrics.impressions,
          metrics.conversions FROM customer WHERE segments.date DURING LAST_14_DAYS
        ORDER BY segments.date DESC"""):
        m = r.metrics
        daily.append({"date": r.segments.date, "cost": round(m.cost_micros / 1e6, 2),
                      "clicks": m.clicks, "impr": m.impressions, "conv": round(m.conversions, 1)})

    # ALL search terms with clicks
    terms = []
    for r in am.gaql(client, cid, f"""
        SELECT search_term_view.search_term, segments.search_term_match_type, campaign.name,
          metrics.clicks, metrics.impressions, metrics.cost_micros, metrics.conversions
        FROM search_term_view WHERE segments.date {win} AND metrics.clicks > 0
        ORDER BY metrics.cost_micros DESC"""):
        m = r.metrics
        terms.append({
            "term": r.search_term_view.search_term,
            "match": r.segments.search_term_match_type.name.replace("_", " ").title(),
            "campaign": r.campaign.name, "clicks": m.clicks, "impr": m.impressions,
            "cost": round(m.cost_micros / 1e6, 2), "conv": round(m.conversions, 1),
        })

    # Existing negatives (to flag already-blocked terms)
    existing = set()
    for r in am.gaql(client, cid, """
        SELECT campaign_criterion.keyword.text FROM campaign_criterion
        WHERE campaign_criterion.negative=TRUE AND campaign_criterion.type='KEYWORD'"""):
        t = _norm(r.campaign_criterion.keyword.text)
        if t:
            existing.add(t)

    # Vetter: what the review would negate -> split NEW vs already-negated
    review = ar.review_client(slug, set(), apply=False)
    to_negate = {_norm(j["term"]) for j in review.get("applied", [])}
    def covered(t): return any(neg == t or neg in t for neg in existing)
    new_negs = {t for t in to_negate if not covered(t)}

    # Tag each search term with a status
    for t in terms:
        n = _norm(t["term"])
        if covered(n):
            t["status"] = "negated"
        elif n in new_negs:
            t["status"] = "to_negate"
        elif t["conv"] > 0:
            t["status"] = "converting"
        else:
            t["status"] = "active"

    totals = {
        "cost": round(sum(c["cost"] for c in campaigns), 2),
        "clicks": sum(c["clicks"] for c in campaigns),
        "impr": sum(c["impr"] for c in campaigns),
        "conv": round(sum(c["conv"] for c in campaigns), 1),
        "value": round(sum(c["value"] for c in campaigns)),
        "terms": len(terms),
        "new_neg_count": len(new_negs),
        "new_neg_cost": round(sum(t["cost"] for t in terms if t["status"] == "to_negate"), 2),
        "negated_existing": len(existing),
    }
    return {"name": name, "slug": slug, "customer_id": cid, "days": days,
            "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "totals": totals, "campaigns": campaigns, "daily": daily, "terms": terms}


HTML = """<!DOCTYPE html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>{name} — Google Ads</title>
<style>
:root{{--bg:#f7f8fa;--card:#fff;--bd:#e7e9ee;--ink:#0f172a;--mut:#64748b;--accent:#4f46e5;
--rose:#e11d48;--amber:#d97706;--emerald:#059669;--amberbg:#fffbeb;--rosebg:#fff1f2;--embg:#ecfdf5;}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1280px;margin:0 auto;padding:32px 24px 80px}}
h1{{font-size:22px;font-weight:700;letter-spacing:-.01em;margin:0}}
.sub{{color:var(--mut);font-size:13px;margin-top:4px}}
.tiles{{display:grid;grid-template-columns:repeat(6,1fr);gap:1px;background:var(--bd);
border:1px solid var(--bd);border-radius:16px;overflow:hidden;margin:24px 0}}
.tile{{background:var(--card);padding:16px 18px}}
.tile .l{{font-size:12px;color:var(--mut);font-weight:500}}
.tile .v{{font-size:24px;font-weight:700;letter-spacing:-.02em;margin-top:2px;font-variant-numeric:tabular-nums}}
.card{{background:var(--card);border:1px solid var(--bd);border-radius:16px;overflow:hidden;margin:20px 0}}
.card h2{{font-size:14px;font-weight:700;margin:0;padding:16px 20px;border-bottom:1px solid var(--bd)}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{text-align:left;padding:9px 14px;border-bottom:1px solid #f1f2f5;white-space:nowrap}}
th{{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut);font-weight:700;
cursor:pointer;user-select:none}}
td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums}}
tr:last-child td{{border-bottom:0}}
.term{{font-weight:500;max-width:340px;overflow:hidden;text-overflow:ellipsis}}
.camp{{color:var(--mut);font-size:12px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700}}
.b-negate{{background:var(--amberbg);color:var(--amber)}}
.b-negated{{background:#f1f5f9;color:var(--mut)}}
.b-converting{{background:var(--embg);color:var(--emerald)}}
.b-active{{background:#eef2ff;color:var(--accent)}}
.bar{{display:inline-block;height:8px;background:var(--accent);border-radius:4px;vertical-align:middle}}
.controls{{display:flex;gap:8px;flex-wrap:wrap;padding:14px 20px;border-bottom:1px solid var(--bd);align-items:center}}
.filter{{padding:6px 12px;border:1px solid var(--bd);background:#fff;border-radius:999px;font-size:12px;
font-weight:600;color:var(--mut);cursor:pointer}}
.filter.on{{background:var(--ink);color:#fff;border-color:var(--ink)}}
#q{{margin-left:auto;padding:7px 12px;border:1px solid var(--bd);border-radius:10px;font-size:13px;width:220px}}
.note{{background:var(--amberbg);border:1px solid #fde68a;border-radius:14px;padding:14px 18px;margin:20px 0;font-size:13px;color:#92400e}}
.muted{{color:var(--mut)}}
</style></head><body><div class=wrap>
<h1>{name} — Google Ads</h1>
<div class=sub>Customer {customer_id} · last {days} days · generated {generated}</div>

<div class=tiles>
<div class=tile><div class=l>Spend</div><div class=v>${t_cost}</div></div>
<div class=tile><div class=l>Clicks</div><div class=v>{t_clicks}</div></div>
<div class=tile><div class=l>Impressions</div><div class=v>{t_impr}</div></div>
<div class=tile><div class=l>Conversions</div><div class=v>{t_conv}</div></div>
<div class=tile><div class=l>Cost / conv</div><div class=v>{t_cpa}</div></div>
<div class=tile><div class=l>Conv. value</div><div class=v>${t_value}</div></div>
</div>

<div class=note><b>{new_neg_count} new negative keywords</b> to apply (${new_neg_cost} wasted in {days}d) —
on top of the <b>{negated_existing}</b> already on the account. Filter the table by
<b>“To negate (new)”</b> below.</div>

<div class=card><h2>Campaigns</h2><table id=camps>
<thead><tr><th>Campaign</th><th>Status</th><th class=num>Spend</th><th class=num>Clicks</th>
<th class=num>Conv</th><th class=num>Lost→Rank</th><th class=num>Lost→Budget</th></tr></thead>
<tbody>{camp_rows}</tbody></table></div>

<div class=card><h2>Daily (last 14 days)</h2><table>
<thead><tr><th>Date</th><th class=num>Spend</th><th class=num>Clicks</th><th class=num>Impr</th>
<th class=num>Conv</th><th>Spend trend</th></tr></thead><tbody>{daily_rows}</tbody></table></div>

<div class=card><h2>Search terms that got clicks ({t_terms})</h2>
<div class=controls>
<span class=filter data-f=all onclick=f(this)>All</span>
<span class="filter" data-f=to_negate onclick=f(this)>To negate (new)</span>
<span class=filter data-f=negated onclick=f(this)>Already negated</span>
<span class=filter data-f=converting onclick=f(this)>Converting</span>
<span class=filter data-f=active onclick=f(this)>Active (kept)</span>
<input id=q placeholder="search terms…" oninput=draw()>
</div>
<table id=terms><thead><tr>
<th data-k=term>Search term</th><th data-k=match>Match</th><th data-k=campaign>Campaign</th>
<th class=num data-k=clicks>Clicks</th><th class=num data-k=impr>Impr</th>
<th class=num data-k=cost>Cost</th><th class=num data-k=conv>Conv</th><th>Status</th>
</tr></thead><tbody id=tbody></tbody></table></div>

<p class=muted style=font-size:12px>Zero-backend snapshot · re-run <code>ads_dashboard.py --slug {slug}</code> to refresh.</p>
</div>
<script>
const DATA={data_json};
let cur='all', sortK='cost', sortDir=-1;
const BADGE={{to_negate:['To negate','b-negate'],negated:['Negated','b-negated'],
converting:['Converting','b-converting'],active:['Kept','b-active']}};
function f(el){{document.querySelectorAll('.filter').forEach(x=>x.classList.remove('on'));
el.classList.add('on');cur=el.dataset.f;draw();}}
document.querySelectorAll('#terms th[data-k]').forEach(th=>th.onclick=()=>{{
  const k=th.dataset.k; sortDir=(sortK===k)?-sortDir:-1; sortK=k; draw();}});
function draw(){{
  const q=(document.getElementById('q').value||'').toLowerCase();
  let rows=DATA.terms.filter(t=>cur==='all'||t.status===cur)
    .filter(t=>!q||t.term.toLowerCase().includes(q));
  rows.sort((a,b)=>{{let x=a[sortK],y=b[sortK];
    if(typeof x==='string')return sortDir*x.localeCompare(y);return sortDir*(x-y);}});
  document.getElementById('tbody').innerHTML=rows.map(t=>{{
    const [lab,cls]=BADGE[t.status]||['','b-active'];
    return `<tr><td class=term>${{esc(t.term)}}</td><td class=muted>${{t.match}}</td>
    <td class=camp>${{esc(shortC(t.campaign))}}</td><td class=num>${{t.clicks}}</td>
    <td class=num>${{t.impr}}</td><td class=num>$${{t.cost.toFixed(2)}}</td>
    <td class=num>${{t.conv||''}}</td><td><span class="badge ${{cls}}">${{lab}}</span></td></tr>`;
  }}).join('')||'<tr><td colspan=8 class=muted style=padding:24px;text-align:center>No terms match.</td></tr>';
}}
function shortC(c){{return c.replace('National Restoration Construction - ','').replace('LocalServicesCampaign:SystemGenerated:','LSA ');}}
function esc(s){{return (s||'').replace(/[&<>]/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[m]));}}
document.querySelector('.filter[data-f=all]').classList.add('on');draw();
</script></body></html>"""


def render(d: dict) -> str:
    t = d["totals"]
    cpa = f"${t['cost']/t['conv']:,.0f}" if t["conv"] else "—"
    def st(s): return {"negated": ["Negated", "b-negated"], "to_negate": ["To negate", "b-negate"],
                       "converting": ["Converting", "b-converting"]}.get(s, ["Kept", "b-active"])
    camp_rows = "".join(
        f"<tr><td class=term>{html.escape(c['name'])}</td><td class=muted>{c['status']}</td>"
        f"<td class=num>${c['cost']:,.0f}</td><td class=num>{c['clicks']}</td>"
        f"<td class=num>{c['conv']}</td><td class=num>{c['lost_rank']}%</td>"
        f"<td class=num>{c['lost_budget']}%</td></tr>" for c in d["campaigns"])
    mx = max((x["cost"] for x in d["daily"]), default=1) or 1
    daily_rows = "".join(
        f"<tr><td>{x['date']}</td><td class=num>${x['cost']:,.2f}</td><td class=num>{x['clicks']}</td>"
        f"<td class=num>{x['impr']}</td><td class=num>{x['conv']}</td>"
        f"<td><span class=bar style=width:{int(x['cost']/mx*180)}px></span></td></tr>" for x in d["daily"])
    return HTML.format(
        name=html.escape(d["name"]), customer_id=d["customer_id"], days=d["days"],
        generated=d["generated"], slug=d["slug"],
        t_cost=f"{t['cost']:,.0f}", t_clicks=f"{t['clicks']:,}", t_impr=f"{t['impr']:,}",
        t_conv=t["conv"], t_cpa=cpa, t_value=f"{t['value']:,}", t_terms=t["terms"],
        new_neg_count=t["new_neg_count"], new_neg_cost=f"{t['new_neg_cost']:,.2f}",
        negated_existing=t["negated_existing"],
        camp_rows=camp_rows, daily_rows=daily_rows,
        data_json=json.dumps({"terms": d["terms"]}))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()
    d = gather(args.slug, args.days)
    out_dir = ROOT / "ads-dashboard"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{args.slug}.html"
    out.write_text(render(d))
    print(f"==> {out}")
    print(f"    open: file://{out}")
    print(f"    {d['totals']['terms']} search terms | {d['totals']['new_neg_count']} new negatives "
          f"(${d['totals']['new_neg_cost']}) | spend ${d['totals']['cost']:,.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
