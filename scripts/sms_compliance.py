#!/usr/bin/env python3
"""sms_compliance.py — what carrier review checks, as code, shared by the
toll-free (tollfree_autoreg.py) and A2P 10DLC (a2p_provision.py) pipelines.

Every rule here is a rejection we already paid for. Before anything is
submitted, `preflight()` says whether the client's WEBSITE and DATA will pass,
so a registration goes in right the first time instead of bouncing.

LESSONS (keep this list current; docs/SMS-COMPLIANCE.md mirrors it):
  1. LEGAL NAME + DBA (DryCor 2026-09/10, error 30484 "Business Name Must
     Match Official Records"). Submitting only the brand ("DRYCOR RESTORE")
     was rejected; the retry with only the legal name was rejected too.
     What passes: BusinessName = the entity the EIN is registered to
     (company_phone_setup.legal_business_name), DoingBusinessAs = the brand,
     AdditionalInformation saying "{brand} is the trade name of {legal}".
  2. THE WEBSITE MUST NAME THE LEGAL ENTITY. Reviewers open the site. The
     footer must read "(c) {legal}, doing business as {brand}" (build_site
     now renders that whenever the vaulted legal name differs from the
     brand) and the privacy/terms pages state the trade-name relationship.
  3. EIN WITH IDENTIFIER (DISS 2026-09-08, error 30527): send
     BusinessRegistrationNumber AND BusinessRegistrationIdentifier=EIN.
  4. SMS PRIVACY CLAUSE (A2P campaign vetting; Davis campaign FAILED
     2026-10-01): the privacy page must say mobile numbers / SMS opt-in data
     are never shared with third parties for marketing, and describe
     frequency, rates, STOP and HELP.
  5. PHYSICAL ADDRESS: A2P customer profiles reject PO boxes; use the
     street address on file.
  6. ENTITY TYPE must match the IRS record (LLC vs Corporation vs sole
     prop); a2p_state.business_type overrides the LLC default.
  7. A2P TRUSTHUB OBJECTS LIVE IN THE CLIENT SUBACCOUNT, linked to our
     approved ISV primary profile in the master (brands failed "Unable to
     fetch A2P Profile Bundle" when built in the master).
"""
from __future__ import annotations

import re
import urllib.request

_SUFFIX = re.compile(r"\b(llc|l l c|inc|incorporated|corp|corporation|co|"
                     r"company|ltd|pllc|lp|llp)\b")


def entity_key(name: str) -> str:
    """Compare entity names ignoring punctuation, '&' vs 'and', and LLC/Inc."""
    n = re.sub(r"[^a-z0-9 ]", " ", str(name or "").lower().replace("&", " and "))
    return re.sub(r"\s+", " ", _SUFFIX.sub(" ", n)).strip()


def distinct_legal(legal: str, brand: str) -> bool:
    """True when the legal entity is a different name than the brand, i.e.
    the submission needs a DBA and the site needs a trade-name line."""
    return bool(legal) and entity_key(legal) != entity_key(brand)


def _fetch(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return ""


def _site(website: str) -> str:
    w = (website or "").strip().rstrip("/")
    if w and not w.startswith("http"):
        w = "https://" + w
    return w


def site_names_legal(website: str, legal: str) -> bool:
    """The homepage (footer) or privacy page shows the legal entity."""
    base = _site(website)
    if not base or not legal:
        return False
    want = entity_key(legal)
    for path in ("/", "/privacy/"):
        html = re.sub(r"<[^>]+>", " ", _fetch(base + path))
        if want and want in entity_key(html.replace("&amp;", "&")):
            return True
    return False


def site_has_sms_clause(website: str) -> bool:
    base = _site(website)
    html = _fetch(base + "/privacy/").lower() if base else ""
    return ("mobile information" in html or "sms" in html) and "stop" in html


def tf_identity_fields(brand: str, legal: str, website: str) -> dict:
    """BusinessName / DoingBusinessAs / AdditionalInformation for a Twilio
    toll-free verification (lesson 1)."""
    if not distinct_legal(legal, brand):
        return {"BusinessName": legal or brand}
    w = _site(website)
    return {
        "BusinessName": legal,
        "DoingBusinessAs": brand,
        "AdditionalInformation": (
            f"{brand} is the trade name of {legal}. The website footer and "
            f"legal pages state this" + (f": {w}/privacy/" if w else ".")),
    }


def preflight(brand: str, legal: str, website: str,
              need_sms_clause: bool = False) -> list[str]:
    """Blocking problems a reviewer would reject on; [] means go."""
    problems = []
    if distinct_legal(legal, brand) and not site_names_legal(website, legal):
        problems.append(
            f"website does not name the legal entity '{legal}' (footer should "
            f"read '(c) {legal}, doing business as {brand}'; redeploy the site "
            "so build_site renders it)")
    if need_sms_clause and not site_has_sms_clause(website):
        problems.append("privacy page has no SMS / mobile-information clause "
                        "(add the 'SMS and mobile information is never shared' "
                        "+ Text Messaging sections)")
    return problems
