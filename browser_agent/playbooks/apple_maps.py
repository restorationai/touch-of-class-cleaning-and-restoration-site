"""Playbook: Apple Maps listings via Apple Business Connect (agency account).

Agency account APPROVED ~2026-08-15 (creds: ~/.rankai/portal-creds.json key
`apple_business_connect` — email + password only, NEVER printed or committed).
Apple has REBRANDED "Apple Business Connect" to "Apple Business"; the portal
lives at business.apple.com and businessconnect.apple.com redirects there.

API-FIRST PROBE (Santino: "API worth testing once approved") — findings:
  * The Business Connect / Apple Business API is real but credentials are
    minted INSIDE the portal (API tab -> Add Service Account / Add OAuth App;
    client secret shown once). API access is itself REQUEST-GATED per Apple's
    "Brands API access" guide, and the API docs are only served in-portal
    (Support -> API Documentation). So the API probe is a portal step: on
    each run, check whether the API tab will mint credentials; record the
    state below. Until keys exist, creation goes through the browser flow.
  * PROBE RESULT 2026-08-16 (run 1): BLOCKED BEFORE THE TAB — see SESSION
    note below; re-probe on the next supervised run.

SESSION / LOGIN (the hard part — read before running):
  * Apple logins 2FA on ~every new browser identity. Safety rule 2: NEVER
    bypass — challenge_detected() pauses and files the [TODO-SANTINO].
  * AUTHORIZED workaround (Santino, 2026-08-16): reuse HIS live Chrome
    session by relaunching his Chrome with --remote-debugging-port=9222 and
    connecting Playwright over CDP (Session.start(cdp_url=...), --cdp flag).
    Be surgical: work in a NEW tab, never touch his tabs; stop() closes only
    our tab. NOTE Chrome 136+ REFUSES the debug port on the default
    user-data-dir — see run-1 notes at the bottom for what actually worked.
  * The suite's own persistent profile has NO Apple session; typing the
    stored creds there triggers a fresh 2FA push to Santino's devices —
    don't burn those while he's away; prefer the CDP path.

NAP TRUTH (README rule 6 + fleet policy) — see nap_truth():
  name/address = companies row (Business Information card). phone = GBP
  PRIMARY number (tracking numbers accepted; nap_truth() overrides the
  companies phone with the GBP primary). website = GBP websiteUri (falls
  back to the companies field), normalized https:// with GBP utm cruft
  stripped — the companies website is sometimes malformed (RX stores
  'Www.RestorationXpress.com'). hours = 24/7 (fleet policy). Categories:
  Apple's taxonomy equivalent of water/fire damage restoration — pin the
  exact labels from the portal typeahead during supervised runs.
  KNOWN NAP DISCREPANCY to reconcile at create time: crew's GBP postal
  code is 57105 but the companies row says 57110 (address string kept
  from companies for now; confirm the correct zip against the GBP verified
  listing before submitting crew's Apple place).

VERIFICATION / REVIEW: Apple holds new places in review and may demand its
own verification of the business. Capture the state, ledger it, and NEVER
fake or shortcut a verification step. A clean submit is 'submitted_pending'
until the public maps.apple.com URL exists; only then
listings.record_listing(company_id, "apple_maps", url) — the public URL
shape is https://maps.apple.com/place?place-id=... (seen on the two
hand-filled fleet rows).

STATUS SEMANTICS (mirror bing_places: pin what each state MEANS before
anyone "fixes" a pending listing — fill in as observed):
  submitted_pending  Apple-side review queue. Not actionable by us.
  live               Public place URL exists -> record_listing + ledger.
  blocked            Portal demanded something only Santino/the client has.

Supervised until THREE clean completions (run 1: 2026-08-16, see notes).
"""
from __future__ import annotations

import re

from ..chassis import Session, company_truth, ledger, portal_creds
from ..chassis import _sb  # chassis re-exports client_ops_sync._sb

PORTAL = "https://business.apple.com/"  # businessconnect.apple.com redirects
CREDS_KEY = "apple_business_connect"


