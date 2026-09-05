#!/usr/bin/env python3
"""render_sweep.py — cloud renderer for pending site pages.

Part of the dev-agent scale-up (Santino 2026-09-03): the agent stopped
rendering page volume inline. When a task expands a site's plan (new
cities, new services), the agent edits the plan, scaffolds the stubs,
commits, and DISPATCHES this — the purpose-built renderer with parallel
workers, per-page idempotent retries and cost logging. A nightly sweep
also catches any site whose plan changed without a dispatch (belt +
braces: nothing stays half-scaffolded for more than a day).

Modes:
    --slug X       render every pending (rendered: false) page of one site,
                   then commit + sync-deploy to the branch the site already
                   lives on (main if it has ever been pushed to main, else
                   staging).
    (no args)      sweep: same treatment for EVERY site with pending pages,
                   oldest-scaffold first, under a per-run page cap.
    --dry-run      inventory only — print pending counts, render nothing.

Cost guard: RENDER_SWEEP_CAP pages per run (default 400 ≈ $16). A site that
would blow the cap is deferred to the next night with a loud line.

Env: ANTHROPIC_API_KEY (render), SUPABASE + CLOUDFLARE + GitHub PAT
(sync-deploy). Runs in .github/workflows/site-render.yml.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITES = ROOT / "sites"
CLIENTS = ROOT / "clients"


def pending_pages(slug: str) -> int:
    """Count content files scaffolded but not yet rendered."""
    base = SITES / slug / "src" / "content"
    if not base.is_dir():
        return 0
    n = 0
    for p in base.rglob("*.md"):
        try:
            raw = p.read_text(errors="ignore")
        except OSError:
            continue
        # Examine the WHOLE frontmatter block (FAQ/link arrays run past any
        # fixed head window — a 600-char peek marked live sites pending).
        # Pending = frontmatter NOT carrying rendered:true, matching
        # build_site render's own skip logic (fresh scaffolds carry no
        # rendered: key at all — Arch 2026-09-04).
        fm = raw
        if raw.startswith("---"):
            end = raw.find("\n---", 3)
            if end != -1:
                fm = raw[:end + 4]
        if not re.search(r"^rendered:\s*true\b", fm, re.M):
            n += 1
    return n


def images_missing(slug: str) -> bool:
    """A rendered site without its image pass ships grey placeholder heroes
    (Frontline 2026-09-04). Cheap check: the core hero is the sentinel —
    gen_site_images is idempotent and fills whatever else is missing."""
    return not (SITES / slug / "public" / "images" / "hero-bg.webp").exists()


def run_image_pass(slug: str) -> bool:
    """Core + per-service images, each capped so one silent API hang cannot
    stall the sweep (the 25-min gen_site_images hang, 2026-09-03)."""
    ok = True
    for extra in ([], ["--services"]):
        try:
            rc = run([sys.executable, str(ROOT / "scripts" / "gen_site_images.py"),
                      "--slug", slug, *extra], timeout=1800)
            ok = ok and rc == 0
        except subprocess.TimeoutExpired:
            print(f"[{slug}] image pass timed out (30 min) — next sweep resumes "
                  "(generation skips existing files)")
            ok = False
    return ok


def deploy_branch(slug: str) -> str:
    """The branch this site's audience actually sees (rule 2f)."""
    try:
        c = json.loads((CLIENTS / f"{slug}.json").read_text())
        if (c.get("build") or {}).get("last_pushed_main_at"):
            return "main"
    except (OSError, json.JSONDecodeError):
        pass
    return "staging"


def run(cmd: list[str], timeout: int = 7200) -> int:
    print("  $", " ".join(cmd), flush=True)
    return subprocess.run(cmd, timeout=timeout).returncode


def render_one(slug: str, workers: int) -> bool:
    n = pending_pages(slug)
    if n == 0 and not images_missing(slug):
        print(f"[{slug}] nothing pending — skip")
        return True
    if n == 0:
        print(f"[{slug}] pages rendered but images missing — image pass only")
        run_image_pass(slug)
    # Per-site nightly drip (Santino 2026-09-04): a brand-new site should not
    # publish its whole 100+ page plan in one shot. Money pages render first
    # (build_site orders by priority), then ~SITE_CAP pages land per night
    # until the plan is done — a 106-page site rolls out over ~4 nights.
    site_cap = int(os.environ.get("RENDER_SWEEP_SITE_CAP", "30"))
    if n > site_cap:
        print(f"[{slug}] {n} pending page(s) — rendering top-priority {site_cap} "
              f"tonight (drip; ~{-(-n // site_cap)} night(s) to finish)")
    else:
        print(f"[{slug}] {n} pending page(s) — rendering")
    rc = run([sys.executable, str(ROOT / "scripts" / "build_site.py"),
              "render", "--slug", slug, "--workers", str(workers),
              "--limit", str(site_cap)])
    if images_missing(slug):
        run_image_pass(slug)
    if rc != 0:
        print(f"[{slug}] render exited {rc} (partial progress is committed anyway; "
              "the next sweep resumes the remainder)")
    # commit whatever rendered — idempotency means a re-run only does the rest
    run(["git", "add", f"sites/{slug}/", f"clients/{slug}.json"])
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
        run(["git", "commit", "-m",
             f"render sweep: {slug} pending pages [automated]"])
        run(["git", "pull", "--rebase", "--autostash"])
        run(["git", "push"])
    branch = deploy_branch(slug)
    rc2 = run([sys.executable, str(ROOT / "scripts" / "build_site.py"),
               "sync-deploy", "--slug", slug, "--branch", branch])
    print(f"[{slug}] deployed to {branch}" if rc2 == 0
          else f"[{slug}] sync-deploy exited {rc2}")
    return rc == 0 and rc2 == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    if args.slug:
        if args.dry_run:
            print(f"[{args.slug}] pending: {pending_pages(args.slug)}")
            return 0
        return 0 if render_one(args.slug, args.workers) else 1

    cap = int(os.environ.get("RENDER_SWEEP_CAP", "400"))
    inventory = []
    for d in sorted(SITES.iterdir()):
        if not (d / "src").is_dir():
            continue
        # never spend render budget on paused/suspended accounts
        try:
            status = str(json.loads((CLIENTS / f"{d.name}.json").read_text())
                         .get("status") or "").lower()
            if status in ("paused", "suspended", "inactive", "cancelled"):
                continue
        except (OSError, json.JSONDecodeError):
            pass
        n = pending_pages(d.name)
        if n:
            inventory.append((d.name, n))
        elif images_missing(d.name) and (d / "src" / "lib" / "brand.ts").exists():
            # fully rendered but never imaged — backstop pass + redeploy
            inventory.append((d.name, 0))
    if not inventory:
        print("render sweep: nothing pending anywhere — clean")
        return 0
    print(f"render sweep: {sum(n for _, n in inventory)} pending page(s) "
          f"across {len(inventory)} site(s); cap {cap}")
    for slug, n in inventory:
        print(f"  {slug}: {n}")
    if args.dry_run:
        return 0
    spent, failures = 0, 0
    for slug, n in inventory:
        if spent + n > cap:
            print(f"[{slug}] DEFERRED — {n} pages would pass the {cap}-page "
                  "cap; next sweep picks it up")
            continue
        spent += n
        if not render_one(slug, args.workers):
            failures += 1
    print(f"render sweep done: {spent} page(s) attempted, {failures} site(s) "
          "with errors")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
