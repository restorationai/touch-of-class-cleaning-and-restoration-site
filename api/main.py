"""
Rank AI FastAPI service — Phase 3.

Exposes HTTP endpoints so the React app (app.restorationai.io) can trigger
on-demand pipeline runs and read job status.

Authentication: Bearer token (API_SECRET_KEY env var).
Deployed on Railway from the rank-ai monorepo.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Depends
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
    allow_origins=["https://app.restorationai.io", "http://localhost:5173"],
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
