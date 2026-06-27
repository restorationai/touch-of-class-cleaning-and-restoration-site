#!/usr/bin/env python3
"""
analytics_set.py — set a client's GA4 / Clarity ids in their site brand.ts.

Update-or-insert (idempotent). Also mirrors the ids into the client's
plan-input.json brand block, so a future re-scaffold keeps them.

Usage:
    python3 scripts/analytics_set.py --slug narestco --ga4 G-XXXXXXXXXX
    python3 scripts/analytics_set.py --slug narestco --clarity abcdef1234
    python3 scripts/analytics_set.py --slug narestco --ga4 G-XX --clarity abcdef --push
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITES = ROOT / "sites"
CLIENTS = ROOT / "clients"


def _set_field(text: str, key: str, value: str) -> str:
    """Replace `key: "..."` if present, else insert after googleMapsApiKey."""
    pat = re.compile(rf'(\b{re.escape(key)}:\s*")[^"]*(")')
    if pat.search(text):
        return pat.sub(rf'\g<1>{value}\g<2>', text, count=1)
    anchor = next((l for l in text.splitlines() if "googleMapsApiKey:" in l), None)
    if not anchor:
        raise RuntimeError("brand.ts has no googleMapsApiKey anchor to insert after")
    return text.replace(anchor, f'{anchor}\n  {key}: "{value}",', 1)


def update_brand_ts(slug: str, ga4: str | None, clarity: str | None) -> Path:
    bp = SITES / slug / "src" / "lib" / "brand.ts"
    if not bp.exists():
        raise FileNotFoundError(f"no site brand.ts for '{slug}' at {bp}")
    text = bp.read_text()
    if ga4 is not None:
        text = _set_field(text, "ga4MeasurementId", ga4)
    if clarity is not None:
        text = _set_field(text, "clarityProjectId", clarity)
    bp.write_text(text)
    return bp


def mirror_plan_input(slug: str, ga4: str | None, clarity: str | None) -> None:
    pi = CLIENTS / slug / "plan-input.json"
    if not pi.exists():
        return
    d = json.loads(pi.read_text())
    brand = d.setdefault("brand", {})
    if ga4 is not None:
        brand["ga4_measurement_id"] = ga4
    if clarity is not None:
        brand["clarity_project_id"] = clarity
    pi.write_text(json.dumps(d, indent=2))


def git_push_site(slug: str) -> None:
    """Commit the brand.ts change to the monorepo, then deploy via subtree push so
    Cloudflare rebuilds. NOTE: sites/{slug} is a monorepo subdir (NOT its own repo), so
    a plain `git push` here would push the monorepo, not the client site — use sync-deploy."""
    subprocess.run(["git", "add", f"sites/{slug}/src/lib/brand.ts"], cwd=ROOT, check=True)
    subprocess.run(["git", "commit", "-m", f"analytics: set GA4/Clarity ids for {slug}"],
                   cwd=ROOT, check=False)  # no-op if nothing staged
    subprocess.run(["python3", "scripts/build_site.py", "sync-deploy",
                    "--slug", slug, "--branch", "main", "--allow-dirty"], cwd=ROOT, check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--ga4", help="GA4 Measurement ID (G-XXXXXXXXXX)")
    ap.add_argument("--clarity", help="Microsoft Clarity project id")
    ap.add_argument("--push", action="store_true", help="git commit+push the site repo")
    args = ap.parse_args()
    if not (args.ga4 or args.clarity):
        print("Nothing to set — pass --ga4 and/or --clarity.", file=sys.stderr)
        return 1
    bp = update_brand_ts(args.slug, args.ga4, args.clarity)
    mirror_plan_input(args.slug, args.ga4, args.clarity)
    print(f"updated {bp}")
    if args.ga4:
        print(f"  ga4MeasurementId = {args.ga4}")
    if args.clarity:
        print(f"  clarityProjectId = {args.clarity}")
    if args.push:
        git_push_site(args.slug)
        print("  committed + pushed site repo (Cloudflare will redeploy).")
    else:
        print("  (not pushed — rerun with --push to deploy, or rebuild the site.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
