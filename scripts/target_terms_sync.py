#!/usr/bin/env python3
"""target_terms_sync.py — "What do you want to rank for?" -> content queue.

The app's Content tab (TargetTermsCard) lets the client or a superadmin add
target search terms into marketing_target_terms (Santino 2026-09-05: "I'd
rather this be in the app"). This sync drains status='queued' rows into the
client's content-queue.json as PRIORITY-1 items, so requested terms jump the
research line and the next content-writer pass picks them up. Rows flip to
'accepted' here and to 'published' when the queue item verifies live.

Runs at the top of the Content Daily workflow. Idempotent: a term whose
combo_key already exists in the queue just gets stamped accepted.

Usage:
  python3 scripts/target_terms_sync.py            # all clients
  python3 scripts/target_terms_sync.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")
import requests  # noqa: E402

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HDR = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}


def _slug_map() -> dict:
    m = json.loads((ROOT / "clients" / "company_map.json").read_text())
    return {v: k for k, v in m.items()}  # company_id -> slug


def _slugify(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:70]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = requests.get(
        f"{SB}/rest/v1/marketing_target_terms?status=eq.queued"
        "&select=id,company_id,term,added_by", headers=HDR, timeout=30).json()
    if not isinstance(rows, list) or not rows:
        print("target-terms: nothing queued")
        return 0
    by_cid = _slug_map()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    touched: set[str] = set()
    for r in rows:
        slug = by_cid.get(r["company_id"])
        if not slug:
            print(f"  skip {r['term']!r}: no slug for {r['company_id']}")
            continue
        q_path = ROOT / "clients" / slug / "content-queue.json"
        if not q_path.exists():
            print(f"  skip {slug}: no content queue yet (site not planned)")
            continue
        q = json.loads(q_path.read_text())
        items = q.setdefault("items", [])
        combo = _slugify(r["term"])
        existing = next((i for i in items if i.get("combo_key") == combo), None)
        if not existing:
            items.insert(0, {
                "id": f"{now[:10]}-{combo}",
                "status": "queued",
                "queued_at": now,
                "priority": 1,
                "content_type": "target_term",
                "combo_key": combo,
                "primary_keyword": r["term"],
                "intent": "commercial",
                "target_word_count": 1400,
                "city_anchor": None,
                "source": f"app target-term ({r.get('added_by') or 'client'})",
            })
            print(f"  {slug}: queued priority-1 item for {r['term']!r}")
            if not args.dry_run:
                q_path.write_text(json.dumps(q, indent=2) + "\n")
                touched.add(slug)
        else:
            print(f"  {slug}: {r['term']!r} already in queue ({existing.get('status')})")
        if not args.dry_run:
            requests.patch(
                f"{SB}/rest/v1/marketing_target_terms?id=eq.{r['id']}",
                headers={**HDR, "Prefer": "return=minimal"},
                json={"status": "accepted", "queued_at": now}, timeout=20)

    # published back-propagation: accepted terms whose queue item went live
    acc = requests.get(
        f"{SB}/rest/v1/marketing_target_terms?status=eq.accepted"
        "&select=id,company_id,term", headers=HDR, timeout=30).json()
    for r in acc if isinstance(acc, list) else []:
        slug = by_cid.get(r["company_id"])
        if not slug:
            continue
        q_path = ROOT / "clients" / slug / "content-queue.json"
        if not q_path.exists():
            continue
        q = json.loads(q_path.read_text())
        combo = _slugify(r["term"])
        item = next((i for i in q.get("items", [])
                     if i.get("combo_key") == combo), None)
        if item and item.get("status") == "published" and not args.dry_run:
            requests.patch(
                f"{SB}/rest/v1/marketing_target_terms?id=eq.{r['id']}",
                headers={**HDR, "Prefer": "return=minimal"},
                json={"status": "published"}, timeout=20)
            print(f"  {slug}: {r['term']!r} -> published")

    if touched and not args.dry_run:
        import subprocess
        subprocess.run(["git", "add"] + [f"clients/{s}/content-queue.json" for s in touched], cwd=ROOT)
        subprocess.run(["git", "commit", "-m",
                        "target-terms sync: app-requested terms queued at priority 1 [automated]"], cwd=ROOT)
        subprocess.run(["git", "pull", "--rebase", "--autostash"], cwd=ROOT)
        subprocess.run(["git", "push"], cwd=ROOT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
