"""
Rank AI FastAPI service — Phase 3.

Exposes HTTP endpoints so the React app (app.restorationai.io) can trigger
on-demand pipeline runs and read job status.

Authentication: Bearer token (API_SECRET_KEY env var).
Deployed on Railway from the rank-ai monorepo.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "scripts"))  # so we can import the geogrid pipeline

import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from supabase import create_client

from api.runner import create_and_run_job, COMPANY_MAP

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Rank AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.restorationai.io",
        "https://rank.restorationai.io",   # free-audit lead form
        "http://localhost:5173",
        "http://localhost:4321",           # sales page astro dev
        "http://localhost:4322",           # landing-page astro dev
    ],
    allow_origin_regex=r"https://[a-z0-9-]+\.rank-ai-landing-page\.pages\.dev",  # Pages previews
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

API_SECRET = os.environ.get("API_SECRET_KEY", "")
bearer = HTTPBearer()


def auth(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    if not API_SECRET or creds.credentials != API_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")


def sb():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


SYSTEM_LABELS = {
    1: "Keyword Research (S1)",
    2: "Write Post (S2)",
    3: "Onsite Audit (S3)",
    4: "Refresh Recommender (S4)",
    "gbp_face": "GBP Face Fix",
    "gbp_set_cover": "GBP Set Cover Photo",
}

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RunJobRequest(BaseModel):
    slug: str
    system: int | str  # 1, 2, 3, 4 — or "gbp_face" (GBP front-face audit + safe
                       # auto-fixes) / "gbp_set_cover" (needs photo_url)
    photo_url: str | None = None  # gbp_set_cover: the photo to set as COVER


class CompleteJobRequest(BaseModel):
    status: str   # "completed" or "failed"
    log: str = ""
    error: str = ""


class GeogridScanRequest(BaseModel):
    company_id: str        # = companies.id (TEXT), the app's join key
    keyword: str
    city_label: str        # must match a label in clients/{slug}/geogrid-cities.json

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "service": "rank-ai-api"}


@app.get("/status", dependencies=[Depends(auth)])
def status():
    """Return all active clients and their last-run timestamps from marketing_sites."""
    rows = (
        sb().table("marketing_sites")
        .select("rank_ai_slug,domain,build_status,last_audit_verdict,s1_last_run_at,s2_last_run_at,s3_last_run_at,s4_last_run_at")
        .in_("rank_ai_slug", list(COMPANY_MAP.keys()))
        .execute()
    )
    return {"clients": rows.data}


# ---------------------------------------------------------------------------
# Domains: in-app search + purchase (GoDaddy PAT), phantom-domain pipeline.
# Purchase = availability re-check -> Cloudflare zone created FIRST (so the
# domain is born pointing at our infrastructure) -> GoDaddy buy with CF
# nameservers -> marketing_sites row updated. We absorb the cost (Santino,
# 2026-07-21); premium domains blocked by the price cap.
# ---------------------------------------------------------------------------

GODADDY_API = "https://api.godaddy.com"
DOMAIN_PRICE_CAP_USD = 50.0
REGISTRANT = {
    "nameFirst": os.environ.get("DOMAIN_REG_FIRST", "Santino"),
    "nameLast": os.environ.get("DOMAIN_REG_LAST", "Velci"),
    "email": os.environ.get("DOMAIN_REG_EMAIL", "contact@getrestorationai.com"),
    "phone": os.environ.get("DOMAIN_REG_PHONE", "+1.8053293449"),
    "addressMailing": {
        "address1": os.environ.get("DOMAIN_REG_ADDR", "30 N Gould Street Ste R"),
        "city": os.environ.get("DOMAIN_REG_CITY", "Sheridan"),
        "state": os.environ.get("DOMAIN_REG_STATE", "Wyoming"),
        "postalCode": os.environ.get("DOMAIN_REG_ZIP", "82801"),
        "country": "US",
    },
}


def _gd(method: str, path: str, body=None, timeout=60):
    req = urllib.request.Request(
        GODADDY_API + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + os.environ["GODADDY_PAT"],
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def _cf_zone(domain: str):
    """Create (or fetch) the Cloudflare zone; returns (zone_id, nameservers)."""
    tok = os.environ["CLOUDFLARE_API_TOKEN"]
    acct = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    hdrs = {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}
    req = urllib.request.Request("https://api.cloudflare.com/client/v4/zones",
        method="POST", headers=hdrs,
        data=json.dumps({"name": domain, "account": {"id": acct}, "type": "full"}).encode())
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=60).read())
        z = d["result"]
        return z["id"], z.get("name_servers") or []
    except urllib.error.HTTPError as e:
        err = json.loads(e.read())
        if any(x.get("code") == 1061 for x in err.get("errors", [])):  # already exists
            q = urllib.request.Request(
                "https://api.cloudflare.com/client/v4/zones?name=" + domain, headers=hdrs)
            d = json.loads(urllib.request.urlopen(q, timeout=30).read())
            z = (d.get("result") or [{}])[0]
            return z.get("id"), z.get("name_servers") or []
        raise


class DomainSearchRequest(BaseModel):
    query: str


@app.post("/domains/search", dependencies=[Depends(auth)])
def domains_search(req: DomainSearchRequest):
    """Availability + price for the query (and GoDaddy suggestions)."""
    q = re.sub(r"[^a-z0-9.-]", "", req.query.lower().strip())
    if not q:
        raise HTTPException(status_code=400, detail="Enter a domain to search.")
    candidates = [q if "." in q else q + ".com"]
    try:
        sug = _gd("GET", "/v1/domains/suggest?query={}&limit=8&waitMs=800".format(
            urllib.parse.quote(q)))
        candidates += [s["domain"] for s in sug if s.get("domain")][:8]
    except Exception:
        pass
    seen, out = set(), []
    for dom in candidates:
        if dom in seen:
            continue
        seen.add(dom)
        try:
            a = _gd("GET", "/v1/domains/available?domain=" + urllib.parse.quote(dom))
            out.append({"domain": dom, "available": bool(a.get("available")),
                        "price_usd": round((a.get("price") or 0) / 1e6, 2),
                        "definitive": a.get("definitive", False)})
        except Exception:
            continue
        if len(out) >= 6:
            break
    return {"results": out, "price_cap_usd": DOMAIN_PRICE_CAP_USD}


class DomainPurchaseRequest(BaseModel):
    domain: str
    company_id: str = ""


@app.post("/domains/purchase", dependencies=[Depends(auth)])
def domains_purchase(req: DomainPurchaseRequest):
    """Buy the domain on our GoDaddy account, born on Cloudflare nameservers."""
    dom = re.sub(r"[^a-z0-9.-]", "", req.domain.lower().strip())
    if "." not in dom:
        raise HTTPException(status_code=400, detail="Full domain required, e.g. example.com")
    a = _gd("GET", "/v1/domains/available?domain=" + urllib.parse.quote(dom))
    price = round((a.get("price") or 0) / 1e6, 2)
    if not a.get("available"):
        raise HTTPException(status_code=409, detail="{} is no longer available.".format(dom))
    if price > DOMAIN_PRICE_CAP_USD:
        raise HTTPException(status_code=400,
                            detail="{} costs ${:.2f} — over the ${:.0f} auto-purchase cap. "
                                   "Check with Santino first.".format(dom, price, DOMAIN_PRICE_CAP_USD))
    tld = dom.split(".")[-1]
    ag = _gd("GET", "/v1/domains/agreements?tlds={}&privacy=false".format(tld))
    keys = [x["agreementKey"] for x in ag] or ["DNRA"]

    zone_id, ns = _cf_zone(dom)
    body = {
        "domain": dom,
        "consent": {"agreementKeys": keys, "agreedBy": "45.29.84.10",
                    "agreedAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")},
        "period": 1, "privacy": False, "renewAuto": True,
        "contactAdmin": REGISTRANT, "contactBilling": REGISTRANT,
        "contactRegistrant": REGISTRANT, "contactTech": REGISTRANT,
    }
    if ns:
        body["nameServers"] = ns
    try:
        order = _gd("POST", "/v1/domains/purchase", body)
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=502,
                            detail="GoDaddy rejected the purchase: " + e.read().decode()[:300])

    if req.company_id:
        try:
            sb().table("marketing_sites").update(
                {"domain": dom, "cf_zone_id": zone_id}
            ).eq("company_id", req.company_id).execute()
        except Exception:
            pass
    return {"status": "purchased", "domain": dom, "price_usd": price,
            "order_id": order.get("orderId"), "cf_zone_id": zone_id,
            "nameservers": ns}


# ---------------------------------------------------------------------------
# Site builds: brief helpers + push-button build (Isaac/RestorationXpress is
# the pilot — everything through the app, nothing manual).
# ---------------------------------------------------------------------------

class DomainAttachRequest(BaseModel):
    company_id: str
    domain: str


@app.post("/domains/attach", dependencies=[Depends(auth)])
def domains_attach(req: DomainAttachRequest):
    """Client already OWNS a domain (Isaac case): record it on the site row
    and pre-create the Cloudflare zone so go-live is just a nameserver
    change at their registrar. No purchase, no DNS changes on their side."""
    dom = re.sub(r"[^a-z0-9.-]", "", req.domain.lower().strip()
                 .replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0])
    if "." not in dom or len(dom) < 4:
        raise HTTPException(status_code=400, detail="Enter a full domain, e.g. example.com")
    zone_id, ns = None, []
    try:
        zone_id, ns = _cf_zone(dom)
    except Exception:
        pass  # zone can be created at cutover; recording the domain still works
    upd = {"domain": dom}
    if zone_id:
        upd["cf_zone_id"] = zone_id
    r = sb().table("marketing_sites").update(upd).eq("company_id", req.company_id).execute()
    if not r.data:
        raise HTTPException(status_code=400, detail="No site record for this company (not bootstrapped yet).")
    return {"status": "attached", "domain": dom, "cf_zone_id": zone_id,
            "nameservers": ns,
            "note": "Existing site untouched; cutover happens at go-live."}


class SiteBriefColorsRequest(BaseModel):
    company_id: str


@app.post("/site-brief/extract-colors", dependencies=[Depends(auth)])
def site_brief_extract_colors(req: SiteBriefColorsRequest):
    """Fetch the client's CURRENT website and return its dominant brand
    colors ("use the same green as my site" without hex-code archaeology)."""
    rows = sb().table("companies").select("website").eq("id", req.company_id).execute()
    site = (rows.data[0].get("website") if rows.data else "") or ""
    site = site.strip()
    if not site:
        raise HTTPException(status_code=400, detail="No website on file for this company.")
    if not site.startswith("http"):
        site = "https://" + site.lstrip("/")
    ua = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

    def fetch(u):
        try:
            r = urllib.request.Request(u, headers=ua)
            return urllib.request.urlopen(r, timeout=20).read().decode("utf-8", "ignore")
        except Exception:
            return ""

    html_text = fetch(site)
    if not html_text:
        raise HTTPException(status_code=502, detail="Couldn't fetch their website.")
    corpus = html_text
    for href in re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)', html_text)[:3]:
        corpus += fetch(urllib.parse.urljoin(site + "/", href))

    counts: dict = {}
    for m in re.findall(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", corpus):
        h = m.lower()
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        counts[h] = counts.get(h, 0) + 1
    for m in re.findall(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", corpus):
        r0, g0, b0 = (min(int(x), 255) for x in m)
        counts["{:02x}{:02x}{:02x}".format(r0, g0, b0)] =             counts.get("{:02x}{:02x}{:02x}".format(r0, g0, b0), 0) + 1

    def is_gray(h):
        r0, g0, b0 = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        if max(r0, g0, b0) - min(r0, g0, b0) < 26:
            return True                       # gray family
        return (r0 + g0 + b0) > 705 or (r0 + g0 + b0) < 45  # near white/black

    ranked = sorted(((h, n) for h, n in counts.items() if not is_gray(h)),
                    key=lambda x: -x[1])[:8]
    return {"website": site,
            "colors": [{"hex": "#" + h, "count": n} for h, n in ranked]}


class SiteBuildRequest(BaseModel):
    company_id: str


@app.post("/site-build", dependencies=[Depends(auth)])
def site_build(req: SiteBuildRequest):
    """Queue a full site build (plan -> scaffold -> render -> staging preview)
    on GitHub Actions. Validates the brief; long work never runs on this
    server (a redeploy would kill it)."""
    site_rows = sb().table("marketing_sites").select(
        "rank_ai_slug,domain,build_status").eq("company_id", req.company_id).execute()
    if not site_rows.data:
        raise HTTPException(status_code=400,
                            detail="Client isn't bootstrapped yet — no site record. The 2-hour automation will create it, or run the bootstrap.")
    site = site_rows.data[0]
    slug, domain = site.get("rank_ai_slug"), site.get("domain") or ""
    if not slug:
        raise HTTPException(status_code=400, detail="No Rank AI slug on the site record.")
    if domain.endswith(".invalid") or not domain:
        raise HTTPException(status_code=400,
                            detail="No real domain yet — buy or set one in the Domain Purchase card first.")
    if site.get("build_status") in ("queued", "building"):
        raise HTTPException(status_code=409, detail="A build is already {}.".format(site["build_status"]))

    co = sb().table("companies").select("integration_settings").eq("id", req.company_id).execute()
    ints = (co.data[0].get("integration_settings") if co.data else None) or {}
    brand = ints.get("brand") or {}
    brief = ints.get("site_brief") or {}
    missing = []
    if not brand.get("primary_color"):
        missing.append("primary brand color")
    if not (brief.get("cities") or []):
        missing.append("at least one build city")
    if missing:
        raise HTTPException(status_code=400,
                            detail="Brief incomplete: add " + " and ".join(missing) + ", then save.")

    gh_pat = os.environ.get("GH_PAT", "")
    if not gh_pat:
        raise HTTPException(status_code=500, detail="GH_PAT not configured on the API service.")
    disp = urllib.request.Request(
        "https://api.github.com/repos/restorationai/Rank-AI-Pipeline/actions/workflows/site-build.yml/dispatches",
        method="POST",
        data=json.dumps({"ref": "main", "inputs": {"slug": slug}}).encode(),
        headers={"Authorization": "Bearer " + gh_pat,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "rank-ai-api"})
    try:
        urllib.request.urlopen(disp, timeout=30)
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=502,
                            detail="GitHub dispatch failed: " + e.read().decode()[:200])
    sb().table("marketing_sites").update({"build_status": "queued"}).eq(
        "company_id", req.company_id).execute()
    return {"status": "queued", "slug": slug,
            "note": "Plan + render + staging preview takes 1-3 hours; "
                    "watch build_status and the ops email for the preview link."}


@app.post("/jobs/run", dependencies=[Depends(auth)])
def run_job(req: RunJobRequest):
    """Trigger a system run for a client. Returns job_id immediately; runs in background."""
    if req.slug not in COMPANY_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown slug: {req.slug}")
    if req.system not in (1, 2, 3, 4, "gbp_face", "gbp_set_cover"):
        raise HTTPException(status_code=400,
                            detail="system must be 1, 2, 3, 4, 'gbp_face', or 'gbp_set_cover'")
    if req.system == "gbp_set_cover" and not (req.photo_url or "").startswith("https://"):
        raise HTTPException(status_code=400, detail="gbp_set_cover requires an https photo_url")

    job_id = create_and_run_job(req.slug, req.system, photo_url=req.photo_url)

    return {
        "job_id":  job_id,
        "slug":    req.slug,
        "system":  req.system,
        "label":   SYSTEM_LABELS[req.system],
        "status":  "queued",
        "note":    "Poll GET /jobs/{job_id} for status updates.",
    }


@app.get("/jobs/{job_id}", dependencies=[Depends(auth)])
def get_job(job_id: str):
    """Get the current status of a job."""
    rows = (
        sb().table("marketing_jobs")
        .select("id,type,status,params,result,error,queued_at,started_at,completed_at")
        .eq("id", job_id)
        .execute()
    )
    if not rows.data:
        raise HTTPException(status_code=404, detail="Job not found")
    return rows.data[0]


@app.post("/jobs/{job_id}/complete", dependencies=[Depends(auth)])
def complete_job(job_id: str, req: CompleteJobRequest):
    """
    Callback endpoint for GitHub Actions to mark agent-driven jobs (S1, S3) done.
    The on-demand.yml workflow calls this after claude -p finishes.
    """
    rows = sb().table("marketing_jobs").select("params").eq("id", job_id).execute()
    if not rows.data:
        raise HTTPException(status_code=404, detail="Job not found")

    slug = rows.data[0]["params"].get("slug")
    update = {
        "status":       req.status,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "log":          req.log[-8000:] if req.log else None,
        "error":        req.error or None,
    }
    sb().table("marketing_jobs").update(update).eq("id", job_id).execute()

    # Sync Supabase after agent-driven job completes
    if req.status == "completed" and slug:
        import subprocess
        subprocess.Popen(
            ["python3", str(ROOT / "scripts" / "supabase_sync.py"), "--slug", slug],
            cwd=str(ROOT),
        )

    return {"ok": True}


# ---------------------------------------------------------------------------
# Geo-grid: on-demand local-map-rankings scan (one keyword + one city)
# ---------------------------------------------------------------------------

# Reverse of COMPANY_MAP — the app sends company_id; the pipeline keys off slug.
SLUG_BY_COMPANY = {cid: slug for slug, cid in COMPANY_MAP.items()}


def _resolve_city(slug: str, city_label: str) -> dict:
    """Find {label,lat,lng} for a city_label in the client's geogrid-cities.json."""
    f = ROOT / "clients" / slug / "geogrid-cities.json"
    if not f.exists():
        raise HTTPException(status_code=404, detail=f"No geogrid-cities.json for {slug}")
    for c in json.loads(f.read_text()):
        if c.get("label") == city_label:
            return c
    raise HTTPException(status_code=404, detail=f"city_label '{city_label}' not configured for {slug}")


