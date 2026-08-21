#!/usr/bin/env python3
"""logo_stranded_check.py — stranded uploaded logos resolve THEMSELVES.

Santino 2026-08-21 ("I shouldn't have to be the one to apply it or close
the row"): the first upload_stranded_check run surfaced NINE pinned
'Logo uploaded — apply to site + favicon' rows sitting planned 7-31 days,
each expecting a human to either apply the logo or close the row. Both
halves are checkable by machine:

  APPLIED?   The uploaded file's bytes match a logo file in the client's
             site repo, OR the site's logo files were git-committed AFTER
             the upload landed (applied-and-processed: dark-bg variants and
             background cleanup change the bytes, but the commit time tells
             the story). Either way -> the action row resolves itself with
             the evidence in the note.
  NOT APPLIED? File ONE [DEV] note (deduped per row) so the dev/imagery
             pipeline applies it — never a Santino card.

Runs inside client_ops_sync.run() daily. CLI:
    python3 scripts/logo_stranded_check.py [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import requests

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
       or os.environ["SUPABASE_SERVICE_KEY"])
HDR = {"apikey": KEY, "Authorization": f"Bearer {KEY}",
       "Content-Type": "application/json"}


def _slug_for(cid: str) -> str | None:
    m = json.loads((ROOT / "clients" / "company_map.json").read_text())
    for slug, c in m.items():
        if c == cid:
            return slug
    return None


def _git_commit_ts(path: Path) -> int | None:
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", str(path)],
            capture_output=True, text=True, cwd=ROOT, timeout=30)
        return int(out.stdout.strip()) if out.stdout.strip() else None
    except Exception:  # noqa: BLE001
        return None


def check_logos(dry_run: bool = False) -> list[str]:
    out: list[str] = []
    rows = requests.get(
        f"{SB}/rest/v1/marketing_action_plan?status=eq.planned&pinned=is.true"
        "&title=ilike.Logo%20uploaded*"
        "&select=id,company_id,title,target,created_at,source_run_at",
        headers=HDR, timeout=30).json()
    if not isinstance(rows, list):
        return [f"logo check query failed: {str(rows)[:80]}"]
    for r in rows:
        cid = r["company_id"]
        slug = _slug_for(cid)
        target = (r.get("target") or "").removeprefix("branding/")
        uploaded_at = r.get("source_run_at") or r.get("created_at")
        if not (slug and target):
            continue
        site_dir = ROOT / "sites" / slug / "public" / "images"
        if not site_dir.exists():
            # no site yet — the logo cannot be "stranded on the site"; the
            # scaffold consumes it from branding at build time
            continue
        # download the uploaded original
        try:
            blob = requests.get(
                f"{SB}/storage/v1/object/branding/{target}",
                headers=HDR, timeout=60).content
        except Exception as e:  # noqa: BLE001
            out.append(f"{slug}: upload fetch failed ({str(e)[:60]})")
            continue
        up_hash = hashlib.sha256(blob).hexdigest()
        logo_files = [p for p in site_dir.glob("logo*") if p.is_file()]
        applied = any(
            hashlib.sha256(p.read_bytes()).hexdigest() == up_hash
            for p in logo_files)
        reason = "byte-identical file in the site repo"
        if not applied and uploaded_at and logo_files:
            try:
                up_ts = datetime.fromisoformat(
                    str(uploaded_at).replace("Z", "+00:00")).timestamp()
                commit_ts = max(filter(None, (
                    _git_commit_ts(p) for p in logo_files)), default=None)
                if commit_ts and commit_ts > up_ts:
                    applied = True
                    reason = ("site logo files committed after the upload "
                              "(applied + processed)")
            except (TypeError, ValueError):
                pass
        if applied:
            out.append(f"{slug}: logo VERIFIED applied ({reason}) — row auto-resolved")
            if not dry_run:
                requests.patch(
                    f"{SB}/rest/v1/marketing_action_plan?id=eq.{r['id']}",
                    headers=HDR,
                    json={"status": "done", "pinned": False,
                          "rationale": (f"AUTO-RESOLVED {datetime.now(timezone.utc).date()}: "
                                        f"{reason} (logo_stranded_check).")},
                    timeout=30)
        else:
            # truly unapplied -> ONE [DEV] card for the imagery/dev pipeline
            marker = f"[LOGO-APPLY {slug}]"
            notes = requests.get(
                f"{SB}/rest/v1/marketing_ops_notes?company_id=eq.{cid}"
                "&status=eq.open&select=id,body", headers=HDR, timeout=30).json()
            if any(marker in (n.get("body") or "") for n in notes):
                continue
            out.append(f"{slug}: logo NOT applied — [DEV] card filed")
            if not dry_run:
                requests.post(
                    f"{SB}/rest/v1/marketing_ops_notes", headers=HDR,
                    json={"company_id": cid, "status": "open", "body":
                          f"[DEV] {marker} Client's uploaded logo is NOT on their "
                          f"site yet. File: branding/{target} (uploaded {str(uploaded_at)[:10]}). "
                          f"Apply to sites/{slug}/public/images/ (logo.png + "
                          "logo-dark-bg.png variant per the imagery guide), "
                          "rebuild + redeploy the site's current branches, then "
                          "mark the pinned action row done."},
                    timeout=30)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    lines = check_logos(args.dry_run)
    for ln in lines:
        print("  LOGO: " + ln)
    if not lines:
        print("  LOGO: nothing stranded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
