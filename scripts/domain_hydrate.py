#!/usr/bin/env python3
"""domain_hydrate.py — the launch-path rehydration guard (built 2026-09-18
after Dry Bros: the app held domain drybros.com + delegate_granted while the
repo record said domain null and brand.ts/astro.config still carried the
scaffold's .invalid placeholder — so Refresh Readiness reported "no real
domain" against a domain we'd been holding for days).

ONE canonical store per fact (house law): the app's marketing_sites.domain
is where domains land (purchase flow, access flow). This sweep flows it
outward every nightly run:

  marketing_sites.domain
    -> clients/{slug}.json  "domain"
    -> sites/{slug}/src/lib/brand.ts        (domain / canonicalUrl / imagesBase)
    -> sites/{slug}/astro.config.mjs        (site + sitemap priority URL)

Only ever fills placeholders/blanks — a repo record that already carries a
DIFFERENT real domain prints a conflict for a human instead of overwriting.
Idempotent; the ops-sync commit step ships whatever changed.

CLI: python3 scripts/domain_hydrate.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from client_ops_sync import _sb  # noqa: E402


def hydrate_site_files(slug: str, domain: str, dry: bool) -> list[str]:
    """Replace the scaffold's {slug}.invalid placeholders with the real
    domain in brand.ts + astro.config.mjs. Returns the files touched."""
    touched = []
    placeholder = f"{slug}.invalid"
    repl = {
        f'domain: "{placeholder}"': f'domain: "{domain}"',
        f'canonicalUrl: "https://{placeholder}"': f'canonicalUrl: "https://{domain}"',
        f'imagesBase: "https://images.{placeholder}"': f'imagesBase: "https://images.{domain}"',
        f'site: "https://{placeholder}"': f'site: "https://{domain}"',
        f'"https://{placeholder}/"': f'"https://{domain}/"',
    }
    for rel in ("src/lib/brand.ts", "astro.config.mjs"):
        f = ROOT / "sites" / slug / rel
        if not f.exists():
            continue
        s = orig = f.read_text()
        for a, b in repl.items():
            s = s.replace(a, b)
        if s != orig:
            if not dry:
                f.write_text(s)
            touched.append(rel)
    return touched


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    rows = _sb("GET", "/rest/v1/marketing_sites"
               "?select=rank_ai_slug,domain&domain=not.is.null") or []
    changed = 0
    for r in rows:
        slug, domain = r.get("rank_ai_slug"), str(r.get("domain") or "").strip()
        if not slug or not domain or "." not in domain:
            continue
        if domain.endswith(".invalid"):
            continue  # scaffold placeholder mirrored into the app, not a domain
        rec_p = ROOT / "clients" / f"{slug}.json"
        if not rec_p.exists():
            continue
        rec = json.loads(rec_p.read_text())
        cur = str(rec.get("domain") or "").strip()
        if cur and cur.lower() != domain.lower():
            print(f"  !! {slug}: repo says {cur!r}, app says {domain!r} — "
                  "conflicting real domains, human call needed")
            continue
        wrote = []
        if not cur:
            rec["domain"] = domain
            if not a.dry_run:
                rec_p.write_text(json.dumps(rec, indent=2) + "\n")
            wrote.append("client record")
        wrote += hydrate_site_files(slug, domain, a.dry_run)
        if wrote:
            changed += 1
            print(f"  {slug}: {domain} -> {', '.join(wrote)}"
                  + (" [dry-run]" if a.dry_run else ""))
    print(f"domain hydrate: {changed} client(s) updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
