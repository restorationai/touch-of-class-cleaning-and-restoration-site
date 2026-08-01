"""Playbook: Bing Places listing create/claim.

Strategy (fastest legitimate path): Bing Places offers "Import from Google
My Business" — since we hold the client's GBP, the import route carries the
whole verified profile over in one flow and usually skips PIN verification
via the Google-account handshake.

Flow (selectors get pinned during the SUPERVISED first run — this playbook
runs supervised until three clean completions, then it earns unattended):
  1. bingplaces.com → signed in as the agency Microsoft account (profile).
  2. Search for the business (name + city) — if a listing already exists,
     switch to CLAIM path; ledger 'exists'.
  3. Else "Import from Google" → pick the client's GBP location → verify the
     imported NAP against company_truth() (REAL phone!) → fix mismatches.
  4. guard_live() → submit. Audit shots before/after.
  5. On verified completion: ledger 'done', update the citations nap_audit
     row, and mark_ledger_item_done ONLY when Bing was the last missing
     us-create platform for the client.
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
