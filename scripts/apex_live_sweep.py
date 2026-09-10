#!/usr/bin/env python3
"""Reconcile marketing_sites.apex_live with REALITY (Santino 2026-09-10,
the Fran/QCI incident: Monica told a client their live site "is not live
yet" because apex_live was stale-false after a domain was attached without
the record being updated).

Truth test per client: the Pages deploy serves content-hashed /_astro/*
asset names unique to each build. If the apex HTML references the same
hashed asset as rankai-{slug}.pages.dev, the apex IS serving our deploy.
This can never false-positive on a legacy host and needs no flags anyone
has to remember to set.

Non-destructive: only writes marketing_sites.apex_live when it disagrees
with the probe, and prints every row it touches. Run ad hoc or from cron.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SB = "https://nyscciinkhlutvqkgyvq.supabase.co"
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""


def fetch(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "rank-ai-apex-sweep/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(400_000).decode("utf-8", "replace")


def sb(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(
        f"{SB}/rest/v1/{path}", method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode()
        return json.loads(raw) if raw else None


ASSET = re.compile(r"/_astro/[A-Za-z0-9_.-]+\.(?:css|js)")


def main() -> int:
    if not KEY:
        sys.exit("SUPABASE_SERVICE_ROLE_KEY required (source .env)")
    rows = sb("GET", "marketing_sites?select=company_id,domain,apex_live,rank_ai_slug"
              "&domain=not.is.null&rank_ai_slug=not.is.null") or []
    changed = mismatch_only = 0
    for row in rows:
        slug, domain = row["rank_ai_slug"], (row["domain"] or "").strip().lower()
        if not domain or "pages.dev" in domain:
            continue
        try:
            deploy_html = fetch(f"https://rankai-{slug}.pages.dev/")
            assets = set(ASSET.findall(deploy_html))
        except Exception:
            continue  # no deploy: nothing to compare against
        live = False
        if assets:
            try:
                apex_html = fetch(f"https://{domain}/")
                live = any(a in apex_html for a in assets)
            except Exception:
                live = False  # unreachable apex is not live
        if bool(row.get("apex_live")) != live:
            print(f"  FIX {slug}: apex_live {row.get('apex_live')} -> {live} ({domain})")
            sb("PATCH", f"marketing_sites?company_id=eq.{row['company_id']}",
               {"apex_live": live})
            changed += 1
        else:
            mismatch_only += 0
    print(f"==> {len(rows)} rows checked, {changed} corrected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
