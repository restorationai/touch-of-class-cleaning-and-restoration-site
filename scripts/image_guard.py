#!/usr/bin/env python3
"""image_guard.py - an approved (live) site image is never silently replaced.

WHY (Santino 2026-09-29, ProRestoration): "I'm so confused why all these
images have been getting changed." Three things had happened, none of them
asked for image by image:
  1. a "deterministic pixel recolor" (PIL hue-shift of red -> navy, taught to
     every agent as dev_agent.md rule 2e on 09-03) turned the technicians' red
     shirts navy AND every skin pixel that shares red's hue: blue ears, blue
     forearms, blue knuckles, blue flecks on wood. 11 ProRestoration service
     images shipped like that for 26 days.
  2. a reverted overhaul left orphan -1200w.webp variants behind, so desktop
     visitors kept seeing the REJECTED photos for two services while mobile saw
     the restored ones (resize_images only regenerates a variant older than its
     base, and git checkouts make every mtime "now").
  3. the ops-sync parity step added service pages with no image, so they all
     fell back to the one shared /images/services.webp card.

THE RULE this file enforces at the deploy choke point (build_site.py
sync-deploy calls enforce() before the subtree push):
  - Any base image under public/images/ that is LIVE (present in the per-client
    deploy repo's branch) may only be replaced when clients/{slug}/image-changes.jsonl
    carries an approval for that exact path + exact new content (git blob sha),
    naming the explicit client request for THAT image.
  - An unapproved replacement is not deployed: enforce() restores the live
    version into the monorepo, archives the rejected candidate under
    clients/{slug}/image-archive/rejected/, commits, and deploys the rest. The
    deploy itself is never blocked, the change is loud, and nothing is lost.
  - Responsive variants (-480w/-768w/-1200w) are derived, never approved: any
    variant whose content no longer matches its base is regenerated from it.
  - New images (paths not yet live) pass freely: new pages must get images.

The approval path (the ONLY way to replace a live image):
  python3 scripts/image_guard.py approve --slug SLUG --path services/foo.webp \
      --request "<the client's words asking to change THIS image>" \
      --requested-by "<who + when, e.g. Shana (client), 09-02 call>"
It archives the live version to clients/{slug}/image-archive/{date}/ (so the
old image stays recoverable outside git history too), records old+new blob
shas, and must be committed together with the new image.

Other commands:
  check   --slug S [--branch main]   report what enforce() would do (no writes)
  restore --slug S --path P [--rev REV]   put the live (or REV) version back
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITES = ROOT / "sites"
CLIENTS = ROOT / "clients"
VARIANT = re.compile(r"-(\d+)w\.webp$")
IMG_EXT = (".webp", ".png", ".jpg", ".jpeg", ".svg", ".gif", ".avif")


def _git(args: list[str], *, check: bool = True, text: bool = True):
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=text)
    if check and r.returncode != 0:
        raise RuntimeError((r.stderr if text else r.stderr.decode(errors="replace")).strip()[:300])
    return r.stdout


def _is_base_image(rel: str) -> bool:
    return rel.lower().endswith(IMG_EXT) and not VARIANT.search(rel)


def _tree(ref: str, prefix: str) -> dict[str, str]:
    """{path relative to public/images: blob sha} for base images at ref."""
    out = _git(["ls-tree", "-r", ref, "--", prefix], check=False)
    res = {}
    for line in out.splitlines():
        try:
            meta, path = line.split("\t", 1)
        except ValueError:
            continue
        sha = meta.split()[2]
        rel = path.split("public/images/", 1)[-1]
        res[rel] = sha
    return res


def ledger_path(slug: str) -> Path:
    return CLIENTS / slug / "image-changes.jsonl"


def approvals(slug: str) -> set[tuple[str, str]]:
    """Only the LATEST approve/restore per path counts, so an image cannot be
    silently swapped back to some older once-approved version."""
    p = ledger_path(slug)
    latest: dict[str, str] = {}
    if p.exists():
        for line in p.read_text().splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("action") in ("approve", "restore") and e.get("path") and e.get("new_blob"):
                latest[e["path"]] = e["new_blob"]
    return set(latest.items())


def _append_ledger(slug: str, entry: dict) -> None:
    p = ledger_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def _blob_of_file(path: Path) -> str:
    return _git(["hash-object", str(path)]).strip()


def live_ref(slug: str, branch: str = "main") -> str | None:
    """Fetch the per-client deploy repo's branch (what visitors see) and return
    a ref to it; None when unreachable or never deployed."""
    remote = f"deploy-{slug}"
    if not _git(["remote", "get-url", remote], check=False).strip():
        try:
            sys.path.insert(0, str(ROOT / "scripts"))
            import build_site as bs  # lazy: heavy module
            repo = f"{slug}-site"
            rec = CLIENTS / f"{slug}.json"
            if rec.exists():
                gh = (json.loads(rec.read_text()).get("build") or {}).get("github_repo") or ""
                if "/" in gh:
                    repo = gh.split("/", 1)[1]
            url = f"https://x-access-token:{bs.gh_token()}@github.com/{bs.GH_OWNER}/{repo}.git"
            _git(["remote", "add", remote, url])
        except Exception as e:  # noqa: BLE001
            print(f"  image-guard: no deploy remote for {slug} ({str(e)[:100]})")
            return None
    r = subprocess.run(["git", "-C", str(ROOT), "fetch", "-q", "--no-tags", remote,
                        f"+refs/heads/{branch}:refs/image-guard/{slug}/{branch}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  image-guard: could not fetch live {slug}/{branch} "
              f"({r.stderr.strip()[:120]}) - first deploy or offline, skipping")
        return None
    return f"refs/image-guard/{slug}/{branch}"


def plan(slug: str, live: str) -> tuple[list[tuple[str, str, str]], list[str]]:
    """(unapproved replacements [(rel, live_blob, local_blob)], live paths now deleted)."""
    live_imgs = {k: v for k, v in _tree(live, "public/images").items() if _is_base_image(k)}
    local = {k: v for k, v in _tree("HEAD", f"sites/{slug}/public/images").items()
             if _is_base_image(k)}
    ok = approvals(slug)
    bad, gone = [], []
    for rel, lblob in live_imgs.items():
        cur = local.get(rel)
        if cur is None:
            gone.append(rel)
        elif cur != lblob and (rel, cur) not in ok:
            bad.append((rel, lblob, cur))
    return bad, gone


def stale_variants(slug: str) -> list[Path]:
    """Variants whose picture no longer matches their base (the orphan-1200w bug)."""
    from PIL import Image, ImageChops, ImageStat
    img_dir = SITES / slug / "public" / "images"
    out = []
    for v in img_dir.rglob("*w.webp"):
        m = VARIANT.search(v.name)
        if not m:
            continue
        base = v.with_name(VARIANT.sub(".webp", v.name))
        if not base.exists():
            continue
        try:
            a = Image.open(base).convert("L").resize((64, 36))
            b = Image.open(v).convert("L").resize((64, 36))
        except Exception:  # noqa: BLE001
            continue
        if ImageStat.Stat(ImageChops.difference(a, b)).mean[0] > 12:
            out.append(v)
    return out


def heal_variants(slug: str) -> list[str]:
    sys.path.insert(0, str(ROOT / "scripts"))
    from resize_images import open_rgb, variant_bytes
    healed = []
    for v in stale_variants(slug):
        base = v.with_name(VARIANT.sub(".webp", v.name))
        w = int(VARIANT.search(v.name).group(1))
        im = open_rgb(base)
        if w < im.width:
            v.write_bytes(variant_bytes(im, w))
        else:
            v.unlink()  # never referenced (srcset only lists widths < base width)
        healed.append(str(v.relative_to(ROOT)))
    return healed


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def enforce(slug: str, branch: str = "main", *, commit: bool = True) -> dict:
    """Called by sync-deploy before the subtree split. Reverts unapproved
    replacements of live images (archiving the candidate), heals stale
    variants, commits both. Never raises: a guard failure must not block a
    deploy, it only loses the protection for this run (printed loudly)."""
    report = {"reverted": [], "variants": [], "deleted_live": []}
    try:
        live = live_ref(slug, branch)
        touched: list[str] = []
        if live:
            bad, gone = plan(slug, live)
            report["deleted_live"] = gone
            stamp = _dt.date.today().isoformat()
            for rel, lblob, cur in bad:
                dst = SITES / slug / "public" / "images" / rel
                arch = CLIENTS / slug / "image-archive" / "rejected" / stamp / rel
                arch.parent.mkdir(parents=True, exist_ok=True)
                arch.write_bytes(_git(["cat-file", "blob", cur], text=False))
                dst.write_bytes(_git(["cat-file", "blob", lblob], text=False))
                _append_ledger(slug, {"ts": _now(), "action": "guard-revert", "path": rel,
                                      "live_blob": lblob, "rejected_blob": cur,
                                      "rejected_archived_to": str(arch.relative_to(ROOT)),
                                      "branch": branch})
                touched += [str(dst.relative_to(ROOT)), str(arch.relative_to(ROOT))]
                report["reverted"].append(rel)
                print(f"  IMAGE GUARD: {rel} was replaced without an approval -> live "
                      f"version restored; candidate kept at {arch.relative_to(ROOT)}. "
                      "To ship it, the client must have asked for THIS image: "
                      f"python3 scripts/image_guard.py approve --slug {slug} --path {rel} "
                      "--request '...' --requested-by '...'")
            if gone:
                print(f"  image-guard: note - {len(gone)} live image path(s) no longer in "
                      f"the site: {', '.join(gone[:6])}")
        healed = heal_variants(slug)
        report["variants"] = healed
        touched += healed
        for h in healed:
            print(f"  image-guard: stale variant regenerated from its base: {h}")
        if touched and commit:
            paths = touched + ([str(ledger_path(slug).relative_to(ROOT))]
                               if report["reverted"] else [])
            # -A so a deleted (never-referenced) variant is staged as a removal;
            # only the exact paths this run touched, never other in-flight work.
            _git(["add", "-A", "--", *paths])
            msg = (f"image guard: {slug} - "
                   f"{len(report['reverted'])} unapproved image replacement(s) reverted, "
                   f"{len(healed)} stale variant(s) regenerated [automated]")
            _git(["commit", "-m", msg, "--", *paths], check=False)
    except Exception as e:  # noqa: BLE001
        print(f"  IMAGE GUARD ERROR for {slug} (protection skipped this run): {str(e)[:200]}")
    return report


def approve(slug: str, rel: str, request: str, requested_by: str,
            old_rev: str | None, branch: str) -> int:
    request, requested_by = (request or "").strip(), (requested_by or "").strip()
    if len(request) < 12 or not requested_by:
        print("REFUSED: --request must quote the explicit client request for THIS "
              "image and --requested-by must name who asked and when.")
        return 2
    dst = SITES / slug / "public" / "images" / rel
    if not dst.exists():
        print(f"REFUSED: {dst.relative_to(ROOT)} does not exist")
        return 2
    ref = old_rev or live_ref(slug, branch)
    old_blob = None
    if ref:
        path = (f"public/images/{rel}" if ref.startswith("refs/image-guard/")
                else f"sites/{slug}/public/images/{rel}")
        old_blob = _git(["rev-parse", f"{ref}:{path}"], check=False).strip() or None
    new_blob = _blob_of_file(dst)
    archived = None
    if old_blob and old_blob != new_blob:
        arch = (CLIENTS / slug / "image-archive" / _dt.date.today().isoformat() / rel)
        arch.parent.mkdir(parents=True, exist_ok=True)
        arch.write_bytes(_git(["cat-file", "blob", old_blob], text=False))
        archived = str(arch.relative_to(ROOT))
    _append_ledger(slug, {"ts": _now(), "action": "approve", "path": rel,
                          "old_blob": old_blob, "new_blob": new_blob,
                          "archived_to": archived, "request": request,
                          "requested_by": requested_by})
    print(f"approved {slug}:{rel} ({(old_blob or 'new')[:10]} -> {new_blob[:10]}); "
          f"old kept at {archived or '(no live version)'}. Commit the image, "
          f"{ledger_path(slug).relative_to(ROOT)} and the archive together.")
    return 0


def restore(slug: str, rel: str, rev: str | None, branch: str) -> int:
    ref = rev or live_ref(slug, branch)
    if not ref:
        print("no live ref reachable - pass --rev")
        return 2
    path = (f"public/images/{rel}" if ref.startswith("refs/image-guard/")
            else f"sites/{slug}/public/images/{rel}")
    blob = _git(["rev-parse", f"{ref}:{path}"], check=False).strip()
    if not blob:
        print(f"{rel} not found at {ref}")
        return 2
    dst = SITES / slug / "public" / "images" / rel
    dst.write_bytes(_git(["cat-file", "blob", blob], text=False))
    _append_ledger(slug, {"ts": _now(), "action": "restore", "path": rel,
                          "new_blob": blob, "from": ref})
    print(f"restored {rel} from {ref}; stale variants: {heal_variants(slug)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "enforce", "approve", "restore"):
        p = sub.add_parser(name)
        p.add_argument("--slug", required=True)
        p.add_argument("--branch", default="main")
        if name in ("approve", "restore"):
            p.add_argument("--path", required=True, help="relative to public/images/")
        if name == "approve":
            p.add_argument("--request", required=True)
            p.add_argument("--requested-by", required=True)
            p.add_argument("--old-rev", help="where the previous version lives "
                           "(default: the live deploy branch)")
        if name == "restore":
            p.add_argument("--rev")
    a = ap.parse_args()
    if a.cmd == "check":
        live = live_ref(a.slug, a.branch)
        if live:
            bad, gone = plan(a.slug, live)
            for rel, _l, _c in bad:
                print(f"UNAPPROVED replacement: {rel}")
            for rel in gone:
                print(f"live path removed: {rel}")
        for v in stale_variants(a.slug):
            print(f"stale variant: {v.relative_to(ROOT)}")
        return 0
    if a.cmd == "enforce":
        print(json.dumps(enforce(a.slug, a.branch), indent=2))
        return 0
    if a.cmd == "approve":
        return approve(a.slug, a.path, a.request, a.requested_by, a.old_rev, a.branch)
    return restore(a.slug, a.path, a.rev, a.branch)


if __name__ == "__main__":
    sys.exit(main())
