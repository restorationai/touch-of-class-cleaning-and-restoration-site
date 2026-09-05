"""Nightly citations sweep — the browser agent's scheduled pass.

Runs only playbook steps that have EARNED unattended status (3 clean
supervised completions). The roster as of 2026-08-03:

  1. BING dashboard Sync + listing verification (earned 2026-08-01) — for
     clients newly GBP-manager-accessible the dashboard import picks them up.
     "Pending publish" is EXPECTED and is not our work item: Bing publishes
     GBP-imported listings on its own 7-12 day queue after verification
     completes. See the note above bing_dashboard_state() for the full
     2026-08-04 investigation. The sweep only DETECTS the flip; the states
     that do demand a human are "Needs review" and "Suspended", which the
     dashboard counts separately and which now raise outcome='attention'.
  2. HOMEGUIDE listing CREATION queue (earned 2026-08-03: narestco, RX,
     HomeLyft all clean end-to-end; enrolled on Santino's call same day —
     new signups like Reign get their citations built automatically). Up to
     TWO clients per night (velocity rule — Houzz taught us portals throttle
     bursts of new accounts) whose citations-build platform_status shows
     homeguide=todo AND whose NAP is complete: GBP-primary phone, address or
     SAB city+zip, logo in sites/{slug}/public/images/. NEWEST clients
     first. Driver: playbooks/homeguide_state_machine.py — HomeGuide has no
     email-verification gate, so it is fully unattended-safe.
  3. HOUZZ is NOT unattended yet: signup requires an email confirmation code
     that only Claude-side Gmail access can fetch, so Houzz stays
     session-driven — the sweep just LOGS which clients are Houzz-pending so
     the next session picks them up.
     TODO(houzz-unattended): Gmail API with a delegated scope on
     contact@restorationai.io would let the sweep read the 'Your
     Confirmation Code' email itself and graduate Houzz into this queue.

Safety rules (all inherited from the chassis, none waived here): kill
switch checked before every account creation and re-checked between runs;
max 2 new accounts per portal per night; challenge_detected() inside a
driver pauses EVERYTHING (kill switch set) and the queue stops; success is
recorded via the driver's ledger + record_listing + work_log writes. The
WORK QUEUE is the Ops Attention board itself: the scheduled citations audit
detects new live listings and updates the cards, so completion is always
detection-based, never honor-system.

Run: python3 -m browser_agent.sweep                (launchd: nightly 21:30 local)
     python3 -m browser_agent.sweep --queue-dry-run  (print tonight's picks, no browser)
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import string
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from browser_agent.chassis import (CREDS_PATH, ROOT, Session, ledger,  # noqa: E402
                                   paused)
from client_ops_sync import _sb, slug_map  # noqa: E402

PORTAL_NIGHTLY_CAP = 2  # velocity: max NEW accounts per portal per night
RUN_TIMEOUT_S = 45 * 60  # one homeguide creation incl. search-index waits


def bing_sync(s: Session) -> dict:
    # SSO (Bing sessions are session-scoped — every run signs in fresh)
    s.page.goto("https://www.bing.com/forbusiness/genericLogin",
                wait_until="domcontentloaded", timeout=60000)
    s.page.wait_for_timeout(6000)
    if "genericLogin" in s.page.url:
        try:
            # Sign in through Google's GSI button. Click the ELEMENT inside
            # the accounts.google.com/gsi/button iframe — the old fixed
            # coordinate (1174, 295) is whatever the layout happened to be on
            # 08-01 and missed entirely on 08-04 (30s timeout waiting for a
            # popup that was never opened). Coordinates stay as the fallback.
            gsi = next((f for f in s.page.frames if "gsi/button" in f.url), None)
            with s._ctx.expect_page(timeout=45000) as pi:
                if gsi:
                    gsi.locator("div[role=button], button").first.click(timeout=15000)
                else:
                    s.page.mouse.click(1174, 295)
                    s.page.wait_for_timeout(1500)
                    s.page.keyboard.press("Enter")
            pop = pi.value
            pop.wait_for_load_state("domcontentloaded")
            pop.wait_for_timeout(4000)
            try:
                if pop.locator("text=contact@restorationai.io").count():
                    pop.locator("text=contact@restorationai.io").first.click(timeout=8000)
            except Exception:
                pass
            for _ in range(6):
                try:
                    if pop.is_closed():
                        break
                    pop.wait_for_timeout(2500)
                except Exception:
                    break
        except Exception as e:
            return {"error": f"sso failed: {str(e)[:80]}"}
    s.page.wait_for_timeout(6000)
    s.page.goto("https://www.bing.com/forbusiness/multipleEntities",
                wait_until="domcontentloaded", timeout=60000)
    s.page.wait_for_timeout(8000)
    if "genericLogin" in s.page.url:
        return {"error": "not signed in after sso"}
    try:
        s.page.get_by_text(re.compile("^Sync$", re.I)).first.click(timeout=6000)
        s.page.wait_for_timeout(45000)
    except Exception:
        pass  # Sync button absent = nothing new; dashboard still verifies
    s.page.goto("https://www.bing.com/forbusiness/multipleEntities",
                wait_until="domcontentloaded", timeout=60000)
    s.page.wait_for_timeout(8000)
    state = bing_dashboard_state(s.page)
    shot = s.audit_shot("nightly-sync")
    state["shot"] = shot
    return state


# "Pending publish" is Bing's own server-side queue — NOT our work item.
# Investigated end-to-end 2026-08-04 (Santino asked why 6 of 8 sat pending
# since the 08-01 GBP batch import). What the dashboard actually says:
#   * header counts: Total listings 8 / Published 2 / Needs review 0 /
#     Suspended 0  -> Bing has NO complaint about any listing.
#   * on the 08-02 dashboard every pending row carried the sub-label "New
#     import from Google" — they are exactly the 6 brought over by the 08-01
#     import (Home Pride/Crew, already published, never carried it). Bing had
#     dropped that label by 08-04.
#   * each pending listing's singleEntity page states, verbatim:
#       "Your verification is done, and now we're publishing your listing."
#       "Publishing ETA is 7-12 days. We will notify you when your listing
#        is published."
# So: verification is COMPLETE, no field is missing, and there is NO publish
# / submit / resubmit control anywhere in the UI (the only buttons on a
# pending listing are Sync and View analytics). Home Pride + Crew are
# published simply because they predate the batch. Nothing accelerates this;
# do not "fix" pending listings, do not re-import (that restarts the clock),
# and do not open a support ticket inside the stated ETA window.
# The sweep's job is therefore DETECTION ONLY: record the queue each night so
# the flip to Published is caught the day it happens.
_BING_COUNTS = ("Total listings", "Published", "Needs review", "Suspended")


def bing_dashboard_state(page) -> dict:
    """Parse the Bing Places dashboard into {counts, rows}.

    The UI renders each header stat as label-then-value on SEPARATE lines
    ("Total listings\\n8\\nPublished\\n2"). The old regex required a colon
    ("Total listings: 8"), which the UI stopped emitting — so every nightly
    run since logged 'count unparsed' (ledger 08-03/08-04) and we lost the
    published-count trail. Accept BOTH shapes.
    """
    body = page.inner_text("body")
    counts: dict[str, int] = {}
    for label in _BING_COUNTS:
        m = re.search(rf"{re.escape(label)}\s*[:\n]\s*(\d+)", body)
        if m:
            counts[label] = int(m.group(1))

    rows: list[dict] = []
    try:
        n = page.locator("[role=row]").count()
        for i in range(n):
            cells = page.locator("[role=row]").nth(i).inner_text().split("\n")
            cells = [c.strip() for c in cells if c.strip()]
            if not cells or cells[0] == "Name and address":
                continue
            status = next((c for c in cells if re.match(
                r"^(Published|Pending publish|Needs review|Suspended)$", c)), None)
            if not status:
                continue
            rows.append({
                "name": cells[0],
                "status": status,
                # "New import from Google" marked GBP-batch imports on the
                # 08-02 dashboard (see that day's audit shot). Bing had
                # dropped the sub-label by 08-04, so this is best-effort and
                # currently False everywhere — keep reading it in case the
                # label returns, but never gate logic on it.
                "new_import": any("New import from Google" in c for c in cells),
            })
    except Exception as e:
        print(f"  [bing] row scrape failed: {str(e)[:80]}", file=sys.stderr)
    return {"counts": counts, "rows": rows}


# ---- per-client attribution + the public URL of a PUBLISHED listing --------
# Until 2026-08-04 the dashboard read produced ONE agency-account ledger row
# whose detail named five clients in prose, so the setup ledger could only
# ever recognise those five — Coastal and Mold Solutionz, imported by later
# syncs, were invisible, and so was every future client. And nothing ever
# captured the listing's PUBLIC url, so a published Bing listing had no way
# to reach the client's Business Listings card.
#
# Pinned 2026-08-04 on the real dashboard: a listing's detail page carries
#   https://www.bing.com/maps?ss=ypid.YN841719F0A3CAB26F&mkt=en-US
# ONLY once it is Published (Crew had it; Coastal, pending, had no such link).
# That link is therefore both the public URL and independent proof of "live".
_PUBLIC_RE = re.compile(r"https://www\.bing\.com/maps\?ss=ypid\.[A-Za-z0-9]+")


def _name_key(name: str) -> str:
    """Normalized business name — Bing carries the GBP title, which drifts
    from the app's company name by legal suffix and spacing. Mirrors
    setup_ledger._bing_name_key; keep the two in step."""
    parts: list[str] = []
    for w in re.split(r"[^A-Za-z0-9]+", name or ""):
        if not w:
            continue
        parts += [p.lower() for p in
                  (re.findall(r"[A-Z][a-z0-9]*|[A-Z]+(?![a-z])|[a-z0-9]+", w) or [w])]
    drop = {"inc", "llc", "l", "c", "co", "corp", "the", "and", "of", "ltd"}
    return " ".join(p for p in parts if p and p not in drop)


def _company_by_name() -> dict:
    """{normalized name: company_id} for ACTIVE companies. Suspended/paused
    clients are excluded (Santino 2026-09-05: the daily sweep was still
    ledgering Mold Solutionz — Suspended — because the old comment's "paused
    included" rationale outlived the account). Their dashboard rows now go
    unattributed and untouched."""
    out: dict[str, str] = {}
    inactive = {"paused", "suspended", "cancelled", "canceled", "churned",
                "inactive", "archived"}
    try:
        for c in _sb("GET", "/rest/v1/companies?select=id,name,status",
                     prefer="return=representation") or []:
            if str(c.get("status") or "").lower() in inactive:
                continue
            key = _name_key(c.get("name") or "")
            if key:
                out.setdefault(key, c["id"])
    except Exception as e:
        print(f"  [bing] company map failed: {str(e)[:80]}", file=sys.stderr)
    return out


def bing_capture_listings(s, rows: list[dict]) -> list[str]:
    """Attribute each dashboard row to a client, ledger its publish state, and
    for PUBLISHED listings capture the public URL into the client's Business
    Listings card via record_listing(). Read-only on Bing's side."""
    if not rows:
        return []
    by_name = _company_by_name()
    notes: list[str] = []
    for row in rows:
        name, status = row.get("name") or "", row.get("status") or ""
        cid = by_name.get(_name_key(name))
        published = status.lower() == "published"
        public_url = None
        if published:
            try:
                s.page.get_by_text(name, exact=False).first.click(timeout=15000)
                s.page.wait_for_timeout(8000)
                m = _PUBLIC_RE.search(" ".join(s.page.eval_on_selector_all(
                    "a[href]", "els => els.map(e => e.href)")))
                public_url = m.group(0) if m else None
            except Exception as e:
                notes.append(f"{name}: detail page unreadable ({str(e)[:60]})")
            finally:
                s.page.goto("https://www.bing.com/forbusiness/multipleEntities",
                            wait_until="domcontentloaded", timeout=60000)
                s.page.wait_for_timeout(6000)
        if not cid:
            notes.append(f"{name}: on Bing but matches no company we track")
            continue
        outcome = "published" if published else (
            "pending_publish_bing_queue" if status.lower() == "pending publish"
            else "attention")
        detail = (f"Bing Places '{name}' status={status}."
                  + (f" Public listing: {public_url}" if public_url else "")
                  + ("" if published else
                     " Bing-side publish queue (verification done, ETA 7-12 "
                     "days) — nothing to action."))
        ledger(cid, "bing-places", "bing-publish-status", outcome,
               detail=detail, live=False,
               meta={"status": status, "public_url": public_url,
                     "source": "nightly-sweep"})
        if published and public_url:
            try:
                from listings import record_listing
                record_listing(cid, "bing_places", public_url, status="found")
                notes.append(f"{name}: PUBLISHED -> {public_url}")
            except Exception as e:
                notes.append(f"{name}: record_listing failed ({str(e)[:60]})")
        elif published:
            notes.append(f"{name}: PUBLISHED but no public URL on the page")
    return notes


# ------------------------------------------------------------------ queue
def _brand(slug: str) -> dict:
    try:
        return json.loads((ROOT / "clients" / slug / "plan-input.json")
                          .read_text()).get("brand", {})
    except Exception:
        return {}


def _client_rec_gbp(slug: str) -> dict:
    try:
        return json.loads((ROOT / "clients" / f"{slug}.json")
                          .read_text()).get("gbp") or {}
    except Exception:
        return {}


def _logo_exists(slug: str) -> bool:
    imgdir = ROOT / "sites" / slug / "public" / "images"
    return (imgdir / "logo.png").exists() or (imgdir / "logo.webp").exists()


def _gbp_primary(cid: str, slug: str) -> tuple[str | None, str | None, str]:
    """(phone_digits, gbp_street_line, source) — the citations phone policy is
    GBP-primary (Santino 2026-07-31). Source order mirrors citations_audit's
    google_listing: live GBP API via the client's connection, then the
    clients/{slug}.json gbp snapshot, then the companies row."""
    try:
        import gbp as _gbp
        place = (_gbp._place_id_from_connection(cid)
                 or _brand(slug).get("place_id")
                 or _client_rec_gbp(slug).get("place_id"))
        tok = _gbp.get_access_token(cid) if place else None
        loc = _gbp.find_location(tok, place) if tok and place else None
        if loc:
            ph = re.sub(r"\D", "", (loc.get("phoneNumbers") or {})
                        .get("primaryPhone") or "")[-10:]
            addr_lines = ((loc.get("storefrontAddress") or {})
                          .get("addressLines") or [])
            if ph:
                return ph, (addr_lines[0] if addr_lines else None), "gbp_api"
    except Exception:
        pass
    snap = re.sub(r"\D", "", _client_rec_gbp(slug).get("listing_phone") or "")[-10:]
    if snap:
        return snap, None, "client_record"
    return None, None, "companies_row"  # caller falls back to companies.phone


def _gen_password() -> str:
    """Guarantee lower+upper+digit+symbol (Houzz lesson 2026-08-01: the
    generator MUST cover every class or portal validators reject it)."""
    core = [secrets.choice(string.ascii_lowercase),
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.digits),
            secrets.choice("!#%+@")]
    core += [secrets.choice(string.ascii_letters + string.digits)
             for _ in range(12)]
    secrets.SystemRandom().shuffle(core)
    return "".join(core)


