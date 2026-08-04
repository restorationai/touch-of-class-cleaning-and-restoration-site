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

Verified-creation write-back (2026-08-02): the LAST step of every verified
creation is scripts/listings.record_listing(company_id, portal, public_url)
— it puts the URL in the app's client-facing Business Listings card
(user_integrations provider='citations', audit-shape nap_audit entry) and
logs the client-readable work_log line IMMEDIATELY; the monthly
citations_audit pass then merely re-verifies. Never make the client wait a
month to see a listing we already shipped.
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
        # Run 5 attempt (homelyft, 2026-08-04 ~01:30 UTC): the throttle window
        #    is ROLLING ~24h from each creation, not calendar-night — RX's
        #    account (08-03 05:46 UTC) still inside the window blocked a new
        #    signup 20h later. Soft-block DISGUISES as sticky form errors:
        #    'Did you mean contact+{slug}@restorationai.in? - Ignore' under
        #    #email plus 'Passwords need to have a mix of letters, numbers
        #    and symbols' on a VERIFIED-correct password (same generator
        #    narestco passed with). Two real lessons regardless: dismiss the
        #    Did-you-mean box BEFORE typing #password (its re-render can
        #    swallow a keystroke — attempt 2 landed 18/19 chars), and always
        #    compare input_value() to the intended secret pre-submit. No
        #    account/email results from a soft-blocked attempt; retry next
        #    night (coastal succeeded on its retry).
        # Public verify (2026-08-02): both created profiles are LIVE — URL
        #    shape professionals/environmental-services-and-restoration/
        #    {name-slug}-pfvwus-pf~{id}. Read-only dedupe/verify search:
        #    houzz.com/professionals/query/{name-dashes}/nqrwns?l={client
        #    zip} — WITHOUT ?l= the search geo-defaults to the agent's IP
        #    metro (50mi radius) and hides out-of-area pros. record_listing()
        #    backfilled for narestco + flood-fixers.
        "selectors": {"supervised_runs_clean": 2},
    },
    "porch": {
        "label": "Porch",
        "search": "https://porch.com/pros",  # NO name search — see recon note
        "create": "https://pro.porch.com/pro",  # landing only; signup CLOSED
        "notes": "PARKED (recon 2026-08-02): Porch pivoted to insurance and "
                 "self-serve pro signup is GONE — pro.porch.com/signup, "
                 "/login, /registration, porch.com/join all 404; the pro "
                 "landing's 'Become a Vetted Pro' is a plain <h4>, not a "
                 "link, and its only CTAs are Log in / GET SUPPORT. Getting "
                 "listed needs a human via Pro Support. NEVER enter "
                 "porch.com/checkout/start (the /pros search box funnels "
                 "straight into a homeowner LEAD-REQUEST wizard; water "
                 "damage restoration = serviceTypeId 6324).",
        # Pinned during read-only recon (2026-08-02, no account touched):
        #  dedupe: on-portal name search does not exist. porch.com/pros only
        #    autocompletes service CATEGORIES (picking one navigates to the
        #    checkout/start lead wizard — abort). Directory browse is dead:
        #    porch.com/near-me/{category} 301s to pro.porch.com/near-me/*
        #    which 404s; porch.com/{city}-{st}/{category} 404s. Dedupe via
        #    engine query site:porch.com "{business name}" (legacy profiles
        #    end in /pp) — treat any hit as claim-path research for a human.
        #  porch.com/signup is CUSTOMER (insurance) signup — wrong product.
        "selectors": {},
    },
    "homeguide": {
        "label": "HomeGuide",
        # {zip} = client zip; service id is opaque — f876B6Fz is the 'Water
        # Damage Cleanup And Restoration' category our clients live in.
        "search": "https://homeguide.com/search?service=f876B6Fz&zipcode={zip}",
        "create": "https://homeguide.com/pro",  # signup/pro 404s; this is live
        "notes": "Free pro profile ('Join as a pro' header link -> /pro). "
                 "Hero form service+zip, submit label 'Sign up for free' — "
                 "that click STARTS account creation, so it stays behind "
                 "guard_live(). Lead credits are the upsell (the /pro page "
                 "shows 'X is looking for...' teaser cards that all gate on "
                 "signup); booking software itself is free per "
                 "/for-business/pricing. Login: homeguide.com/login.",
        # Pinned during read-only recon (2026-08-02, no account created):
        #  create entry: input#service (typeahead) + input#zip + submit
        #    'Sign up for free' on homeguide.com/pro; consumer home search is
        #    input#searchBarInput + input#main-search-zip + button#submit.
        #  dedupe: results at /search?service={id}&zipcode={zip} are
        #    JS-RENDERED (raw HTML is a ~6KB shell) — read the rendered DOM,
        #    never page-source. Suggestion click auto-navigates using a
        #    GEO-IP zip, so always goto the search URL with the client zip
        #    explicitly. Profile URL pattern:
        #    homeguide.com/{st}/{city}/{category}/{slug}-{id}.
        #  2026-08-02 @98409: NaRestCo NOT in top-10; client 'Allpro
        #    Construction' (Auburn WA) IS already listed.
        # Pinned during supervised run 1 (narestco, 2026-08-02, clean —
        #  public URL live same night; homeguide_state_machine.py is the
        #  reference driver):
        #  signup: /pro hero -> zip FIRST, then #service typeahead ('Water
        #    Damage' surfaces 'Water Damage Cleanup And Restoration' — pick
        #    it), 'Sign up for free' opens a MODAL on the same page: 'Sign up
        #    with email' -> email + MOBILE PHONE (tel, becomes account phone;
        #    enter GBP primary) + password; 'enable texts for account and job
        #    updates' checkbox PRE-TICKED -> uncheck; submit 'Sign up'. NO
        #    email-verification gate; HomeGuide sent zero emails all run.
        #  wizard (homeguide.com/pro/onboarding/* — body-text state machine):
        #    more-services = additional-category PILLS are <button>s, NOT
        #    checkboxes (Mold Inspection And Removal + General Contracting
        #    are the useful restoration adds; Skip works);
        #    {svc}/business-info (business-name, website; Continue validates,
        #    Skip fine — full NAP lives in the app later);
        #    {svc}/profile-image input[type=file] <- logo PNG -> Save;
        #    {svc}/business-intro textarea <- description;
        #    tutorial-aperture?aperture_id=pricing|payment = info, Continue;
        #    services/{svc}/job-preference: job-scope checkboxes ALL
        #    PRE-CHECKED, leave and Continue;
        #    services/{svc}/provider/geo-preference: map, default 'by
        #    distance 25 miles', text warns matches will AUTO-PAY -> Continue
        #    (harmless with no card);
        #    services/{svc}/budget -> Continue (default budget, inert w/o
        #    card); services/{svc}/creditcard (cc-number/cc-exp/cc-csc +
        #    Save, NO skip) = THE upsell wall -> navigate away; account and
        #    listing survive.
        #  app dashboard = app.homeguide.com/pros (Talo booking software,
        #    help.talo.com). Profile: /pros/profile (overview; phones show
        #    'Hidden from customers' — public page routes contact through
        #    HG messaging, so phone/website absence on the public profile is
        #    by design, not an error), /pros/profile/edit-info NAP form
        #    (#business-name #year-founded #number-of-employees
        #    #phone-number #company-phone-number #company-email #website
        #    #street-address #address-suite #postal-code + payment-type
        #    checkboxes + social/GBP/Yelp URL inputs), /edit-intro,
        #    /edit-media. TRAPS for regex fillers: the suite input is
        #    name='business-name' id='address-suite'; 'company-email'
        #    matches naive /company/ patterns; #year-founded and
        #    #number-of-employees come PREFILLED '0' (input_value truthy ->
        #    fill-if-empty logic skips them; set explicitly).
        #  public URL appears in /search within ~minutes of profile
        #    completion (no review hold): narestco ->
        #    homeguide.com/wa/federal-way/water-damage-restoration/
        #    national-restoration-construction-A8aisT6gf. Renders name,
        #    '22 years in business' (from year-founded), 'Serves {city},
        #    WA', intro, specialties. record_listing() written 2026-08-02.
        # Runs 2+3 (restorationxpress, homelyft-restoration-ms — both
        #  2026-08-04 ~01:30/02:00 UTC, both clean end-to-end, public URLs
        #  live same-run; homeguide_state_machine.py now takes a JSON
        #  overrides arg for GBP-primary NAP when the companies row lags):
        #    geo-preference can present TWICE — second pass has a 'Save for
        #    this service only' button (generic advance() handles it);
        #    business-info may re-present once after Continue (Skip clears
        #    it; full NAP lands in /pros/profile/edit-info anyway). RX
        #    profile: homeguide.com/fl/davie/water-damage-restoration/
        #    restorationxpress-_VgGv-Adz; HomeLyft: homeguide.com/ms/
        #    gulfport/water-damage-restoration/homelyft-restoration-_ZLeDzvnC.
        "selectors": {"supervised_runs_clean": 3},
    },
    "bbb": {
        "label": "BBB",
        "search": "https://www.bbb.org/search?find_country=USA"
                  "&find_text={name}&find_loc={city}%2C+{st}",
        "create": "https://www.bbb.org/get-listed",
        "notes": "Request form, not accreditation: dedupe lookup ON the "
                 "get-listed page first; existing record -> 'Select' (claim "
                 "path), else 'Add It Now' -> /get-listed/form -> 'I own a "
                 "business' -> /get-listed/business. Final button 'Create "
                 "Profile' creates a BBB account+profile — guard_live() "
                 "only. BBB then verifies with the BUSINESS, so file a "
                 "Monica heads-up note after submitting. Accreditation is "
                 "the paid product: never opt in — leave the "
                 "learnMoreAboutAccreditation checkbox UNCHECKED and skip "
                 "/get-accredited & /apply links.",
        # Pinned during read-only recon (2026-08-02, nothing submitted):
        #  /get-listed/business form#addBusinessForm fields:
        #    businessContactFirstName / businessContactLastName /
        #    businessContactTitle (opt), businessName, address, address2
        #    (opt), city, state (native <select>, 'WA - Washington' style),
        #    postalCode, phoneNumber (tel), email, url,
        #    addBusinessFormCategoryInput (typeahead — e.g. 'Fire and Water
        #    Damage Restoration'), learnMoreAboutAccreditation checkbox
        #    (default UNCHECKED — keep it that way), submit 'Create Profile'.
        #  dedupe: /search results are SERVER-RENDERED (name + /profile/
        #    links present in raw HTML); profile URL pattern
        #    bbb.org/us/{st}/{city}/profile/{category}/{slug}-{bureau}-{id}.
        #  PerimeterX (pxcelframe) is on every page — no challenge fired
        #    logged-out, but pace requests and never retry a block.
        #  2026-08-02: NaRestCo ALREADY EXISTS — A+ profile, Federal Way WA
        #    98003, (844) 672-2424 -> claim path / ledger 'exists', never a
        #    duplicate create.
        # Pinned during LIVE run 1 (restorationxpress, 2026-08-04, submitted):
        #  dedupe traps: the get-listed on-page lookup navigates to /search
        #    with the Near field PRE-FILLED from geo-ip — clear it before
        #    typing or you search 'Davie, FLDavie, FL'; and never match
        #    'Select' unanchored — the header's 'Select language' button
        #    false-positives the claim path. 'No results for' in body =
        #    definitively absent.
        #  category typeahead is downshift: its open li.ta-suggestion list
        #    OVERLAYS the Create Profile button — click a suggestion (or
        #    Escape) before submitting. Typing 'Fire and Water Damage
        #    Restoration' surfaces exactly that option (plus Fire/Water-only
        #    variants); input_value() reads empty after picking (selection is
        #    stored off-input) — that's normal.
        #  submit -> bbb.org/get-listed/success: 'Your local BBB will review
        #    the information you provided before the business appears in our
        #    search directory.' NO account/password step, NO email/SMS gate —
        #    verification is BBB-side with the business (file the Monica
        #    heads-up). No public URL until their review clears, so
        #    record_listing waits for the monthly citations_audit (or a
        #    manual re-check) to find the /profile/ URL.
        #  PerimeterX never fired across 4 headed page-loads at human pace.
        "selectors": {"supervised_runs_clean": 1},
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
        print(" 5. On verified completion: ledger 'done', then")
        print("    listings.record_listing(company_id, portal, public_url) —")
        print("    the app's Business Listings card shows the URL immediately;")
        print("    citations_audit's next pass re-verifies (never wait for it)")
        if session.guard_live(f"create {cfg['label']} listing"):
            print("LIVE armed but selectors unpinned — refusing blind clicks.")
            ledger(session.company_id, session.playbook, f"{portal}-create",
                   "needs_supervised_run", live=True)
            return 2
        return 0

    # Earned-unattended path lands here once selectors are pinned and the
    # portal has three clean supervised completions.
    raise NotImplementedError("no portal has earned unattended form-fill yet")
