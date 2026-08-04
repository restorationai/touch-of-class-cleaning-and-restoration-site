"""Nightly citations sweep — the browser agent's scheduled pass.

Runs only playbook steps that have EARNED unattended status (3 clean
supervised completions). The roster as of 2026-08-03:

  1. BING dashboard Sync + listing verification (earned 2026-08-01) — for
     clients newly GBP-manager-accessible the dashboard import picks them up.
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


def bing_sync(s: Session) -> str:
    # SSO (Bing sessions are session-scoped — every run signs in fresh)
    s.page.goto("https://www.bing.com/forbusiness/genericLogin",
                wait_until="domcontentloaded", timeout=60000)
    s.page.wait_for_timeout(6000)
    if "genericLogin" in s.page.url:
        try:
            with s._ctx.expect_page(timeout=30000) as pi:
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
            return f"sso failed: {str(e)[:80]}"
    s.page.wait_for_timeout(6000)
    s.page.goto("https://www.bing.com/forbusiness/multipleEntities",
                wait_until="domcontentloaded", timeout=60000)
    s.page.wait_for_timeout(8000)
    if "genericLogin" in s.page.url:
        return "not signed in after sso"
    try:
        s.page.get_by_text(re.compile("^Sync$", re.I)).first.click(timeout=6000)
        s.page.wait_for_timeout(45000)
    except Exception:
        pass  # Sync button absent = nothing new; dashboard still verifies
    s.page.goto("https://www.bing.com/forbusiness/multipleEntities",
                wait_until="domcontentloaded", timeout=60000)
    s.page.wait_for_timeout(8000)
    body = s.page.inner_text("body")[:2000]
    m = re.search(r"Total listings:\s*(\d+).*?Published:\s*(\d+)", body, re.S)
    shot = s.audit_shot("nightly-sync")
    return (f"listings={m.group(1)} published={m.group(2)} shot={shot}"
            if m else f"count unparsed shot={shot}")


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
        "&select=id,name,phone,address,city,state,postal_code,website,created_at",
        prefer="return=representation") or []}
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue-dry-run", action="store_true",
                    help="print tonight's creation-queue selection and exit "
                         "(no browser, no writes)")
    ap.add_argument("--skip-bing", action="store_true")
    a = ap.parse_args()

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
            print("bing:", result)
            ledger(None, "nightly-sweep", "bing-sync", "done", detail=result, live=True)
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
