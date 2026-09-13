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


def _run_subprocess(cmd: list[str], cwd: str | None = None) -> tuple[int, str]:
    """Run a command, return (exit_code, combined_output)."""
    result = subprocess.run(
        cmd,
        cwd=cwd or str(ROOT),
        capture_output=True,
        text=True,
        timeout=1800,  # 30 min max
    )
    output = result.stdout + result.stderr
    return result.returncode, output


# ---------------------------------------------------------------------------
# DEPLOY CHECKOUT (queue #5, 2026-09-14). The Railway image ships source
# WITHOUT .git (Nixpacks strips it), so anything that needs real git —
# sync-deploy's subtree split, cutover's stamp commits — runs from a full
# runtime clone instead. FULL clone on purpose: subtree split walks the
# whole history of sites/{slug} and breaks on shallow clones. The clone
# persists for the container's life (fetch+reset per job = always HEAD);
# a redeploy just re-clones. Refuses to run when the fetch fails — the
# worker must never deploy a stale or half-updated tree.
CHECKOUT = Path(os.environ.get("RANKAI_CHECKOUT_DIR", "/tmp/rankai-checkout"))


def _ensure_checkout() -> tuple[Path | None, str]:
    if not GITHUB_TOKEN:
        return None, ("GITHUB_PERSONAL_ACCESS_TOKEN is not set on this "
                      "Railway service — deploys need it for the monorepo "
                      "clone and the per-client repo push")
    repo_url = (f"https://x-access-token:{GITHUB_TOKEN}"
                f"@github.com/{GITHUB_REPO}.git")
    log_all = ""
    if (CHECKOUT / ".git").exists():
        # keep the PAT in the remote fresh (tokens rotate)
        _run_subprocess(["git", "-C", str(CHECKOUT), "remote", "set-url",
                         "origin", repo_url])
        for cmd in (["git", "-C", str(CHECKOUT), "fetch", "origin", "main"],
                    ["git", "-C", str(CHECKOUT), "reset", "--hard",
                     "origin/main"],
                    ["git", "-C", str(CHECKOUT), "clean", "-fd"]):
            rc, log = _run_subprocess(cmd)
            log_all += log
            if rc != 0:
                return None, f"checkout refresh failed: {log_all[-400:]}"
    else:
        rc, log = _run_subprocess(
            ["git", "clone", "--single-branch", "--branch", "main",
             repo_url, str(CHECKOUT)])
        if rc != 0:
            return None, f"monorepo clone failed: {log[-400:]}"
    _run_subprocess(["git", "-C", str(CHECKOUT), "config", "user.email",
                     "ops-worker@restorationai.io"])
    _run_subprocess(["git", "-C", str(CHECKOUT), "config", "user.name",
                     "Rank AI Ops Worker"])
    return CHECKOUT, "ok"


