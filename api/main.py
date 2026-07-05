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
    ],
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
}

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RunJobRequest(BaseModel):
    slug: str
    system: int  # 1, 2, 3, or 4


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


@app.post("/jobs/run", dependencies=[Depends(auth)])
def run_job(req: RunJobRequest):
    """Trigger a system run for a client. Returns job_id immediately; runs in background."""
    if req.slug not in COMPANY_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown slug: {req.slug}")
    if req.system not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="system must be 1, 2, 3, or 4")

    job_id = create_and_run_job(req.slug, req.system)

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

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")


class LeadAuditRequest(BaseModel):
    website: str
    name: str = ""
    email: str
    phone: str


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


def _run_lead_audit_job(job_id: str, req: "LeadAuditRequest"):
    client = sb()
    client.table("marketing_jobs").update(
        {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", job_id).execute()
    try:
        import lead_audit  # scripts/ is on sys.path (see header)
        res = lead_audit.run_audit(req.website, req.name, req.email, req.phone,
                                   audit_id=job_id.replace("-", "")[:12])
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
    """Public: queue a free visibility audit for a prospect's website."""
    domain = _lead_norm_domain(req.website)
    if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", domain):
        raise HTTPException(status_code=400, detail="Please enter a valid website, e.g. yourcompany.com")
    if not EMAIL_RE.match(req.email or ""):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if len(re.sub(r"\D", "", req.phone or "")) < 10:
        raise HTTPException(status_code=400, detail="Please enter a valid phone number.")

    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "") or "").split(",")[0].strip()
    client = sb()
    if _lead_count_today(client) >= LEAD_AUDIT_DAILY_CAP:
        raise HTTPException(status_code=429, detail="We've hit today's audit limit — please try again tomorrow, or email contact@restorationai.io.")
    if ip and _lead_count_today(client, "ip", ip) >= LEAD_AUDIT_IP_CAP:
        raise HTTPException(status_code=429, detail="Too many audits from this connection today.")
    if _lead_count_today(client, "domain", domain) >= LEAD_AUDIT_DOMAIN_CAP:
        raise HTTPException(status_code=429, detail="We've already run audits for this website today — check your inbox.")

    row = client.table("marketing_jobs").insert({
        "type": "lead_audit", "status": "queued", "triggered_by": "rank.restorationai.io",
        "params": {"domain": domain, "name": req.name, "email": req.email,
                   "phone": req.phone, "ip": ip},
    }).execute()
    job_id = row.data[0]["id"]

    threading.Thread(target=_run_lead_audit_job, args=(job_id, req), daemon=True).start()
    return {"audit_id": job_id, "status": "queued",
            "note": "Your audit is running — it takes about 5 minutes. We'll email the report to you. "
                    "You can also poll GET /lead-audit/{audit_id}."}


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