def _ensure_homeguide_creds(slug: str) -> dict:
    """Policy: creds are SAVED to ~/.rankai/portal-creds.json BEFORE any
    submit — the driver refuses to run without them. Idempotent."""
    data = {}
    if CREDS_PATH.exists():
        data = json.loads(CREDS_PATH.read_text())
    hg = data.setdefault("homeguide", {})
    if slug not in hg:
        hg[slug] = {"email": f"contact+{slug}@restorationai.io",
                    "password": _gen_password(),
                    "created": datetime.now(timezone.utc).isoformat(),
                    "note": "generated by nightly sweep (creds exist before "
                            "any submit)"}
        CREDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        CREDS_PATH.write_text(json.dumps(data, indent=1))
        CREDS_PATH.chmod(0o600)
    return hg[slug]


def select_creation_queue() -> tuple[list[dict], list[str], list[str]]:
    """Tonight's HomeGuide picks (max PORTAL_NIGHTLY_CAP, newest clients
    first) + the Houzz-pending slug list + skip notes for the log.

    Eligibility: citations-build platform_status homeguide=todo, no listing
    already recorded in the live citations metadata (the ledger snapshot can
    lag a same-night creation by ~4h — RX/HomeLyft 2026-08-03), no prior
    homeguide-create ledger outcome, and complete NAP (GBP-primary phone,
    address or SAB city+zip, logo in sites/{slug}/public/images/)."""
    sm = slug_map()  # cid -> slug
    rows = _sb("GET", "/rest/v1/marketing_setup_ledger?item_key=eq.citations-build"
               "&select=company_id,evidence", prefer="return=representation") or []
    cand = {}  # cid -> platform_status
    for r in rows:
        ps = (r.get("evidence") or {}).get("platform_status") or {}
        if r["company_id"] in sm:
            cand[r["company_id"]] = ps
    if not cand:
        return [], [], ["no citations-build ledger rows"]

    cid_in = "in.(" + ",".join(f'"{c}"' for c in cand) + ")"
    cos = {c["id"]: c for c in _sb(
        "GET", f"/rest/v1/companies?id={cid_in}"
        "&select=id,name,phone,address,city,state,postal_code,website,"
        "created_at,status",
        prefer="return=representation") or []}
    # ACCOUNT-STATUS GATE (Santino 2026-08-04: Mold Solutionz paused after
    # the client cancelled — its citations-build ledger row still said
    # homeguide=todo and this queue never re-checked companies.status, so
    # Mold was next in line for tonight's HomeGuide creation). The ledger
    # only GATHERS active clients but never retires rows on pause, so the
    # queue must check live status itself. Statuses are mixed-case in prod
    # ('Active' vs 'paused') — compare lowercased; unknown/empty stays
    # eligible (legacy rows).
    _inactive = {"paused", "cancelled", "canceled", "churned", "inactive",
                 "archived"}
    for cid in list(cand):
        st = str((cos.get(cid) or {}).get("status") or "").strip().lower()
        if st in _inactive:
            slug = sm.get(cid, cid)
            print(f"  [queue] {slug}: account status '{st}' — excluded from "
                  "creation queue")
            cand.pop(cid, None)
    if not cand:
        return [], [], ["all candidates paused/cancelled"]
    # Live citations metadata beats the ledger snapshot for "already live".
    live_nap = {}
    for r in _sb("GET", f"/rest/v1/user_integrations?client_id={cid_in}"
                 "&provider=eq.citations&select=client_id,connection_metadata",
                 prefer="return=representation") or []:
        md = r.get("connection_metadata") or {}
        live_nap[r["client_id"]] = {
            "nap": md.get("nap_audit") or {}, "urls": md.get("citation_urls") or {}}
    # Any prior create attempt (done/exists/blocked/review) = not tonight's
    # unattended work — a session owns retries and edge states.
    prior = {}
    for r in _sb("GET", "/rest/v1/browser_agent_actions"
                 "?action=eq.homeguide-create&select=company_id,outcome",
                 prefer="return=representation") or []:
        if r.get("outcome") != "dry_run":
            prior.setdefault(r["company_id"], set()).add(r.get("outcome"))

    def _hg_live(cid: str) -> bool:
        ln = live_nap.get(cid) or {}
        st = ((ln.get("nap") or {}).get("homeguide") or {}).get("status")
        return bool(st in ("found", "discrepancy") or (ln.get("urls") or {}).get("homeguide"))

    picks: list[dict] = []
    houzz_pending: list[str] = []
    notes: list[str] = []
    ordered = sorted(cand, key=lambda c: (cos.get(c) or {}).get("created_at") or "",
                     reverse=True)  # newest clients first — Reign tops the list
    for cid in ordered:
        slug = sm[cid]
        ps = cand[cid]
        if (ps.get("houzz") or {}).get("status") == "todo" and not (
                ((live_nap.get(cid) or {}).get("nap") or {}).get("houzz")):
            houzz_pending.append(slug)
        if (ps.get("homeguide") or {}).get("status") != "todo":
            continue
        if _hg_live(cid):
            notes.append(f"{slug}: homeguide already live (ledger snapshot lags)")
            continue
        if prior.get(cid):
            notes.append(f"{slug}: prior homeguide-create outcome "
                         f"{sorted(prior[cid])} — session-owned, not queued")
            continue
        co = cos.get(cid) or {}
        zipc = ((co.get("postal_code") or "").strip()
                or (_brand(slug).get("postal_code") or "").strip())
        has_addr = bool((co.get("address") or "").strip())
        sab_ok = bool((co.get("city") or "").strip() and zipc)
        if not (has_addr or sab_ok) or not zipc:
            notes.append(f"{slug}: NAP incomplete (no address and no city+zip)")
            continue
        if not _logo_exists(slug):
            notes.append(f"{slug}: NAP incomplete (no logo in sites/{slug}/public/images)")
            continue
        if len(picks) >= PORTAL_NIGHTLY_CAP:
            notes.append(f"{slug}: eligible but over the {PORTAL_NIGHTLY_CAP}/night "
                         "velocity cap — next night")
            continue
        phone, gbp_street, src = _gbp_primary(cid, slug)
        if not phone:
            phone = re.sub(r"\D", "", co.get("phone") or "")[-10:]
        if not phone:
            notes.append(f"{slug}: NAP incomplete (no GBP-primary or companies phone)")
            continue
        picks.append({"slug": slug, "cid": cid, "phone": phone,
                      "phone_source": src, "gbp_street": gbp_street,
                      "zip": zipc, "name": co.get("name"),
                      "created_at": co.get("created_at")})
    return picks, houzz_pending, notes