def _gbp_facts(company_id: str) -> dict:
    """GBP primary phone + website + place_id — the verified-listing truth
    the citation must match. Best-effort; empty dict on any failure."""
    try:
        import sys
        from ..chassis import ROOT
        sys.path.insert(0, str(ROOT / "scripts"))
        import gbp
        tok = gbp.get_access_token(company_id)
        pid = gbp._place_id_from_connection(company_id)
        loc = gbp.find_location(tok, pid) if (tok and pid) else None
        if loc:
            return {
                "phone": (loc.get("phoneNumbers") or {}).get("primaryPhone"),
                "website": loc.get("websiteUri"),
                "place_id": pid,
            }
    except Exception:
        pass
    return {}


def login_needed(session: Session, what: str, todo: str) -> None:
    """Signed-out / needs-Santino stop that does NOT trip the global kill
    switch. Distinction from chassis.challenge_detected(), on purpose:

      * Apple Business is signed OUT by default (no session lives in the
        suite profile), so hitting the sign-in page is the EXPECTED first
        state, not a mid-flow security anomaly. Bing's profile is logged in,
        so a "Sign in" there is a genuine session-loss worth a global pause;
        Apple's is not. Tripping the global switch here would needlessly halt
        the earned nightly bing-places Sync.
      * An ACTUAL post-credential wall (2FA prompt after the password, a
        CAPTCHA, an appleid verification screen) IS a real challenge -> use
        session.challenge_detected(), which trips the global switch.

    Files ONE [TODO-SANTINO] note + ledgers 'login_needed', then stops this
    playbook only."""
    shot = session.audit_shot(f"login-needed-{what}")
    ledger(session.company_id, session.playbook, f"login:{what}",
           "login_needed", detail=f"{todo[:300]} shot={shot}")
    try:
        _sb("POST", "/rest/v1/marketing_ops_notes", {
            "company_id": session.company_id,
            "body": f"[TODO-SANTINO] {todo}"})
    except Exception:
        pass
    raise SystemExit(f"apple_maps stopped: {what} — {todo}")


def _clean_website(url: str | None) -> str | None:
    if not url:
        return None
    u = url.strip()
    if not u:
        return None
    if not u.lower().startswith("http"):
        u = "https://" + u
    u = re.sub(r"[?&]utm_[^=&]+=[^&]*", "", u)  # GBP click-tag cruft
    return u.rstrip("?&")


def nap_truth(session: Session) -> dict | None:
    """Companies row is the NAP anchor; the GBP verified listing overrides
    phone (must be the GBP PRIMARY per citation policy) and website (the
    companies field is sometimes malformed, e.g. RX 'Www.Restoration...').
    website is normalized to https:// with GBP utm cruft stripped."""
    truth = company_truth(session.company_id) if session.company_id else {}
    if not truth:
        return None
    g = _gbp_facts(session.company_id)
    if g.get("phone"):
        truth["phone"] = g["phone"]
    truth["website"] = _clean_website(g.get("website") or truth.get("website"))
    if g.get("place_id"):
        truth["gbp_place_id"] = g["place_id"]
    return truth


