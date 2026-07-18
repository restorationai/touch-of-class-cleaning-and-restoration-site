#!/usr/bin/env python3
"""
Rank AI KPI aggregator.
Pulls Meta Ads + GHL + Stripe + GA4 + Supabase, computes the real scoreboard
(cost per demo, lead->demo, demo->close, CAC, lead quality), and writes one
permanent snapshot file per month to data/YYYY-MM.json.

Runs server-side only. Secrets stay in config.env (gitignored). Only the
computed aggregates (no PII, no keys) are written to data/ and deployed.
"""
import json, os, sys, urllib.request, urllib.error, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))

def load_env(path):
    out = {}
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out

CFG = load_env(os.path.join(HERE, "config.env"))

def file_val(path_key, var):
    f = CFG.get(path_key)
    if not f or not os.path.exists(f): return None
    for line in open(f):
        line = line.strip()
        if line.startswith(var + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
def getj(url, headers=None, data=None, method=None):
    headers = dict(headers or {})
    headers.setdefault("User-Agent", UA)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"_err": f"{e.code} {e.read().decode()[:200]}"}
    except Exception as e:
        return {"_err": str(e)[:200]}

# ---- month window ----
NOW = dt.datetime.now(dt.timezone.utc)
MONTH = sys.argv[1] if len(sys.argv) > 1 else NOW.strftime("%Y-%m")
y, m = map(int, MONTH.split("-"))
MSTART = dt.datetime(y, m, 1, tzinfo=dt.timezone.utc)
MEND = (dt.datetime(y + (m == 12), (m % 12) + 1, 1, tzinfo=dt.timezone.utc))
UNTIL = min(NOW, MEND - dt.timedelta(seconds=1))
since_s, until_s = MSTART.strftime("%Y-%m-%d"), UNTIL.strftime("%Y-%m-%d")
def in_month(iso):
    if not iso: return False
    try:
        d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if d.tzinfo is None: d = d.replace(tzinfo=dt.timezone.utc)
        return MSTART <= d < MEND
    except Exception:
        return False

IS_CURRENT = (MONTH == NOW.strftime("%Y-%m"))
snap = {"month": MONTH, "generated_at": NOW.isoformat(),
        "backfilled": not IS_CURRENT, "sources": {}}

# ---------- META ----------
def meta():
    tok = CFG.get("META_ACCESS_TOKEN"); act = CFG.get("META_AD_ACCOUNT_ID")
    base = f"https://graph.facebook.com/v21.0/{act}/insights"
    q = f"?access_token={tok}&level=campaign&time_range={{'since':'{since_s}','until':'{until_s}'}}&fields=campaign_name,spend,impressions,clicks,ctr,actions&limit=100"
    d = getj(base + q)
    if d.get("_err"): return {"error": d["_err"]}
    spend = leads = clicks = impr = 0.0
    camps = []
    for r in d.get("data", []):
        s = float(r.get("spend", 0)); cl = int(r.get("clicks", 0)); im = int(r.get("impressions", 0))
        acts = {a["action_type"]: int(a["value"]) for a in r.get("actions", [])}
        ld = acts.get("lead", 0) or acts.get("onsite_conversion.lead_grouped", 0)
        spend += s; leads += ld; clicks += cl; impr += im
        if s > 0:
            camps.append({"name": r.get("campaign_name"), "spend": round(s), "clicks": cl,
                          "ctr": round(float(r.get("ctr", 0)), 2), "leads": ld})
    return {"spend": round(spend), "leads": int(leads), "clicks": int(clicks),
            "impressions": int(impr), "campaigns": sorted(camps, key=lambda c: -c["spend"])}

