#!/usr/bin/env python3
"""deploy_guard.py — PRE-DEPLOY GUARD for production sync-deploys
(Santino 2026-09-29: "We definitely don't want these sites getting reverted
after we make changes").

Incidents it exists for:
  09-23  an automated client-ops-sync scaffold rewrote layouts, components,
         brand.ts and tailwind on many live sites (Crew lost Kyle's homepage
         videos, its logo sizing and its Case Studies nav).
  09-29  a 3.5h gbp-maintenance run deployed All Pro + Crew from an hours-old
         checkout and rolled newer work back (East Niles came back).
  09-2x  service images replaced by automation (ProRestoration blue cast +
         duplicates, Crew services all on the /images/services.webp fallback).

WHAT IT DOES. Before `build_site.py sync-deploy --branch main` force-pushes
sites/{slug}/, compare the tree about to ship (HEAD:sites/{slug}) with what
is on github.com/restorationai/{slug}-site main right now (= what is live).
Every path that would change is attributed to the monorepo commits that
changed it since the live state (the live tree is matched to a local commit
via its tree hash). REFUSE when the push would:

  (a) delete / rewrite a DESIGN file (src/layouts, src/components, src/pages,
      src/styles, src/lib/brand.ts, tailwind.config.mjs) beyond a small line
      threshold, where the lines were removed by AUTOMATED commits (or by no
      commit at all = this checkout is older than the live site);
  (b) remove a live page (content .md/.mdx or a src/pages route file) that an
      automated commit (or no commit) deleted;
  (c) change or delete an existing public/images/ file via an automated commit
      (or no commit);
  (d) roll back work the live site already has but this checkout lacks
      (another lane deployed, its monorepo push has not landed yet) when that
      work touches (a)-(c) and is younger than ROLLBACK_FRESH_HOURS.

A commit is INTENTIONAL (allowed to do (a)-(c)) when it is a human commit
(not a bot identity, no [automated] tag), a dev-agent commit (author "Rank AI
Dev Agent" / subject "DEV AGENT:"), or any commit carrying the explicit marker
"[design-change]" (or a "Design-Change: yes" trailer). New content, new pages,
blog posts, AI-answer blocks and small brand.ts syncs pass untouched.

Override: `sync-deploy --allow-design-change` (deliberate human work). Every
override is logged to ops_kv deploy-guard-log. Kill switch for an emergency:
DEPLOY_GUARD_MODE=warn (report, never block) or off.

A block writes ops_kv deploy-guard-block/{slug} and files ONE company-less
[PIPELINE ALERT] card (pipeline_watchdog pattern); the next passing deploy of
that site clears both.

CLI (dry run, no push, no writes):
  python3 scripts/deploy_guard.py --slug crew-restoration-construction
  python3 scripts/deploy_guard.py --all
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
GH_OWNER = "restorationai"

DESIGN_PREFIXES = ("src/layouts/", "src/components/", "src/pages/", "src/styles/")
DESIGN_FILES = ("src/lib/brand.ts", "tailwind.config.mjs")
IMAGE_PREFIX = "public/images/"
LINE_LIMIT_FILE = 12     # lines an automated commit may remove from one design file
LINE_LIMIT_TOTAL = 40    # ... and across all design files in one deploy
ROLLBACK_FRESH_HOURS = 4
DEAD_SLUGS = {"mcc-restoration", "mold-solutionz"}

BOT_EMAILS = {"ops@restorationai.io", "ops-worker@restorationai.io"}
BOT_NAMES = {"ignite systems"}   # Mac Mini operator box (browser agents)
MARKERS = ("[design-change]", "design-change: yes")


# ---------------------------------------------------------------- helpers
def _git(args: list[str], cwd: Path = ROOT, stdin: str | None = None) -> str:
    out = subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True,
                         text=True, input=stdin)
    if out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:3])} failed: {out.stderr.strip()[:200]}")
    return out.stdout


def _gh(path: str) -> requests.Response:
    tok = (os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
           or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT", ""))
    return requests.get(f"https://api.github.com{path}", timeout=30, headers={
        "Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"})


def is_design(p: str) -> bool:
    return p.startswith(DESIGN_PREFIXES) or p in DESIGN_FILES


def is_page(p: str) -> bool:
    if p.startswith("src/content/") and p.endswith((".md", ".mdx")):
        return True
    if p.startswith("src/pages/") and p.endswith((".astro", ".md", ".mdx")):
        return not any(seg.startswith("_") for seg in p.split("/"))
    return False


def is_image(p: str) -> bool:
    return p.startswith(IMAGE_PREFIX)


def classify_commit(name: str, email: str, message: str) -> str:
    """intentional | automated."""
    low = message.lower()
    if any(m in low for m in MARKERS):
        return "intentional"
    if name.strip() == "Rank AI Dev Agent" or message.startswith("DEV AGENT"):
        return "intentional"
    if ("[automated]" in low or email.strip().lower() in BOT_EMAILS
            or "[bot]" in email or name.strip().lower() in BOT_NAMES
            or name.startswith("Rank AI")):
        return "automated"
    return "intentional"   # a human commit


def _ls_tree(treeish: str) -> dict[str, str]:
    out = _git(["ls-tree", "-r", "--full-tree", treeish])
    res = {}
    for line in out.splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) >= 3 and parts[1] == "blob":
            res[path] = parts[2]
    return res


def _blob_text(sha: str, repo: str) -> str | None:
    try:
        return _git(["cat-file", "-p", sha])
    except RuntimeError:
        pass
    r = _gh(f"/repos/{GH_OWNER}/{repo}/git/blobs/{sha}")
    if not r.ok:
        return None
    import base64
    try:
        return base64.b64decode(r.json().get("content") or "").decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return None


def _removed_lines(old: str | None, new: str | None) -> int:
    a = (old or "").splitlines()
    b = (new or "").splitlines()
    if not b:
        return len(a)
    n = 0
    for tag, i1, i2, _j1, _j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("delete", "replace"):
            n += i2 - i1
    return n


def _age_hours(iso: str) -> float:
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return 999.0
    return (datetime.now(timezone.utc) - t).total_seconds() / 3600


def client_repo_for(slug: str) -> str:
    rec = ROOT / "clients" / f"{slug}.json"
    if rec.exists():
        try:
            gh_field = (json.loads(rec.read_text()).get("build") or {}).get("github_repo")
            if gh_field and "/" in gh_field:
                return gh_field.split("/", 1)[1]
        except (json.JSONDecodeError, OSError):
            pass
    return f"{slug}-site"


# ---------------------------------------------------------------- core
def _local_commits(rng: list[str], slug: str) -> list[dict]:
    """Commits in the range touching sites/{slug}, with per-file status and
    removed-line counts (paths relative to the site root)."""
    fmt = "%x1e%H%x1f%an%x1f%ae%x1f%cI%x1f%B%x1f"
    out = _git(["log", "--no-renames", "--raw", "--numstat", f"--format={fmt}"]
               + rng + ["--", f"sites/{slug}"])
    pre = f"sites/{slug}/"
    commits = []
    for blk in out.split("\x1e"):
        if not blk.strip():
            continue
        parts = blk.split("\x1f")
        if len(parts) < 6:
            continue
        sha, name, email, date, body, rest = parts[:6]
        c = {"sha": sha, "name": name, "email": email, "date": date,
             "subject": body.strip().splitlines()[0] if body.strip() else "",
             "klass": classify_commit(name, email, body), "status": {}, "removed": {}}
        for line in rest.splitlines():
            if line.startswith(":"):
                meta, _, path = line.partition("\t")
                if path.startswith(pre):
                    c["status"][path[len(pre):]] = meta.split()[-1]
            elif line.count("\t") >= 2:
                a, r, path = line.split("\t", 2)
                if path.startswith(pre) and r.isdigit():
                    c["removed"][path[len(pre):]] = int(r)
        commits.append(c)
    return commits   # newest first


def _find_base(slug: str, remote_commits: list[dict],
               head: str = "HEAD") -> tuple[str | None, int]:
    """Local commit whose sites/{slug} tree equals a remote commit's tree.
    Returns (local_sha, index into remote_commits) or (None, -1)."""
    shas = _git(["log", "-n", "600", "--format=%H", head, "--", f"sites/{slug}"]).split()
    if not shas:
        return None, -1
    batch = "".join(f"{s}:sites/{slug}\n" for s in shas)
    out = _git(["cat-file", "--batch-check"], stdin=batch).splitlines()
    tree_to_local: dict[str, str] = {}
    for s, line in zip(shas, out):
        t = line.split()[0]
        tree_to_local.setdefault(t, s)
    for i, rc in enumerate(remote_commits):
        if rc["tree"] in tree_to_local:
            return tree_to_local[rc["tree"]], i
    return None, -1


def evaluate(slug: str, repo: str | None = None, head: str = "HEAD",
             live_rev: str | None = None) -> dict:
    """Compare {head}:sites/{slug} with the per-client repo's main. Never
    raises for data problems; returns {verdict, findings, warnings, ...}.
    live_rev (tests/replays): a LOCAL monorepo commit standing in for the
    live site, e.g. replaying 09-23 with head=b68f92332 live_rev=b68f92332^."""
    repo = repo or client_repo_for(slug)
    res = {"slug": slug, "repo": repo, "verdict": "pass", "findings": [],
           "warnings": [], "base": None, "remote_only": [], "changed": 0}
    if live_rev:
        remote_commits = [{
            "sha": _git(["rev-parse", live_rev]).strip(),
            "tree": _git(["rev-parse", f"{live_rev}:sites/{slug}"]).strip(),
            "date": _git(["log", "-1", "--format=%cI", live_rev]).strip(),
            "subject": "(replay)"}]
    else:
        r = _gh(f"/repos/{GH_OWNER}/{repo}/commits?sha=main&per_page=100")
        if r.status_code in (404, 409):
            res["warnings"].append("no live main on the per-client repo (first deploy)")
            return res
        r.raise_for_status()
        remote_commits = [{"sha": c["sha"], "tree": c["commit"]["tree"]["sha"],
                           "date": c["commit"]["committer"]["date"],
                           "subject": (c["commit"]["message"] or "").splitlines()[0][:100]}
                          for c in r.json()]
    if not remote_commits:
        return res
    head_tree = _git(["rev-parse", f"{head}:sites/{slug}"]).strip()
    if head_tree == remote_commits[0]["tree"]:
        return res   # identical to what is live

    if live_rev:
        remote = _ls_tree(f"{live_rev}:sites/{slug}")
    else:
        t = _gh(f"/repos/{GH_OWNER}/{repo}/git/trees/{remote_commits[0]['tree']}?recursive=1")
        t.raise_for_status()
        tj = t.json()
        if tj.get("truncated"):
            res["warnings"].append("remote tree listing truncated; checks are partial")
        remote = {e["path"]: e["sha"] for e in tj.get("tree", []) if e.get("type") == "blob"}
    local = _ls_tree(f"{head}:sites/{slug}")

    base_sha, idx = _find_base(slug, remote_commits, head)
    if base_sha:
        base = _ls_tree(f"{base_sha}:sites/{slug}")
        commits = _local_commits([f"{base_sha}..{head}"], slug)
        remote_only = remote_commits[:idx]
        res["base"] = base_sha[:10]
        res["remote_only"] = [f"{c['sha'][:9]} {c['date']} {c['subject']}" for c in remote_only]
        fresh_rollback = bool(remote_only) and _age_hours(remote_only[-1]["date"]) < ROLLBACK_FRESH_HOURS
    else:
        # The live tree matches no commit in this checkout's history (the
        # checkout is OLDER than live, or live was pushed from elsewhere):
        # attribute by date against the live head; unexplained = rollback.
        base = None
        commits = _local_commits([f"--since={remote_commits[0]['date']}", head], slug)
        remote_only, fresh_rollback = [], False
        res["warnings"].append("live tree matches no commit in this checkout; "
                               "date-based attribution")

    touched: dict[str, list[dict]] = {}
    for c in commits:
        for p in set(c["status"]) | set(c["removed"]):
            touched.setdefault(p, []).append(c)

    def who(p: str) -> str:
        cs = touched.get(p) or []
        return ", ".join(f"{c['sha'][:9]} '{c['subject'][:60]}'" for c in cs[:2]) or "no commit (checkout older than live)"

    changed = [p for p in set(remote) | set(local) if remote.get(p) != local.get(p)]
    res["changed"] = len(changed)
    total_auto_removed = 0
    rollbacks = []
    for p in sorted(changed):
        rsha, lsha = remote.get(p), local.get(p)
        if rsha is None:
            continue            # brand-new file: always fine
        harmful = ((is_design(p)) or (is_page(p) and lsha is None) or is_image(p))
        if not harmful:
            continue
        if base is not None:
            bsha = base.get(p)
            local_origin = lsha != bsha
            remote_origin = rsha != bsha
        else:
            local_origin, remote_origin = True, False
        if remote_origin:
            rollbacks.append(p)
        if not local_origin:
            continue
        cs = touched.get(p) or []
        autos = [c for c in cs if c["klass"] == "automated"]
        if is_page(p) and lsha is None:
            deleter = next((c for c in cs if c["status"].get(p) == "D"), None)
            if deleter is None or deleter["klass"] == "automated":
                res["findings"].append(f"(b) removes live page {p} [by {who(p)}]")
            continue
        if is_image(p):
            if not cs or autos:
                verb = "deletes" if lsha is None else "changes"
                res["findings"].append(f"(c) {verb} live image {p} [by {who(p)}]")
            continue
        # design file (modified or deleted)
        new_text = None if lsha is None else _blob_text(lsha, repo)
        net_removed = _removed_lines(_blob_text(rsha, repo), new_text)
        if not cs:
            res["findings"].append(
                f"(a) {'deletes' if lsha is None else 'reverts'} {p} (-{net_removed} lines) "
                "with no commit since the live deploy (checkout older than live)")
            continue
        if net_removed <= LINE_LIMIT_FILE and lsha is not None:
            if autos:
                total_auto_removed += net_removed
            continue
        auto_removed = sum(c["removed"].get(p, 0) for c in autos)
        total_auto_removed += min(net_removed, auto_removed)
        if lsha is None and autos:
            res["findings"].append(f"(a) deletes design file {p} [by {who(p)}]")
        elif auto_removed > LINE_LIMIT_FILE:
            res["findings"].append(
                f"(a) rewrites {p}: -{min(net_removed, auto_removed)} lines by automated "
                f"commit(s) [{who(p)}]")
    if total_auto_removed > LINE_LIMIT_TOTAL and not any(f.startswith("(a)") for f in res["findings"]):
        res["findings"].append(
            f"(a) automated commits remove {total_auto_removed} lines across design files "
            f"(limit {LINE_LIMIT_TOTAL})")
    if rollbacks:
        msg = (f"(d) live site has {len(remote_only)} deploy(s) this checkout lacks "
               f"({'; '.join(res['remote_only'][:2])}); pushing rolls back "
               f"{len(rollbacks)} protected file(s): {', '.join(rollbacks[:4])}")
        if fresh_rollback:
            res["findings"].append(msg + f" (younger than {ROLLBACK_FRESH_HOURS}h: that "
                                   "lane's monorepo push has not landed yet)")
        else:
            res["warnings"].append(msg + " (orphaned: older than "
                                   f"{ROLLBACK_FRESH_HOURS}h, monorepo wins)")
    if res["findings"]:
        res["verdict"] = "block"
    return res


# ---------------------------------------------------------------- side effects
def _sb(method: str, path: str, body=None, prefer: str = "return=minimal"):
    url = os.environ["SUPABASE_URL"].rstrip("/") + path
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    r = requests.request(method, url, json=body, timeout=20, headers={
        "apikey": key, "Authorization": f"Bearer {key}",
        "Content-Type": "application/json", "Prefer": prefer})
    r.raise_for_status()
    return r.json() if r.content else None


def _alert_issue(slug: str, res: dict) -> str:
    return (f"deploy guard blocked: {slug} — production deploy refused, the "
            f"live site is unchanged. " + " | ".join(res["findings"][:4])
            + ". Fix the monorepo copy (restore the files) or, if this is "
            "deliberate, redeploy with `build_site.py sync-deploy --slug "
            f"{slug} --branch main --allow-design-change`.")


def _record(slug: str, res: dict, blocked: bool) -> None:
    """Fail-open bookkeeping: block row + card, or clear them on a pass."""
    try:
        key = f"deploy-guard-block/{slug}"
        if blocked:
            _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
                {"k": key, "v": {"at": datetime.now(timezone.utc).isoformat(),
                                 "issue": _alert_issue(slug, res),
                                 "findings": res["findings"][:10]}},
                prefer="resolution=merge-duplicates,return=minimal")
        else:
            had = _sb("GET", f"/rest/v1/ops_kv?k=eq.{key}&select=k",
                      prefer="return=representation") or []
            if not had:
                return
            _sb("DELETE", f"/rest/v1/ops_kv?k=eq.{key}")
        from pipeline_watchdog import reconcile_notes, alert_key, text_santino
        scope = alert_key(f"deploy guard blocked: {slug} — x")
        fresh = reconcile_notes([_alert_issue(slug, res)] if blocked else [], scope=scope)
        text_santino(fresh)
    except Exception as e:  # noqa: BLE001 — bookkeeping never decides a deploy
        print(f"      (deploy-guard bookkeeping skipped: {str(e)[:120]})")


def _log_override(slug: str, res: dict) -> None:
    entry = {"at": datetime.now(timezone.utc).isoformat(), "slug": slug,
             "head": _git(["rev-parse", "--short", "HEAD"]).strip(),
             "by": os.environ.get("GITHUB_ACTOR") or os.environ.get("USER") or "?",
             "ci_run": os.environ.get("GITHUB_RUN_ID"),
             "findings": res["findings"][:10]}
    print("      OVERRIDE LOGGED (--allow-design-change): "
          + json.dumps(entry)[:600])
    try:
        cur = ((_sb("GET", "/rest/v1/ops_kv?k=eq.deploy-guard-log&select=v",
                    prefer="return=representation") or [{}])[0].get("v") or {})
        items = (cur.get("overrides") or [])[-199:] + [entry]
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": "deploy-guard-log", "v": {"overrides": items}},
            prefer="resolution=merge-duplicates,return=minimal")
    except Exception as e:  # noqa: BLE001
        print(f"      (override log write failed: {str(e)[:120]})")


def enforce(slug: str, repo: str, allow_design_change: bool = False) -> None:
    """Called by build_site.py sync-deploy (branch main). Exits non-zero on a
    block. Internal errors fail OPEN (a GitHub hiccup must not stall lanes)."""
    mode = (os.environ.get("DEPLOY_GUARD_MODE") or "enforce").lower()
    if mode == "off":
        print("      deploy guard: OFF (DEPLOY_GUARD_MODE=off)")
        return
    try:
        res = evaluate(slug, repo)
    except Exception as e:  # noqa: BLE001
        print(f"      deploy guard: could not evaluate ({str(e)[:160]}); proceeding")
        return
    for w in res["warnings"]:
        print(f"      deploy guard warning: {w}")
    if res["verdict"] == "pass":
        print(f"      deploy guard: PASS ({res['changed']} changed path(s) vs live)")
        _record(slug, res, blocked=False)
        return
    print(f"      deploy guard: {len(res['findings'])} protected change(s) vs live:")
    for f in res["findings"]:
        print(f"        - {f}")
    if allow_design_change:
        _log_override(slug, res)
        _record(slug, res, blocked=False)
        return
    if mode == "warn":
        print("      deploy guard: WARN mode, deploying anyway")
        return
    # A (d)-only block (another lane's deploy has not reached main yet) heals
    # itself within ROLLBACK_FRESH_HOURS; no card/SMS for a transient race.
    if not all(f.startswith("(d)") for f in res["findings"]):
        _record(slug, res, blocked=True)
    print(f"ERROR: REFUSING to deploy {slug} to production: this push would "
          "degrade the live site (see findings above). Restore the files in the "
          "monorepo, or re-run with --allow-design-change for deliberate human "
          "work (logged). Commits tagged [design-change] also pass.",
          file=sys.stderr)
    sys.exit(3)


def _all_slugs() -> list[str]:
    out = []
    for d in sorted((ROOT / "sites").iterdir()):
        if d.is_dir() and not d.name.startswith("_") and d.name not in DEAD_SLUGS:
            out.append(d.name)
    return out


def main() -> int:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    if not os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN"):
        load_dotenv(Path.home() / "Desktop/mywebsitecode/rank-ai/.env")
    ap = argparse.ArgumentParser(description="Dry-run the production deploy guard.")
    ap.add_argument("--slug")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--head", default="HEAD",
                    help="replay: evaluate this commit as the tree about to ship")
    ap.add_argument("--live-rev",
                    help="replay: a local commit standing in for the live site")
    a = ap.parse_args()
    slugs = _all_slugs() if a.all else [a.slug] if a.slug else []
    if not slugs:
        ap.error("--slug or --all")
    blocked = 0
    for s in slugs:
        try:
            res = evaluate(s, head=a.head, live_rev=a.live_rev)
        except Exception as e:  # noqa: BLE001
            print(f"{s:48} ERROR {str(e)[:120]}")
            continue
        if a.json:
            print(json.dumps(res))
            continue
        blocked += res["verdict"] == "block"
        print(f"{s:48} {res['verdict'].upper():5} changed={res['changed']} "
              f"base={res['base']} remote_only={len(res['remote_only'])}")
        for f in res["findings"]:
            print(f"    BLOCK {f}")
        for w in res["warnings"]:
            print(f"    warn  {w}")
    print(f"\n{blocked} of {len(slugs)} site(s) would be blocked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