@app.post("/geogrid/scan", dependencies=[Depends(auth)])
def geogrid_scan(req: GeogridScanRequest):
    """Run ONE keyword×city geo-grid scan, store it, return the new scan row.

    Server-enforced rate limit: at most 1 scan per (company_id, keyword, city_label)
    per UTC day — re-scanning the same cell same-day returns 429 with the existing
    row (the dashboard should just show that one). Scans are ~10-60s; this blocks
    until the row + points + PNG are written. The app refreshes the card from the
    returned row (or via realtime subscribe to marketing_geogrid_scans).
    """
    slug = SLUG_BY_COMPANY.get(req.company_id)
    if not slug:
        raise HTTPException(status_code=404, detail=f"Unknown company_id: {req.company_id}")
    city = _resolve_city(slug, req.city_label)

    client = sb()
    # Rate limit: any scan for this cell since UTC midnight?
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")
    existing = (
        client.table("marketing_geogrid_scans")
        .select("id,avg_rank,pct_in_top3,found_points,total_points,image_url,scanned_at")
        .eq("company_id", req.company_id).eq("keyword", req.keyword)
        .eq("city_label", req.city_label).gte("scanned_at", today)
        .order("scanned_at", desc=True).limit(1).execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=429,
            detail={"message": "Already scanned today (1/keyword/city/day).",
                    "scan": existing.data[0]},
        )

    # Lazy import — keeps PIL/requests out of the cold-start path for other routes.
    from geogrid_store import scan_and_store
    row = scan_and_store(client, slug, req.keyword, city)
    return {
        "id":           row["id"],
        "company_id":   req.company_id,
        "keyword":      req.keyword,
        "city_label":   req.city_label,
        "avg_rank":     row.get("avg_rank"),
        "pct_in_top3":  row.get("pct_in_top3"),
        "found_points": row.get("found_points"),
        "total_points": row.get("total_points"),
        "image_url":    row.get("image_url"),
        "cost_usd":     row.get("cost_usd"),
        "scanned_at":   row.get("scanned_at"),
    }


