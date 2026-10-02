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
    return len(pending_paths(slug))


def pending_paths(slug: str) -> set[str]:
    """Content files (relative to src/content) scaffolded but not rendered."""
    base = SITES / slug / "src" / "content"
    if not base.is_dir():
        return set()
    out: set[str] = set()
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
            out.add(str(p.relative_to(base)))
    return out


_PAGE_KIND = {"serviceAreas": ("city page", "city pages"),
              "locations": ("local service page", "local service pages"),
              "services": ("service page", "service pages"),
              "blog": ("article", "articles"),
              "caseStudies": ("project story", "project stories"),
              "pages": ("main page", "main pages"),
              "legal": ("policy page", "policy pages")}


def pages_line(rendered: set[str], live: bool) -> str:
    """Plain client line for pages this sweep wrote (Reports tab)."""
    kinds: dict[str, int] = {}
    for rel in rendered:
        kinds[rel.split("/", 1)[0]] = kinds.get(rel.split("/", 1)[0], 0) + 1
    parts = []
    for k, c in sorted(kinds.items(), key=lambda kv: -kv[1]):
        one, many = _PAGE_KIND.get(k, ("page", "pages"))
        parts.append(f"{c} {one if c == 1 else many}")
    n = len(rendered)
    head = (f"{n} new page{'s' if n != 1 else ''} written and published on your website"
            if live else
            f"{n} new page{'s' if n != 1 else ''} written for your new website "
            "(in preview until it launches)")
    return head + (f": {', '.join(parts)}." if parts else ".")


def log_rendered(slug: str, rendered: set[str], branch: str) -> None:
    """Reports tab (2026-09-29, every client action logs): the sweep commits
    as [automated], which the monthly summary's git roll-up skips, so the
    pages must land in marketing_work_log. Fail-soft by contract."""
    if not rendered:
        return
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from work_log import company_id_for_slug, work_log
        work_log(company_id_for_slug(slug), "site", "pages-rendered",
                 pages_line(rendered, branch == "main"),
                 evidence={"pages": sorted(rendered)[:200], "branch": branch},
                 actor="automation", source="render_sweep.py")
    except Exception as e:  # noqa: BLE001
        print(f"[{slug}] work-log warn: {str(e)[:100]}")


def images_missing(slug: str) -> bool:
    """A rendered site without its image pass ships grey placeholder heroes
    (Frontline 2026-09-04). The core hero is the sentinel, AND (2026-09-29,
    ProRestoration/Crew) every service page must own a registered image: the
    ops-sync parity step adds service pages to LIVE sites, the hero already
    exists, and those pages all fell back to the one shared services.webp
    card (19 of 35 on ProRestoration). gen_site_images is idempotent and never
    overwrites, so running it for a gap only ever ADDS images."""
    if not (SITES / slug / "public" / "images" / "hero-bg.webp").exists():
        return True
    return bool(service_images_missing(slug))


