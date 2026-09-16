#!/usr/bin/env python3
"""agency_tf_watch.py — watch the agency toll-free verification and flip the
fleet on the moment it clears (C11, Santino 2026-09-16).

The agency toll-free (+18338056699, "Ignite Systems" subaccount) is the
ESTIMATE_SMS_* sender every client site's /api/estimate prefers when the
client's own toll-free isn't approved yet — the enabler for office SMS
before a client's number clears compliance. Verification was resubmitted
2026-09-16 (EIN digits-only + restorationai.io/sms-consent disclosure).

Each run:
  1. Polls the Toll-Free Verification status (subaccount creds).
  2. On TWILIO_APPROVED: sets ESTIMATE_SMS_FROM / ESTIMATE_SMS_SID /
     ESTIMATE_SMS_TOKEN as production env vars on EVERY rankai-* Pages
     project, then stamps state so this is one-shot. New sites get the
     envs from this same sweep (it re-runs after the stamp only when a
     project is missing the vars — self-healing for future scaffolds).
  3. Any other status: prints one line and exits.

Rides client-ops-sync.yml. CLI: python3 scripts/agency_tf_watch.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")
import os  # noqa: E402

STATE = ROOT / "clients" / "_agency" / "tollfree.json"
CF = "https://api.cloudflare.com/client/v4"


def _cf_headers() -> dict:
    return {"Authorization": f"Bearer {os.environ['CLOUDFLARE_R2_API_TOKEN']}"}


def _pages_projects(acct: str) -> list[str]:
    names, page = [], 1
    while True:
        r = requests.get(f"{CF}/accounts/{acct}/pages/projects",
                         headers=_cf_headers(), params={"page": page},
                         timeout=30).json()
        rows = r.get("result") or []
        if not rows:
            break
        names += [p["name"] for p in rows]
        page += 1
    return [n for n in names if n.startswith("rankai-")]


def _ensure_envs(acct: str, project: str, envs: dict, dry: bool) -> bool:
    """Idempotently merge the ESTIMATE_SMS_* vars into the project's
    production env. Returns True when a write happened."""
    r = requests.get(f"{CF}/accounts/{acct}/pages/projects/{project}",
                     headers=_cf_headers(), timeout=30).json()
    cur = (((r.get("result") or {}).get("deployment_configs") or {})
           .get("production") or {}).get("env_vars") or {}
    missing = {k: v for k, v in envs.items()
               if (cur.get(k) or {}).get("value") != v}
    if not missing:
        return False
    if dry:
        print(f"  [dry-run] {project}: would set {sorted(missing)}")
        return True
    body = {"deployment_configs": {"production": {"env_vars": {
        k: {"type": "secret_text", "value": v} for k, v in missing.items()}}}}
    pr = requests.patch(f"{CF}/accounts/{acct}/pages/projects/{project}",
                        headers=_cf_headers(), json=body, timeout=30).json()
    if not pr.get("success"):
        print(f"  {project}: env set FAILED {str(pr.get('errors'))[:120]}")
        return False
    print(f"  {project}: ESTIMATE_SMS_* set")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    st = json.loads(STATE.read_text())
    sub_sid, sub_tok = st["subaccount_sid"], st["subaccount_auth_token"]
    ver_sid = st.get("verification_sid")
    if not ver_sid:
        print("agency-tf: no verification on record")
        return 0

    r = requests.get("https://messaging.twilio.com/v1/Tollfree/Verifications/"
                     f"{ver_sid}", auth=(sub_sid, sub_tok), timeout=30)
    status = r.json().get("status") if r.ok else f"poll-error {r.status_code}"
    if status != st.get("verification_status"):
        st["verification_status"] = status
        st["updated_at"] = datetime.now(timezone.utc).isoformat()
        if not a.dry_run:
            STATE.write_text(json.dumps(st, indent=2) + "\n")
    if status != "TWILIO_APPROVED":
        print(f"agency-tf: verification {status} — waiting")
        return 0

    envs = {"ESTIMATE_SMS_FROM": st["phone_number"],
            "ESTIMATE_SMS_SID": sub_sid,
            "ESTIMATE_SMS_TOKEN": sub_tok}
    acct = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    changed = sum(_ensure_envs(acct, p, envs, a.dry_run)
                  for p in _pages_projects(acct))
    print(f"agency-tf: APPROVED — sender {st['phone_number']}; "
          f"{changed} project(s) updated this run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
