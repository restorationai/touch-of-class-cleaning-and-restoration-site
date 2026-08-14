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


def _execute_job(job_id: str, slug: str, system: int,
                 photo_url: str | None = None) -> None:
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

        elif system == "gbp_face":
            # GBP front-face audit + safe auto-fixes (photos/description/services;
            # never categories). The script is bounded (--max-photos) and
            # idempotent (sha1 provenance + dedupe), and writes its own
            # marketing_gbp_face_audit row, so no supabase_sync needed.
            rc, log = _run_subprocess([
                "python3", str(ROOT / "scripts" / "gbp_face_audit.py"),
                "--apply", "--slug", slug, "--max-photos", "10",
            ])
            if rc != 0:
                _update_job(job_id, status="failed", completed_at=_now(),
                            error=f"gbp_face_audit exited {rc}", log=log[-8000:])
                return
            _update_job(job_id, status="completed", completed_at=_now(), log=log[-8000:])

        elif system == "gbp_set_cover":
            # One-click cover photo: upload the chosen photo as COVER, then
            # the script re-audits and rewrites the marketing_gbp_face_audit
            # row itself (same as gbp_face).
            rc, log = _run_subprocess([
                "python3", str(ROOT / "scripts" / "gbp_face_audit.py"),
                "--slug", slug, "--set-cover", photo_url or "",
            ])
            if rc != 0:
                _update_job(job_id, status="failed", completed_at=_now(),
                            error=f"gbp_face_audit --set-cover exited {rc}", log=log[-8000:])
                return
            _update_job(job_id, status="completed", completed_at=_now(), log=log[-8000:])

        elif system == "ads_account_create":
            # One-click Google Ads account creation under the agency MCC
            # (LSA board button). The script carries its own refusal guards
            # (existing ads/lsa customer_id on any surface) and stamps
            # integration_settings.ads + a work_log line itself. Credential
            # note: Railway has no token files, so the script uses the
            # GOOGLE_ADS_REFRESH_TOKEN env fallback and exits with a clear
            # one-manual-step error if it is unset.
            company_id = COMPANY_MAP.get(slug, "")
            rc, log = _run_subprocess([
                "python3", str(ROOT / "scripts" / "ads_account_create.py"),
                "--company", company_id, "--apply",
            ])
            if rc != 0:
                _update_job(job_id, status="failed", completed_at=_now(),
                            error=f"ads_account_create exited {rc}", log=log[-8000:])
                return
            # The script's last line is machine-readable: RESULT {"customer_id": ...}
            result = None
            for line in reversed(log.splitlines()):
                if line.startswith("RESULT "):
                    try:
                        result = json.loads(line[len("RESULT "):])
                    except json.JSONDecodeError:
                        pass
                    break
            _update_job(job_id, status="completed", completed_at=_now(),
                        log=log[-8000:], result=result)

        elif system == "cutover":
            # ONE-CLICK CUTOVER: phased domain launch (zone + email-safe DNS
            # capture -> nameserver gate -> Pages attach -> stamp/GSC/IndexNow
            # -> outside verification -> baseline). Idempotent; exit 3 means
            # it stopped cleanly at the nameserver gate (the expected
            # mid-state the app's readiness panel keeps polling), which is a
            # successful run, not a failure. The script commits its own
            # stamps back to the monorepo and PATCHes marketing_sites, then
            # supabase_sync reconciles the rest.
            rc, log = _run_subprocess([
                "python3", str(ROOT / "scripts" / "cutover_execute.py"),
                "run", "--slug", slug, "--apply",
            ])
            _run_sync(slug)  # partial progress (zone/domain stamp) should surface either way
            if rc == 0:
                _update_job(job_id, status="completed", completed_at=_now(), log=log[-8000:],
                            result={"state": "live"})
            elif rc == 3:
                _update_job(job_id, status="completed", completed_at=_now(), log=log[-8000:],
                            result={"state": "waiting_on_nameservers",
                                    "note": "Zone + email records staged. Waiting on the "
                                            "registrar nameserver transfer — re-run after "
                                            "it propagates."})
            else:
                _update_job(job_id, status="failed", completed_at=_now(),
                            error=f"cutover_execute exited {rc}", log=log[-8000:])

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


def create_and_run_job(slug: str, system, photo_url: str | None = None) -> str:
    """Create a marketing_jobs record and kick off the background worker. Returns job_id."""
    company_id = COMPANY_MAP.get(slug)
    if not company_id:
        raise ValueError(f"Unknown slug: {slug}")

    system_names = {1: "keyword_research", 2: "write_post", 3: "audit", 4: "refresh",
                    "gbp_face": "gbp_face_fix", "gbp_set_cover": "gbp_set_cover",
                    "cutover": "cutover", "ads_account_create": "ads_account_create"}
    params = {"slug": slug, "system": system}
    if photo_url:
        params["photo_url"] = photo_url
    row = {
        "company_id": company_id,
        "type":       system_names[system],
        "status":     "queued",
        "params":     params,
        "queued_at":  _now(),
    }
    result = _sb().table("marketing_jobs").insert(row).execute()
    job_id = result.data[0]["id"]

    thread = threading.Thread(target=_execute_job, args=(job_id, slug, system, photo_url),
                              daemon=True)
    thread.start()

    return job_id
