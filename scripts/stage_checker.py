#!/usr/bin/env python3
"""Stage-dwell checker for ALL eight Build Stages boards (Santino's design,
2026-08-10 website-only; extended to the full board set 2026-08-12; the
per-location Locations board joined 2026-08-13).

The self-driving customer-success loop: every night, know what stage every
active Rank AI client is in ON EVERY BOARD the app renders — Website, GBP,
LSA, Reviews, YouTube, Citations, AI Receptionist, Locations — how long they
have been there, what exactly blocks their exit, and TRIGGER the existing
action for each blocker. Nothing here invents new outreach or new builds — every unmet
exit item routes to the system that already owns it (auto-build's blocker
asks, the ledger's domain ask, ops-sync's launch seeder, the [DEV] inbox) or
is reported with its owner.

STAGE DERIVATION is an exact replica of the app's Build Stages board
(app-work/components/BuildStagesBoard.tsx v9 — its build-stages edge
function only supplies raw rows, all derivation lives in the component and
is mirrored here) — stages are DERIVED from verifiable signals, never from
a manual field. v9 (2026-08-12): LSA "running" requires campaign ENABLED
AND affirmative serve-ability (lsa.serving flag or a verification note with
no FAILED / NO_SUBMISSION / blocked PENDING) — Google auto-creates an
ENABLED SystemGenerated campaign for every LSA account, so ENABLED alone
proves nothing. Company scope matches the board exactly:
plan = 'Rank AI' (case-insensitive), status not in the excluded set, minus
the internal canary account. Per-board sources:

    website      marketing_sites (build_status / apex_live)     websiteStage()
    gbp          user_integrations provider=google status=active
                 + marketing_gbp_profiles                       gbpStage()
    receptionist company_phone_numbers (neq call_tracking)
                 + call_metadata presence                       rStage inline
    lsa          companies.integration_settings lsa + lsa_intent  lsaStage()
    reviews      review_requests + the hub's customer-list pin  vStage inline
    youtube      user_integrations provider=youtube             inline
    citations    user_integrations provider=citations
                 connection_metadata.nap_audit                  cStage inline
    locations    company_locations expansion rows (is_primary=
                 false) + their launch checklist jsonb          locations_stage()

The LOCATIONS board (8th, 2026-08-13) is per-LOCATION, not per-company: one
card per expansion company_locations row, so a client launching two offices
holds two cards. Stage derives from row status + the launch checklist
(20260813200000), sharing _step_done() with location_checklist_sync so the
board, the ask seeder and this checker can never disagree about a step.

STAGE HISTORY lives in ops_kv key 'stage-history'. Backward compatible with
the phase-1 (website-only) shape: the website entry stays FLAT
({company_id: {board:'website', stage, entered_at}}); the six other boards
live under {company_id: {..., boards: {gbp: {stage, entered_at}, ...}}}.
Location entries also live under boards{}, keyed 'locations:{location_id}'
because a company can hold several. Updated on change only, entered_at=now
seeded on first sight (dwell counts start that day). ops_kv over a new
table: zero schema risk, same pattern as docs-seen and the email-sync cursor.

DWELL ALERTS are per-board, per-stage (DWELL_DAYS below — the semantics of a
stage decide its threshold; None = a stage that legitimately dwells forever
never alarms). An alert is a digest line AND a plain-English
marketing_ops_notes row — one per condition per client, deduped against open
notes by its [STAGE:board:tag] marker (the same open-note dedupe the
phase-1 [DEV] imagery task uses) plus a per-episode flag in the history so a
human resolving the note isn't re-nagged nightly while the stage is unchanged.

EXIT CHECKLISTS where a cheap derived check exists:
  website   unchanged from phase 1 (services/logo/plan gaps -> auto-build,
            imagery -> the [DEV] visual-pass task, launch -> ops-sync seeder).
  gbp       'synced' must actually be OPTIMIZED: services + description +
            business hours present on marketing_gbp_profiles. (GBP attributes
            are never persisted to Supabase — gbp.py reads them live — so
            has_hours is the closest stored completeness signal.)
  reviews   'active' must actually be SENDING: newest last_sent_at within
            REVIEWS_STALL_DAYS — catches the pace_capped-style silent stall
            (2026-08-11). 'received' with rows scheduled but ZERO ever
            dispatched past a grace = the dispatcher never started.
  citations 'complete' (the board's built claim) requires the nap_audit
            found-count to clear CITATIONS_FOUND_FLOOR — an audit that found
            2 platforms is not 'core listings complete'.

Runs inside client_ops_sync.run() (same independent try/except as the setup
ledger and email_inbox_sync — a checker raise must never take the sweep down).
CLI for manual runs (prints the full per-client stage table + fleet
distribution per board):

    python3 scripts/stage_checker.py --dry-run     # derive + print, write nothing
    python3 scripts/stage_checker.py               # live

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (rank-ai/.env or CI secrets).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = ROOT / "clients"
SITES_DIR = ROOT / "sites"
sys.path.insert(0, str(Path(__file__).parent))

from client_ops_sync import _sb, action_key, load_env, slug_map  # noqa: E402
from client_concierge import kv_get, kv_set  # noqa: E402
# The ONE shared step-truth helper — the ask seeder, the app board and this
# checker must never disagree about whether a checklist step is done.
from location_checklist_sync import _step_done  # noqa: E402

HISTORY_KEY = "stage-history"
BOARD = "website"           # phase-1 name; the website history entry stays flat
BOARDS = ("website", "gbp", "lsa", "reviews", "youtube", "citations",
          "receptionist")
LOC_BOARD = "locations"     # 8th board — per-location cards, handled after
                            # the per-company loop (a company can hold 0..n)
LOGO_SOAK_DAYS = 7          # mirror of setup_ledger.ensure_auto_site_build
MIN_IMAGE_META_ENTRIES = 3
# Mirror of client_ops_sync.ensure_internal_launch_tasks READY_ACCESS — the
# "granted-ish" domain_access_status values that mean we can act without the
# client.
READY_ACCESS = {"granted", "creds_provided", "ns_live", "delegate_granted"}
# Idempotency marker for the imagery task — an OPEN [DEV] note containing this
# phrase means the task is already in the dev inbox; never file a second.
VISUAL_PASS_MARKER = "full visual pass"

# Company scope — EXACT replica of BuildStagesBoard.tsx's roster filter:
# EXCLUDED_COMPANY_STATUSES (case-insensitive; prod holds 'Active',
# 'Inactive' AND 'paused'), EXCLUDED_COMPANY_IDS (the "Test (Rank AI)"
# canary, on the plan so the plan filter can't drop it), RANK_AI_PLAN
# compared trimmed/lowered.
EXCLUDED_COMPANY_STATUSES = {"paused", "cancelled", "churned", "inactive",
                             "archived"}
EXCLUDED_COMPANY_IDS = {"CO-1782880883337"}  # Test (Rank AI)
RANK_AI_PLAN = "rank ai"

# ---------------------------------------------------------------- thresholds
# Per-board, per-stage dwell thresholds in DAYS (alert when dwell EXCEEDS the
# number). None = never alarm: terminal stages, and stages whose whole point
# is to dwell (a parked LSA, a mid-drip review campaign). The numbers come
# from the SEMANTICS of each stage, not one global constant:
#
# website  7 everywhere (Santino's phase-1 design): a build pipeline stage
#          that hasn't moved in a week is stuck, whoever owns the blocker.
# gbp      none=14 (connecting Google is a client action; the rank-0 connect
#          ask nags — two silent weeks is escalation-worthy)
#          connected=10 (no listing synced is OUR selection/creation work;
#          the ledger watchdog reports it, ten days stuck deserves a card)
#          synced=None (terminal; the optimized exit-check below still runs)
# lsa      unknown=21 (a client DECISION — Yes/No/Later buttons +
#          lsa_intent_check's ask own the nag; decisions dwell longer before
#          we alarm), wants=10 (they said yes; account linking is our move),
#          pending=30 (Google LSA verification — background check, license,
#          insurance — routinely takes weeks; alarm only when a month passes),
#          running/parked=None (terminal; an expired 'later' re-derives to
#          unknown on its own).
# reviews  none=None (plenty of clients legitimately have no list yet; the
#          rank-30 customer-list ask owns that nag — alarming here would page
#          on every new client), received=7 (a list arrived / rows staged and
#          nothing dispatches: the Rudy case, THE silent-stall column),
#          active=None (a mid-drip campaign is not stuck — the send-freshness
#          exit-check catches real stalls instead), complete=None.
# youtube  none=None (a rank-40 nice-to-have, client-paced; nearly the whole
#          fleet connects eventually and alarming would flood), connected=None.
# citations none=30 (the NAP audit is a monthly pipeline; a client with no
#          audit after a month fell out of the loop), gaps=None (gaps are the
#          normal working state while the creation queue grinds — the
#          found-floor exit-check guards the built claim), complete=None.
# receptionist none=None (the receptionist is optional per client;
#          provisioning is sales-driven), provisioned=14 (a line exists but
#          zero calls handled in two weeks: routing never finished or the
#          number is unused), live=None.
# locations (8th board, per-location):
#          planned=None (a saved scout recommendation is a parked idea until
#          paperwork starts; the nightly dba ask owns the client nag —
#          alarming here would page on every "Save as planned" click),
#          paperwork=21 (STATE APPROVALS ARE SLOW — an Iowa filing routinely
#          takes weeks and the registry watcher checks nightly; only three
#          silent weeks earns a card),
#          profile=30 (GBP exists, verification untouched — verification is
#          a client action with its own nightly ask; a month of silence is
#          escalation-worthy),
#          verifying=14 (Google's postcard runs ~5-14 days and codes EXPIRE;
#          two weeks stuck means re-request or switch method),
#          live=30 (amplification — site pages, citations, hub — is OUR
#          work; a live listing left un-amplified for a month is our miss),
#          amplified=None (terminal).
DWELL_DAYS: dict[str, dict[str, int | None]] = {
    "website": {"building": 7, "preview": 7, "staging": 7, "ready": 7,
                "live": None},
    "gbp": {"none": 14, "connected": 10, "synced": None},
    "lsa": {"unknown": 21, "wants": 10, "pending": 30, "running": None,
            "parked": None},
    "reviews": {"none": None, "received": 7, "active": None, "complete": None},
    "youtube": {"none": None, "connected": None},
    "citations": {"none": 30, "gaps": None, "complete": None},
    "receptionist": {"none": None, "provisioned": 14, "live": None},
    "locations": {"planned": None, "paperwork": 21, "profile": 30,
                  "verifying": 14, "live": 30, "amplified": None},
}
REVIEWS_STALL_DAYS = 7          # 'active' with no send in a week = stalled
REVIEWS_NEVER_STARTED_DAYS = 2  # rows scheduled, zero EVER sent, oldest due
                                # date this far past = dispatcher never started
CITATIONS_FOUND_FLOOR = 3       # 'complete' with fewer platforms found than
                                # this is a thin audit, not built listings


# ---------------------------------------------------------------- derivations
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


def gbp_stage(has_google: bool, profile: dict | None) -> str:
    """EXACT replica of BuildStagesBoard.tsx gbpStage(): a
    marketing_gbp_profiles row is the verifiable 'listing synced' signal —
    it only exists when gbp.py actually pulled the listing, and it wins even
    if the OAuth row later went inactive."""
    return "synced" if profile else ("connected" if has_google else "none")


def receptionist_stage(line: dict | None, has_calls: bool) -> str:
    """EXACT replica of BuildStagesBoard.tsx's receptionist derivation:
    an ai_agent-ish line row (the edge fn excludes number_type=
    'call_tracking' — those are Ads tracking numbers) = provisioned;
    call_metadata evidence the agent actually handled calls = live."""
    if not line:
        return "none"
    return "live" if has_calls else "provisioned"


def _lsa_intent_answer(intent) -> tuple[str | None, str | None]:
    """EXACT replica of BuildStagesBoard.tsx lsaIntentAnswer(): dict
    {answer, revisit_on} from OpsAttention / the board / lsa_intent_check,
    or a legacy free-text string ('yes - LSA already live..., managed by
    RGP'). Returns (answer, revisit_on)."""
    if not intent:
        return None, None
    if isinstance(intent, str):
        s = intent.strip().lower()
        if s.startswith("yes"):
            return "yes", None
        if s.startswith("no"):
            return "no", None
        if s.startswith("later"):
            m = re.search(r"\d{4}-\d{2}-\d{2}", intent)
            return "later", (m.group(0) if m else None)
        return None, None
    a = str((intent.get("answer") if isinstance(intent, dict) else "") or "").lower()
    if a in ("yes", "no", "later"):
        return a, (intent.get("revisit_on") if isinstance(intent, dict) else None)
    return None, None


def _lsa_serveable(lsa: dict) -> bool:
    """EXACT replica of BuildStagesBoard.tsx lsaServeable() (v9):
    affirmative evidence the ENABLED campaign can actually serve — an
    explicit serving flag, or a verification note (lsa_detect.py, nightly)
    containing no FAILED / NO_SUBMISSION / BLOCKED / SUSPENDED and no
    blocking PENDING. An 'mcc invite PENDING' clause is OUR access, not
    their eligibility, so it never blocks; a license / background /
    insurance PENDING does. Missing or 'unchecked' verification = NOT
    serve-able: unknown must read as not-running, never as running."""
    if lsa.get("serving") is True:
        return True
    v = str(lsa.get("verification") or "").strip().upper()
    if not v or re.search(r"FAILED|NO_SUBMISSION|BLOCKED|SUSPENDED|UNCHECKED", v):
        return False
    return all("PENDING" not in seg or "MCC" in seg or "INVITE" in seg
               for seg in re.split(r"[;,]", v))


def lsa_stage(lsa, intent) -> str:
    """EXACT replica of BuildStagesBoard.tsx lsaStage() (v9 serve-ability
    gate). Precedence: an ENABLED campaign outranks intent — running only
    when affirmatively serve-able, otherwise Setup + verification pending
    whatever anyone said (Google auto-creates an ENABLED SystemGenerated
    campaign for every LSA account, so ENABLED alone proves nothing); an
    explicit no/unexpired-later parks the client even if an old paused
    account exists; a detected account that isn't enabled = setup pending;
    an expired 'later' falls back to unknown (revisit date honoured)."""
    lsa = lsa if isinstance(lsa, dict) else {}
    if str(lsa.get("campaign_status") or "").upper() == "ENABLED":
        return "running" if _lsa_serveable(lsa) else "pending"
    answer, revisit = _lsa_intent_answer(intent)
    if answer == "no":
        return "parked"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if answer == "later" and (not revisit or str(revisit) >= today):
        return "parked"
    if lsa.get("customer_id"):
        return "pending"
    if answer == "yes":
        return "wants"
    return "unknown"


def reviews_stage(reqs: list[dict], pin: dict | None) -> str:
    """EXACT replica of BuildStagesBoard.tsx's reviews derivation (vStage):
    live row = could still be dispatched; dispatch evidence = some row
    actually went out; the hub's customer-list pin counts as 'received'
    before anything is loaded into review_requests."""
    live = [r for r in reqs
            if (r.get("status") or "").lower() in ("pending", "sent")
            and not r.get("opted_out") and r.get("next_send_at") is not None]
    dispatched = sum(1 for r in reqs if r.get("last_sent_at") is not None)
    terminal = sum(1 for r in reqs if (r.get("status") or "").lower() in
                   ("completed", "clicked", "reviewed", "feedback_given",
                    "unsubscribed"))
    if not reqs and not pin:
        return "none"
    if live and dispatched > 0:
        return "active"
    if reqs and not live and (dispatched > 0 or terminal > 0):
        return "complete"
    return "received"   # rows staged/parked, or a list uploaded but not loaded


def youtube_stage(yt: dict | None) -> str:
    """EXACT replica of BuildStagesBoard.tsx's YouTube derivation: an
    integration row with status connected/active = connected."""
    return ("connected" if yt and (yt.get("status") or "").lower()
            in ("connected", "active") else "none")


def citations_stage(nap_audit: dict | None) -> str:
    """EXACT replica of BuildStagesBoard.tsx's citations derivation (cStage):
    nap_audit = {platform: {status: found|discrepancy|missing}} written by
    the monthly NAP-audit pipeline into the citations integration."""
    entries = list((nap_audit or {}).values())
    if not entries:
        return "none"
    missing = sum(1 for p in entries if ((p or {}).get("status") or "") == "missing")
    return "gaps" if missing > 0 else "complete"


# The 8 launch steps in order — mirrors LocationsPanel CHECKLIST_STEPS and
# location_checklist_sync STEP_ORDER; the short chips match the app cards.
LOC_STEPS = (("dba", "DBA"), ("address", "Addr"), ("gbp_created", "GBP"),
             ("verification", "Verify"), ("live", "Live"),
             ("site_pages", "Pages"), ("citations", "Cites"), ("hub", "Hub"))


def _loc_step_started(loc: dict, step: str) -> bool:
    """EXACT replica of BuildStagesBoard.tsx locStepStarted(): the step is
    done, OR carries any recorded fact (a filing date, a photo, a note) —
    evidence somebody started it. Step-done truth is the SHARED
    location_checklist_sync._step_done (checklist first, then column-derived:
    address/gbp_location_id/status-live)."""
    if _step_done(loc, step):
        return True
    st = (loc.get("checklist") or {}).get(step)
    if not st:
        return False
    return any(k != "done" and not (v is None or v == "" or v is False)
               for k, v in st.items())


def locations_stage(loc: dict) -> str:
    """EXACT replica of BuildStagesBoard.tsx locationStage(). Do not
    'improve' one side without the other — most-launched first:
      amplified  site_pages + citations + hub ALL done
      live       row status live, or the live step done
      verifying  row status verifying, or verification in progress (a done
                 verification with the listing not yet live also sits here)
      profile    gbp_created done, verification untouched
      paperwork  dba or address in progress (both done but no GBP yet also
                 reads paperwork — waiting on us)
      planned    nothing started"""
    if (_step_done(loc, "site_pages") and _step_done(loc, "citations")
            and _step_done(loc, "hub")):
        return "amplified"
    if loc.get("status") == "live" or _step_done(loc, "live"):
        return "live"
    if loc.get("status") == "verifying" or _loc_step_started(loc, "verification"):
        return "verifying"
    if _step_done(loc, "gbp_created"):
        return "profile"
    if _loc_step_started(loc, "dba") or _loc_step_started(loc, "address"):
        return "paperwork"
    return "planned"


def _loc_blocker(stage: str, loc: dict) -> str:
    """One-line 'what blocks the exit and who owns it' per locations stage.
    Every blocker names the system that already owns it — the registry
    watcher, the checklist sync's asks, or us."""
    checklist = loc.get("checklist") or {}
    if stage == "paperwork":
        gaps = []
        dba = checklist.get("dba") or {}
        if not _step_done(loc, "dba"):
            watch = dba.get("watch") or {}
            if watch.get("status") == "needs-browser-agent":
                gaps.append("dba filing pending but the state registry "
                            "blocks server-side reads — needs-browser-agent "
                            "(see checklist.dba.watch)")
            elif watch:
                gaps.append(f"dba awaiting {watch.get('state', '?')} approval "
                            "— the registry watcher checks nightly and flips "
                            "the step itself")
            else:
                gaps.append("dba not filed — the checklist sync's dba ask "
                            "owns the client nag")
        if not _step_done(loc, "address"):
            gaps.append("address unconfirmed — the checklist sync's address "
                        "ask owns the client nag")
        if not gaps:
            gaps.append("paperwork done but no GBP created yet — creating "
                        "the profile is OUR move (gbp.py)")
        return "; ".join(gaps)
    if stage == "profile":
        return ("GBP profile exists but Google verification has not started "
                "— the checklist sync's verification ask owns the client nag")
    if stage == "verifying":
        if _step_done(loc, "verification"):
            return ("verification done but the listing is not marked live — "
                    "check the listing and record the live step")
        return ("Google verification in flight — postcard codes expire; "
                "re-request or switch method if it stays silent")
    if stage == "live":
        gaps = [chip for key, chip in LOC_STEPS
                if key in ("site_pages", "citations", "hub")
                and not _step_done(loc, key)]
        return ("listing live but amplification incomplete "
                f"({', '.join(gaps) or '?'}) — location pages, citations and "
                "the crew hub are OUR work")
    return "no blocker derived — needs review"


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


# ---------------------------------------------------------------- ops notes
def _open_note_bodies(cid: str, cache: dict) -> list[str] | None:
    """Open marketing_ops_notes bodies for dedupe, cached per company per
    run. None = the notes could not be read; the caller must NOT file (a
    read hiccup would otherwise duplicate every open alert)."""
    if cid not in cache:
        try:
            rows = _sb("GET", "/rest/v1/marketing_ops_notes"
                       f"?company_id=eq.{cid}&status=eq.open&select=body",
                       prefer="return=representation") or []
            cache[cid] = [str(n.get("body") or "") for n in rows]
        except Exception:  # noqa: BLE001
            cache[cid] = None
    return cache[cid]


def _file_alert_note(cid: str, label: str, board: str, tag: str, text: str,
                     dry_run: bool, cache: dict) -> str | None:
    """ONE plain-English marketing_ops_notes row per condition per client,
    deduped against open notes by the [STAGE:board:tag] marker — the same
    open-note dedupe pattern as the phase-1 [DEV] imagery task. Returns a
    sweep-line fragment when a note was (or would be) filed, else None."""
    marker = f"[STAGE:{board}:{tag}]"
    bodies = _open_note_bodies(cid, cache)
    if bodies is None or any(marker in b for b in bodies):
        return None
    body = f"{marker} {label}: {text} Filed by stage_checker.py."
    if dry_run:
        return f"[dry-run] would file ops note {marker}"
    _sb("POST", "/rest/v1/marketing_ops_notes",
        [{"company_id": cid, "body": body}])
    cache[cid].append(body)
    return f"filed ops note {marker}"


# ---------------------------------------------------------------- fleet data
def _fetch_paged(path_base: str, page: int = 1000) -> list[dict]:
    """GET all rows past the PostgREST default cap. The app board tolerates
    the 1000-row truncation (supabase-js default); the checker paginates
    because the reviews stall math needs the REAL newest last_sent_at."""
    out: list[dict] = []
    offset = 0
    while True:
        rows = _sb("GET", f"{path_base}&limit={page}&offset={offset}",
                   prefer="return=representation") or []
        out.extend(rows)
        if len(rows) < page:
            return out
        offset += page


def _fetch_fleet() -> dict:
    """Every table read the app's build-stages edge function performs, with
    the board's own roster filter applied. One dict of per-board maps."""
    cos = _sb("GET", "/rest/v1/companies?plan=ilike.rank%20ai"
              "&select=id,name,status,plan,services,created_at,"
              "lsa:integration_settings->lsa,"
              "lsa_intent:integration_settings->lsa_intent",
              prefer="return=representation") or []
    cos = [c for c in cos
           if (c.get("status") or "").strip().lower() not in EXCLUDED_COMPANY_STATUSES
           and c["id"] not in EXCLUDED_COMPANY_IDS]
    ids = {c["id"] for c in cos}

    sites = _sb("GET", "/rest/v1/marketing_sites?select=company_id,"
                "rank_ai_slug,domain,build_status,apex_live,"
                "domain_access_status", prefer="return=representation") or []

    google = _sb("GET", "/rest/v1/user_integrations?provider=eq.google"
                 "&status=eq.active&select=client_id",
                 prefer="return=representation") or []
    has_google = {r["client_id"] for r in google if r.get("client_id")}

    profiles = _sb("GET", "/rest/v1/marketing_gbp_profiles?select=company_id,"
                   "title,synced_at,services,description,has_hours",
                   prefer="return=representation") or []
    profile_by_cid = {p["company_id"]: p for p in profiles if p.get("company_id")}

    # Receptionist lines — the edge fn excludes number_type='call_tracking'
    # (Ads tracking numbers); one line per company, primary preferred, else
    # oldest (rows ordered created_at asc, first-seen wins).
    plines = _sb("GET", "/rest/v1/company_phone_numbers"
                 "?number_type=neq.call_tracking&select=company_id,"
                 "phone_number,is_primary,created_at&order=created_at.asc",
                 prefer="return=representation") or []
    line_by_cid: dict[str, dict] = {}
    for l in plines:
        cid = l.get("company_id")
        if not cid or cid not in ids:
            continue
        if cid not in line_by_cid or (l.get("is_primary")
                                      and not line_by_cid[cid].get("is_primary")):
            line_by_cid[cid] = l
    # "Live" evidence = the agent actually handled calls. The board head-
    # counts call_metadata; the stage only needs existence, so probe one row
    # per line-owning company.
    has_calls: dict[str, bool] = {}
    for cid in line_by_cid:
        try:
            rows = _sb("GET", f"/rest/v1/call_metadata?company_id=eq.{cid}"
                       "&select=id&limit=1", prefer="return=representation") or []
            has_calls[cid] = bool(rows)
        except Exception:  # noqa: BLE001 — an unreadable count reads as 0
            has_calls[cid] = False

    yt_rows = _sb("GET", "/rest/v1/user_integrations?provider=eq.youtube"
                  "&select=client_id,status", prefer="return=representation") or []
    yt_by_cid = {y["client_id"]: y for y in yt_rows if y.get("client_id")}

    cit_rows = _sb("GET", "/rest/v1/user_integrations?provider=eq.citations"
                   "&select=client_id,nap_audit:connection_metadata->nap_audit",
                   prefer="return=representation") or []
    cit_by_cid: dict[str, dict] = {}
    for r in cit_rows:
        cid = r.get("client_id")
        if not cid:
            continue
        # Prefer a row that actually carries an audit if duplicates exist
        # (same rule as the board's citMap fill).
        if cid not in cit_by_cid or (r.get("nap_audit")
                                     and not cit_by_cid[cid].get("nap_audit")):
            cit_by_cid[cid] = r

    reqs = _fetch_paged("/rest/v1/review_requests?select=company_id,status,"
                        "opted_out,next_send_at,last_sent_at&order=id.asc")
    reqs_by_cid: dict[str, list[dict]] = {}
    for r in reqs:
        reqs_by_cid.setdefault(r.get("company_id"), []).append(r)

    # The hub upload flow's "Customer list uploaded — load into the review
    # campaign" pin: evidence a list arrived before anyone loaded it.
    pins = _sb("GET", "/rest/v1/marketing_action_plan?pinned=eq.true"
               "&title=ilike.Customer%20list%20uploaded*"
               "&select=company_id,status", prefer="return=representation") or []
    pin_by_cid = {p["company_id"]: p for p in pins if p.get("company_id")}

    # Locations board (2026-08-13): EXPANSION rows only, same scope the
    # build-stages edge fn serves (is_primary=false — the 65 backfilled
    # primaries never went through the launch pipeline and their empty
    # checklists would read as "live but never amplified" fleet-wide).
    locs = _sb("GET", "/rest/v1/company_locations?is_primary=eq.false"
               "&select=id,company_id,label,city,state,address,status,"
               "is_primary,dba_name,gbp_location_id,checklist"
               "&order=company_id", prefer="return=representation") or []
    locs_by_cid: dict[str, list[dict]] = {}
    for l in locs:
        if l.get("company_id") in ids:
            locs_by_cid.setdefault(l["company_id"], []).append(l)

    return {"companies": cos, "sites": sites, "has_google": has_google,
            "profiles": profile_by_cid, "lines": line_by_cid,
            "has_calls": has_calls, "youtube": yt_by_cid,
            "citations": cit_by_cid, "reviews": reqs_by_cid,
            "pins": pin_by_cid, "locations": locs_by_cid}


# ---------------------------------------------------------------- checklists
def _blockers(co: dict, slug: str | None, site: dict | None, stage: str,
              dry_run: bool, dwell: int = 0) -> list[tuple[str, str]]:
    """WEBSITE exit checklist (unchanged phase-1 logic): unmet exit items for
    this stage, ordered most-blocking first. Each is (what/action, owner).
    Filing side effects (the [DEV] task) happen here; everything else is
    routed by reporting the system that already owns it."""
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

        # MID-BUILD STALL TEETH (2026-08-19, the rt-olson lesson: a broken
        # gitlink made the nightly bootstrap re-scaffold the same site for 8
        # nights; every night refreshed the timestamps, so nothing here ever
        # read as stale, and the calm auto-build hand-off lines above carry
        # no escalation). The signal that DOES catch a loop: the build
        # STARTED long ago (first scaffold / plan generation) yet
        # build_status still is not a finished state. Repeats in every
        # digest until a human or a dispatched site-build clears it.
        _bs = (site or {}).get("build_status") or "pending"
        if dwell >= 2 and _bs not in ("content_rendered", "pushed_staging",
                                      "pushed_main"):
            out.append((
                f"MID-BUILD STALL: {dwell}d in 'building' and build_status "
                f"is still '{_bs}' — a build looping or dead (rt-olson "
                "class: nightly re-scaffolds refresh every client-record "
                "timestamp, but this dwell clock only resets on a real "
                "stage change); dispatch site-build or investigate",
                "needs-human"))

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


def _board_blocker(board: str, stage: str, ctx: dict) -> str:
    """One-line 'what blocks the exit and who owns it' per non-website board
    stage — the dwell-note body and the digest STUCK line share it. Cheap
    derived text only; each blocker names the system that already owns it."""
    if board == "gbp":
        if stage == "none":
            return ("no active Google connection — ops-sync's connect ask "
                    "(rank 0) owns the nag; escalate to a call if it stays "
                    "silent")
        if stage == "connected":
            return ("Google connected but NO GBP listing synced — the account "
                    "holds zero listings (create+verify one) or several (a "
                    "selection is needed); every GBP system skips this client "
                    "meanwhile (ledger watchdog also reports it)")
    if board == "lsa":
        if stage == "unknown":
            return ("no LSA decision recorded — lsa_intent_check's ask and "
                    "the board's Yes/No/Later buttons own the capture")
        if stage == "wants":
            return ("client said YES to LSA but no LSA account is linked — "
                    "provisioning/linking is our move (mcc_link/lsa flow)")
        if stage == "pending":
            note = str(ctx.get("verification") or "").strip()
            if str(ctx.get("campaign_status") or "").upper() == "ENABLED":
                # v9: Google auto-creates an ENABLED SystemGenerated campaign
                # for every LSA account — ENABLED here is NOT evidence of
                # serving, the verification note is what blocks the exit.
                return ("LSA campaign ENABLED but NOT serve-able — "
                        + (f"verification: {note}" if note else
                           "verification never checked (lsa_detect.py "
                           "populates it nightly)"))
            return ("LSA account linked but the campaign is not ENABLED — "
                    + (f"verification: {note}" if note else
                       "verification/budget still pending in the portal"))
    if board == "reviews" and stage == "received":
        if ctx.get("pin_only"):
            return ("customer list UPLOADED but never loaded into "
                    "review_requests — ingest it and launch the reactivation "
                    "campaign (sender per the 08-03 policy)")
        return ("review rows staged but the campaign never dispatches — "
                "check the dispatcher schedule / sender for this client")
    if board == "citations" and stage == "none":
        return ("no NAP audit on file — the monthly citations audit pass "
                "(citations_audit) skipped this client")
    if board == "receptionist" and stage == "provisioned":
        return (f"receptionist line {ctx.get('phone', '?')} provisioned but "
                "ZERO calls handled — routing never finished or the number "
                "is unused")
    return "no blocker derived — needs review"


def _board_conditions(board: str, stage: str, ctx: dict) -> list[tuple[str, str]]:
    """EXIT-CHECKLIST alert conditions with cheap derived checks, per board.
    Returns (tag, plain-English text) pairs; each becomes one deduped
    marketing_ops_notes row. Website is handled by _blockers() (phase 1)."""
    out: list[tuple[str, str]] = []

    # GBP: "synced" must actually be optimized — services + description +
    # hours present on the profile row gbp.py wrote. (Attributes are read
    # live from the API and never persisted, so has_hours stands in as the
    # stored completeness signal.)
    if board == "gbp" and stage == "synced":
        prof = ctx.get("profile") or {}
        gaps = []
        svcs = prof.get("services")
        if not (svcs if isinstance(svcs, list) else []):
            gaps.append("no services")
        if not str(prof.get("description") or "").strip():
            gaps.append("no business description")
        if prof.get("has_hours") is not True:
            gaps.append("no business hours")
        if gaps:
            out.append(("unoptimized",
                        "their Google listing is synced but not optimized: "
                        + ", ".join(gaps) + " on the profile — run the GBP "
                        "optimizer (gbp.py) for this client."))

    # Reviews: "active" must actually be SENDING — the pace_capped-style
    # silent stall (2026-08-11): rows read live/pending while the dispatcher
    # quietly stopped. Newest real send older than REVIEWS_STALL_DAYS = alert.
    if board == "reviews" and stage == "active":
        newest = max((r.get("last_sent_at") for r in ctx.get("reqs", [])
                      if r.get("last_sent_at")), default=None)
        idle = _age_days(newest) if newest else None
        if idle is not None and idle > REVIEWS_STALL_DAYS:
            out.append(("stalled",
                        f"their review campaign reads ACTIVE but nothing has "
                        f"actually sent in {idle} days (last send "
                        f"{str(newest)[:10]}) — check the dispatcher pace "
                        "cap, sender compliance and the send schedule."))

    # Reviews: rows scheduled, ZERO ever dispatched, and the oldest due date
    # is well past — the campaign never started at all.
    if board == "reviews" and stage == "received":
        reqs = ctx.get("reqs", [])
        live = [r for r in reqs
                if (r.get("status") or "").lower() in ("pending", "sent")
                and not r.get("opted_out") and r.get("next_send_at")]
        ever_sent = any(r.get("last_sent_at") for r in reqs)
        if live and not ever_sent:
            oldest_due = min(r["next_send_at"] for r in live)
            if _age_days(oldest_due) > REVIEWS_NEVER_STARTED_DAYS:
                out.append(("never-started",
                            f"{len(live)} review requests are scheduled "
                            f"(oldest due {str(oldest_due)[:10]}) but ZERO "
                            "have ever dispatched — the campaign never "
                            "started; check the dispatcher and sender."))

    # Citations: the board's "complete" is a BUILT claim — it must clear the
    # found-count floor, or the audit was just thin.
    if board == "citations" and stage == "complete":
        entries = list((ctx.get("nap_audit") or {}).values())
        found = sum(1 for p in entries
                    if ((p or {}).get("status") or "") == "found")
        if found < CITATIONS_FOUND_FLOOR:
            out.append(("thin",
                        f"citations read 'complete' but the NAP audit only "
                        f"found {found} platform(s) (floor "
                        f"{CITATIONS_FOUND_FLOOR}) — the audit scope is too "
                        "thin to call the listings built; re-audit."))
    return out


# ---------------------------------------------------------------- history
def _hist_entry(history: dict, cid: str, board: str) -> dict | None:
    """Read one board's history entry. Backward compatible: website is the
    phase-1 FLAT entry ({board,stage,entered_at} right on history[cid]);
    other boards live under history[cid]['boards'][board]."""
    h = history.get(cid)
    if not isinstance(h, dict):
        return None
    if board == BOARD:
        return h if h.get("board") == BOARD else None
    b = h.get("boards")
    return b.get(board) if isinstance(b, dict) else None


def _hist_write(history: dict, cid: str, board: str, entry: dict) -> None:
    if board == BOARD:
        boards = (history.get(cid) or {}).get("boards")
        history[cid] = {"board": BOARD, **entry}
        if isinstance(boards, dict):
            history[cid]["boards"] = boards
        return
    h = history.setdefault(cid, {})
    h.setdefault("boards", {})[board] = entry


# ---------------------------------------------------------------- main pass
def check_stages(dry_run: bool, cid_to_slug: dict | None = None,
                 verbose: bool = False) -> list[str]:
    """One pass over every board for every client the app's Build Stages
    board shows. Returns '{slug}: ...' lines for the sweep log / daily
    digest. Mutations: the history write, the (idempotent) [DEV] imagery
    task, and the deduped [STAGE:*] alert notes."""
    cid_to_slug = cid_to_slug or slug_map()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    fleet = _fetch_fleet()
    cos = fleet["companies"]
    by_cid = {s["company_id"]: s for s in fleet["sites"] if s.get("company_id")}
    by_slug = {s["rank_ai_slug"]: s for s in fleet["sites"] if s.get("rank_ai_slug")}

    history = kv_get(HISTORY_KEY) or {}
    if not isinstance(history, dict):
        history = {}
    out: list[str] = []
    table: list[tuple[str, dict[str, str], str]] = []
    loc_table: list[tuple[str, str, str, int, str]] = []  # label, loc, stage, dwell, chips
    dist: dict[str, Counter] = {b: Counter() for b in BOARDS + (LOC_BOARD,)}
    note_cache: dict = {}
    seeded = 0
    dirty = False

    for co in sorted(cos, key=lambda c: cid_to_slug.get(c["id"], "~") or "~"):
        cid = co["id"]
        slug = cid_to_slug.get(cid)
        label = slug or co.get("name") or cid
        site = by_cid.get(cid) or (by_slug.get(slug) if slug else None)
        line = fleet["lines"].get(cid)
        reqs = fleet["reviews"].get(cid, [])
        nap_audit = (fleet["citations"].get(cid) or {}).get("nap_audit")

        stages = {
            "website": website_stage(site),
            "gbp": gbp_stage(cid in fleet["has_google"],
                             fleet["profiles"].get(cid)),
            "lsa": lsa_stage(co.get("lsa"), co.get("lsa_intent")),
            "reviews": reviews_stage(reqs, fleet["pins"].get(cid)),
            "youtube": youtube_stage(fleet["youtube"].get(cid)),
            "citations": citations_stage(nap_audit),
            "receptionist": receptionist_stage(line,
                                               fleet["has_calls"].get(cid, False)),
        }
        # Per-board context the blocker/condition text draws on.
        lsa_info = co.get("lsa") if isinstance(co.get("lsa"), dict) else {}
        ctx = {
            "gbp": {"profile": fleet["profiles"].get(cid)},
            "lsa": {"verification": lsa_info.get("verification"),
                    "campaign_status": lsa_info.get("campaign_status")},
            "reviews": {"reqs": reqs,
                        "pin_only": bool(fleet["pins"].get(cid)) and not reqs},
            "citations": {"nap_audit": nap_audit},
            "receptionist": {"phone": (line or {}).get("phone_number")},
        }

        website_summary = "-"
        for board in BOARDS:
            stage = stages[board]
            dist[board][stage] += 1

            ent = _hist_entry(history, cid, board)
            if ent is None or ent.get("stage") is None:
                _hist_write(history, cid, board,
                            {"stage": stage, "entered_at": now_iso})
                seeded += 1
                dirty = True
            elif ent.get("stage") != stage:
                if board == BOARD:
                    out.append(f"{label}: stage {ent.get('stage')} -> {stage}")
                else:
                    out.append(f"{label}: [{board}] {ent.get('stage')} "
                               f"-> {stage}")
                _hist_write(history, cid, board,
                            {"stage": stage, "entered_at": now_iso})
                dirty = True
            ent = _hist_entry(history, cid, board) or {}
            dwell = _age_days(ent.get("entered_at"))

            # ---- website keeps its phase-1 checklist + line formats -------
            if board == BOARD:
                blockers = _blockers(co, slug, site, stage, dry_run, dwell)
                website_summary = "; ".join(b[0] for b in blockers) or "-"
                if stage == "live":
                    continue   # terminal — no exit checklist, no dwell alarm
                threshold = DWELL_DAYS[BOARD].get(stage)
                if threshold is not None and dwell > threshold:
                    top, owner = blockers[0] if blockers else (
                        "no blocker derived — needs review", "Santino")
                    out.append(f"{label}: STUCK {dwell}d in {stage}: {top} "
                               f"-> {owner}")
                    if not ent.get("dwell_noted"):
                        did = _file_alert_note(
                            cid, label, BOARD, f"dwell-{stage}",
                            f"stuck {dwell} days in website stage '{stage}'. "
                            f"Top blocker: {top} (owner: {owner}).",
                            dry_run, note_cache)
                        if did:
                            ent["dwell_noted"] = True
                            dirty = True
                            out.append(f"{label}: {did}")
                elif blockers:
                    out.append(f"{label}: {stage} ({dwell}d) — "
                               f"{website_summary}")
                continue

            # ---- the six new boards ---------------------------------------
            threshold = DWELL_DAYS[board].get(stage)
            if threshold is not None and dwell > threshold:
                blocker = _board_blocker(board, stage, ctx.get(board, {}))
                out.append(f"{label}: [{board}] STUCK {dwell}d in {stage}: "
                           f"{blocker}")
                if not ent.get("dwell_noted"):
                    did = _file_alert_note(
                        cid, label, board, f"dwell-{stage}",
                        f"stuck {dwell} days in {board} stage '{stage}'. "
                        f"{blocker}.", dry_run, note_cache)
                    if did:
                        ent["dwell_noted"] = True
                        dirty = True
                        out.append(f"{label}: {did}")

            for tag, text in _board_conditions(board, stage, ctx.get(board, {})):
                did = _file_alert_note(cid, label, board, tag, text,
                                       dry_run, note_cache)
                out.append(f"{label}: [{board}] {text}"
                           + (f" ({did})" if did else " (note already open)"))

        # ---- the locations board (8th, 2026-08-13) --------------------
        # Per-LOCATION cards: history keys 'locations:{location_id}' under
        # boards{}, dwell notes tagged per location so two stuck launches
        # at one company each get their own (deduped) card.
        for loc in fleet["locations"].get(cid, []):
            loc_label = (loc.get("label") or loc.get("city") or loc["id"][:8])
            stage = locations_stage(loc)
            dist[LOC_BOARD][stage] += 1
            hkey = f"locations:{loc['id']}"

            ent = _hist_entry(history, cid, hkey)
            if ent is None or ent.get("stage") is None:
                _hist_write(history, cid, hkey,
                            {"stage": stage, "entered_at": now_iso})
                seeded += 1
                dirty = True
            elif ent.get("stage") != stage:
                out.append(f"{label}: [locations:{loc_label}] "
                           f"{ent.get('stage')} -> {stage}")
                _hist_write(history, cid, hkey,
                            {"stage": stage, "entered_at": now_iso})
                dirty = True
            ent = _hist_entry(history, cid, hkey) or {}
            dwell = _age_days(ent.get("entered_at"))
            chips = " ".join(
                (chip if _step_done(loc, key) else chip.lower() + "·")
                for key, chip in LOC_STEPS)
            loc_table.append((label, loc_label, stage, dwell, chips))

            threshold = DWELL_DAYS[LOC_BOARD].get(stage)
            if threshold is not None and dwell > threshold:
                blocker = _loc_blocker(stage, loc)
                out.append(f"{label}: [locations:{loc_label}] STUCK {dwell}d "
                           f"in {stage}: {blocker}")
                if not ent.get("dwell_noted"):
                    did = _file_alert_note(
                        cid, f"{label} ({loc_label})", LOC_BOARD,
                        f"dwell-{stage}-{loc['id'][:8]}",
                        f"the {loc_label} location is stuck {dwell} days in "
                        f"stage '{stage}'. {blocker}.", dry_run, note_cache)
                    if did:
                        ent["dwell_noted"] = True
                        dirty = True
                        out.append(f"{label}: {did}")

        table.append((label, stages, website_summary))

    if seeded:
        out.insert(0, f"(stage-history) seeded entered_at=now for {seeded} "
                      "board entr(ies) — dwell counts start today")
    if dirty and not dry_run:
        kv_set(HISTORY_KEY, history)

    if verbose:
        cols = ("website", "gbp", "lsa", "reviews", "youtube", "citations",
                "receptionist")
        print(f"\n  {'client':44s} " + " ".join(f"{c[:10]:>11s}" for c in cols))
        for label, stages, _summary in table:
            print(f"  {label:44s} "
                  + " ".join(f"{stages[c][:11]:>11s}" for c in cols))
        print("\n  fleet distribution per board:")
        for b in BOARDS + (LOC_BOARD,):
            parts = ", ".join(f"{s}={n}" for s, n in dist[b].most_common())
            print(f"    {b:13s} {parts or '(no cards)'}")
        if loc_table:
            # Per-location cards (a company can hold several) — chips echo
            # the app card's done-row: UPPER = done, lower· = not yet.
            print("\n  locations board (one card per expansion location):")
            for label, loc_label, stage, dwell, chips in loc_table:
                print(f"    {label:32s} {loc_label:16s} {stage:10s} "
                      f"{dwell:3d}d  {chips}")
        print("\n  website blockers:")
        for label, stages, summary in table:
            if summary != "-":
                print(f"    {label:42s} {summary[:120]}")
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
    print(f"stage checker ({len(BOARDS) + 1} boards)"
          f"{' [DRY RUN]' if args.dry_run else ''}")
    for ln in check_stages(args.dry_run, slug_map(), verbose=True):
        print("  " + ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
