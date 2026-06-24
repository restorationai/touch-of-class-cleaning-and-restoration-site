"""
Background job runner for the Rank AI FastAPI service.

S2 (content_writer) and S4 Layer 1 (refresh_scorer) run as direct subprocesses.
S1 (keyword-researcher) and S3 (onsite-audit) are agent-driven — dispatched to
GitHub Actions which already has the claude CLI + DataForSEO MCP configured.
"""

import json
import os
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

import httpx
from supabase import create_client

ROOT = Path(__file__).parent.parent

# Single source of truth for slug -> company_id: clients/company_map.json.
# Fail-soft: a missing/corrupt file yields {} and degrades to the existing
# "no company_id mapping" handling rather than crashing the FastAPI import.
try:
    COMPANY_MAP = json.loads((ROOT / "clients" / "company_map.json").read_text())
except Exception:
    COMPANY_MAP = {}

GITHUB_REPO  = "restorationai/Rank-AI-Pipeline"
GITHUB_TOKEN = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")
ONDEMAND_WORKFLOW = "on-demand.yml"


def _sb():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _update_job(job_id: str, **fields) -> None:
    _sb().table("marketing_jobs").update(fields).eq("id", job_id).execute()


def _dispatch_github(slug: str, system: int, job_id: str) -> None:
    """Trigger the on-demand GitHub Actions workflow for agent-driven systems."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{ONDEMAND_WORKFLOW}/dispatches"
    payload = {
        "ref": "main",
        "inputs": {
            "slug":   slug,
            "system": str(system),
            "job_id": job_id,
        },
    }
    resp = httpx.post(
        url,
        json=payload,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        timeout=15,
    )
    if resp.status_code not in (204, 200):
        raise RuntimeError(f"GitHub dispatch failed: {resp.status_code} {resp.text}")


def _run_subprocess(cmd: list[str]) -> tuple[int, str]:
    """Run a command, return (exit_code, combined_output)."""
    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=1800,  # 30 min max
    )
    output = result.stdout + result.stderr
    return result.returncode, output


def _run_sync(slug: str) -> None:
    """Run supabase_sync for a single client after a job completes."""
    subprocess.run(
        ["python3", str(ROOT / "scripts" / "supabase_sync.py"), "--slug", slug],
        cwd=str(ROOT),
        capture_output=True,
        timeout=120,
    )


def _execute_job(job_id: str, slug: str, system: int) -> None:
    """Worker function — runs in a background thread."""
    _update_job(job_id, status="running", started_at=_now())

    try:
        if system == 2:
            rc, log = _run_subprocess([
                "python3", str(ROOT / "scripts" / "content_writer.py"),
                "next-post", "--slug", slug, "--branch", "main",
            ])
            if rc != 0:
                _update_job(job_id, status="failed", completed_at=_now(),
                            error=f"content_writer exited {rc}", log=log[-8000:])
                return
            _run_sync(slug)
            _update_job(job_id, status="completed", completed_at=_now(), log=log[-8000:])

        elif system == 4:
            # Layer 1 runs directly; Layer 2 is agent-driven (dispatched to CI)
            rc, log = _run_subprocess([
                "python3", str(ROOT / "scripts" / "refresh_scorer.py"),
                "--slug", slug,
            ])
            if rc != 0:
                _update_job(job_id, status="failed", completed_at=_now(),
                            error=f"refresh_scorer exited {rc}", log=log[-8000:])
                return
            _run_sync(slug)
            # Layer 1 complete — mark completed (Layer 2 is advisory, not blocking)
            _update_job(job_id, status="completed", completed_at=_now(), log=log[-8000:],
                        result={"note": "Layer 1 (scorer) complete. Layer 2 runs via CI schedule."})

        else:
            # S1 and S3 are agent-driven — dispatch to GitHub Actions
            _dispatch_github(slug, system, job_id)
            # Status stays "running" — the CI workflow will call back via /jobs/{id}/complete
            # or the app polls marketing_jobs until GitHub Actions updates it
            _update_job(job_id,
                        result={"note": f"Dispatched to GitHub Actions (system {system}). Check CI for progress."})

    except Exception as exc:
        _update_job(job_id, status="failed", completed_at=_now(), error=str(exc))


def create_and_run_job(slug: str, system: int) -> str:
    """Create a marketing_jobs record and kick off the background worker. Returns job_id."""
    company_id = COMPANY_MAP.get(slug)
    if not company_id:
        raise ValueError(f"Unknown slug: {slug}")

    system_names = {1: "keyword_research", 2: "write_post", 3: "audit", 4: "refresh"}
    row = {
        "company_id": company_id,
        "type":       system_names[system],
        "status":     "queued",
        "params":     {"slug": slug, "system": system},
        "queued_at":  _now(),
    }
    result = _sb().table("marketing_jobs").insert(row).execute()
    job_id = result.data[0]["id"]

    thread = threading.Thread(target=_execute_job, args=(job_id, slug, system), daemon=True)
    thread.start()

    return job_id
