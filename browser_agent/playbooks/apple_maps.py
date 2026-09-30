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
  * PROBE RESULT 2026-08-16 (run 1): access request SENT from the portal
    (Settings -> Integrations -> API -> Request API Access; services =
    Listing management + Marketing; "work directly with all" owners;
    Business or Location Data, total count 30). Portal confirms "requestor
    will receive an email with next steps". Even once granted, production
    is a staged pipeline (Integration tests -> Data Qualification ->
    Production), so browser creation stays the path for now. In-portal API
    docs: https://business.apple.com/docs (login required). Webhooks and
    OAuth Apps both gate on API access.

SESSION / LOGIN (measured 2026-08-16, run 1):
  * The Apple Business session does NOT survive a browser restart: the
    session cookies are session-scoped, and a fresh login re-challenges
    2FA even after "Trust" was clicked the login before. So EVERY run
    starts with one supervised login: email + stored password, then the
    6-digit SMS code Apple texts to the account phone ending 49 — the
    code MUST be relayed live by Santino/the coordinator (it lands on the
    company's CRM-managed number; it is NOT in our Twilio fleet). Never a
    code that wasn't relayed for THIS login (safety rule 2).
  * WORKING RUN PATTERN (what run 1 did): background process launches the
    suite profile with --remote-debugging-port=9223 (allowed on a
    NON-default user-data-dir), walks to the 2FA prompt, HOLDS the browser
    open; the code is typed in over CDP when relayed; every subsequent
    step runs over CDP from short-lived scripts against the held browser.
    Do the whole run inside that one held session.
  * CDP reuse of Santino's own Chrome does NOT work on Chrome 151 — see
    run-1 notes at the bottom.

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
anyone "fixes" a pending listing):
  In Review          Portal's own state after create. Verbatim banner:
                     "Your location verification is in review. Reviews can
                     take up to 5 days to complete. Updates will be
                     published once approved." NOT actionable — no button,
                     no verification step offered or demanded. Ledger
                     'submitted_pending' and wait; do NOT resubmit.
  (published)        Expected terminal success — public place URL appears;
                     then listings.record_listing(cid,'apple_maps',url) +
                     ledger 'done'. Not yet observed (run 1 was today).
  blocked            Portal demanded something only Santino/the client has.

