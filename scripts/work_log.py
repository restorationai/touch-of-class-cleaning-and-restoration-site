#!/usr/bin/env python3
"""work_log.py — the marketing work ledger (Santino 2026-08-01: "every tiny
movement we make should be recorded as a line item").

One helper, one table: work_log() appends a row to Supabase
marketing_work_log (superadmin-view RLS, service-role writes — created
2026-08-01 via the management API, same mechanism as browser_agent_actions).

Each row's `detail` is a CLIENT-READABLE sentence, written so it can appear
verbatim in a monthly report. scripts/work_report.py aggregates this table
together with the dedicated event tables (marketing_gbp_posts,
marketing_gbp_changes, marketing_content_items, marketing_videos,
marketing_press_releases, browser_agent_actions, ...) — flows that already
land in one of those tables are NOT double-written here.

Categories in use: site, keyword-research, routine, outreach, citations.

FAIL-OPEN BY CONTRACT: a logging failure can never break the calling
pipeline. Every path is wrapped; on any error we print a warning and return
None. Never raise from this module.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = ROOT / "clients"


def _load_env() -> None:
    """Fail-soft .env loader (matches master_scheduler.py) — never overrides
    already-set env vars, so CI keeps injecting secrets via workflow env."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


def company_id_for_slug(slug: str) -> str | None:
    """slug -> company_id: clients/{slug}.json first, company_map.json backstop
    (flood-fixers has company_id null in its record but IS in the map)."""
    try:
        rec = CLIENTS_DIR / f"{slug}.json"
        if rec.exists():
            cid = json.loads(rec.read_text()).get("company_id")
            if cid:
                return cid
        cmap = CLIENTS_DIR / "company_map.json"
        if cmap.exists():
            return json.loads(cmap.read_text()).get(slug)
    except Exception:
        pass
    return None


def work_log(company_id: str | None, category: str, action: str, detail: str,
             evidence: dict | None = None, actor: str = "system",
             source: str | None = None) -> None:
    """Append one line item to marketing_work_log. Fail-open: never raises."""
    try:
        _load_env()
        url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
        if not (url and key):
            print("  [work-log] warn: SUPABASE_URL/KEY unset — line not recorded")
            return None
        if not company_id:
            print(f"  [work-log] warn: no company_id — line not recorded "
                  f"({category}/{action})")
            return None
        import requests
        resp = requests.post(
            f"{url}/rest/v1/marketing_work_log",
            json={"company_id": company_id, "category": category,
                  "action": action, "detail": detail,
                  "evidence": evidence or {}, "actor": actor,
                  "source": source},
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Content-Type": "application/json",
                     "Prefer": "return=minimal"},
            timeout=15)
        if resp.status_code not in (200, 201, 204):
            print(f"  [work-log] warn: HTTP {resp.status_code} — "
                  f"{resp.text[:120]}")
    except Exception as e:  # noqa: BLE001 — fail-open by contract
        print(f"  [work-log] warn: not recorded ({str(e)[:120]})")
    return None
