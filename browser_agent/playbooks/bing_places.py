"""Playbook: Bing Places listing create/claim.

Strategy (fastest legitimate path): Bing Places offers "Import from Google
My Business" — since we hold the client's GBP, the import route carries the
whole verified profile over in one flow and usually skips PIN verification
via the Google-account handshake.

Flow (selectors get pinned during the SUPERVISED first run — this playbook
runs supervised until three clean completions, then it earns unattended):
  1. bingplaces.com → signed in as the agency Microsoft account (profile).
     LOGIN URL (Santino 2026-09-27): Bing Places now lives at
     https://www.bing.com/forbusiness/multipleEntities — sign in THERE
     (Bing for Business / Microsoft Advertising account), not at a generic
     Microsoft login page.
  2. Search for the business (name + city) — if a listing already exists,
     switch to CLAIM path; ledger 'exists'.
  3. Else "Import from Google" → pick the client's GBP location → verify the
     imported NAP against company_truth() (REAL phone!) → fix mismatches.
  4. guard_live() → submit. Audit shots before/after.
  5. On verified completion: ledger 'done', update the citations nap_audit
     row, and mark_ledger_item_done ONLY when Bing was the last missing
     us-create platform for the client.

STATUS SEMANTICS — pinned 2026-08-04 after a full dashboard investigation
(Santino asked why 6 of 8 listings sat at "Pending publish" since the 08-01
GBP batch import). Read this BEFORE anyone tries to "fix" a pending listing:

  Published       Live on Bing. Terminal success.
  Pending publish NOT a defect and NOT actionable. Bing's own server-side
                  publishing queue. The singleEntity page states verbatim:
                    "Your verification is done, and now we're publishing
                     your listing."
                    "Publishing ETA is 7-12 days. We will notify you when
                     your listing is published."
                  Confirmed on 2026-08-04 across all 6 pending listings
                  (Flood Fixers, ProRestoration, Restoration Xpress,
                  NaRestCo, Mold Solutionz, Coastal): header counts read
                  "Needs review 0 / Suspended 0", every pending row is
                  tagged "New import from Google", and the ONLY buttons on a
                  pending listing are Sync and View analytics. There is no
                  publish/submit/resubmit control, no missing required field
                  (name/address/phone/website/category/hours/photos/
                  description/services are all populated — a pending listing
                  like Restoration Xpress carries the exact same fields as
                  PUBLISHED Home Pride), and no PIN/postcard step outstanding.
                  Home Pride + Crew are published only because they predate
                  the 08-01 batch.
                  DO NOT re-import a pending listing to hurry it — that
                  restarts the queue. DO NOT open a support ticket inside
                  the stated ETA window. There is nothing that accelerates it.
  Needs review    REAL work item — Bing wants something changed.
  Suspended       REAL work item — escalate (cf. the Go Green GBP suspension).

Only the last two should ever generate a card. The nightly sweep records the
queue each night (sweep.bing_dashboard_state) so the flip to Published is
detected the day it happens.

Gotcha: on a PUBLISHED listing the detail page also shows the word "Pending"
— that belongs to the Announcements block (a queued Bing Post, e.g. Home
Pride's 8/3-9/23 announcement), NOT to the listing's publish status. Match
the exact string "Pending publish" against the row/header status, never a
bare substring search for "Pending".

Service-area businesses import with an EMPTY address (Coastal, 2026-08-04) —
that is inherited from the GBP address-hiding setting and does not block
publishing.
"""
from __future__ import annotations

from ..chassis import Session, company_truth, ledger

BING_PLACES = "https://www.bingplaces.com/"


def run(session: Session) -> int:
    truth = company_truth(session.company_id) if session.company_id else {}
    if not truth:
        print("no company truth row — refusing to operate on unknown NAP")
        return 1
    page = session.page
    page.goto(BING_PLACES, wait_until="domcontentloaded")
    session.audit_shot("landing")

    # Signed-out detection: anything asking for a Microsoft login is a
    # challenge — supervised login only, never automated credential entry.
    if page.locator("text=Sign in").count() > 0:
        session.challenge_detected("microsoft-signin")

    print(f"Bing Places for {truth.get('name')} — {truth.get('city')}, {truth.get('state')}")
    print("NAP truth:", truth.get("phone"), "|", truth.get("address"))

    # --- SUPERVISED SECTION: selector pinning happens on the first live run.
    # The flow below is the checklist the human watches the agent perform;
    # each TODO becomes a locator once observed in the real UI.
    print("\nSupervised checklist (first runs):")
    print(" 1. Search existing listings for the business name + city")
    print(" 2. If found -> CLAIM path; if not -> 'Import from Google'")
    print(" 3. Verify imported NAP vs truth above (REAL phone, exact address)")
    print(" 4. Submit only behind guard_live()")
    if session.guard_live("create/claim Bing Places listing"):
        print("LIVE mode armed — selectors not yet pinned; run supervised and")
        print("pin locators here as the UI is observed. Refusing blind clicks.")
        ledger(session.company_id, session.playbook, "create-listing",
               "needs_supervised_run", live=True)
        return 2
    return 0