# ---------------------------------------------------------------------------
# Free-audit lead magnet (rank.restorationai.io) — PUBLIC endpoints.
# Jobs are tracked in marketing_jobs (type='lead_audit', company_id NULL);
# rate limits are derived from the same table so they survive restarts.
# ---------------------------------------------------------------------------

LEAD_AUDIT_DAILY_CAP = 10       # global per UTC day
LEAD_AUDIT_IP_CAP = 3           # per IP per UTC day
LEAD_AUDIT_DOMAIN_CAP = 2       # per target domain per UTC day
LEAD_LOOKUP_DAILY_CAP = 60      # global business-name lookups per UTC day
LEAD_LOOKUP_IP_CAP = 15         # per IP per UTC day

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")


class LeadAuditRequest(BaseModel):
    # Path A (classic): website + contact info.
    # Path B (stepper): business_name + place_id/cid (+ optional domain) + contact info.
    website: str = ""
    name: str = ""
    email: str
    phone: str
    business_name: str = ""
    place_id: str = ""
    cid: str = ""
    domain: str = ""
    # Sales-funnel mode (e.g. OpDigital application → GHL webhook): the lead is
    # NOT emailed; the report + teaser image land on their GHL contact and the
    # team gets an ops ping. Requires the shared secret.
    source: str = ""
    secret: str = ""


