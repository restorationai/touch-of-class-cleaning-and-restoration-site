#!/usr/bin/env python3
"""
Rank AI — Paced video automation cron (System 5 cadence).

For every active client that has CONNECTED their YouTube channel in the app
(user_integrations, provider='youtube', status='connected'), each run produces
AT MOST ONE video, cycling blog -> geo -> geo. With the workflow scheduled
Mon/Wed/Fri that is 1 blog video + 2 geo videos per client per week:

  blog  — the next published blog post that has no youtube_id yet
          (falls back to a geo video when every post already has one)
  geo   — the next city x service combo from the geo matrix
          (plan-input service_areas x top services, cursor-tracked)

Cadence state lives in clients/{slug}/video-state.json:
  {
    "last_kind": "geo",         // what the previous run produced
    "cycle_pos": 2,             // 0=blog, 1=geo, 2=geo — advances each run
    "geo_cursor": 5,            // index into the geo matrix (wraps)
    "history": [ {ts, kind, ...} ]   // last 30 runs, newest last
  }

Upload privacy comes from the client record's `video_publish_mode` field
(default "unlisted") — video_maker reads it, so nothing goes public here until
a client is explicitly flipped (e.g. flood-fixers stays unlisted until their
channel is renamed off the owner's personal name).

video_maker does the heavy lifting (script -> TTS -> AI images -> ffmpeg ->
upload to THEIR channel -> ledger row in marketing_videos). Runs headless in
GitHub Actions. Clients who haven't connected YouTube are skipped — so this
no-ops until a client connects, then starts producing automatically.

Usage:
  python3 scripts/video_cron.py                       # all connected clients, <=1 video each
  python3 scripts/video_cron.py --slug narestco       # one client
  python3 scripts/video_cron.py --dry-run             # show what it WOULD make, render nothing
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
CLIENTS_DIR = ROOT / "clients"

TOP_SERVICES = 3          # geo matrix: first N plan-input services x all service areas
CYCLE = ("blog", "geo", "geo")   # Mon/Wed/Fri -> 1 blog + 2 geo per week
HISTORY_KEEP = 30


def _load_json(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _cmap_id(slug: str) -> str | None:
    """slug -> company_id via clients/company_map.json (flood-fixers has
    company_id null in its record but IS in the map)."""
    try:
        cmap = _load_json(CLIENTS_DIR / "company_map.json") or {}
        return cmap.get(slug)
    except Exception:
        return None


def active_clients() -> list[str]:
    """Slugs of every current client eligible for videos.

    YouTube is its own search engine — geo videos only need the city x
    service matrix (plan-input), NOT a live website, so pre-launch and
    siteless (franchise) clients are included from day one (2026-07-23,
    Santino). Blog-kind videos still require published posts and fall back
    to geo naturally. Only truly departed clients are excluded."""
    DEPARTED = {"archived", "churned", "paused", "cancelled", "canceled",
                "inactive"}
    # The app's pause button writes companies.status in Supabase and NEVER
    # touches the local clients/*.json status (Mold Solutionz 2026-08-04:
    # local status 'onboarding', DB 'paused', YouTube connected — the cron
    # would have kept making videos for a cancelled client). Check BOTH.
    # Fail-open on the DB read: never skip paying clients on an API hiccup.
    db_departed: set[str] = set()
    try:
        if os.environ.get("SUPABASE_URL"):
            from supabase import create_client
            sb = create_client(os.environ["SUPABASE_URL"],
                               os.environ["SUPABASE_SERVICE_ROLE_KEY"])
            rows = sb.table("companies").select("id,status").execute().data or []
            db_departed = {r["id"] for r in rows
                           if str(r.get("status") or "").strip().lower()
                           in DEPARTED}
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"  companies status lookup failed: {str(e)[:120]}\n")
    out = []
    for f in sorted(CLIENTS_DIR.glob("*.json")):
        rec = _load_json(f)
        if not rec or str(rec.get("status") or "").lower() in DEPARTED:
            continue
        if rec.get("company_id") in db_departed or \
                _cmap_id(f.stem) in db_departed:
            continue
        try:
            plan = _load_json(CLIENTS_DIR / f.stem / "plan-input.json") or {}
        except Exception:
            plan = {}
        live = rec.get("cut_over_at") or rec.get("apex_cutover", {}).get("completed_at")
        if live or plan.get("service_areas"):
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


def has_publishable_channel(slug: str) -> bool:
    """Can we actually publish for this client, or is the connection channelless?

    A connected Google account with NO YouTube channel passes every check the
    cron used to make, then fails at videos().insert — AFTER a full production
    run has already been paid for (Claude script + TTS narration + Gemini scene
    images). ProRestoration 2026-08-04 sat in exactly that state. Skip cleanly
    instead: the ledger raises the card and Monica does the asking.

    Fails OPEN — an unverifiable read (no OAuth env, API hiccup) must never
    silently stop a paying client's videos.
    """
    try:
        import video_maker as vm
        return vm.youtube_channel_state(slug)["has_channel"] is not False
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"  channel check failed for {slug}: {str(e)[:120]}\n")
        return True


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
        # Highest-value first: frontmatter priority (bigger = more valuable
        # keyword), then newest — a fresh high-intent post gets its video while
        # it's climbing, instead of waiting behind the whole archive
        # (2026-07-23; was oldest-first).
        try:
            prio = int(float(fm.get("priority", 5)))
        except ValueError:
            prio = 5
        candidates.append((prio, fm.get("published_at", ""), md.stem))
    if not candidates:
        return None
    # priority desc, then published_at desc (newest first)
    candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return candidates[0][2]


# ---------------------------------------------------------------------------
# Cadence state (clients/{slug}/video-state.json)
# ---------------------------------------------------------------------------


def state_path(slug: str) -> Path:
    return CLIENTS_DIR / slug / "video-state.json"


def load_state(slug: str) -> dict:
    st = _load_json(state_path(slug)) or {}
    st.setdefault("last_kind", None)
    st.setdefault("cycle_pos", 0)
    st.setdefault("geo_cursor", 0)
    st.setdefault("history", [])
    return st


def save_state(slug: str, st: dict) -> None:
    st["history"] = st.get("history", [])[-HISTORY_KEEP:]
    state_path(slug).write_text(json.dumps(st, indent=2) + "\n")


def geo_matrix(slug: str) -> list[tuple[str, str]]:
    """(service, city) combos: top plan-input services x every service-area city.
    Primary service blankets the whole service area first, then the next service."""
    plan = _load_json(CLIENTS_DIR / slug / "plan-input.json") or {}
    services = (plan.get("services") or [])[:TOP_SERVICES]
    cities = [a["city"] for a in plan.get("service_areas", []) if a.get("city")]
    return [(svc, city) for svc in services for city in cities]


def plan_next(slug: str, st: dict) -> dict | None:
    """Decide what this run should produce for a client (no side effects)."""
    kind = CYCLE[st["cycle_pos"] % len(CYCLE)]
    if kind == "blog":
        post = next_video_post(slug)
        if post:
            return {"kind": "blog", "post": post}
        kind = "geo"  # every published post already has a video -> extra geo
    matrix = geo_matrix(slug)
    if not matrix:
        return None
    service, city = matrix[st["geo_cursor"] % len(matrix)]
    return {"kind": "geo", "service": service, "city": city,
            "cursor": st["geo_cursor"] % len(matrix), "of": len(matrix)}


# ---------------------------------------------------------------------------
# Production
# ---------------------------------------------------------------------------


def _run_maker(argv: list[str]) -> dict:
    """Run video_maker in its own process — a failure on one client doesn't
    kill the whole cron run."""
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "video_maker.py"), *argv],
        cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
    )
    ok = r.returncode == 0
    m = re.search(r"youtu\.be/([\w-]+)", r.stdout)
    return {"ok": ok, "youtube_id": m.group(1) if m else None,
            "err": (r.stderr[-300:] if not ok else None)}


def make_planned(slug: str, plan: dict, dry_run: bool) -> dict:
    if dry_run:
        return {"slug": slug, **plan, "ok": True, "dry": True}
    if plan["kind"] == "blog":
        res = _run_maker(["make", "--slug", slug, "--post", plan["post"]])
    else:
        res = _run_maker(["geo", "--slug", slug,
                          "--service", plan["service"], "--city", plan["city"]])
    return {"slug": slug, **plan, **res}


def main() -> int:
    ap = argparse.ArgumentParser(description="Rank AI paced video automation cron")
    ap.add_argument("--slug", help="One client (default: all connected, active clients)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what it would make; render nothing, save no state")
    args = ap.parse_args()

    slugs = [args.slug] if args.slug else active_clients()
    connected = connected_company_ids()
    print(f"==> Video cron: {len(slugs)} client(s) | {len(connected)} with YouTube connected"
          f" | cadence blog->geo->geo | mode: {'DRY-RUN' if args.dry_run else 'LIVE'}\n")

    made, skipped = [], []
    for slug in slugs:
        cid = _company_id_for(slug)
        if cid not in connected:
            skipped.append((slug, "no connected YouTube"))
            continue
        if not has_publishable_channel(slug):
            skipped.append((slug, "YouTube connected but the account has NO channel "
                                  "— nothing could be published (ledger card raised)"))
            continue
        st = load_state(slug)
        plan = plan_next(slug, st)
        if not plan:
            skipped.append((slug, "nothing to produce (no posts, empty geo matrix)"))
            continue

        label = (f"blog: {plan['post']}" if plan["kind"] == "blog" else
                 f"geo: {plan['service']} x {plan['city']} "
                 f"[{plan['cursor'] + 1}/{plan['of']}]")
        print(f"  [{slug}] {'would make' if args.dry_run else 'making'} {label}"
              f" (cycle_pos={st['cycle_pos']}, last_kind={st['last_kind']})")

        res = make_planned(slug, plan, args.dry_run)
        made.append(res)
        if not res["ok"]:
            sys.stderr.write(f"    FAILED: {res.get('err')}\n")
            continue  # state NOT advanced — the same slot retries next run
        if not args.dry_run:
            if res.get("youtube_id"):
                print(f"    -> youtu.be/{res['youtube_id']}")
            # Advance cadence state only on success
            st["last_kind"] = plan["kind"]
            st["cycle_pos"] = (st["cycle_pos"] + 1) % len(CYCLE)
            if plan["kind"] == "geo":
                st["geo_cursor"] = st["geo_cursor"] + 1
            st["history"].append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "kind": plan["kind"],
                "post": plan.get("post"),
                "service": plan.get("service"),
                "city": plan.get("city"),
                "youtube_id": res.get("youtube_id"),
            })
            save_state(slug, st)

    print(f"\nDone. {sum(1 for m in made if m['ok'])} video(s) "
          f"{'planned' if args.dry_run else 'made'}; {len(skipped)} client(s) skipped.")
    for slug, why in skipped:
        print(f"  skip {slug}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