def service_images_missing(slug: str) -> list[str]:
    """service_slugs whose page has no hero: override and no registered
    /images/services/{slug}.webp (the serviceImage() fallback condition)."""
    import re as _re
    site = SITES / slug
    svc_dir = site / "src" / "content" / "services"
    if not svc_dir.is_dir():
        return []
    try:
        meta = json.loads((site / "src" / "data" / "image-meta.json").read_text())
    except (OSError, json.JSONDecodeError):
        meta = {}
    missing = []
    for md in sorted(svc_dir.glob("*.md")):
        head = md.read_text(encoding="utf-8").split("---", 2)
        fm = head[1] if len(head) > 2 else ""
        if _re.search(r"^hero:\s*\S", fm, _re.M):
            continue
        m = _re.search(r"""^service_slug:\s*['"]?([^'"\n]+?)['"]?\s*$""", fm, _re.M)
        s = m.group(1).strip() if m else md.stem
        if f"/images/services/{s}.webp" not in meta:
            missing.append(s)
    return missing


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
    before = pending_paths(slug)
    n = len(before)
    if n == 0 and not images_missing(slug):
        print(f"[{slug}] nothing pending — skip")
        return True
    if n == 0:
        print(f"[{slug}] pages rendered but images missing — image pass only "
              f"(service cards on the fallback: {service_images_missing(slug)[:12]})")
        run_image_pass(slug)
    # Per-site nightly drip (Santino 2026-09-04): a brand-new site should not
    # publish its whole 100+ page plan in one shot. Money pages render first
    # (build_site orders by priority), then ~SITE_CAP pages land per night
    # until the plan is done — every site finishes inside 7 nights (10 for 250+ page builds).
    site_cap = int(os.environ.get("RENDER_SWEEP_SITE_CAP", "50"))
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
    # clients/{slug}/ too: the image pass writes photo-manifest.json there,
    # and an unstaged manifest left the tree dirty -> sync-deploy refused
    # (2026-09-05 sweep failure)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "conflict_marker_guard.py")])
    run(["git", "add", f"sites/{slug}/", f"clients/{slug}.json", f"clients/{slug}/"])
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
        run(["git", "commit", "-m",
             f"render sweep: {slug} pending pages [automated]"])
        run(["git", "pull", "--rebase", "--autostash"])
        run(["git", "push"])
    branch = deploy_branch(slug)
    # --allow-dirty: the subtree split reads COMMITTED state, and this
    # site's changes were just committed. Residual dirt is other sites'
    # in-flight work in the same multi-site run (2026-09-22 failure: two
    # sites refused to deploy over each other's uncommitted leftovers).
    rc2 = run([sys.executable, str(ROOT / "scripts" / "build_site.py"),
               "sync-deploy", "--slug", slug, "--branch", branch,
               "--allow-dirty"])
    print(f"[{slug}] deployed to {branch}" if rc2 == 0
          else f"[{slug}] sync-deploy exited {rc2}")
    if rc2 == 0:
        log_rendered(slug, before - pending_paths(slug), branch)
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
            _rec = json.loads((CLIENTS / f"{d.name}.json").read_text())
            status = str(_rec.get("status") or "").lower()
            if status in ("paused", "suspended", "inactive", "cancelled"):
                continue
            if _rec.get("pages_paused"):   # Santino 10-01 (Paul Davis Charleston)
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
    # FAIR SHARE (Dry1 Out 2026-10-01): the budget used to charge each site
    # its WHOLE backlog while render_one only writes site_cap pages a night,
    # so after the first site (alphabetical) every site with more than the
    # remaining budget was DEFERRED every single night. Dry1 Out (619
    # pending) never got a page or an image during its 10-day soak. Now a
    # site is charged what it actually renders tonight, sites with service
    # images missing go first (they render the pass even with 0 pages), and
    # the rest rotate least-recently-swept first.
    site_cap = int(os.environ.get("RENDER_SWEEP_SITE_CAP", "50"))

    def _last_swept(slug: str) -> str:
        r = subprocess.run(["git", "log", "-1", "--format=%cI", "--grep",
                            f"render sweep: {slug}", "--", f"sites/{slug}"],
                           cwd=ROOT, capture_output=True, text=True)
        return r.stdout.strip() or "0000"

    inventory.sort(key=lambda sn: (not images_missing(sn[0]), _last_swept(sn[0])))
    print("tonight's order: " + ", ".join(s for s, _ in inventory[:12])
          + (" ..." if len(inventory) > 12 else ""))
    if args.dry_run:
        return 0
    spent, failures = 0, 0
    for slug, n in inventory:
        charge = min(n, site_cap)
        if spent + charge > cap:
            print(f"[{slug}] DEFERRED — tonight's {cap}-page budget is spent; "
                  "it rotates to the front of the next sweep")
            continue
        spent += charge
        if not render_one(slug, args.workers):
            failures += 1
    print(f"render sweep done: {spent} page(s) attempted, {failures} site(s) "
          "with errors")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