# ---------- GHL ----------
def ghl():
    tok = CFG.get("GHL_TOKEN"); loc = CFG.get("GHL_LOCATION")
    H = {"Authorization": f"Bearer {tok}", "Version": "2021-07-28", "Accept": "application/json"}
    STAGES = {"cf8e6e3a-ca9d-4ad4-a85e-a16e367bc413": "New Leads From Ads",
              "e56d0608-e783-4b5a-8a64-363c702612a3": "No-Show",
              "5256e690-de7c-4b6f-be9d-81ae9213aba8": "Demo Meeting Booked",
              "4f5f6022-5259-4419-be3a-d6aaf75c04df": "Follow-Up Meeting Booked",
              "fa184149-7644-4bc1-a4a8-0effeb29b590": "Client Not Yet Secured",
              "eeb9f748-951c-4151-8d46-b9b1936ac638": "Waiting For Follow Up",
              "9fb3928a-33e3-4592-a080-56b3f353e56b": "Ready For Follow Up",
              "7e48bb16-9e5d-4961-b087-47b5e5c82f58": "Client Signed Up"}
    DEMO_OR_BEYOND = {"5256e690-de7c-4b6f-be9d-81ae9213aba8", "4f5f6022-5259-4419-be3a-d6aaf75c04df",
                      "fa184149-7644-4bc1-a4a8-0effeb29b590", "eeb9f748-951c-4151-8d46-b9b1936ac638",
                      "9fb3928a-33e3-4592-a080-56b3f353e56b", "7e48bb16-9e5d-4961-b087-47b5e5c82f58"}
    SIGNED = "7e48bb16-9e5d-4961-b087-47b5e5c82f58"
    pid = CFG.get("GHL_SALES_PIPELINE_ID")
    page, all_ops, total = 1, [], None
    while page <= 12:
        d = getj(f"https://services.leadconnectorhq.com/opportunities/search?location_id={loc}&pipeline_id={pid}&limit=100&page={page}", headers=H)
        if d.get("_err"):
            if page == 1: return {"error": d["_err"]}
            break
        ops = d.get("opportunities", [])
        all_ops += ops
        total = d.get("meta", {}).get("total", total)
        if len(ops) < 100: break
        page += 1
    def created(o): return o.get("createdAt") or o.get("created_at") or o.get("dateAdded")
    month_ops = [o for o in all_ops if in_month(created(o))]
    leads_m = len(month_ops)
    demos_m = sum(1 for o in month_ops if o.get("pipelineStageId") in DEMO_OR_BEYOND)
    signed_m = sum(1 for o in month_ops if o.get("pipelineStageId") == SIGNED)
    # full pipeline snapshot (all-time, open + closed) by stage
    by_stage = {}
    for o in all_ops:
        nm = STAGES.get(o.get("pipelineStageId"), "Other")
        by_stage[nm] = by_stage.get(nm, 0) + 1
    return {"pulled": len(all_ops), "pipeline_total": total,
            "leads_this_month": leads_m, "demos_booked_this_month": demos_m,
            "signed_up_this_month": signed_m, "pipeline_by_stage": by_stage}

# ---------- STRIPE ----------
def stripe():
    key = file_val("STRIPE_KEY_FILE", "STRIPE_SECRET_KEY")
    if not key: return {"error": "no key"}
    import base64
    auth = {"Authorization": "Basic " + base64.b64encode(f"{key}:".encode()).decode()}
    subs = getj("https://api.stripe.com/v1/subscriptions?status=active&limit=100", headers=auth)
    if subs.get("_err"): return {"error": subs["_err"]}
    mrr = 0.0; new_subs = 0
    for s in subs.get("data", []):
        if in_month(dt.datetime.fromtimestamp(s["created"], dt.timezone.utc).isoformat()): new_subs += 1
        for it in s["items"]["data"]:
            p = it.get("price", {}); amt = (p.get("unit_amount") or 0) * it.get("quantity", 1)
            iv = (p.get("recurring") or {}).get("interval", "month")
            mrr += amt / (12 if iv == "year" else 1 if iv == "month" else 1)
    # revenue this month from charges
    ch = getj("https://api.stripe.com/v1/charges?limit=100", headers=auth)
    rev = sum(c["amount"] for c in ch.get("data", []) if c.get("paid") and in_month(
        dt.datetime.fromtimestamp(c["created"], dt.timezone.utc).isoformat()))
    return {"mrr": round(mrr / 100), "active_subs": len(subs.get("data", [])),
            "new_subs_this_month": new_subs, "revenue_this_month": round(rev / 100)}

# ---------- GA4 ----------
def ga():
    try:
        from google.oauth2 import service_account
        import google.auth.transport.requests as gtr
    except Exception as e:
        return {"error": "google-auth missing: " + str(e)[:80]}
    creds = service_account.Credentials.from_service_account_file(
        CFG.get("GA_SA_PATH"), scopes=["https://www.googleapis.com/auth/analytics.readonly"])
    creds.refresh(gtr.Request())
    H = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
    out = {}
    for label, prop in [("site", CFG.get("GA_PROP_SITE")), ("funnel", CFG.get("GA_PROP_FUNNEL"))]:
        body = json.dumps({"dateRanges": [{"startDate": since_s, "endDate": until_s}],
                           "metrics": [{"name": "sessions"}]}).encode()
        d = getj(f"https://analyticsdata.googleapis.com/v1beta/properties/{prop}:runReport", headers=H, data=body)
        if d.get("_err"): out[label] = {"error": d["_err"]}
        else:
            rows = d.get("rows", [])
            out[label] = int(rows[0]["metricValues"][0]["value"]) if rows else 0
    return out

