"""Playbook: pure form-fill directory listings — Houzz, Porch, HomeGuide, BBB.

Unlike Bing (GBP import) these portals have no shortcut: the agent fills the
create/claim form field-by-field from company_truth(). Supervised-first —
every portal below runs with Santino watching until it has THREE clean
completions, then it earns a slot in the nightly sweep (browser_agent/sweep.py).

Dedupe is step zero, always: search the portal's PUBLIC directory for the
business before touching any create form. Existing listing -> CLAIM path (or
ledger 'exists' if claiming needs owner identity), never a duplicate create.

Phone policy (Santino 2026-07-31): the number entered is the client's GBP
PRIMARY number — tracking numbers are ACCEPTED on citations because they're
what GBP itself shows; NAP consistency means matching GBP, not the carrier
record. citations_audit's ok_phones mirrors this.

Portal accounts: created under the agency identity (contact@restorationai.io)
inside the persistent profile. If a portal demands per-client owner identity
or phone verification mid-flow, that's a challenge_detected() stop — the
platform belongs on the CLIENT-owed list, not here (mirror of setup_ledger's
us_create/client_create split).
"""
from __future__ import annotations

from ..chassis import Session, company_truth, ledger

# Each entry: where to dedupe-search, where the create/claim flow starts, and
# the quirks observed so far. `selectors` stays empty until pinned during the
# supervised runs — an empty dict means "not yet earned, supervised only".
PORTALS = {
    "houzz": {
        "label": "Houzz",
        "search": "https://www.houzz.com/professionals/probr0-bo~t_11785",  # + query via UI search box
        "create": "https://www.houzz.com/",  # Sign In -> Sign Up (join URLs 404)
        "notes": "Free pro profile. Category: 'Environmental Services & "
                 "Restoration'. Take the free listing path ONLY — never a "
                 "trial, demo, or ad product.",
        # Pinned during supervised run 1 (narestco, 2026-08-01, clean):
        #  account: email+pw signup — NEVER Google SSO (one Houzz identity per
        #    account; we alias contact+{slug}@restorationai.io). Email code
        #    lands in agency Gmail ('Your Confirmation Code'). Password policy
        #    8+/digit/symbol — generator MUST guarantee all classes. React
        #    inputs need focus()+keyboard.type (fill() leaves submit disabled;
        #    floating labels intercept click()).
        #  wizard (pro-onboarding-wizard): identifyProNProjectType = Contractor
        #    + combobox 'Environmental Services & Restoration' + 'Client
        #    project(s)'; proIntent = 'Free Business Profile' ONLY;
        #    revenueNEmployees = 'Prefer not to say' + '2-10';
        #    projectTimelineNBusinessTool = 'Within the next week' + 'Other
        #    software' + required text 'Restoration AI'; hearAboutUs = 'AI
        #    (e.g. ChatGPT)'.
        #  pro-basic-info: businessName/businessPhone/businessWebsite/
        #    contactFirstName/contactLastName; SMS-consent checkbox comes
        #    PRE-TICKED — always uncheck.
        #  pro.houzz.com/pro-onboarding: location (state = native <select>),
        #    serviceAreas + servicesProvided accept the suggested sets,
        #    profilePhoto = logo PNG via input[type=file] then Save. A sales
        #    demo-scheduler modal ('good time for a demo') blocks all clicks —
        #    close via [aria-label='Close'] / Escape before advancing.
        # Run 2 (flood-fixers, 2026-08-01, complete): the wizard SHUFFLES —
        #    same questions recombine across step ids (projectTypeNIntent,
        #    revenueTimeline), so drive it as a state machine keyed on body
        #    text (scratchpad houzz_resume.py is the reference), never a fixed
        #    sequence. New pages seen: 'What features interest you?' custom
        #    dropdown (options were only SaaS features — no free-profile
        #    option in this variant; pick is cosmetic); 'Want help getting
        #    set up?' -> 'No, thanks'; pro-onboarding-pricing (Start Free
        #    Trial wall) -> NEVER click, goto pro.houzz.com/pro-onboarding.
        #    Logout: /logout is 404; JS-click [data-objid="navSignOut"].
        # Run 3 attempt (coastal, same night): signup silently bounced to a
        #    sign-in page, no email sent — VELOCITY THROTTLE after 2 accounts
        #    from one browser/night. Pace: max 2 new accounts per day.
        "selectors": {"supervised_runs_clean": 2},
    },
    "porch": {
        "label": "Porch",
        "search": "https://porch.com/search",
        "create": "https://pro.porch.com/signup",
        "notes": "Free pro profile; Porch resells leads — decline every "
                 "paid-lead upsell screen. Service: water/fire/mold damage "
                 "restoration.",
        "selectors": {},
    },
    "homeguide": {
        "label": "HomeGuide",
        "search": "https://homeguide.com/",  # search box on landing
        "create": "https://homeguide.com/signup/pro",
        "notes": "Free listing; lead credits are the upsell — skip. Fast "
                 "form: name/category/zip/phone/email.",
        "selectors": {},
    },
    "bbb": {
        "label": "BBB",
        "search": "https://www.bbb.org/search",
        "create": "https://www.bbb.org/get-listed",
        "notes": "Request form, not an account: BBB calls/emails the BUSINESS "
                 "to verify, so the client should expect the call — file a "
                 "Monica heads-up note after submitting. Accreditation is a "
                 "paid product we never opt into; the free listing is the ask.",
        "selectors": {},
    },
    # Data aggregators (Data Axle / Localeze / Foursquare) feed hundreds of
    # long-tail directories. Their submission portals want business-owner
    # attestations and some charge; parked until the four above are earned.
    # Revisit: localsite.data-axle.com, foursquare.com/products/places.
}