def _push_stamps(co: Path, slug: str) -> str:
    """Deploy stamps (clients/{slug}.json) must reach origin/main or the
    NEXT deploy silently refuses on a dirty/stale tree (the lesson this
    repo has relearned repeatedly). Rebase-retry because the worker races
    CI's automated commits."""
    stamp = f"clients/{slug}.json"
    rc, _ = _run_subprocess(["git", "-C", str(co), "diff", "--quiet",
                             "--", stamp])
    if rc == 0:
        return "no stamp changes"
    _run_subprocess(["git", "-C", str(co), "add", stamp])
    rc, log = _run_subprocess(["git", "-C", str(co), "commit", "-m",
                               f"{slug}: deploy stamps [app push]"])
    if rc != 0:
        return f"stamp commit failed: {log[-200:]}"
    for _ in range(3):
        rc, log = _run_subprocess(["git", "-C", str(co), "push",
                                   "origin", "main"])
        if rc == 0:
            return "stamps pushed"
        _run_subprocess(["git", "-C", str(co), "pull", "--rebase",
                         "origin", "main"])
    return f"stamp push FAILED after retries: {log[-200:]}"


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

        elif system == "site_push_main":
            # PUSH TO PRODUCTION from the app (Santino 2026-09-10: "can it
            # still not be done fully in app?"). Promotes the already-rendered
            # site to the per-client repo's main branch via sync-deploy, the
            # same command the pipeline machine runs. Railway's checkout pulls
            # latest first so it promotes what agents committed, not a stale
            # tree. Needs GITHUB_PERSONAL_ACCESS_TOKEN in the service env.
            co, err = _ensure_checkout()
            if co is None:
                _update_job(job_id, status="failed", completed_at=_now(),
                            error=err, log=err)
                return
            rc, log = _run_subprocess([
                "python3", str(co / "scripts" / "build_site.py"),
                "sync-deploy", "--slug", slug, "--branch", "main",
            ], cwd=str(co))
            stamp_note = _push_stamps(co, slug) if rc == 0 else ""
            _run_sync(slug)
            if rc == 0:
                _update_job(job_id, status="completed", completed_at=_now(),
                            log=(log + "\n" + stamp_note)[-8000:],
                            result={"state": "pushed_main",
                                    "note": "Production build pushed - Cloudflare Pages is "
                                            "building it now (a few minutes)."})
            else:
                hint = (" (if this mentions credentials, add "
                        "GITHUB_PERSONAL_ACCESS_TOKEN to the Railway service env)"
                        if "auth" in log.lower() or "credential" in log.lower()
                        or "403" in log or "denied" in log.lower() else "")
                _update_job(job_id, status="failed", completed_at=_now(),
                            error=f"sync-deploy exited {rc}{hint}", log=log[-8000:])

        elif system == "cutover_provision":
            # LAUNCH-SAFE PROVISION ONLY (Santino 2026-09-10, Frontline: the
            # panel's Provision click ran the FULL cutover, whose site-readiness
            # pre-flight refuses staging-only clients BEFORE the zone gets
            # created — so "Provision" did nothing). This path is the staging
            # step by itself: create the zone, snapshot + stage the email
            # records, report the required NS pair. Nothing goes live.
            co, err = _ensure_checkout()
            if co is None:
                _update_job(job_id, status="failed", completed_at=_now(),
                            error=err, log=err)
                return
            rc, log = _run_subprocess([
                "python3", str(co / "scripts" / "cutover_execute.py"),
                "provision", "--slug", slug, "--apply",
            ], cwd=str(co))
            log += "\n" + _push_stamps(co, slug)
            _run_sync(slug)
            if rc in (0, 3):
                _update_job(job_id, status="completed", completed_at=_now(), log=log[-8000:],
                            result={"state": "provisioned",
                                    "note": "Zone created and email records staged. Set the "
                                            "reported nameservers at the registrar, then "
                                            "launch."})
            else:
                _update_job(job_id, status="failed", completed_at=_now(),
                            error=f"cutover_execute provision exited {rc}", log=log[-8000:])

        elif system == "cutover":
            # ONE-CLICK CUTOVER: phased domain launch (zone + email-safe DNS
            # capture -> nameserver gate -> Pages attach -> stamp/GSC/IndexNow
            # -> outside verification -> baseline). Idempotent; exit 3 means
            # it stopped cleanly at the nameserver gate (the expected
            # mid-state the app's readiness panel keeps polling), which is a
            # successful run, not a failure. The script commits its own
            # stamps back to the monorepo and PATCHes marketing_sites, then
            # supabase_sync reconciles the rest.
            co, err = _ensure_checkout()
            if co is None:
                _update_job(job_id, status="failed", completed_at=_now(),
                            error=err, log=err)
                return
            rc, log = _run_subprocess([
                "python3", str(co / "scripts" / "cutover_execute.py"),
                "run", "--slug", slug, "--apply",
            ], cwd=str(co))
            log += "\n" + _push_stamps(co, slug)
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
                    "cutover": "cutover", "cutover_provision": "cutover_provision",
                    "site_push_main": "site_push_main",
                    "ads_account_create": "ads_account_create"}
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
