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

    # Daily spend-by-date (full window)
    daily = []
    for r in am.gaql(client, cid, f"""
        SELECT segments.date, metrics.cost_micros, metrics.clicks, metrics.impressions,
          metrics.conversions FROM customer WHERE segments.date {win}
        ORDER BY segments.date DESC"""):
        m = r.metrics
        daily.append({"date": r.segments.date, "cost": round(m.cost_micros / 1e6, 2),
                      "clicks": m.clicks, "impr": m.impressions, "conv": round(m.conversions, 1)})

    # ALL search terms with clicks, BY DATE (so each day can be drilled into) — incl.
    # the ad group ("ad set") + the keyword that triggered each click.
    raw = []
    for r in am.gaql(client, cid, f"""
        SELECT search_term_view.search_term, segments.date, segments.search_term_match_type,
          campaign.name, ad_group.name, segments.keyword.info.text, segments.keyword.info.match_type,
          metrics.clicks, metrics.impressions, metrics.cost_micros, metrics.conversions
        FROM search_term_view WHERE segments.date {win} AND metrics.clicks > 0
        ORDER BY metrics.cost_micros DESC"""):
        m = r.metrics
        kw = r.segments.keyword.info
        raw.append({
            "term": r.search_term_view.search_term, "date": r.segments.date,
            "match": r.segments.search_term_match_type.name.replace("_", " ").title(),
            "campaign": r.campaign.name, "adgroup": r.ad_group.name,
            "kw": kw.text or "", "kwmatch": kw.match_type.name.title() if kw.text else "",
            "clicks": m.clicks, "impr": m.impressions,
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

    # Per-term aggregate (status is per-term, not per-day) -> tag every dated row.
    from collections import defaultdict
    agg = defaultdict(lambda: {"cost": 0.0, "conv": 0.0})
    for t in raw:
        a = agg[_norm(t["term"])]; a["cost"] += t["cost"]; a["conv"] += t["conv"]
    def status_for(term: str) -> str:
        n = _norm(term)
        if covered(n): return "negated"
        if n in new_negs: return "to_negate"
        if agg[n]["conv"] > 0: return "converting"
        return "active"
    for t in raw:
        t["status"] = status_for(t["term"])

    uniq = {_norm(t["term"]): t["status"] for t in raw}
    new_neg_terms = [n for n, s in uniq.items() if s == "to_negate"]
    totals = {
        "cost": round(sum(c["cost"] for c in campaigns), 2),
        "clicks": sum(c["clicks"] for c in campaigns),
        "impr": sum(c["impr"] for c in campaigns),
        "conv": round(sum(c["conv"] for c in campaigns), 1),
        "value": round(sum(c["value"] for c in campaigns)),
        "terms": len(uniq),
        "new_neg_count": len(new_neg_terms),
        "new_neg_cost": round(sum(agg[n]["cost"] for n in new_neg_terms), 2),
        "negated_existing": len(existing),
    }
    terms = raw
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
tr.drow{{cursor:pointer}} tr.drow:hover{{background:#f4f6fb}} tr.drow.sel{{background:#eef2ff}}
tr.drow td:first-child::before{{content:"▸ ";color:var(--accent)}} tr.drow.sel td:first-child::before{{content:"▾ "}}
#datebanner{{display:none;align-items:center;gap:12px;padding:12px 20px;background:#eef2ff;
border-bottom:1px solid var(--bd);font-size:13px;color:var(--ink)}}
.link{{color:var(--accent);font-weight:700;cursor:pointer}}
</style></head><body><div class=wrap>
<h1>{name} — Google Ads</h1>
<div class=sub>Customer {customer_id} · last {days} days · generated {generated}</div>

<div class=tiles>
<div class=tile><div class=l>Spend</div><div class=v id=k-cost>${t_cost}</div></div>
<div class=tile><div class=l>Clicks</div><div class=v id=k-clicks>{t_clicks}</div></div>
<div class=tile><div class=l>Impressions</div><div class=v id=k-impr>{t_impr}</div></div>
<div class=tile><div class=l>Conversions</div><div class=v id=k-conv>{t_conv}</div></div>
<div class=tile><div class=l>Cost / conv</div><div class=v id=k-cpa>{t_cpa}</div></div>
<div class=tile><div class=l>Conv. value</div><div class=v id=k-value>${t_value}</div></div>
</div>
<div class=sub id=period style=margin-top:-10px>Showing all {days} days · click any date below to drill into that day</div>

<div class=note><b>{new_neg_count} new negative keywords</b> to apply (${new_neg_cost} wasted in {days}d) —
on top of the <b>{negated_existing}</b> already on the account. Filter the table by
<b>“To negate (new)”</b> below.</div>

<div class=card><h2>Campaigns</h2><table id=camps>
<thead><tr><th>Campaign</th><th>Status</th><th class=num>Spend</th><th class=num>Clicks</th>
<th class=num>Conv</th><th class=num>Lost→Rank</th><th class=num>Lost→Budget</th></tr></thead>
<tbody>{camp_rows}</tbody></table></div>

<div class=card><h2>Spend by date</h2><table>
<thead><tr><th>Date</th><th class=num>Spend</th><th class=num>Clicks</th><th class=num>Impr</th>
<th class=num>Conv</th><th>Spend trend</th></tr></thead><tbody>{daily_rows}</tbody></table></div>

<div class=card><h2>Search terms that got clicks ({t_terms})</h2>
<div id=datebanner></div>
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
<th data-k=adgroup>Ad group (set)</th><th data-k=kw>Triggered by keyword</th>
<th class=num data-k=clicks>Clicks</th><th class=num data-k=impr>Impr</th>
<th class=num data-k=cost>Cost</th><th class=num data-k=conv>Conv</th><th>Status</th>
</tr></thead><tbody id=tbody></tbody></table></div>

<p class=muted style=font-size:12px>Zero-backend snapshot · re-run <code>ads_dashboard.py --slug {slug}</code> to refresh.</p>
</div>
<script>
const DATA={data_json};
let cur='all', curDate=null, sortK='cost', sortDir=-1;
const byDate={{}}; DATA.daily.forEach(d=>byDate[d.date]=d);
const BADGE={{to_negate:['To negate','b-negate'],negated:['Negated','b-negated'],
converting:['Converting','b-converting'],active:['Kept','b-active']}};
const fmt=n=>Number(n||0).toLocaleString('en-US');
function f(el){{document.querySelectorAll('.filter').forEach(x=>x.classList.remove('on'));
el.classList.add('on');cur=el.dataset.f;draw();}}
document.querySelectorAll('#terms th[data-k]').forEach(th=>th.onclick=()=>{{
  const k=th.dataset.k; sortDir=(sortK===k)?-sortDir:-1; sortK=k; draw();}});
function setk(id,v){{document.getElementById('k-'+id).textContent=v;}}
function setTiles(){{
  if(curDate){{const d=byDate[curDate]||{{cost:0,clicks:0,impr:0,conv:0}};
    setk('cost','$'+fmt(Math.round(d.cost))); setk('clicks',fmt(d.clicks)); setk('impr',fmt(d.impr));
    setk('conv',d.conv); setk('cpa', d.conv?'$'+fmt(Math.round(d.cost/d.conv)):'—'); setk('value','—');
    document.getElementById('period').textContent='Showing '+curDate+' only · click the date again to go back';
  }} else {{const t=DATA.totals;
    setk('cost','$'+fmt(t.cost)); setk('clicks',fmt(t.clicks)); setk('impr',fmt(t.impr));
    setk('conv',t.conv); setk('cpa', t.conv?'$'+fmt(Math.round(t.cost/t.conv)):'—'); setk('value','$'+fmt(t.value));
    document.getElementById('period').textContent='Showing all '+DATA.days+' days · click any date below to drill into that day';
  }}
}}
function pickDate(d){{
  curDate=(curDate===d)?null:d;
  document.querySelectorAll('.drow').forEach(r=>r.classList.toggle('sel', r.dataset.date===curDate));
  const b=document.getElementById('datebanner');
  if(curDate){{b.style.display='flex';
    b.innerHTML='Search terms & clicks on <b>&nbsp;'+curDate+'</b> &nbsp;·&nbsp; <span class=link onclick="pickDate(curDate)">← back to all '+DATA.days+' days</span>';}}
  else b.style.display='none';
  setTiles(); draw();
}}
function aggregate(rows){{
  const m={{}};
  for(const t of rows){{const key=t.term.toLowerCase();
    if(!m[key]) m[key]=Object.assign({{}},t,{{clicks:0,impr:0,cost:0,conv:0}});
    m[key].clicks+=t.clicks; m[key].impr+=t.impr; m[key].cost+=t.cost; m[key].conv+=t.conv;}}
  return Object.values(m);
}}
function draw(){{
  const q=(document.getElementById('q').value||'').toLowerCase();
  let rows=DATA.terms.filter(t=>(!curDate||t.date===curDate) && (cur==='all'||t.status===cur))
    .filter(t=>!q||t.term.toLowerCase().includes(q));
  if(!curDate) rows=aggregate(rows);          // sum each term across all days
  rows.sort((a,b)=>{{let x=a[sortK],y=b[sortK];
    if(typeof x==='string')return sortDir*x.localeCompare(y);return sortDir*(x-y);}});
  document.getElementById('tbody').innerHTML=rows.map(t=>{{
    const [lab,cls]=BADGE[t.status]||['','b-active'];
    return `<tr><td class=term>${{esc(t.term)}}</td><td class=muted>${{t.match}}</td>
    <td class=camp>${{esc(shortC(t.campaign))}}</td><td class=camp>${{esc(shortG(t.adgroup))}}</td>
    <td class=camp>${{esc(t.kw)}}${{t.kwmatch?' <span class=muted>['+t.kwmatch[0]+']</span>':''}}</td>
    <td class=num>${{t.clicks}}</td>
    <td class=num>${{t.impr}}</td><td class=num>$${{t.cost.toFixed(2)}}</td>
    <td class=num>${{t.conv||''}}</td><td><span class="badge ${{cls}}">${{lab}}</span></td></tr>`;
  }}).join('')||'<tr><td colspan=10 class=muted style=padding:24px;text-align:center>No terms match.</td></tr>';
}}
function shortC(c){{return (c||'').replace('National Restoration Construction - ','').replace('LocalServicesCampaign:SystemGenerated:','LSA ');}}
function shortG(g){{return (g||'').replace('National Restoration Construction - ','').replace(' - Exact','').replace(' - Phrase','');}}
function esc(s){{return (s||'').replace(/[&<>]/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[m]));}}
document.querySelector('.filter[data-f=all]').classList.add('on');setTiles();draw();
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
        f"<tr class=drow data-date='{x['date']}' onclick=\"pickDate('{x['date']}')\">"
        f"<td>{x['date']}</td><td class=num>${x['cost']:,.2f}</td><td class=num>{x['clicks']}</td>"
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
        data_json=json.dumps({"terms": d["terms"], "daily": d["daily"],
                              "totals": d["totals"], "days": d["days"]}))


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