def _lead_norm_domain(url: str) -> str:
    d = re.sub(r"^https?://", "", (url or "").strip().lower()).split("/")[0].split("?")[0]
    return d.replace("www.", "")


def _lead_count_today(client, col_json: str = None, value: str = None) -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")
    q = (client.table("marketing_jobs").select("id", count="exact")
         .eq("type", "lead_audit").gte("queued_at", today))
    if col_json:
        q = q.eq(f"params->>{col_json}", value)
    return q.execute().count or 0


# --- DataForSEO business lookup (name -> candidate GBP listings) ------------

DFS_LISTINGS = "https://api.dataforseo.com/v3/business_data/business_listings/search/live"
DFS_MAPS_LIVE = "https://api.dataforseo.com/v3/serp/google/maps/live/advanced"


def _dfs_post(url: str, body: list, timeout: int = 60) -> list:
    """POST one DataForSEO live task; return result items (or [])."""
    import base64
    import urllib.request
    import geogrid_scan as gs  # scripts/ on sys.path; load_dfs_creds handles env/~/.claude.json
    u, p = gs.load_dfs_creds()
    auth = base64.b64encode("{}:{}".format(u, p).encode()).decode()
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": "Basic " + auth, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read())
    task = (d.get("tasks") or [{}])[0]
    if task.get("status_code") and int(task["status_code"]) >= 40000:
        raise RuntimeError(task.get("status_message") or "DataForSEO task error")
    result = (task.get("result") or [{}])[0] or {}
    return result.get("items") or []