# ---------- SUPABASE ----------
def supa():
    url = file_val("SUPABASE_URL_FILE", "SUPABASE_URL") or file_val("SUPABASE_URL_FILE", "VITE_SUPABASE_URL")
    key = file_val("SUPABASE_KEY_FILE", "SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key: return {"error": "no creds"}
    H = {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "count=exact",
         "Range": "0-0", "User-Agent": UA}
    out = {}
    for col in ("created_at", "createdAt", "inserted_at"):
        req = urllib.request.Request(
            f"{url}/rest/v1/companies?select=id&{col}=gte.{since_s}", headers=H)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                cr = r.headers.get("Content-Range", "")
                out["new_companies_this_month"] = cr.split("/")[-1] if "/" in cr else "?"
                out["date_col"] = col
                return out
        except urllib.error.HTTPError as e:
            out["error"] = f"{e.code} ({col})"
            continue
        except Exception as e:
            return {"error": str(e)[:150]}
    return out

for name, fn in [("meta", meta), ("ghl", ghl), ("stripe", stripe), ("ga", ga), ("supabase", supa)]:
    try: snap["sources"][name] = fn()
    except Exception as e: snap["sources"][name] = {"error": str(e)[:200]}

# ---------- derived scoreboard ----------
M, G, S = snap["sources"]["meta"], snap["sources"]["ghl"], snap["sources"]["stripe"]
spend = M.get("spend", 0) if isinstance(M, dict) else 0
leads = M.get("leads", 0) if isinstance(M, dict) else 0
demos = G.get("demos_booked_this_month", 0) if isinstance(G, dict) else 0
signed = G.get("signed_up_this_month", 0) if isinstance(G, dict) else 0
def safe_div(a, b): return round(a / b, 2) if b else None
snap["scoreboard"] = {
    "ad_spend": spend,
    "leads": leads,
    "demos_booked": demos,
    "clients_signed": signed,
    "cost_per_lead": safe_div(spend, leads),
    "cost_per_demo": safe_div(spend, demos),
    "cost_per_client": safe_div(spend, signed),
    "lead_to_demo_pct": safe_div(demos * 100, leads),
    "demo_to_close_pct": safe_div(signed * 100, demos),
    "mrr": S.get("mrr") if isinstance(S, dict) else None,
}

os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
outp = os.path.join(HERE, "data", f"{MONTH}.json")
json.dump(snap, open(outp, "w"), indent=2)

# month index so the static page knows which snapshots exist
months = sorted(f[:-5] for f in os.listdir(os.path.join(HERE, "data"))
                if f.endswith(".json") and f != "index.json")
json.dump({"months": months, "updated": NOW.isoformat()},
          open(os.path.join(HERE, "data", "index.json"), "w"), indent=2)

print(f"\n===== RANK AI SCOREBOARD — {MONTH} (through {until_s}) =====")
sb = snap["scoreboard"]
print(f"  Ad spend ............. ${sb['ad_spend']:,}")
print(f"  Leads (Meta) ......... {sb['leads']}")
print(f"  Demos booked (GHL) ... {sb['demos_booked']}      <- the number that matters")
print(f"  Clients signed ....... {sb['clients_signed']}")
print(f"  Cost / lead .......... ${sb['cost_per_lead']}")
print(f"  Cost / DEMO .......... ${sb['cost_per_demo']}")
print(f"  Cost / client ........ ${sb['cost_per_client']}")
print(f"  Lead -> demo ......... {sb['lead_to_demo_pct']}%")
print(f"  Demo -> close ........ {sb['demo_to_close_pct']}%")
print(f"  MRR (Stripe) ......... ${sb['mrr']:,}" if sb['mrr'] else "  MRR: n/a")
print("\n  source status:")
for k, v in snap["sources"].items():
    err = v.get("error") if isinstance(v, dict) else None
    print(f"    {k:10} {'ERROR: ' + err if err else 'ok'}")
print(f"\n  wrote {outp}")