def run_homeguide_queue(picks: list[dict]) -> None:
    for i, p in enumerate(picks):
        why = paused()
        if why:  # a challenge in an earlier run pauses everything mid-queue
            print(f"homeguide queue stopped before {p['slug']} — kill switch: {why}")
            ledger(p["cid"], "nightly-sweep", "homeguide-queue", "skipped_kill_switch",
                   detail=str(why)[:200])
            break
        _ensure_homeguide_creds(p["slug"])
        overrides = {"phone": p["phone"]}
        if p.get("gbp_street") and p.get("phone_source") == "gbp_api":
            overrides["address"] = p["gbp_street"]  # the clean GBP street line
        print(f"\n== homeguide create {i + 1}/{len(picks)}: {p['slug']} "
              f"(phone {p['phone']} via {p['phone_source']})", flush=True)
        try:
            r = subprocess.run(
                [sys.executable, "-m",
                 "browser_agent.playbooks.homeguide_state_machine",
                 p["slug"], json.dumps(overrides)],
                cwd=str(ROOT), timeout=RUN_TIMEOUT_S)
            outcome = {0: "done", 1: "review_needed", 2: "guard_blocked",
                       3: "blocked_verification"}.get(r.returncode,
                                                      f"exit_{r.returncode}")
        except subprocess.TimeoutExpired:
            outcome = "timeout"
        # The driver itself writes the authoritative ledger + record_listing +
        # work_log on success; this line is the sweep's own queue trail.
        ledger(p["cid"], "nightly-sweep", "homeguide-queue", outcome,
               detail=f"phone={p['phone']} ({p['phone_source']})", live=True)
        print(f"   -> {outcome}", flush=True)