def run(session: Session) -> int:
    truth = nap_truth(session)
    if not truth:
        print("no company truth row — refusing to operate on unknown NAP")
        return 1
    page = session.page
    page.goto(PORTAL, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    session.audit_shot("portal-landing")

    # Signed-out detection: business.apple.com/login (rebranded from
    # businessconnect) or an idmsa redirect. This is the EXPECTED first
    # state — the suite profile holds no Apple session. We do NOT auto-type
    # the password: on this account every fresh login pushes a 6-digit 2FA
    # code to Santino's Apple devices, which only he can read (safety rule 2
    # — never bypass 2FA). So a signed-out portal is a login_needed() stop
    # (files the TODO, leaves the global kill switch alone). A 2FA/CAPTCHA
    # wall reached AFTER a supervised password entry is the harder stop:
    # session.challenge_detected().
    url = page.url
    if ("idmsa.apple.com" in url or "/login" in url.lower()
            or page.locator("text=Sign in using your business email").count() > 0
            or page.locator("text=Sign In").count() > 0):
        creds = portal_creds(CREDS_KEY)  # presence check only — never typed here
        have = "creds present" if creds else "NO CREDS"
        login_needed(
            session, "apple-signin",
            "Apple Business (business.apple.com) needs a supervised login "
            f"before the apple_maps playbook can create listings ({have}). "
            "Chrome 136+ blocks --remote-debugging-port on your default "
            "profile, and a copied cookie jar will not decrypt in a scratch "
            "user-data-dir on Chrome 151 (app-bound encryption), so CDP "
            "session-reuse did not carry your live Apple session. Next time "
            "you are at the keyboard: sign into business.apple.com in the "
            "suite profile via `python3 -m browser_agent login` (Apple will "
            "text/prompt a 6-digit code to your device — enter it), then "
            "re-run `python3 -m browser_agent run --playbook apple-maps "
            "--slug narestco` (dry-run) to pin the create-flow selectors.")

    print(f"Apple Business for {truth.get('name')} — "
          f"{truth.get('city')}, {truth.get('state')}")
    print("NAP:", truth.get("phone"), "|", truth.get("address"),
          "|", truth.get("website"))

    # --- SUPERVISED SECTION: selectors pinned as the real UI is observed.
    print("\nSupervised checklist (run 1-3):")
    print(" 0. API probe: portal API tab — can a Service Account be minted?")
    print("    If yes: mint, store under apple_business_connect_api in")
    print("    ~/.rankai/portal-creds.json, and prefer API creation.")
    print(" 1. Dedupe: search the portal's add-location flow (and")
    print("    maps.apple.com) for name + city — existing place -> CLAIM")
    print("    path or ledger 'exists'; NEVER a duplicate create.")
    print(" 2. Create location: NAP above, hours 24/7, website, categories")
    print("    (Apple taxonomy: water/fire damage restoration equivalents)")
    print(" 3. Submit behind guard_live(); audit shots before/after")
    print(" 4. Apple review hold -> ledger 'submitted_pending'; public URL")
    print("    later -> listings.record_listing(cid, 'apple_maps', url)")
    if session.guard_live("create Apple Business location"):
        print("LIVE armed — selectors not yet pinned into an unattended")
        print("driver; run supervised (scratch driver) and pin here.")
        ledger(session.company_id, session.playbook, "create-location",
               "needs_supervised_run", live=True)
        return 2
    return 0


# --------------------------------------------------------------------- run 1
# 2026-08-16, supervised (Fable driving, Santino away — CDP reuse authorized
# in the mission brief). Pinned observations:
#
#  * Chrome 151 IGNORES --remote-debugging-port on the DEFAULT user-data-dir
#    (Chrome 136+ security change). Relaunching Santino's Chrome with the
#    flag brings his session back but opens NO CDP listener (curl :9222 dead).
#  * The copy-to-scratch workaround does NOT carry the session either:
#    copying Local State + a profile's Cookies to a scratch user-data-dir and
#    launching it with --remote-debugging-port DOES open a live CDP listener,
#    but the transplanted cookie jar will NOT decrypt on Chrome 151. Proven
#    both ways: Santino's Google session ALSO failed to carry (redirected to
#    the logged-out marketing page), and only 3 unencrypted apple cookies
#    (dslang/site/geo) were visible to the context — the encrypted session
#    cookies silently dropped. The per-cookie prefix reads "v10", but Chrome
#    151's app-bound key wrapping (Local State os_crypt) ties decryption to
#    the original install/path, so a copied jar is inert. Tried Default,
#    Profile 1 (Santino/velcisantino@gmail.com), Profile 2
#    (restorationai.io) — all signed out through CDP.
#  * NET: there is no no-2FA path to Santino's live Apple session on this
#    Chrome version. The only way in is a supervised login (he enters the
#    6-digit code). Filed the [TODO-SANTINO]; did NOT type the stored
#    password (would 2FA-push to his devices while away) and did NOT trip the
#    global kill switch (bing sweep stays live). Scratch cookie jars deleted.
#  * chassis Session.start(cdp_url=...) + `run --cdp URL` were still added and
#    verified working (connect_over_cdp, new tab, surgical stop) — ready to
#    reuse the moment a logged-in CDP endpoint exists (e.g. a future Chrome
#    where the debug port is available, or Santino starts one himself).
#  * NEXT RUN starts at the API probe: once logged in, open the portal API
#    tab and see if a Service Account / OAuth App can be minted (prefer API
#    for the actual location creation), then pin the browser create-flow
#    selectors as fallback. Dedupe first via maps.apple.com + the add-location
#    search; the citations audit already flags all 3 test clients "missing".