def run(session: Session, portal: str) -> int:
    cfg = PORTALS.get(portal)
    if not cfg:
        print(f"unknown portal '{portal}' — one of: {', '.join(PORTALS)}")
        return 1
    truth = company_truth(session.company_id) if session.company_id else {}
    if not truth:
        print("no company truth row — refusing to operate on unknown NAP")
        return 1
    page = session.page

    # --- Step 0: DEDUPE against the public directory.
    page.goto(cfg["search"], wait_until="domcontentloaded")
    session.audit_shot(f"{portal}-dedupe-search")
    print(f"{cfg['label']} for {truth.get('name')} — {truth.get('city')}, "
          f"{truth.get('state')}")
    print("NAP:", truth.get("phone"), "|", truth.get("address"))
    print(f"quirks: {cfg['notes']}")

    if not cfg["selectors"]:
        # SUPERVISED SECTION — selectors get pinned here as the real UI is
        # observed, exactly like bing_places earned its SSO coordinates.
        print("\nSupervised checklist (portal not yet earned):")
        print(" 0. Search the public directory for name + city — existing")
        print("    listing -> CLAIM path or ledger 'exists'; NEVER duplicate")
        print(f" 1. Open create flow: {cfg['create']}")
        print(" 2. Fill from the NAP truth above (GBP-primary phone)")
        print(" 3. Decline every paid upsell (see quirks)")
        print(" 4. Submit only behind guard_live(); audit shots before/after")
        print(" 5. On verified completion: ledger 'done'; citations_audit's")
        print("    next pass flips the board card — never pre-clear it")
        if session.guard_live(f"create {cfg['label']} listing"):
            print("LIVE armed but selectors unpinned — refusing blind clicks.")
            ledger(session.company_id, session.playbook, f"{portal}-create",
                   "needs_supervised_run", live=True)
            return 2
        return 0

    # Earned-unattended path lands here once selectors are pinned and the
    # portal has three clean supervised completions.
    raise NotImplementedError("no portal has earned unattended form-fill yet")