def access_sweep(dry_run: bool = False) -> None:
    """Take every scrap of Google access we can take ourselves, nightly.

    Santino 2026-08-05: "asking a client for things we already have access to
    is a big no-no" — and the strongest version of that rule is not a better
    guard on the ask, it is having nothing left to ask for by morning.

    Two passes, no browser, both idempotent:

      1. ads_link_accept — PENDING Google Ads / Local Services manager links
         approved with the CLIENT'S OWN admin grant. This is why the step
         lives on Santino's Mac and not on Railway: reaching the MCC needs
         GOOGLE_ADS_DEVELOPER_TOKEN + GOOGLE_ADS_MCC_CUSTOMER_ID, which the
         Railway ops-worker has never had (the same gap that left
         lsa_ask_guard inert in production until 08-05).
      2. gbp_admin_invite — the agency manager seat on each GBP, invited AND
         accepted through the invitations inbox. Runs daily on Railway too;
         re-running here is a cheap no-op (7-day memo) and keeps the memo the
         concierge's ask guard reads warm.

    Whatever these two cannot get is exactly the list of things a human still
    has to ask for, and both passes report it as attention lines.
    """
    print("\n== access sweep (no browser)", flush=True)
    try:
        from ads_link_accept import accept_pending_links
        results, attention = accept_pending_links(dry_run=dry_run)
        for r in results:
            print(f"   ads-link {r['outcome']:14} {r['slug']:32} "
                  f"{r['account']}  {r['detail'][:70]}")
        if not results:
            print("   ads-link: no pending manager links")
        for a in attention:
            print("   ATTENTION:", a)
        if results and not dry_run:
            ledger(None, "nightly-sweep", "ads-link-accept",
                   "attention" if attention else "done",
                   detail="; ".join(f"{r['slug']}:{r['outcome']}"
                                    for r in results)[:380], live=True)
    except Exception as e:  # noqa: BLE001 — never let this stop the sweep
        print(f"   ads-link pass failed: {str(e)[:160]}")

    try:
        from gbp_admin_invite import ensure_agency_manager
        res, attention = ensure_agency_manager(dry_run=dry_run)
        changed = {s: v for s, v in res.items() if v.get("changed")}
        owed = {s: v for s, v in res.items() if v["state"] == "owner_must_add"}
        print(f"   gbp-seat: {len(res)} checked, {len(changed)} changed, "
              f"{len(owed)} need the owner")
        for s, v in sorted(changed.items()):
            print(f"     * {s}: {v['state']} ({v['note']})")
        for a in attention:
            print("   ATTENTION:", a)
        if changed and not dry_run:
            ledger(None, "nightly-sweep", "gbp-manager-seat", "done",
                   detail="; ".join(f"{s}:{v['state']}"
                                    for s, v in changed.items())[:380],
                   live=True)
    except Exception as e:  # noqa: BLE001
        print(f"   gbp-seat pass failed: {str(e)[:160]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue-dry-run", action="store_true",
                    help="print tonight's creation-queue selection and exit "
                         "(no browser, no writes)")
    ap.add_argument("--skip-bing", action="store_true")
    ap.add_argument("--skip-access", action="store_true",
                    help="skip the Google access pass (Ads manager links + "
                         "GBP agency seat)")
    ap.add_argument("--access-only", action="store_true",
                    help="run ONLY the Google access pass, then exit")
    a = ap.parse_args()

    # The access pass is API-only, so it runs BEFORE the kill switch is
    # consulted: the switch exists to stop unattended BROWSER automation, and
    # nothing here drives a browser. It is also the cheapest, highest-value
    # thing in the sweep — every link it clears is a text nobody has to send.
    if a.access_only:
        access_sweep(dry_run=False)
        return 0
    if not (a.skip_access or a.queue_dry_run):
        access_sweep(dry_run=False)

    # Citations rotation (2026-08-21, un-parked by Santino): tracker-driven
    # nightly pass — write-back outcomes, verify pending listings, pick
    # tonight's 3 companies, flag supervised corrections, streak watchdog.
    # API-only (no browser), so it runs before the kill switch like the
    # access pass; a raise must never take the sweep down.
    if not a.queue_dry_run:
        try:
            from browser_agent.citations_rotation import rotate
            for _ln in rotate(dry_run=False):
                print("  ROTATE: " + _ln)
        except Exception as _e:  # noqa: BLE001
            print(f"  ROTATE: errored: {str(_e)[:120]}")

    if a.queue_dry_run:
        picks, houzz_pending, notes = select_creation_queue()
        print("HomeGuide picks (max %d/night, newest first):" % PORTAL_NIGHTLY_CAP)
        for p in picks:
            print(f"  {p['slug']}  phone={p['phone']} ({p['phone_source']})"
                  f"  zip={p['zip']}  gbp_street={p.get('gbp_street')}"
                  f"  signed={str(p.get('created_at'))[:10]}")
        print("Houzz pending (session-driven — email code needs Claude-side "
              "Gmail):", ", ".join(houzz_pending) or "none")
        for n in notes:
            print("  note:", n)
        return 0

    why = paused()
    if why:
        print(f"sweep skipped — kill switch: {why}")
        return 0

    if not a.skip_bing:
        s = Session(playbook="nightly-sweep", slug=None, live=True).start(headless=False)
        try:
            result = bing_sync(s)
            counts = result.get("counts") or {}
            rows = result.get("rows") or []
            pending = [r["name"] for r in rows if r["status"] == "Pending publish"]
            attention = [f"{r['name']}:{r['status']}" for r in rows
                         if r["status"] in ("Needs review", "Suspended")]
            if result.get("error"):
                # Previously EVERY outcome was hardcoded "done" — the 08-03
                # 05:39 ledger row says done/"sso failed", which is a lie the
                # board can't act on.
                outcome, detail = "failed", result["error"]
            else:
                outcome = "attention" if attention else "done"
                detail = (f"listings={counts.get('Total listings')} "
                          f"published={counts.get('Published')} "
                          f"needs_review={counts.get('Needs review')} "
                          f"suspended={counts.get('Suspended')} "
                          f"pending_publish={len(pending)} shot={result.get('shot')}")
                if attention:
                    detail += " | ATTENTION: " + ", ".join(attention)
            print("bing:", detail)
            if pending:
                # Bing-side publish queue (7-12 day ETA, verification already
                # done). Informational — nobody should action these.
                print("bing pending publish (Bing-side queue, no action "
                      "available):", ", ".join(pending))
            if rows:
                # Per-client attribution + public-URL capture. Without this
                # the dashboard state stays a single agency-account blob that
                # no client card can read (2026-08-04 fix).
                for n in bing_capture_listings(s, rows):
                    print("  bing listing:", n)
            ledger(None, "nightly-sweep", "bing-sync", outcome, detail=detail,
                   live=True, meta={"counts": counts, "rows": rows,
                                    "pending_publish": pending})
        finally:
            s.stop()  # the creation drivers open their own Session — never two at once

    picks, houzz_pending, notes = select_creation_queue()
    for n in notes:
        print("queue note:", n)
    if houzz_pending:
        # Session pickup list — Houzz signups need the emailed confirmation
        # code (Claude-side Gmail), so they are NOT run here. See the
        # TODO(houzz-unattended) in the module docstring.
        print("houzz pending (session-driven):", ", ".join(houzz_pending))
        ledger(None, "nightly-sweep", "houzz-pending", "noted",
               detail=", ".join(houzz_pending)[:380])
    if picks:
        ledger(None, "nightly-sweep", "homeguide-queue", "selected",
               detail=", ".join(p["slug"] for p in picks))
        run_homeguide_queue(picks)
    else:
        print("homeguide queue: no eligible clients tonight")
    return 0


if __name__ == "__main__":
    sys.exit(main())