def _listing_row(it: dict) -> dict:
    rd = it.get("rating") or {}
    dom = (it.get("domain") or "").replace("www.", "") or None
    return {
        "title": it.get("title"),
        "address": it.get("address"),
        "rating": rd.get("value"),
        "reviews": rd.get("votes_count"),
        "place_id": it.get("place_id"),
        "cid": str(it.get("cid")) if it.get("cid") is not None else None,
        "domain": dom,
        "url": it.get("url"),
    }


def _name_score(a: str, b: str) -> float:
    import difflib
    a, b = (a or "").lower().strip(), (b or "").lower().strip()
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def lookup_business(q: str, limit: int = 3) -> list:
    """US-wide GBP candidate search: business_listings first, Maps SERP fallback."""
    items = []
    try:
        items = _dfs_post(DFS_LISTINGS, [{"title": q[:200], "limit": 20}])
    except Exception:
        items = []
    rows = [it for it in items if isinstance(it, dict) and it.get("title")]
    if not rows:
        try:
            items = _dfs_post(DFS_MAPS_LIVE, [{"keyword": q[:200], "location_code": 2840,
                                               "language_code": "en", "device": "desktop"}])
            rows = [it for it in items if isinstance(it, dict) and it.get("title")]
        except Exception:
            rows = []
    scored = sorted(
        (( _name_score(q, it.get("title")), (it.get("rating") or {}).get("votes_count") or 0, i, it)
         for i, it in enumerate(rows)),
        key=lambda t: (-t[0], -t[1], t[2]))
    out, seen = [], set()
    for score, _votes, _i, it in scored:
        if score < 0.35:
            continue
        key = it.get("place_id") or it.get("cid") or it.get("title")
        if key in seen:
            continue
        seen.add(key)
        out.append(_listing_row(it))
        if len(out) >= limit:
            break
    return out


