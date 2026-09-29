#!/usr/bin/env python3
"""service_ripple.py — truth-table service additions flow into built sites.

Heritage 2026-09-22: the site seeded 4 services at bootstrap; Sarah's
fire/roofing/windows were confirmed into companies.services days later and
the site never grew. The truth table is the source of truth (LAW 09-04) —
a service the client sells belongs on their site without anyone noticing.

Nightly (client-ops-sync): for every ACTIVE client with a built site,
  1. map companies.services -> catalog slugs (same matching as auto-build:
     exact normalized, prefix, then word-overlap >= 0.5)
  2. ADD new slugs to plan-input services (never remove — removals are
     human decisions), then plan generate + scaffold so the stub pages and
     any new before/after pairs exist; the nightly render sweep renders
     and deploys them (50 pages/site/night).
  3. services with NO catalog equivalent (e.g. "windows") file ONE [DEV]
     note so the dev agent builds a custom page — added automatically via
     the existing dev lane, not silently dropped.

Idempotent; run fleet-wide or --slug X. --dry-run prints only.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from client_ops_sync import _sb  # noqa: E402
import verticals  # noqa: E402

CLIENTS = ROOT / "clients"
SITES = ROOT / "sites"


def map_services(slug: str, services: list[str]) -> tuple[list[str], list[str]]:
    """(mapped catalog slugs, unmappable display names) — auto-build logic."""
    cat = json.loads(Path(
        verticals.resolve_template(slug, "services.json")).read_text())
    by_norm = {re.sub(r"[^a-z]", "", s["display_name"].lower()): s["slug"]
               for s in cat["services"]}
    cat_words = {s2["slug"]: set(re.findall(r"[a-z]+",
                                            s2["display_name"].lower()))
                 for s2 in cat["services"]}
    mapped, unmapped = [], []
    for s in services:
        s = str(s or "").strip()
        if not s:
            continue
        key = re.sub(r"[^a-z]", "", s.lower())
        hit = by_norm.get(key) or next(
            (v for k, v in by_norm.items() if key[:12] and key[:12] in k),
            None)
        if not hit:
            words = set(re.findall(r"[a-z]+", s.lower())) - {
                "and", "services", "service", "the"}
            best, score = None, 0.0
            for cslug, cw in cat_words.items():
                # CONTAINMENT, not Jaccard (2026-09-22: 'Roofing Services'
                # vs 'Roofing Installation and Replacement' scored 0.33
                # symmetric and missed) — how much of what the CLIENT said
                # the catalog entry covers.
                ov = len(words & cw) / max(len(words), 1)
                if ov > score:
                    best, score = cslug, ov
            if score >= 0.6:
                hit = best
        if hit:
            if hit not in mapped:
                mapped.append(hit)
        else:
            unmapped.append(s)
    return mapped, unmapped


def _dev_note_once(cid: str, slug: str, services: list[str],
                   dry_run: bool) -> None:
    """ONE combined note per client (11 separate notes for TDI on the
    first dry-run would have flooded the queue)."""
    if not services:
        return
    marker = "[SERVICE RIPPLE] custom pages needed"
    # 2026-09-29: the old filter was 'SERVICE RIPPLE custom' — the ']'
    # between RIPPLE and 'custom' meant it NEVER matched, so every run
    # (4x on 09-29) filed the identical card for all 17 clients. Match the
    # exact marker (URL-encoded), across ALL statuses: a resolved card means
    # the dev lane already handled those services, never re-file them.
    existing = _sb("GET", "/rest/v1/marketing_ops_notes"
                   f"?company_id=eq.{cid}"
                   f"&body=ilike.{quote('*' + marker + '*')}"
                   "&select=id,body,status&order=created_at.desc"
                   "&limit=50") or []
    listed = " ".join((n.get("body") or "") for n in existing)
    fresh = [s for s in services if s not in listed]
    if not fresh:
        return
    open_ones = [n for n in existing if n.get("status") == "open"]
    if open_ones:
        # Fold the new services into the one open card instead of a 2nd card.
        prev = re.search(r"sells (.*?) \(truth table\)",
                         open_ones[0].get("body") or "")
        fresh = ([x.strip() for x in prev.group(1).split(",")] if prev else []) + fresh
    body = (f"[DEV] {slug}: {marker} — the client sells "
            f"{', '.join(fresh)} (truth table) but the vertical catalog "
            "has no archetype for them. Create custom service pages "
            "following the existing patterns (hero, body, FAQ, schema, "
            "internal links) and add them to the services nav.")
    if not dry_run:
        if open_ones:
            _sb("PATCH", "/rest/v1/marketing_ops_notes"
                f"?id=eq.{open_ones[0]['id']}", {"body": body})
        else:
            _sb("POST", "/rest/v1/marketing_ops_notes", {
                "company_id": cid, "author": "service_ripple",
                "status": "open", "body": body}, prefer="return=minimal")
    print(f"  {slug}: [DEV] filed — custom pages for {fresh}")


def run(only_slug: str | None, dry_run: bool, cap: int = 5) -> int:
    cmap = json.loads((CLIENTS / "company_map.json").read_text())
    cos = {c["id"]: c for c in _sb(
        "GET", "/rest/v1/companies?status=ilike.active"
        "&select=id,services") or []}
    changed = 0
    for slug, cid in sorted(cmap.items()):
        if only_slug and slug != only_slug:
            continue
        pi_path = CLIENTS / slug / "plan-input.json"
        if not pi_path.exists() or not (SITES / slug / "src").exists():
            continue
        co = cos.get(cid)
        if not co:
            continue
        truth = [s for s in (co.get("services") or []) if s]
        if not truth:
            continue
        mapped, unmapped = map_services(slug, truth)
        pi = json.loads(pi_path.read_text())
        have = set(pi.get("services") or [])
        new = [m for m in mapped if m not in have]
        _dev_note_once(cid, slug, unmapped, dry_run)
        if not new:
            continue
        if changed >= cap and not dry_run and not only_slug:
            print(f"  {slug}: +{len(new)} due — DEFERRED (run cap {cap}; "
                  "next nightly continues)")
            continue
        print(f"  {slug}: +{len(new)} service(s) from truth table: {new}")
        if dry_run:
            changed += 1
            continue
        pi["services"] = sorted(have | set(new))
        pi_path.write_text(json.dumps(pi, indent=2) + "\n")
        for cmd in (["plan_site.py", "generate", "--slug", slug],
                    ["build_site.py", "scaffold", "--slug", slug]):
            rc = subprocess.run([sys.executable, str(ROOT / "scripts" / cmd[0]),
                                 *cmd[1:]], capture_output=True, text=True)
            if rc.returncode != 0:
                print(f"    {cmd[0]} FAILED: {rc.stdout[-200:]}"
                      f"{rc.stderr[-200:]}")
                break
        else:
            _sb("POST", "/rest/v1/marketing_ops_notes", {
                "company_id": cid, "author": "service_ripple",
                "status": "open",
                "body": f"[SERVICE RIPPLE] {slug}: added {', '.join(new)} "
                        "from the truth table — stub pages scaffolded, the "
                        "nightly render sweep writes + deploys the content "
                        "(50 pages/night)."}, prefer="return=minimal")
            changed += 1
    print(f"service ripple: {changed} site(s) grown")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cap", type=int, default=5,
                    help="max sites grown per run (wave rolls over nights)")
    a = ap.parse_args()
    return run(a.slug, a.dry_run, a.cap)


if __name__ == "__main__":
    sys.exit(main())
