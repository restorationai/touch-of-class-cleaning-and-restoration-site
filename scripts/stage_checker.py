#!/usr/bin/env python3
"""Stage-dwell checker, phase 1: websites (Santino's design, 2026-08-10).

The self-driving customer-success loop: every night, know what WEBSITE stage
every active Rank AI client is in, how long they have been there, what exactly
blocks their exit, and TRIGGER the existing action for each blocker. Nothing
here invents new outreach or new builds — every unmet exit item routes to the
system that already owns it (auto-build's blocker asks, the ledger's domain
ask, ops-sync's launch seeder, the [DEV] inbox) or is reported with its owner.

STAGE DERIVATION is an exact replica of the app's Build Stages board
(app-work/components/BuildStagesBoard.tsx websiteStage()) — stages are DERIVED
from verifiable signals, never from a manual field:

    no marketing_sites row              -> building
    apex_live is true                   -> live      (wins everything)
    build_status pushed_main            -> ready
    build_status pushed_staging         -> staging
    build_status preview_ready|_live    -> preview
    anything else (pending/scaffolded/
      rendering/unknown)                -> building  (never guess rightward)

STAGE HISTORY lives in ops_kv key 'stage-history' as
{company_id: {board, stage, entered_at}} — updated on change only, seeded
entered_at=now on first sight (the first run notes this; dwell counts start
that day). ops_kv over a new table: zero schema risk, same pattern as
docs-seen and the email-sync cursor.

EXIT CHECKLIST per stage (each unmet item -> existing action or owner):
  building  services empty            -> auto-build's Monica ask covers it
            logo missing              -> soak clock (auto-build builds anyway
                                         after 7 days; its ask covers Monica)
            plan/scaffold/render gap  -> auto-build owns it (capped per run —
                                         never duplicated here)
  preview   imagery missing           -> ONE open [DEV] marketing_ops_notes
            (hero-bg.webp absent OR      task: "run the full visual pass per
             image-meta.json < 3)        the AI-first doctrine" — but ONLY
                                         once a logo exists (all imagery is
                                         generated FROM brand assets; a
                                         logoless visual pass ships wrong
                                         branding, the Go Green lesson)
            preview never sent        -> report (no client_input preview ask)
  staging   no client sign-off        -> report "awaiting readiness answer"
            domain access not granted -> report (ledger already seeds the ask)
            imagery missing           -> same [DEV] gate as preview. The
                                         board's "preview" is preview_ready
                                         only, but clients on staging are in
                                         the same client-review window
                                         (Santino's 2026-08-10 list of
                                         imagery-suspect clients was all
                                         pushed_staging), so the visual-pass
                                         gate runs in both pre-launch stages.
  ready     launch task               -> ops-sync's ensure_internal_launch_
                                         tasks owns seeding; report seeded /
                                         gated-on-what
  live      terminal — no checklist, no dwell alarm.

DWELL ALERTS: same stage > 7 days ->
    "{slug}: STUCK {days}d in {stage}: {top blocker} -> {owner}"
Returned with the rest of the lines so the nightly digest picks them up like
every other sweep pass.

Runs inside client_ops_sync.run() (same independent try/except as the setup
ledger and email_inbox_sync — a checker raise must never take the sweep down).
CLI for manual runs (prints the full per-client stage+dwell table):

    python3 scripts/stage_checker.py --dry-run     # derive + print, write nothing
    python3 scripts/stage_checker.py               # live

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (rank-ai/.env or CI secrets).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = ROOT / "clients"
SITES_DIR = ROOT / "sites"
sys.path.insert(0, str(Path(__file__).parent))

from client_ops_sync import _sb, action_key, load_env, slug_map  # noqa: E402
from client_concierge import kv_get, kv_set  # noqa: E402

HISTORY_KEY = "stage-history"
BOARD = "website"
DWELL_ALERT_DAYS = 7
LOGO_SOAK_DAYS = 7          # mirror of setup_ledger.ensure_auto_site_build
MIN_IMAGE_META_ENTRIES = 3
# Mirror of client_ops_sync.ensure_internal_launch_tasks READY_ACCESS — the
# "granted-ish" domain_access_status values that mean we can act without the
# client.
READY_ACCESS = {"granted", "creds_provided", "ns_live", "delegate_granted"}
# Idempotency marker for the imagery task — an OPEN [DEV] note containing this
# phrase means the task is already in the dev inbox; never file a second.
VISUAL_PASS_MARKER = "full visual pass"


def website_stage(site: dict | None) -> str:
    """EXACT replica of BuildStagesBoard.tsx websiteStage(). Do not 'improve':
    the board and the checker must never disagree about what stage a client
    is in."""
    if not site:
        return "building"   # company exists, pipeline hasn't started
    if site.get("apex_live") is True:
        return "live"
    bs = (site.get("build_status") or "pending").lower()
    if bs == "pushed_main":
        return "ready"
    if bs == "pushed_staging":
        return "staging"
    if bs in ("preview_ready", "preview_live"):
        return "preview"
    return "building"       # pending | scaffolded | rendering | unknown


# ---------------------------------------------------------------- signals
def _has_logo(cid: str) -> bool:
    """Brand logo present in the branding bucket. Fail-open (True) on a
    storage hiccup — the same policy as auto-build's soak check: a transient
    storage error must not spray 'no logo' blockers across the fleet."""
    try:
        from setup_ledger import _bucket_logo_files
        return bool(_bucket_logo_files(cid))
    except Exception:  # noqa: BLE001
        return True


def _imagery_gap(slug: str) -> str | None:
    """The spec'd imagery signal: public/images/hero-bg.webp absent OR
    src/data/image-meta.json < 3 entries. None means imagery looks complete."""
    site_dir = SITES_DIR / slug
    if not (site_dir / "src").exists():
        return None   # nothing rendered yet — that's a building gap, not imagery
    if not (site_dir / "public" / "images" / "hero-bg.webp").exists():
        return "hero-bg.webp missing"
    meta_path = site_dir / "src" / "data" / "image-meta.json"
    try:
        meta = json.loads(meta_path.read_text())
        n = len(meta)
    except (OSError, json.JSONDecodeError, TypeError):
        return "image-meta.json missing/unreadable"
    if n < MIN_IMAGE_META_ENTRIES:
        return f"image-meta.json has {n} entries (<{MIN_IMAGE_META_ENTRIES})"
    return None


def _preview_ask(cid: str) -> tuple[bool, bool]:
    """(ask exists, client signed off) — the SAME query the launch seeder uses
    (client_ops_sync.ensure_internal_launch_tasks): the client_input preview
    ask, resolved/done = sign-off recorded."""
    rows = _sb("GET", "/rest/v1/marketing_action_plan"
               f"?company_id=eq.{cid}&action_type=eq.client_input"
               "&title=ilike.*preview*&select=status",
               prefer="return=representation") or []
    signed = any((r.get("status") or "") in ("resolved", "done") for r in rows)
    return bool(rows), signed


def _file_visual_pass_task(cid: str, slug: str, stage: str, gap: str,
                           dry_run: bool) -> str:
    """ONE open [DEV] visual-pass task per client, ever. Returns what
    happened for the sweep line."""
    notes = _sb("GET", "/rest/v1/marketing_ops_notes"
                f"?company_id=eq.{cid}&status=eq.open&select=id,body",
                prefer="return=representation") or []
    if any(n.get("body", "").startswith("[DEV]")
           and VISUAL_PASS_MARKER in n.get("body", "") for n in notes):
        return "[DEV] visual-pass task already open"
    body = (f"[DEV] {slug}: run the full visual pass per the AI-first "
            f"doctrine — the site is on {stage} but {gap}. Follow "
            f"clients/{slug}/image-style-guide.md (real client photos where "
            "pinned, brand-true generated slots otherwise), regenerate the "
            "full slot set, quality-gate, re-render and redeploy. Filed by "
            "stage_checker.py.")
    if dry_run:
        return f"[dry-run] would file [DEV] visual-pass task ({gap})"
    _sb("POST", "/rest/v1/marketing_ops_notes",
        [{"company_id": cid, "body": body}])
    return f"filed [DEV] visual-pass task ({gap})"


def _age_days(iso: str | None) -> int:
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return max((datetime.now(timezone.utc) - d).days, 0)
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------------- checklist
def _blockers(co: dict, slug: str | None, site: dict | None, stage: str,
              dry_run: bool) -> list[tuple[str, str]]:
    """Unmet exit items for this stage, ordered most-blocking first. Each is
    (what/action, owner). Filing side effects (the [DEV] task) happen here;
    everything else is routed by reporting the system that already owns it."""
    cid = co["id"]
    out: list[tuple[str, str]] = []

    if stage == "building":
        if not slug:
            out.append(("no rank-ai slug mapping — never bootstrapped; "
                        "checklist underivable", "Santino"))
            return out
        if not [s for s in (co.get("services") or []) if s]:
            out.append(("services list empty — auto-build already seeds the "
                        "Monica ask (site-build-blocked-services)", "Monica"))
        if not _has_logo(cid):
            age = _age_days(co.get("created_at"))
            if age >= LOGO_SOAK_DAYS:
                out.append((f"no logo after {age}d soak — building anyway "
                            "due (auto-build proceeds with placeholder)",
                            "auto-build"))
            else:
                out.append((f"waiting on logo (day {age} of {LOGO_SOAK_DAYS} "
                            "soak) — auto-build's logo ask covers Monica",
                            "Monica"))
        if not (CLIENTS_DIR / slug / "plan-input.json").exists():
            out.append(("plan-input.json missing (bootstrap gap) — "
                        "auto-build reports it nightly", "auto-build"))
        elif not (SITES_DIR / slug / "src").exists():
            out.append(("plan/scaffold/render pending — auto-build owns it "
                        "(runs capped; not duplicating builds here)",
                        "auto-build"))
        else:
            bs = (site or {}).get("build_status") or "pending"
            out.append((f"site rendered locally but build_status={bs} — "
                        "deploy/supabase_sync owns the status", "auto-build"))

    elif stage in ("preview", "staging"):
        ask_exists, signed = _preview_ask(cid)
        if stage == "staging":
            if not ask_exists:
                out.append(("preview never sent to client — no client_input "
                            "preview ask row", "ops-sync/Monica"))
            elif not signed:
                out.append(("awaiting readiness answer (preview ask still "
                            "open)", "Monica"))
            da = str((site or {}).get("domain_access_status") or "none")
            if da not in READY_ACCESS:
                out.append((f"domain access '{da}' — the ledger already "
                            "seeds the registrar ask", "Monica/ledger"))
        gap = _imagery_gap(slug) if slug else None
        if gap:
            if not _has_logo(cid):
                # Logo-required-first (the FireDEX case): every image is
                # generated FROM the brand assets, so a visual pass before
                # the logo exists would ship wrong branding. Do NOT file.
                out.append((f"imagery incomplete ({gap}) but NO logo yet — "
                            "visual pass blocked on brand assets; [DEV] task "
                            "NOT filed (logo ask covers Monica)", "Monica"))
            else:
                did = _file_visual_pass_task(cid, slug, stage, gap, dry_run)
                out.append((f"imagery incomplete — {did}", "dev-inbox"))
        if stage == "preview" and not ask_exists:
            out.append(("preview never sent to client — no client_input "
                        "preview ask row", "ops-sync/Monica"))

    elif stage == "ready":
        launch = []
        if slug:
            key = action_key(cid, f"internal-push-live-{slug}")
            launch = _sb("GET", "/rest/v1/marketing_action_plan"
                         f"?company_id=eq.{cid}&action_key=eq.{key}"
                         "&select=status", prefer="return=representation") or []
        if launch:
            st = launch[0].get("status") or "planned"
            out.append((f"internal launch task {st} — the ops board owns "
                        "the click", "Santino"))
        else:
            gates = []
            ask_exists, signed = _preview_ask(cid)
            if not ask_exists:
                gates.append("no preview ask row")
            elif not signed:
                gates.append("client sign-off missing (preview ask open)")
            da = str((site or {}).get("domain_access_status") or "none")
            if da not in READY_ACCESS:
                gates.append(f"domain access '{da}' (NS probe may still "
                             "unlock the seeder)")
            if gates:
                out.append(("launch task not seeded — seeder gated: "
                            + "; ".join(gates), "ops-sync"))
            else:
                out.append(("launch task should be seeded — ops-sync's "
                            "ensure_internal_launch_tasks owns it next sweep",
                            "ops-sync"))
    return out


# ---------------------------------------------------------------- main pass
def check_stages(dry_run: bool, cid_to_slug: dict | None = None,
                 verbose: bool = False) -> list[str]:
    """One pass over every ACTIVE Rank AI client. Returns '{slug}: ...' lines
    for the sweep log / daily digest. History write is the only mutation
    besides the (idempotent) [DEV] imagery task."""
    cid_to_slug = cid_to_slug or slug_map()
    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    cos = _sb("GET", "/rest/v1/companies?status=ilike.active"
              "&plan=eq.Rank%20AI&select=id,name,services,created_at",
              prefer="return=representation") or []
    sites = _sb("GET", "/rest/v1/marketing_sites?select=company_id,"
                "rank_ai_slug,domain,build_status,apex_live,"
                "domain_access_status", prefer="return=representation") or []
    by_cid = {s["company_id"]: s for s in sites if s.get("company_id")}
    by_slug = {s["rank_ai_slug"]: s for s in sites if s.get("rank_ai_slug")}

    history = kv_get(HISTORY_KEY) or {}
    if not isinstance(history, dict):
        history = {}
    out: list[str] = []
    table: list[tuple[str, str, int, str]] = []
    seeded = 0
    dirty = False

    for co in sorted(cos, key=lambda c: cid_to_slug.get(c["id"], "~") or "~"):
        cid = co["id"]
        slug = cid_to_slug.get(cid)
        label = slug or co.get("name") or cid
        site = by_cid.get(cid) or (by_slug.get(slug) if slug else None)
        stage = website_stage(site)

        h = history.get(cid)
        if not isinstance(h, dict) or h.get("board") != BOARD:
            h = None
        if h is None:
            history[cid] = {"board": BOARD, "stage": stage,
                            "entered_at": now_iso}
            seeded += 1
            dirty = True
        elif h.get("stage") != stage:
            out.append(f"{label}: stage {h.get('stage')} -> {stage}")
            history[cid] = {"board": BOARD, "stage": stage,
                            "entered_at": now_iso}
            dirty = True
        dwell = _age_days(history[cid]["entered_at"])

        blockers = _blockers(co, slug, site, stage, dry_run)
        summary = "; ".join(b[0] for b in blockers) or "-"
        table.append((label, stage, dwell, summary))

        if stage == "live":
            continue   # terminal — no exit checklist, no dwell alarm
        if dwell > DWELL_ALERT_DAYS:
            top, owner = blockers[0] if blockers else (
                "no blocker derived — needs review", "Santino")
            out.append(f"{label}: STUCK {dwell}d in {stage}: {top} -> {owner}")
        elif blockers:
            out.append(f"{label}: {stage} ({dwell}d) — {summary}")

    if seeded:
        out.insert(0, f"(stage-history) seeded entered_at=now for {seeded} "
                      "client(s) — dwell counts start today")
    if dirty and not dry_run:
        kv_set(HISTORY_KEY, history)

    if verbose:
        print(f"\n  {'client':44s} {'stage':9s} {'dwell':>5s}  blockers")
        for label, stage, dwell, summary in table:
            print(f"  {label:44s} {stage:9s} {dwell:4d}d  {summary[:110]}")
        print()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="derive + print everything; write nothing")
    args = ap.parse_args()
    load_env()
    import os
    if not (os.environ.get("SUPABASE_URL")
            and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")):
        print("ERROR: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required.",
              file=sys.stderr)
        return 2
    print(f"stage checker ({BOARD} board)"
          f"{' [DRY RUN]' if args.dry_run else ''}")
    for ln in check_stages(args.dry_run, slug_map(), verbose=True):
        print("  " + ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