def _listing_by_id(place_id: str = "", cid: str = ""):
    """Fetch one listing by place_id/cid (used to resolve a missing domain)."""
    filters = None
    if place_id:
        filters = ["place_id", "=", place_id]
    elif cid:
        try:
            filters = ["cid", "=", int(cid)]
        except ValueError:
            filters = ["cid", "=", cid]
    if not filters:
        return None
    try:
        items = _dfs_post(DFS_LISTINGS, [{"filters": [filters], "limit": 1}])
        for it in items:
            if isinstance(it, dict) and it.get("title"):
                return _listing_row(it)
    except Exception:
        pass
    return None


@app.get("/lead-audit/business-lookup")
def lead_business_lookup(q: str, request: Request):
    """Public: up to 3 GBP candidates for a business name (stepper step 1)."""
    q = (q or "").strip()
    if len(q) < 3 or len(q) > 120:
        raise HTTPException(status_code=400, detail="Please enter your business name (3-120 characters).")

    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "") or "").split(",")[0].strip()
    client = sb()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")

    def _lookup_count(ip_val=None):
        query = (client.table("marketing_jobs").select("id", count="exact")
                 .eq("type", "lead_lookup").gte("queued_at", today))
        if ip_val:
            query = query.eq("params->>ip", ip_val)
        return query.execute().count or 0

    if _lookup_count() >= LEAD_LOOKUP_DAILY_CAP:
        raise HTTPException(status_code=429, detail="We've hit today's lookup limit — please try again tomorrow.")
    if ip and _lookup_count(ip) >= LEAD_LOOKUP_IP_CAP:
        raise HTTPException(status_code=429, detail="Too many searches from this connection today.")

    matches = lookup_business(q)
    client.table("marketing_jobs").insert({
        "type": "lead_lookup", "status": "completed",
        "params": {"q": q, "ip": ip, "source": "rank.restorationai.io"},
        "result": {"count": len(matches)},
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    return {"query": q, "matches": matches}


def _run_lead_audit_job(job_id: str, req: "LeadAuditRequest"):
    client = sb()
    client.table("marketing_jobs").update(
        {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", job_id).execute()
    try:
        import lead_audit  # scripts/ is on sys.path (see header)
        sales = bool(req.source)
        res = lead_audit.run_audit(req.website or req.domain, req.name, req.email, req.phone,
                                   audit_id=job_id.replace("-", "")[:12],
                                   business_name=req.business_name or None,
                                   place_id=req.place_id or None,
                                   cid=req.cid or None,
                                   email_mode="internal" if sales else "all",
                                   sales_mode=sales)
        client.table("marketing_jobs").update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result": res,
        }).eq("id", job_id).execute()
    except Exception as e:  # noqa: BLE001 — job must always terminate with a status
        client.table("marketing_jobs").update({
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": str(e)[:500],
        }).eq("id", job_id).execute()


@app.post("/lead-audit")
def create_lead_audit(req: LeadAuditRequest, request: Request):
    """Public: queue a free visibility audit.

    Accepts either {website, ...} (classic) or {business_name, place_id/cid,
    domain?, ...} (stepper). When the stepper gives no domain, we resolve it
    from the chosen listing's website field via DataForSEO."""
    domain = _lead_norm_domain(req.website or req.domain)
    if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", domain) and (req.place_id or req.cid):
        listing = _listing_by_id(req.place_id, req.cid)
        if listing and (listing.get("domain") or listing.get("url")):
            domain = _lead_norm_domain(listing.get("domain") or listing.get("url"))
            req.domain = domain
    if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", domain):
        raise HTTPException(status_code=400,
                            detail="We couldn't find a website for that business — please enter your website, e.g. yourcompany.com")
    req.domain = req.domain or domain
    if not EMAIL_RE.match(req.email or ""):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if len(re.sub(r"\D", "", req.phone or "")) < 10:
        raise HTTPException(status_code=400, detail="Please enter a valid phone number.")

    # Sales-funnel calls must present the shared secret (set in Railway env);
    # a bad secret is treated as a normal public request (source stripped).
    if req.source:
        expected = os.environ.get("LEAD_AUDIT_FUNNEL_SECRET", "")
        if not (expected and req.secret == expected):
            req.source = ""

    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "") or "").split(",")[0].strip()
    client = sb()
    trusted = bool(req.source)  # secret already validated above
    if not trusted and _lead_count_today(client) >= LEAD_AUDIT_DAILY_CAP:
        raise HTTPException(status_code=429, detail="We've hit today's audit limit — please try again tomorrow, or email contact@restorationai.io.")
    if not trusted and ip and _lead_count_today(client, "ip", ip) >= LEAD_AUDIT_IP_CAP:
        raise HTTPException(status_code=429, detail="Too many audits from this connection today.")
    if _lead_count_today(client, "domain", domain) >= LEAD_AUDIT_DOMAIN_CAP:
        raise HTTPException(status_code=429, detail="We've already run audits for this website today — check your inbox.")

    row = client.table("marketing_jobs").insert({
        "type": "lead_audit", "status": "queued",  # triggered_by is a UUID col — leave null
        "params": {"domain": domain, "name": req.name, "email": req.email,
                   "phone": req.phone, "ip": ip, "source": "rank.restorationai.io",
                   "business_name": req.business_name or None,
                   "place_id": req.place_id or None, "cid": req.cid or None},
    }).execute()
    job_id = row.data[0]["id"]

    threading.Thread(target=_run_lead_audit_job, args=(job_id, req), daemon=True).start()
    return {"audit_id": job_id, "status": "queued",
            "note": "Your audit is running — it takes about 5 minutes. We'll email the report to you. "
                    "You can also poll GET /lead-audit/{audit_id}."}