Supervised until THREE clean completions. Run 1 (2026-08-16): narestco +
restorationxpress + homepriderestorationandcleaning all created In Review
same night; crew HELD on the zip question. Run 2 should also CHECK the run-1
listings' states and record_listing any that published.
"""
from __future__ import annotations

import re

from ..chassis import Session, company_truth, ledger, portal_creds
from ..chassis import _sb  # chassis re-exports client_ops_sync._sb

# The authenticated home. The marketing root (business.apple.com/) shows a
# "Sign In" button even WITH a live session, so never use it for signed-out
# detection — /main/home redirects to /login only when the session is gone.
PORTAL = "https://business.apple.com/main/home"
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
            # PHONE = the REAL line, never the GBP primary (a tracking number
            # wherever call tracking is live; policy corrected 09-26,
            # sweep incident 09-28/29). The company row is the NAP truth.
            from ..chassis import company_truth
            return {
                "phone": (company_truth(company_id) or {}).get("phone"),
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
    page.wait_for_timeout(6000)  # SPA settles / login redirect happens
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
    if "idmsa.apple.com" in url or "/login" in url.lower():
        creds = portal_creds(CREDS_KEY)  # presence check only — never typed here
        have = "creds present" if creds else "NO CREDS"
        login_needed(
            session, "apple-signin",
            "Apple Business session DROPPED (business.apple.com/main/home "
            f"redirected to login; {have}). Re-login supervised: `python3 -m "
            "browser_agent login`, sign in at business.apple.com as the "
            "agency account, enter the SMS 2FA code Apple texts to the "
            "account phone (..49), click Trust, close the window. Then "
            "re-run the playbook.")

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
# 2026-08-16, supervised. Santino relayed the SMS 2FA code live mid-run.
# THREE locations created, all "In Review": narestco (apple location id
# 1536142091978017843), restorationxpress (1540645688291887667), homepride
# (1549652888091888240). API access request sent the same session.
#
# LOGIN / SESSION MECHANICS (pinned):
#  * Chrome 151 IGNORES --remote-debugging-port on the DEFAULT user-data-dir
#    (Chrome 136+ change), and a cookie jar copied to a scratch dir will NOT
#    decrypt (app-bound key wrapping; even the Google session failed to
#    carry) — reusing Santino's own Chrome over CDP is a dead end on this
#    Chrome. What DOES work: launch the SUITE profile with
#    --remote-debugging-port=9223 (non-default dir = allowed), hold it open
#    from a background process, and drive each step over CDP
#    (connect_over_cdp) from short-lived scripts. Login: business.apple.com
#    /login -> email (input[type=text/email]) -> Continue -> password
#    (input[type=password]) -> SMS code to the account phone (..49) -> six
#    one-box inputs (input[aria-label*='igit'], type the whole code into the
#    first) -> button 'Trust' -> session persists in the profile.
#
# ADD-LOCATION WIZARD (business.apple.com -> Brands -> Locations -> Add a
# Location; /companies/{org}/maps/locations/new; 4 steps, 5 with new brand):
#  * Apple custom elements (apl-*): labels/footers intercept pointer events,
#    so click() often fails — el.focus() + page.keyboard.insert_text() is
#    the reliable fill; Playwright locators DO pierce the shadow DOM but
#    page.evaluate(querySelectorAll) does NOT.
#  * Step 1 (details): aria-labels = Display Name / Primary Category /
#    Phone Number / Location Website (Optional) / Partner's Location ID
#    (use our slug). CATEGORY TAXONOMY: typing 'water damage' surfaces
#    exactly one option, "Damage Restoration Service" — that is Apple's
#    category for the whole fleet. Phone accepts bare digits, renders
#    +1 (xxx) xxx-xxxx.
#  * Step 2 (address): aria-labels Street / Unit, Suite, etc. (Optional) /
#    City / Zip Code; State is role=combobox (click, then click the full
#    state name; search box optional). TRAP: the Street field pops an
#    address-AUTOSUGGEST list (apl-option-list, automation id
#    full-thoroughfare__input__list) that OVERLAYS the State control and
#    Escape does NOT close it — two clicks on neutral ground (the page
#    heading area) dismiss it. TRAP 2: 'text=State'-style loose clicks hit
#    the Country/Region dropdown or day toggles; scope by role+name.
#    Step2->3 can hang on a spinner; goto .../locations/welcome and click
#    Add a Location — the wizard RESUMES at step 2 with step 1 preserved
#    (step 2 fields must be refilled).
#  * Step 3 (hours): 'Add Hours' seeds M-F 9-5 + a Sun/Sat 'Closed' row.
#    Day circles are role=button name=Sunday..Saturday (FIRST occurrence =
#    row 1). 24/7 = add Sunday+Saturday to row 1, click the Opens input
#    (the input whose value is '9:00 AM') and pick the '24 Hours' option
#    (Closes disables), then Remove the leftover Closed row. Place-card
#    preview should read 'Every Day, Open 24 Hours'.
#  * Step 4 (brand): FIRST brand in the org = a plain form (Brand Name +
#    Brand Website (Optional)) and the submit is 'Done'. Once any brand
#    exists it becomes a PICKER — input[type=radio][value=NEW_BRAND] (the
#    radio itself intercepts clicks on the card text), then Next -> brand
#    form (wizard shows 'Step 4 of 5'). Every client gets ITS OWN brand.
#  * Submit lands on /locations/{id}/info (grab the id from the URL) or on
#    the /locations list — click the row for the id. Info page banner =
#    the In Review semantics quoted above; no verification step demanded.
#  * Working driver for the whole flow: scratchpad apple_create.py from this
#    run (config-per-client JSON) — port into this playbook as the
#    unattended path once the 3 supervised runs are clean.
#
# SESSION EPILOGUE, measured after the run: closing the held browser ended
# the session — /main/home redirects to /login on the next launch, and a
# password re-login re-challenged SMS 2FA despite the earlier Trust. So the
# login + hold-open pattern above is the per-run cost until the API lands.
# The marketing root (business.apple.com/) shows "Sign In" even when logged
# in — only the /main/home redirect is a valid signed-out signal.
#
# NEXT RUN: (0) supervised login first (code relayed live); (1) check the
# three In Review listings — on publish, fetch the public maps.apple.com
# URL and record_listing(); (2) create crew once the 57105-vs-57110 zip
# answer lands; (3) watch email for the API-access decision; keys, if
# granted, get stored as apple_business_connect_api in
# ~/.rankai/portal-creds.json (never the repo).
