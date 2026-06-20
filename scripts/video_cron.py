#!/usr/bin/env python3
"""
Rank AI — Paced video automation cron.

For every active client that has CONNECTED their YouTube channel in the app
(user_integrations, provider='youtube', status='connected'), finds the next
published blog post that doesn't have a video yet and generates + uploads one —
paced to a small number per client per run so the channel + site grow naturally
(no mass dump). video_maker does the heavy lifting (script → TTS → AI images →
ffmpeg → upload to THEIR channel → patch youtube_id → embed on the post).

Runs headless in GitHub Actions (ffmpeg + the media APIs live there). Clients who
haven't connected YouTube are skipped — so this no-ops until a client connects,
then starts producing automatically.

Usage:
  python3 scripts/video_cron.py                       # all connected clients, 1 video each
  python3 scripts/video_cron.py --max-per-client 1    # pacing (default 1)
  python3 scripts/video_cron.py --slug narestco       # one client
  python3 scripts/video_cron.py --dry-run             # show what it WOULD make, render nothing
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
CLIENTS_DIR = ROOT / "clients"


def _load_json(p: Path):
    import json
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def active_clients() -> list[str]:
    """Slugs of clients that are active AND cut over to apex (live site)."""
    out = []
    for f in sorted(CLIENTS_DIR.glob("*.json")):
        rec = _load_json(f)
        if not rec or rec.get("status") != "active":
            continue
        if rec.get("cut_over_at") or rec.get("apex_cutover", {}).get("completed_at"):
            out.append(f.stem)
    return out


def _company_id_for(slug: str) -> str | None:
    import video_maker as vm
    return vm._company_id_for(slug)


def connected_company_ids() -> set[str]:
    """company_ids (CO-...) that have a connected YouTube integration."""
    if not os.environ.get("SUPABASE_URL"):
        return set()
    try:
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
        r = (sb.table("user_integrations").select("client_id,status")
             .eq("provider", "youtube").execute())
        return {row["client_id"] for row in r.data
                if row.get("status") in (None, "connected", "active") and row.get("client_id")}
    except Exception as e:
        sys.stderr.write(f"  user_integrations lookup failed: {str(e)[:140]}\n")
        return set()


def _frontmatter(md_text: str) -> dict:
    """Tiny frontmatter reader — enough to check published/rendered/youtube_id."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", md_text, re.S)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^(\w+):\s*(.*)$", line)
        if mm:
            fm[mm.group(1)] = mm.group(2).strip().strip('"').strip("'")
    return fm


def next_video_post(slug: str) -> str | None:
    """The next published blog post (oldest first) that has no youtube_id yet."""
    blog_dir = ROOT / "sites" / slug / "src" / "content" / "blog"
    if not blog_dir.exists():
        return None
    candidates = []
    for md in blog_dir.glob("*.md"):
        fm = _frontmatter(md.read_text())
        if str(fm.get("rendered", "")).lower() != "true":
            continue
        if not fm.get("published_at"):
            continue
        if fm.get("youtube_id"):          # already has a video
            continue
        candidates.append((fm.get("published_at", ""), md.stem))
    candidates.sort()                      # oldest published first
    return candidates[0][1] if candidates else None


def make_video(slug: str, post: str, dry_run: bool) -> dict:
    if dry_run:
        return {"slug": slug, "post": post, "ok": True, "dry": True}
    # Each video in its own process — a failure on one doesn't kill the run.
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "video_maker.py"), "make",
         "--slug", slug, "--post", post],
        cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
    )
    ok = r.returncode == 0
    yt = None
    m = re.search(r"youtu\.be/([\w-]+)", r.stdout)
    if m:
        yt = m.group(1)
    return {"slug": slug, "post": post, "ok": ok,
            "youtube_id": yt, "err": (r.stderr[-300:] if not ok else None)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Rank AI paced video automation cron")
    ap.add_argument("--slug", help="One client (default: all connected, active clients)")
    ap.add_argument("--max-per-client", type=int, default=1, help="Videos per client per run")
    ap.add_argument("--dry-run", action="store_true", help="Show what it would make; render nothing")
    args = ap.parse_args()

    slugs = [args.slug] if args.slug else active_clients()
    connected = connected_company_ids()
    print(f"==> Video cron: {len(slugs)} active client(s) | {len(connected)} with YouTube connected"
          f" | mode: {'DRY-RUN' if args.dry_run else 'LIVE'}\n")

    made, skipped = [], []
    for slug in slugs:
        cid = _company_id_for(slug)
        if cid not in connected:
            skipped.append((slug, "no connected YouTube"))
            continue
        n = 0
        while n < args.max_per_client:
            post = next_video_post(slug)
            if not post:
                if n == 0:
                    skipped.append((slug, "no posts needing a video"))
                break
            print(f"  [{slug}] {'would make' if args.dry_run else 'making'} video for: {post}")
            res = make_video(slug, post, args.dry_run)
            made.append(res)
            if not res["ok"]:
                sys.stderr.write(f"    FAILED: {res.get('err')}\n")
                break
            if not args.dry_run and res.get("youtube_id"):
                print(f"    -> youtu.be/{res['youtube_id']}")
            n += 1
            if args.dry_run:
                break  # dry-run can't actually patch youtube_id, so don't loop forever

    print(f"\nDone. {sum(1 for m in made if m['ok'])} video(s) "
          f"{'planned' if args.dry_run else 'made'}; {len(skipped)} client(s) skipped.")
    for slug, why in skipped:
        print(f"  skip {slug}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
