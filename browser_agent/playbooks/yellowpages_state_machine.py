#!/usr/bin/env python3
"""YellowPages listing driver — supervised run 1. DO NOT SCHEDULE THIS YET.

VERDICT 2026-08-06: YellowPages has NO self-serve free listing creation. Both
routes are sales funnels, and the run stopped one click short of entering one.

  - adsolutions.yp.com/listings/basic, the "free listing signup" every
    third-party guide still cites, HAS NO DNS. It is dead. I repeated that URL
    from a blog before checking it; it does not exist.
  - /claim-your-listing-new, the "click here to submit your business" path, is
    headed "Claim Your Listing" and subtitled "CONNECT WITH A BUSINESS ADVISOR
    to learn more", with "Or, call us to get started: 1-866-794-0889" beneath
    it. Its consent line reads: "By providing your email and mobile number and
    clicking Submit, you consent to THRYV's Terms of Use and Privacy Policy and
    Thryv sending emails and text messages to you for advertising and marketing
    purposes."

Thryv owns YP. Submitting that form does not create a listing; it books a sales
call and opts our number and inbox into their marketing. Same shape as
Expertise.com's Calendly ending, found the same night.

The form fills perfectly and the reCAPTCHA is a real, clickable "I'm not a
robot" box, so this WOULD have gone through had we treated a filled form as
success. It stopped because the run waits for a human and Santino was shown the
screenshot first.

If YP presence is still wanted, the route is the data aggregators that feed it
(Data Axle / Localeze / Foursquare), already parked at the bottom of
form_fill.PORTALS — not YP's own front door.

Everything below is kept because it is correct and reusable if YP ever reopens
a self-serve path: dedupe, NAP mapping, the disabled-until-CAPTCHA behaviour
and the human-in-the-loop wait.

Path, established by recon on 2026-08-06:
  1. yellowpages.com/claim-your-listing — search name + "City, ST". If the
     business is already there, this is a CLAIM (different flow, and the
     claim is what triggers YP's verification call/text). Never duplicate.
  2. "No results found. Please click here to submit your business." ->
     yellowpages.com/claim-your-listing-new — a single flat form, which is the
     path for the 18 clients with no YP presence at all.

The adsolutions.yp.com/listings/basic URL that third-party guides give for the
"free listing signup" HAS NO DNS AT ALL. It is dead. Do not resurrect it.

WHOSE DETAILS GO WHERE, and this matters:
  - the LISTING data (business name, street, city, state, zip, PHONE) is the
    client's real NAP, because it is what the public sees and it has to match
    their Google listing or the citation actively hurts them.
  - the CONTACT data (first/last name, email) is OURS. We are the agency
    filing this, and any sales follow-up belongs in our inbox rather than on a
    restoration owner's phone. Same policy as Houzz and Expertise.

    python3 browser_agent/playbooks/yellowpages_state_machine.py --slug narestco
        [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from browser_agent.chassis import Session, company_truth, ledger  # noqa: E402

SEARCH_URL = "https://www.yellowpages.com/claim-your-listing"
NEW_URL = "https://www.yellowpages.com/claim-your-listing-new"

AGENCY_FIRST = "Santino"
AGENCY_LAST = "Velci"
INDUSTRY = "Water Damage Restoration"

PAYWALL_RE = re.compile(
    r"\bpricing\b|\bcredit card\b|\bcard number\b|\bpayment\b|\bbilling\b|"
    r"\bsubscri|\binvoice\b|\$\s?\d", re.I)


def _controls(page) -> list[dict]:
    return page.evaluate("""() =>
        Array.from(document.querySelectorAll('input,select,textarea,button'))
          .filter(e => e.offsetParent !== null)
          .map(e => ({tag: e.tagName.toLowerCase(), type: e.type || '',
                      name: e.name || '', id: e.id || '',
                      ph: e.placeholder || '',
                      text: (e.innerText || '').trim().slice(0, 45)}))""")


def _dump(page, label: str) -> None:
    print(f"\n--- {label} | {page.url}")
    for c in _controls(page):
        bits = [f"<{c['tag']}>"]
        for k in ("type", "name", "id", "ph", "text"):
            if c[k]:
                bits.append(f"{k}={c[k]!r}")
        print("   " + " ".join(bits))


def _wait_for_recaptcha(page, s, max_seconds: int) -> bool:
    """Block until a human solves the reCAPTCHA in the open window.

    Never solved programmatically: chassis policy is that a CAPTCHA is a hard
    stop, and a solver service would be both a terms violation and a lie about
    who is filling the form. The agent does every other field; a person clicks
    one box.
    """
    if page.evaluate("() => (document.querySelector('#g-recaptcha-response')"
                     "?.value || '').length > 0"):
        return True
    s.audit_shot("yp-awaiting-recaptcha")
    print(f"\n>>> reCAPTCHA: click \"I'm not a robot\" in the browser window. "
          f"Waiting up to {max_seconds}s, then submitting automatically.")
    waited = 0
    while waited < max_seconds:
        page.wait_for_timeout(2000)
        waited += 2
        if page.evaluate("() => (document.querySelector('#g-recaptcha-response')"
                         "?.value || '').length > 0"):
            print(f"    token received after {waited}s — continuing")
            return True
        if waited % 20 == 0:
            print(f"    still waiting ({waited}s)")
    return False


def already_listed(page, s, name: str, geo: str) -> bool:
    """True when YP already has this business — claim path, never duplicate."""
    page.goto(SEARCH_URL, wait_until="commit", timeout=60000)
    page.wait_for_timeout(8000)
    page.fill("input#query", name)
    page.fill("input#geo", geo)
    page.press("input#geo", "Enter")
    page.wait_for_timeout(9000)
    s.audit_shot("yp-dedupe-search")
    body = (page.inner_text("body") or "")
    if "No results found" in body:
        print(f"  dedupe: no YP listing for {name} — create path")
        return False
    print(f"  dedupe: YP RETURNED RESULTS for {name} — this is a CLAIM, not a "
          f"create. Claiming triggers YP's phone/text verification and is a "
          f"different flow; stopping so nothing gets duplicated.")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--captcha-wait", type=int, default=180,
                    help="seconds to wait for a human to solve the "
                         "reCAPTCHA before giving up")
    args = ap.parse_args()

    s = Session(playbook="form-fill", slug=args.slug,
                live=not args.dry_run).start(headless=False)
    page = s.page
    t = company_truth(s.company_id) or {}
    need = ("name", "phone", "city", "state", "postal_code")
    if not all(t.get(k) for k in need):
        print(f"incomplete NAP {[k for k in need if not t.get(k)]} — refusing")
        return 1
    geo = f"{t['city']}, {t['state']}"
    print(f"YellowPages listing for {t['name']} — {geo} {t['postal_code']}")
    print(f"  listing phone (client's real line): {t['phone']}")

    if already_listed(page, s, t["name"], geo):
        ledger(s.company_id, s.playbook, "yellowpages-create", "exists",
               live=not args.dry_run,
               detail="YP search returned an existing listing; claim path")
        return 0

    page.goto(NEW_URL, wait_until="commit", timeout=60000)
    page.wait_for_timeout(9000)
    _dump(page, "add-a-business form")

    fields = {
        "first-name": AGENCY_FIRST,
        "last-name": AGENCY_LAST,
        "business-name": t["name"],
        "industry": INDUSTRY,
        "street": t.get("address") or "",
        "city": t["city"],
        "business-zip": t["postal_code"],
        "email-address": f"contact+{args.slug}@restorationai.io",
        "phone": t["phone"],
    }
    for fid, val in fields.items():
        if not val:
            continue
        el = page.query_selector(f"#{fid}")
        if not el:
            print(f"  MISSING field #{fid} — form changed, stopping")
            s.audit_shot("yp-missing-field")
            return 2
        el.click()
        el.press("Meta+A")
        el.type(val, delay=40)
        page.wait_for_timeout(180)
    try:
        page.select_option("#state", t["state"])
    except Exception:
        print(f"  could not set state={t['state']!r} — stopping")
        s.audit_shot("yp-state-fail")
        return 2
    print(f"  filled: {t['name']} | {t.get('address')} | {t['city']}, "
          f"{t['state']} {t['postal_code']} | {t['phone']}")
    s.audit_shot("yp-form-filled")

    if args.dry_run:
        print("dry run — not submitting")
        return 0
    if not s.guard_live(f"create YellowPages listing for {t['name']}"):
        return 0

    # reCAPTCHA. The Submit button carries disabled="disabled" until Google's
    # token lands in the hidden g-recaptcha-response textarea — every field can
    # be valid and populated and the button still will not enable. We do not
    # solve or bypass CAPTCHAs, so this is where a human takes over: click the
    # "I'm not a robot" box in the open window and the run continues itself.
    # That is the whole human cost of a YP listing, roughly a minute each.
    if not _wait_for_recaptcha(page, s, args.captcha_wait):
        print("\nNo reCAPTCHA token after waiting. Nothing submitted.")
        ledger(s.company_id, s.playbook, "yellowpages-create", "review_needed",
               live=True, detail="recaptcha unsolved — needs a human click")
        return 4

    before = {ln.strip() for ln in (page.inner_text("body") or "").splitlines()}
    page.click("input[type=submit]")
    page.wait_for_timeout(9000)
    s.audit_shot("yp-after-submit")
    body = (page.inner_text("body") or "")
    new = [ln.strip() for ln in body.splitlines()
           if ln.strip() and ln.strip() not in before and len(ln.strip()) < 200]
    print("\n--- what changed after submit ---")
    for ln in new[:25]:
        print("   ", ln)
    hit = next((ln for ln in new if PAYWALL_RE.search(ln)), None)
    if hit:
        print(f"\nPAID FUNNEL: {hit!r}")
        ledger(s.company_id, s.playbook, "yellowpages-create", "review_needed",
               live=True, detail=f"paywall after submit: {hit[:140]}")
        return 3
    if re.search(r"thank you|received|submitted|confirm", body, re.I):
        print("\nSUBMITTED — YP acknowledged the listing request")
        ledger(s.company_id, s.playbook, "yellowpages-create", "done",
               live=True, detail="free listing submitted via claim-your-listing-new")
        return 0
    print("\nNo confirmation text found. NOT recording this as submitted — "
          "read the dump above and the audit shot before claiming anything.")
    ledger(s.company_id, s.playbook, "yellowpages-create", "needs_supervised_run",
           live=True, detail="form submitted, no confirmation observed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
