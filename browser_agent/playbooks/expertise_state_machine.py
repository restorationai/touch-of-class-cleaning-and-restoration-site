#!/usr/bin/env python3
"""Expertise.com "request a review" driver — supervised run 1.

READ THIS BEFORE SCHEDULING THE FLEET (findings, 2026-08-06 run 1, narestco):

The four-step form does NOT end in a submitted listing application. Step 4,
"Verify", is headed "Last Step — Schedule a Time to Verify Your Submission"
and embeds a CALENDLY BOOKING for a call with Expertise. Directly beneath it
sits the "Become a Featured Partner ... pay-for-what-you-get pricing" pitch.
So /review-me is a lead form into their sales team, not a self-serve listing
create. Their own FAQ is consistent with that: listings come from an internal
research and review process, and this form only "requests a review".

Worse for automation: on run 1 the Calendly embed rendered "This Calendly URL
is not valid." Their widget is broken, so even a human cannot complete the
final step right now.

Whether steps 1-3 reached their Salesforce is UNKNOWN and must not be claimed.
The URL never changes across the steps and no confirmation is ever shown, so
the multi-step React form may well POST only at the end — the end we never
reached. Do not mark any client "applied" on the strength of this run.

Consequence for the ledger: expertise should not sit on _US_CREATE_PLATFORMS
as work we owe clients until there is a path that actually completes without a
sales call. Santino's call.

Expertise does not let anyone create a listing. It selects editorially and
accepts REQUESTS in a few categories, ours among them (the typeahead carries
Fire Damage Restoration, Water Damage Restoration and Mold Remediation). So a
clean run here could only ever mean APPLIED, never LISTED.

Step 1 is pinned from read-only recon on 2026-08-05; steps 2-4 were walked on
2026-08-06 and are pinned below.

    python3 browser_agent/playbooks/expertise_state_machine.py --slug narestco \
        [--category "Water Damage Restoration"] [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from browser_agent.chassis import Session, company_truth, ledger  # noqa: E402

FORM_URL = "https://www.expertise.com/review-me"
DEFAULT_CATEGORY = "Water Damage Restoration"

# The contact WE put on a client's request. Ours on purpose: Expertise follows
# up by pitching its paid Featured Partner product, and that call belongs in
# our inbox rather than on a restoration owner's phone mid-job. The email is a
# per-client plus-alias so replies are attributable, same as Houzz.
AGENCY_FIRST = "Santino"
AGENCY_LAST = "Velci"
AGENCY_PHONE = "(855) 648-4464"   # Rank AI toll-free, CONCIERGE_FROM_NUMBER

# Expertise's sales-qualification field. See the note at step 3: this is the
# minimum that unblocks the form, chosen by Santino 2026-08-05 so we never put
# an invented growth target in a client's mouth.
DESIRED_MONTHLY_CLIENTS = "1"

# Anything here on a rendered page means we have walked into the paid funnel.
# "per month" was in here and matched "What number of new clients/customers are
# you looking for per month?" — a lead-VOLUME question, not a price. Kept to
# terms that can only mean money changing hands.
PAYWALL_RE = re.compile(
    r"\bpricing\b|\bcredit card\b|\bcard number\b|\bpayment\b|\bbilling\b|"
    r"\bupgrade\b|\bsubscri|\binvoice\b|\bper month\b\s*\$|\$\s?\d", re.I)


def _visible_controls(page) -> list[dict]:
    """Every visible input/select/textarea/button, for pinning steps 2-4."""
    return page.evaluate("""() =>
        Array.from(document.querySelectorAll('input,select,textarea,button'))
          .filter(e => e.offsetParent !== null)
          .map(e => ({tag: e.tagName.toLowerCase(), type: e.type || '',
                      name: e.name || '', id: e.id || '',
                      ph: e.placeholder || '',
                      label: e.getAttribute('aria-label') || '',
                      text: (e.innerText || '').trim().slice(0, 45),
                      required: !!e.required}))""")


def _dump(page, label: str) -> None:
    print(f"\n--- {label} | {page.url}")
    for c in _visible_controls(page):
        bits = [f"<{c['tag']}>"]
        for k in ("type", "name", "id", "ph", "label", "text"):
            if c[k]:
                bits.append(f"{k}={c[k]!r}")
        if c["required"]:
            bits.append("REQUIRED")
        print("   " + " ".join(bits))


def _paywall(page, baseline: set[str] | None = None) -> str | None:
    """Paid-funnel detector, diffed against the page we started on.

    The naive whole-body scan fires immediately and always: /review-me carries
    a static "Become a Featured Partner" pitch in its own marketing copy, so a
    plain search flags the funnel before anything has been clicked (2026-08-05,
    run 1). Only a paywall line that is NEW relative to the starting page means
    we have actually walked somewhere we should not be.
    """
    baseline = baseline or set()
    for line in (page.inner_text("body") or "").splitlines():
        line = line.strip()
        if not line or len(line) > 200 or line in baseline:
            continue
        if PAYWALL_RE.search(line):
            return line
    return None


def _body_lines(page) -> set[str]:
    return {ln.strip() for ln in (page.inner_text("body") or "").splitlines()
            if ln.strip()}


def pick_category(page, wanted: str) -> str | None:
    """Type into the Downshift typeahead and click the matching suggestion.

    The menu id is the input id with '-input' swapped for '-menu'. Do NOT use a
    bare li/[role=option] selector: it matches the site header nav and returns
    Legal/Finance/Insurance as though they were categories (cost a recon pass
    on 2026-08-05).
    """
    ta = page.query_selector("input[name='vertical_name']")
    if not ta:
        return None
    menu_id = (ta.evaluate("e => e.id") or "").replace("-input", "-menu")
    # Recon typed lowercase and got hits; the term is a substring match, so
    # lead with a short lowercase stem rather than the capitalised full name.
    stem = wanted.split()[0].lower()
    opts: list[str] = []
    for attempt in range(3):
        ta.click()
        ta.press("Meta+A")
        page.wait_for_timeout(250)
        ta.type(stem, delay=110)
        page.wait_for_timeout(2500)
        opts = page.evaluate("""(mid) => {
            const m = document.getElementById(mid)
                   || document.querySelector('ul[role="listbox"]')
                   || document.querySelector('[role="listbox"]');
            if (!m) return [];
            return Array.from(m.querySelectorAll('li,[role="option"]'))
                        .map(o => (o.innerText || '').trim()).filter(Boolean);
        }""", menu_id)
        print(f"  attempt {attempt + 1}: id={menu_id!r} suggestions={opts}")
        if opts:
            break
        menu_id = (ta.evaluate("e => e.id") or "").replace("-input", "-menu")
    if wanted not in opts:
        return None
    page.evaluate("""([mid, want]) => {
        const m = document.getElementById(mid)
               || document.querySelector('ul[role="listbox"]');
        for (const o of m.querySelectorAll('li,[role="option"]'))
            if ((o.innerText || '').trim() === want) { o.click(); return; }
    }""", [menu_id, wanted])
    page.wait_for_timeout(800)
    return wanted


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--category", default=DEFAULT_CATEGORY)
    ap.add_argument("--dry-run", action="store_true",
                    help="fill step 1 but never click through")
    args = ap.parse_args()

    s = Session(playbook="form-fill", slug=args.slug,
                live=not args.dry_run).start(headless=False)
    page = s.page
    truth = company_truth(s.company_id) or {}
    if not truth.get("name") or not truth.get("postal_code"):
        print("no NAP truth (name + zip required) — refusing to submit")
        return 1
    print(f"Expertise.com application for {truth['name']} "
          f"({truth.get('city')}, {truth.get('state')} {truth['postal_code']})")

    page.goto(FORM_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(8000)
    s.audit_shot("expertise-step1-blank")

    website = truth.get("website") or ""
    # focus()+type, never fill(): these are React-controlled inputs and fill()
    # sets the value without firing the events React listens for, so the form
    # stays "empty" as far as the app is concerned. Same trap as Houzz.
    for sel, val in (("input[name='company']", truth["name"]),
                     ("input[name='00N3i00000DEQ9d']", website),
                     ("input[name='Zip_Code__c']", truth["postal_code"])):
        el = page.query_selector(sel)
        if not el:
            print(f"  MISSING FIELD {sel} — form changed, stopping")
            s.audit_shot("expertise-missing-field")
            return 2
        el.click()
        el.press("Meta+A")
        el.type(val, delay=45)
        page.wait_for_timeout(250)
    chosen = pick_category(page, args.category)
    if not chosen:
        print(f"category {args.category!r} not offered — stopping rather than "
              f"filing under the wrong vertical")
        s.audit_shot("expertise-category-miss")
        ledger(s.company_id, s.playbook, "expertise-create",
               "needs_supervised_run", live=not args.dry_run)
        return 2
    print(f"  step 1 filled: {truth['name']} | {website} | "
          f"{truth['postal_code']} | {chosen}")
    s.audit_shot("expertise-step1-filled")

    if args.dry_run:
        print("dry run — not clicking through")
        return 0
    if not s.guard_live(f"submit Expertise.com review request for {truth['name']}"):
        print("guard_live declined — nothing submitted")
        return 0

    baseline = _body_lines(page)
    page.click("button:has-text(\"Let's get started!\")")
    page.wait_for_timeout(6000)
    s.audit_shot("expertise-step2")
    hit = _paywall(page, baseline)
    if hit:
        print(f"\nPAID FUNNEL DETECTED, stopping: {hit!r}")
        s.audit_shot("expertise-paywall")
        ledger(s.company_id, s.playbook, "expertise-create", "review_needed",
               live=True, detail=f"paid-funnel wall: {hit[:120]}")
        return 3
    _dump(page, "STEP 2 — contact info")

    # WHOSE contact details go on the request (Santino, 2026-08-05): OURS, not
    # the client's. We are their marketing agency filing this for them, and
    # Expertise's follow-up is a sales pitch for the paid Featured Partner
    # product. That belongs in our inbox, not on a restoration owner's phone
    # while he is on a job. Same reasoning as the Houzz plus-aliases.
    contact = {
        "first_name": AGENCY_FIRST,
        "last_name": AGENCY_LAST,
        "email": f"contact+{args.slug}@restorationai.io",
        "00N3i00000DZFN5": AGENCY_PHONE,
    }
    for name, val in contact.items():
        el = page.query_selector(f"input[name='{name}']")
        if not el:
            print(f"  MISSING step-2 field {name!r} — form changed, stopping")
            s.audit_shot("expertise-step2-missing-field")
            return 2
        el.click()
        el.press("Meta+A")
        el.type(val, delay=45)
        page.wait_for_timeout(200)
    print(f"  step 2 filled: {AGENCY_FIRST} {AGENCY_LAST} | "
          f"{contact['email']} | {AGENCY_PHONE}")
    s.audit_shot("expertise-step2-filled")

    baseline2 = _body_lines(page)
    page.click("button:has-text('Next')")
    page.wait_for_timeout(6000)
    s.audit_shot("expertise-step3")
    hit = _paywall(page, baseline | baseline2)
    if hit:
        print(f"\nPAID FUNNEL DETECTED at step 3, stopping: {hit!r}")
        s.audit_shot("expertise-paywall-step3")
        ledger(s.company_id, s.playbook, "expertise-create", "review_needed",
               live=True, detail=f"paid-funnel wall at step 3: {hit[:120]}")
        return 3
    _dump(page, "STEP 3 — 'Your Objective'")
    # input[name='desired_monthly_clients'] — Expertise's sales-qualification
    # field. It carries no `required` attribute but Next does NOT advance while
    # it is blank, so it is required in practice.
    #
    # We enter 1, decided by Santino on 2026-08-05. It is the minimum that
    # satisfies validation and it keeps us out of their high-intent sales
    # queue. Treat it as a form toll, not an answer: we do not know how many
    # jobs a month any of these owners want, and putting an invented growth
    # target in a client's mouth is the same class of fabrication the concierge
    # guards exist to stop. If Expertise ever asks, this is OUR entry on the
    # client's behalf and no client has stated a figure.
    el = page.query_selector("input[name='desired_monthly_clients']")
    if el:
        el.click()
        el.press("Meta+A")
        el.type(DESIRED_MONTHLY_CLIENTS, delay=60)
        page.wait_for_timeout(300)
        print(f"  step 3: desired_monthly_clients={DESIRED_MONTHLY_CLIENTS} "
              f"(our standard entry, not a client figure)")
    baseline3 = _body_lines(page)
    page.click("button:has-text('Next')")
    page.wait_for_timeout(6000)
    s.audit_shot("expertise-step4")
    hit = _paywall(page, baseline | baseline2 | baseline3)
    if hit:
        print(f"\nPAID FUNNEL DETECTED at step 4, stopping: {hit!r}")
        s.audit_shot("expertise-paywall-step4")
        ledger(s.company_id, s.playbook, "expertise-create", "review_needed",
               live=True, detail=f"paid-funnel wall at step 4: {hit[:120]}")
        return 3
    _dump(page, "STEP 4 — 'Verify'")
    body = page.inner_text("body") or ""
    done = re.search(r"thank you|received|submitted|we'?ll be in touch|"
                     r"someone will|success", body, re.I)
    if done:
        line = next((l.strip() for l in body.splitlines()
                     if done.re.search(l) and len(l.strip()) < 200), done.group(0))
        print(f"\nAPPLICATION SUBMITTED — Expertise says: {line!r}")
        ledger(s.company_id, s.playbook, "expertise-create", "done",
               live=True, detail=f"review request filed ({chosen}): {line[:160]}")
        return 0
    print("\nStep 4 is Expertise's CALENDLY SALES-CALL BOOKING, not a "
          "confirmation. Nothing here says the request was received, so this "
          "client is NOT applied. See the module docstring.")
    ledger(s.company_id, s.playbook, "expertise-create", "needs_supervised_run",
           live=True, detail="steps 1-3 filled; step 4 is a Calendly sales call and the embed is broken — submission NOT confirmed, do not report applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
