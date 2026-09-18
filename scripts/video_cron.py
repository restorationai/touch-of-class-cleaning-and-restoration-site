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


class LedgerUnavailable(RuntimeError):
    """marketing_videos could not be read, so we cannot prove a post is unused."""


def _ledger_rows(slug: str) -> list:
    """Every marketing_videos row for this client. Raises LedgerUnavailable."""
    if not os.environ.get("SUPABASE_URL"):
        return []             # local/dev with no DB: fall back to frontmatter
    try:
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"],
                           os.environ["SUPABASE_SERVICE_ROLE_KEY"])
        cid = _company_id_for(slug)
        if not cid:
            return []
        r = (sb.table("marketing_videos").select("post_slug,service,city,kind")
             .eq("company_id", cid).execute())
        return r.data or []
    except Exception as e:  # noqa: BLE001
        raise LedgerUnavailable(str(e)[:160]) from e


def videoed_geo_pairs(slug: str) -> set:
    """(service, city) pairs this client already has a geo video for.

    The geo lane duplicated for a DIFFERENT reason than the blog lane: its
    cursor lives in clients/{slug}/video-state.json, and only 6 of 14 clients
    have that file — the rest reset to cursor 0 every run and remake the first
    pair forever. PuroClean and MCC each hold 6 videos covering 2 topics.
    Same cure: ask the ledger, which records service+city per row.
    """
    return {(str(r.get("service") or "").strip().lower(),
             str(r.get("city") or "").strip().lower())
            for r in _ledger_rows(slug)
            if r.get("service") and r.get("city")}


def videoed_post_slugs(slug: str) -> set:
    """post_slugs this client ALREADY has a video for, straight from the ledger.

    Why the ledger and not the blog frontmatter (2026-08-06): frontmatter was
    the only dedupe key, and it is stamped AFTER the expensive work and AFTER
    the upload — so any failure in between leaves the post looking untouched
    and the next cron run rebuilds the whole video. Crew Restoration shipped
    the SAME video four times (07-27, 07-31, 08-03, 08-05); its post has one
    commit ever and never carried a youtube_id. The last successful
    'video automation' commit was 07-29, yet three uploads happened after it.
    Fleet-wide that is 25 duplicate productions across 11 of 14 clients, each
    one a paid Claude script + ElevenLabs narration + Gemini image set, and
    every one of them publicly visible on the client's channel.

    marketing_videos.post_slug is written by record_video BEFORE that failure
    point and cannot be lost to a git problem, so it is the honest source.
    """
    # Deliberately NOT fail-open, unlike has_publishable_channel above. That
    # check asks "can we publish at all"; this one asks "have we already made
    # this exact video". Guessing wrong there costs one skipped run on a
    # Mon/Wed/Fri cadence — nothing. Guessing wrong here costs a paid duplicate
    # and a client's channel showing the same video twice.
    return {r["post_slug"] for r in _ledger_rows(slug) if r.get("post_slug")}


def next_video_post(slug: str) -> str | None:
    """The next published blog post that has no video yet — per the ledger."""
    blog_dir = ROOT / "sites" / slug / "src" / "content" / "blog"
    if not blog_dir.exists():
        return None
    # Authoritative "already has a video" set. Raises LedgerUnavailable rather
    # than guessing — the caller skips this client for the run.
    already = videoed_post_slugs(slug)
    candidates = []
    for md in blog_dir.glob("*.md"):
        fm = _frontmatter(md.read_text())
        if str(fm.get("rendered", "")).lower() != "true":
            continue
        if not fm.get("published_at"):
            continue
        if fm.get("youtube_id"):          # stamped in frontmatter
            continue
        if md.stem in already:            # ...or recorded in the ledger
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
    # Prioritise BEFORE the top-N slice (2026-08-06): the client's stated goals
    # decide which services get videos at all, so cutting first would discard a
    # focus service before it was ever considered.
    from content_focus import prioritise
    services = prioritise(slug, plan.get("services") or [])[:TOP_SERVICES]
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
    # Skip pairs already on the ledger. The cursor alone cannot be trusted:
    # it lives in clients/{slug}/video-state.json and only 6 of 14 clients
    # have that file, so the rest restart at 0 every run.
    done = videoed_geo_pairs(slug)
    start = st["geo_cursor"] % len(matrix)
    for step in range(len(matrix)):
        service, city = matrix[(start + step) % len(matrix)]
        if (service.strip().lower(), city.strip().lower()) in done:
            continue
        return {"kind": "geo", "service": service, "city": city,
                "cursor": (start + step) % len(matrix), "of": len(matrix)}
    print(f"  {slug}: every geo pair already has a video ({len(matrix)} pairs) — nothing to make")
    return None


# ---------------------------------------------------------------------------
# Production
# ---------------------------------------------------------------------------


def _run_maker(argv: list[str]) -> dict:
    """Run video_maker in its own PROCESS GROUP with a hard wall clock.

    D2 (2026-09-17): plain subprocess.run(timeout=...) kills only the child
    — video_maker's ffmpeg GRANDCHILDREN survive holding the stdout pipe,
    and the capture read blocks forever. That is exactly how 7 of 8 fleet
    runs hung to the 120-minute cancel since Aug 31 (orphan ffmpeg pids in
    every teardown log). start_new_session puts the whole tree in one
    group; on timeout the GROUP dies and the run moves to the next client.
    Any exception here is THIS client's failure, never the run's."""
    import os as _os
    import signal as _signal
    try:
        proc = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "video_maker.py"), *argv],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True,
        )
        try:
            out, err = proc.communicate(timeout=1800)
        except subprocess.TimeoutExpired:
            try:
                _os.killpg(_os.getpgid(proc.pid), _signal.SIGKILL)
            except Exception:  # noqa: BLE001
                proc.kill()
            out, err = proc.communicate()
            return {"ok": False, "youtube_id": None,
                    "err": "timeout 30min — process group killed"}
        ok = proc.returncode == 0
        m = re.search(r"youtu\.be/([\w-]+)", out or "")
        return {"ok": ok, "youtube_id": m.group(1) if m else None,
                "err": ((err or "")[-300:] if not ok else None)}
    except Exception as e:  # noqa: BLE001 — one client never sinks the cron
        return {"ok": False, "youtube_id": None, "err": str(e)[:300]}


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
    ap.add_argument("--budget-min", type=int, default=0,
                    help="wall-clock budget: stop cleanly (exit 0) before "
                         "starting a video that would not fit. Turns the "
                         "'cancelled at timeout mid-render' state into a "
                         "SUCCESS with a resume-next-run line (2026-09-18: "
                         "two healthy backfill runs published 16 and 18 "
                         "videos and both concluded 'cancelled').")
    args = ap.parse_args()
    import time as _time
    _t0 = _time.monotonic()

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
        if args.budget_min and (_time.monotonic() - _t0) > args.budget_min * 60 - 600:
            print(f"\n==> budget reached ({args.budget_min} min): "
                  f"{len(made)} published this run, resuming next run")
            break
        st = load_state(slug)
        try:
            plan = plan_next(slug, st)
        except LedgerUnavailable as e:
            # Cannot prove this client has no video for the candidate, so do
            # not spend money finding out. One missed Mon/Wed/Fri slot is
            # cheap; a duplicate on their public channel is not.
            skipped.append((slug, f"video ledger unreadable ({e}) — skipped rather "
                                  f"than risk a duplicate"))
            continue
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