class KickoffPrepRequest(BaseModel):
    contact_id: str
    secret: str = ""
    appointment_time: str = ""   # optional human phrase, e.g. "tomorrow at 5"


@app.post("/kickoff-prep")
def kickoff_prep_endpoint(req: KickoffPrepRequest):
    """Fired by the GHL 'kickoff booked' workflow webhook. Spawns a thread
    that polls Fathom for the just-finished sales demo with this contact,
    extracts what Santino asked them to have ready, and sends ONE friendly
    SMS + email (deduped via the kickoff-prep-sent contact tag)."""
    expected = (os.environ.get("KICKOFF_PREP_SECRET")
                or os.environ.get("LEAD_AUDIT_FUNNEL_SECRET", ""))
    if not (expected and req.secret == expected):
        raise HTTPException(status_code=403, detail="bad secret")
    if not req.contact_id or len(req.contact_id) < 8:
        raise HTTPException(status_code=400, detail="contact_id required")
    import kickoff_prep  # scripts/ is on sys.path (see header)
    threading.Thread(target=kickoff_prep.run, args=(req.contact_id,),
                     kwargs={"appt_time": req.appointment_time},
                     daemon=True).start()
    return {"status": "queued",
            "note": "Polling Fathom for the demo transcript; the reminder "
                    "sends once it lands. Dedupe tag: kickoff-prep-sent."}


@app.get("/lead-audit/{audit_id}")
def get_lead_audit(audit_id: str):
    """Public: audit status. Returns only status + report URL (no contact info)."""
    rows = (sb().table("marketing_jobs")
            .select("id,type,status,result,queued_at,completed_at")
            .eq("id", audit_id).eq("type", "lead_audit").execute())
    if not rows.data:
        raise HTTPException(status_code=404, detail="Audit not found")
    j = rows.data[0]
    result = j.get("result") or {}
    return {"audit_id": j["id"], "status": j["status"],
            "report_url": result.get("report_url"),
            "grade": result.get("grade"),
            "queued_at": j["queued_at"], "completed_at": j["completed_at"]}


@app.get("/jobs", dependencies=[Depends(auth)])
def list_jobs(slug: str = None, limit: int = 20):
    """List recent jobs, optionally filtered by client slug."""
    query = (
        sb().table("marketing_jobs")
        .select("id,company_id,type,status,params,queued_at,completed_at,error")
        .order("queued_at", desc=True)
        .limit(limit)
    )
    if slug and slug in COMPANY_MAP:
        query = query.eq("company_id", COMPANY_MAP[slug])

    rows = query.execute()
    return {"jobs": rows.data}
