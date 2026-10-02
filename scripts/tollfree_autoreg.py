#!/usr/bin/env python3
"""tollfree_autoreg.py — automatic toll-free SMS registration for the fleet.

Santino 2026-09-03: every client's AI dispatcher line should be a VERIFIED
toll-free, registered automatically, kept separate from the DNI tracking
pool. This script is the engine:

  audit               dry-run readiness report (default). Walks every ACTIVE
                      client and prints what the automation WOULD do — submit,
                      ask for the EIN, or skip — without touching anything.
  submit --company X  generate the branded opt-in consent card, upload it,
                      and submit the Twilio toll-free verification for one
                      company. Dry-run unless --apply.
  submit-ready        submit every WOULD-SUBMIT client from the audit.
                      Dry-run unless --apply.

The submission recipe is the one proven live on DISS 2026-09-03 (HHb4bc06,
accepted PENDING_REVIEW): business-identity triple (BusinessType
PRIVATE_PROFIT + EIN + authority/country), business contact = the company's
contact-card owner (NEVER management_contacts), OptInType VERBAL with a
generated consent-documentation image, branded ProductionMessageSample.

Readiness bar (all required):
  * active company (status not Inactive/Cancelled/suspended)
  * toll-free agent line (agent_phone_1 in the 8xx ranges)
  * Twilio subaccount creds + resolvable PhoneNumber SID
  * EIN (company_phone_setup.business_ein or companies.ein, 9 digits)
  * owner contact card with a phone (integration_settings.contacts)
  * legal address (street + city + state + zip)
  * not already submitted (compliance_status approved/pending)

Missing ONLY the EIN -> verdict ASK-EIN (the Monica watcher's queue).
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

TF_RE = re.compile(r"^\+1(800|833|844|855|866|877|888)")
INACTIVE = {"inactive", "cancelled", "canceled", "suspended", "paused"}


def _sb(method: str, path: str, body=None, prefer="return=representation"):
    url = os.environ["SUPABASE_URL"].rstrip("/") + path
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    req = urllib.request.Request(url, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Prefer": prefer})
    with urllib.request.urlopen(req) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


def _e164(s: str) -> str:
    d = re.sub(r"\D", "", s or "")
    if len(d) == 10:
        return "+1" + d
    if len(d) == 11 and d.startswith("1"):
        return "+" + d
    return ("+" + d) if d else ""


def _ein_digits(s: str) -> str | None:
    d = re.sub(r"\D", "", s or "")
    return d if len(d) == 9 and not d.startswith("00") else None


def owner_card(contacts) -> dict | None:
    """Same pick order as app-work utils/businessOwnerContact.ts."""
    cards = contacts if isinstance(contacts, list) else []
    def phone(c): return _e164(c.get("cell") or c.get("phone") or "")
    owners = [c for c in cards if str(c.get("role", "")).lower() == "owner"]
    for pool in ([c for c in owners if c.get("preferred")], owners,
                 [c for c in cards if c.get("preferred") and phone(c)],
                 [c for c in cards if phone(c)]):
        if pool:
            return pool[0]
    return None


def fetch_fleet() -> list[dict]:
    rows = _sb("GET", "/rest/v1/company_phone_setup?select=id,agent_phone_1,"
               "compliance_status,business_ein,twilio_subaccount_sid,"
               "twilio_auth_token,twilio_phone_number_sid,opt_in_image_url,"
               "legal_business_name,tollfree_resubmit"
               "&limit=1000") or []
    comps = {c["id"]: c for c in (_sb("GET", "/rest/v1/companies?select=id,"
             "name,status,plan,ein,address,city,state,postal_code,website,phone,"
             "integration_settings&limit=1000") or [])}
    out = []
    for r in rows:
        c = comps.get(r["id"])
        if not c:
            continue
        r["company"] = c
        out.append(r)
    return out


def assess(r: dict) -> tuple[str, list[str]]:
    """-> (verdict, missing[]) — SUBMITTED | READY | ASK-EIN | SKIP"""
    c = r["company"]
    if str(c.get("status") or "").strip().lower() in INACTIVE:
        return "SKIP", ["inactive"]
    # Santino 2026-09-03: the pipeline targets the Rank AI plan only —
    # Leakproof / Rapid Response era accounts are out of scope.
    if (c.get("plan") or "").strip().lower() != "rank ai":
        return "SKIP", [f"plan={c.get('plan') or 'unset'}"]
    if (r.get("compliance_status") or "not_started") in ("approved", "pending"):
        return "SUBMITTED", []
    if (r.get("compliance_status") or "") == "rejected":
        # A rejection needs a human to fix the flagged item first — the
        # watch cycle must never blind-resubmit the same package.
        return "SKIP", ["rejected — human resubmit"]
    missing = []
    if not TF_RE.match(r.get("agent_phone_1") or ""):
        missing.append("toll-free agent line")
    if not (r.get("twilio_subaccount_sid") and r.get("twilio_auth_token")):
        missing.append("twilio creds")
    ein = _ein_digits(r.get("business_ein") or c.get("ein") or "")
    card = owner_card((c.get("integration_settings") or {}).get("contacts"))
    if not (card and _e164(card.get("cell") or card.get("phone") or "")):
        missing.append("owner contact card w/ phone")
    if not (c.get("address") and c.get("city") and c.get("state")
            and c.get("postal_code")):
        missing.append("legal address")
    if missing:
        return "SKIP", missing + ([] if ein else ["ein"])
    if not ein:
        return "ASK-EIN", ["ein"]
    return "READY", []


# ---------------------------------------------------------------- opt-in card

def render_optin_card(name: str, tf_display: str, address_line: str,
                      website: str, variant: int = 1) -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1200, 1660 + (220 if variant >= 2 else 0)
    img = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(img)

    def F(size, bold=False):
        # macOS Helvetica first; ubuntu CI runners carry DejaVu instead —
        # the hardcoded mac path crashed every CI submit run mid-batch and
        # silently blocked all cloud submissions (found 2026-09-09).
        candidates = [("/System/Library/Fonts/Helvetica.ttc",
                       1 if bold else 0),
                      ("/usr/share/fonts/truetype/dejavu/"
                       + ("DejaVuSans-Bold.ttf" if bold
                          else "DejaVuSans.ttf"), 0)]
        for path, idx in candidates:
            try:
                return ImageFont.truetype(path, size, index=idx)
            except OSError:
                continue
        return ImageFont.load_default()

    def wrap(text, font, maxw):
        words, lines, cur = text.split(), [], ""
        for w_ in words:
            t = (cur + " " + w_).strip()
            if d.textlength(t, font=font) <= maxw:
                cur = t
            else:
                lines.append(cur)
                cur = w_
        if cur:
            lines.append(cur)
        return lines

    M = 80
    d.rectangle([0, 0, W, 190], fill="#0f2547")
    d.text((M, 52), "SMS OPT-IN CONSENT DOCUMENTATION", font=F(40, True),
           fill="#ffffff")
    d.text((M, 118), f"{name}   |   Toll-Free {tf_display}", font=F(30),
           fill="#b9c8e4")
    y = 250
    d.text((M, y), "OPT-IN METHOD: VERBAL CONSENT ON INBOUND CUSTOMER CALLS",
           font=F(28, True), fill="#0f2547"); y += 70
    body, bold = F(28), F(28, True)
    for line in wrap(f"Customers call {name} for service. During the call, "
                     "and before any text message is ever sent, the phone "
                     "receptionist asks the caller for permission to text "
                     "them. The exact consent request read to every caller "
                     "is:", body, W - 2 * M):
        d.text((M, y), line, font=body, fill="#333b47"); y += 42
    y += 24
    quote = ('"Would you like me to text you at this number with updates '
             "about your service request? Message frequency varies and "
             "message and data rates may apply. You can reply STOP at any "
             'time to opt out, or HELP for help."')
    qlines = wrap(quote, F(29), W - 2 * M - 140)
    qh = len(qlines) * 46 + 60
    d.rounded_rectangle([M, y, W - M, y + qh], radius=18, fill="#eef3fb",
                        outline="#c6d5ee", width=2)
    d.rectangle([M, y, M + 10, y + qh], fill="#2f66c4")
    qy = y + 32
    for line in qlines:
        d.text((M + 60, qy), line, font=F(29), fill="#15325e"); qy += 46
    y += qh + 44
    d.rounded_rectangle([M, y, M + 44, y + 44], radius=8, outline="#2f66c4",
                        width=4)
    d.line([M + 10, y + 22, M + 19, y + 33], fill="#2f66c4", width=6)
    d.line([M + 19, y + 33, M + 36, y + 10], fill="#2f66c4", width=6)
    d.text((M + 64, y + 2), "Text messages are sent ONLY after the caller "
           "verbally answers YES.", font=bold, fill="#0f2547")
    y += 66
    d.text((M + 64, y), "Callers who decline are never sent a message.",
           font=body, fill="#333b47")
    y += 76
    d.text((M, y), "FIRST MESSAGE SENT AFTER CONSENT (SAMPLE):",
           font=F(28, True), fill="#0f2547"); y += 56
    sms = (f"{name}: Thanks for calling! We will text you updates about "
           "your service request at this number. Msg frequency varies. "
           "Msg & data rates may apply. Reply STOP to opt out, HELP for "
           "help.")
    slines = wrap(sms, F(27), W - 2 * M - 360)
    sh = len(slines) * 42 + 52
    d.rounded_rectangle([M + 40, y, W - M - 220, y + sh], radius=26,
                        fill="#e9f6ec", outline="#bfe3c8", width=2)
    sy = y + 26
    for line in slines:
        d.text((M + 80, sy), line, font=F(27), fill="#1d4d2a"); sy += 42
    y += sh + 52
    if variant >= 2:
        d.text((M, y), "THE OPT-IN FLOW, STEP BY STEP:", font=F(28, True),
               fill="#0f2547"); y += 52
        steps = [
            f"1.  A customer calls {name} needing service.",
            "2.  The receptionist reads the consent request above, "
            "including the frequency, rate, and STOP/HELP disclosures.",
            "3.  Only if the caller clearly answers YES is the number "
            "marked opted-in and the confirmation text sent.",
            "4.  Replying STOP at any time halts all messages immediately; "
            "HELP returns assistance. Numbers are never shared or sold.",
        ]
        for s in steps:
            for line in wrap(s, body, W - 2 * M - 40):
                d.text((M + 20, y), line, font=body, fill="#333b47"); y += 42
            y += 6
    else:
        for line in wrap("Opt-outs are honored automatically: replying STOP "
                         "immediately stops all future messages. This toll-free "
                         "number is used exclusively for customer-care "
                         "conversations with customers who have requested them "
                         "(appointment updates, arrival times, and service "
                         "follow-ups). No marketing lists are used and phone "
                         "numbers are never shared or sold.", body, W - 2 * M):
            d.text((M, y), line, font=body, fill="#333b47"); y += 42
    d.rectangle([0, H - 110, W, H], fill="#f2f4f8")
    d.text((M, H - 78), f"{name}  •  {address_line}  •  {website}",
           font=F(24), fill="#5a6474")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def upload_optin_card(cid: str, png: bytes) -> str:
    sb = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    path = f"branding/{cid}/compliance/sms-optin-consent.png"
    req = urllib.request.Request(f"{sb}/storage/v1/object/{path}",
        method="POST", data=png,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "image/png",
                 "x-upsert": "true"})
    urllib.request.urlopen(req)
    return f"{sb}/storage/v1/object/public/{path}"


# ---------------------------------------------------------------- submission

def _tf_display(e164: str) -> str:
    d = re.sub(r"\D", "", e164)[-10:]
    return f"+1 ({d[0:3]}) {d[3:6]}-{d[6:]}"


def resolve_pn_sid(r: dict) -> str | None:
    """The stored twilio_phone_number_sid may belong to a different number —
    resolve the SID for agent_phone_1 live from the subaccount."""
    sid, tok = r["twilio_subaccount_sid"], r["twilio_auth_token"]
    auth = base64.b64encode(f"{sid}:{tok}".encode()).decode()
    q = urllib.parse.quote(r["agent_phone_1"])
    req = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}"
        f"/IncomingPhoneNumbers.json?PhoneNumber={q}",
        headers={"Authorization": "Basic " + auth})
    try:
        with urllib.request.urlopen(req) as resp:
            nums = json.load(resp).get("incoming_phone_numbers") or []
        return nums[0]["sid"] if nums else None
    except urllib.error.HTTPError:
        return None


def submit_one(r: dict, apply: bool) -> bool:
    c = r["company"]
    cid, name = r["id"], (c.get("name") or "").strip()
    card = owner_card((c.get("integration_settings") or {}).get("contacts"))
    ein9 = _ein_digits(r.get("business_ein") or c.get("ein") or "")
    ein_fmt = f"{ein9[:2]}-{ein9[2:]}"
    contact_phone = _e164(card.get("cell") or card.get("phone") or "")
    website = (c.get("website") or "").strip()
    if website and not website.startswith("http"):
        website = "https://" + website
    addr_line = (f"{c['address']}, {c['city']}, {c['state']} "
                 f"{c['postal_code']}")
    tf = r["agent_phone_1"]
    print(f"\n[{name}] {tf}  EIN {ein_fmt}  contact "
          f"{card.get('first_name')} {card.get('last_name')} {contact_phone}")
    pn_sid = resolve_pn_sid(r)
    if not pn_sid:
        print(f"  ERROR: could not resolve PhoneNumber SID for {tf} in "
              "subaccount — SKIPPING")
        return False
    # Carrier-review preflight (scripts/sms_compliance.py lessons 1-2): a
    # registration whose website does not name the legal entity bounces with
    # 30484. Hold it and say exactly what to fix instead of burning a review.
    import sms_compliance as smc
    legal = (r.get("legal_business_name") or "").strip()
    problems = smc.preflight(name, legal, website)
    if problems:
        print("  HOLD (would be rejected): " + "; ".join(problems))
        if apply:
            _sb("POST", "/rest/v1/marketing_ops_notes", {
                "company_id": cid, "author": "tollfree-autoreg", "status": "open",
                "body": ("[TODO-SANTINO] Toll-free registration HELD before submit: "
                         + "; ".join(problems))[:1900]}, prefer="return=minimal")
        return False
    if not apply:
        print("  [dry-run] would generate opt-in card + submit TFV")
        return True
    url = r.get("opt_in_image_url")
    if not url:
        png = render_optin_card(name, _tf_display(tf), addr_line,
                                website or "")
        url = upload_optin_card(cid, png)
        print(f"  opt-in card uploaded: {url}")
    auth = base64.b64encode(
        f"{r['twilio_subaccount_sid']}:{r['twilio_auth_token']}"
        .encode()).decode()
    params = {
        **smc.tf_identity_fields(name, legal, website),
        "BusinessWebsite": website or "",
        "NotificationEmail": card.get("email") or "",
        "UseCaseCategories": "CUSTOMER_CARE",
        "UseCaseSummary": "Restoration services emergency dispatch and "
                          "appointment scheduling.",
        "ProductionMessageSample":
            f"{name}: Thanks for calling! We will text you updates about "
            "your service request at this number. Msg frequency varies. "
            "Msg & data rates may apply. Reply STOP to opt out, HELP for "
            "help.",
        "OptInImageUrls": url,
        "OptInType": "VERBAL",
        "MessageVolume": "10",
        "TollfreePhoneNumberSid": pn_sid,
        "BusinessStreetAddress": c["address"],
        "BusinessCity": c["city"],
        "BusinessStateProvinceRegion": c["state"],
        "BusinessPostalCode": c["postal_code"],
        "BusinessCountry": "US",
        "BusinessContactFirstName": card.get("first_name") or "",
        "BusinessContactLastName": card.get("last_name") or "",
        "BusinessContactEmail": card.get("email") or "",
        "BusinessContactPhone": contact_phone,
        "BusinessType": "PRIVATE_PROFIT",
        "BusinessRegistrationNumber": ein_fmt,
        "BusinessRegistrationAuthority": "EIN",
        # DIS 2026-09-08: without BusinessRegistrationIdentifier Twilio
        # treats the number as unclassified and rejects with "Business
        # Registration Number Is Missing or Invalid" (30527) even when the
        # EIN itself is present and correct. Authority alone is NOT enough.
        "BusinessRegistrationIdentifier": "EIN",
        "BusinessRegistrationCountry": "US",
    }
    req = urllib.request.Request(
        "https://messaging.twilio.com/v1/Tollfree/Verifications",
        data=urllib.parse.urlencode(params).encode(),
        headers={"Authorization": "Basic " + auth,
                 "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req) as resp:
            res = json.load(resp)
    except urllib.error.HTTPError as e:
        print(f"  TWILIO REJECTED ({e.code}): {e.read().decode()[:300]}")
        return False
    print(f"  SUBMITTED: {res.get('sid')} status {res.get('status')}")
    _sb("PATCH", f"/rest/v1/company_phone_setup?id=eq.{cid}", {
        "compliance_status": "pending", "compliance_type": "TOLL_FREE",
        "compliance_submitted_at":
            datetime.now(timezone.utc).isoformat(),
        "legal_business_name": name, "business_ein": ein_fmt,
        "opt_in_image_url": url,
        "legal_business_address": json.dumps({
            "line1": c["address"], "city": c["city"], "state": c["state"],
            "zip": c["postal_code"], "country": "US"}),
    }, prefer="return=minimal")
    try:
        _sb("POST", "/rest/v1/marketing_work_log", {
            "company_id": cid, "actor": "tollfree_autoreg",
            "category": "compliance", "action": "tollfree-verification-submitted",
            "detail": f"Toll-free SMS verification submitted for {tf} "
                      f"({res.get('sid')})",
        }, prefer="return=minimal")
    except urllib.error.HTTPError as e:
        print(f"  (work_log line failed: {e.code} — submission itself is in)")
    return True


# ---------------------------------------------------------------- provision

N8N = "https://restorationai.app.n8n.cloud/webhook"


def _n8n(path: str, body: dict, timeout: int = 300):
    req = urllib.request.Request(f"{N8N}/{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        try:
            return json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return raw.decode()[:200]


def cmd_provision(args) -> int:
    """Purchase a toll-free dispatcher line for one company through the SAME
    n8n orchestration the app's ProvisionNumberModal uses (subaccount + SIP
    trunk on the first line, number purchase, Retell wiring), then write the
    company_phone_numbers row the modal writes. Initial lines only — no
    overage webhook (that path is for lines beyond the plan allowance)."""
    cid = args.company
    comp = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}&select=id,name,plan,"
                "status,transfer_primary,transfer_secondary,transfer_third")
            or [None])[0]
    if not comp:
        print(f"no company {cid}")
        return 1
    name = comp["name"].strip()
    if str(comp.get("status") or "").lower() in INACTIVE:
        print(f"[{name}] inactive — refusing")
        return 1
    if (comp.get("plan") or "").strip().lower() != "rank ai":
        print(f"[{name}] plan={comp.get('plan')} — Rank AI only, refusing")
        return 1
    existing = _sb("GET", "/rest/v1/company_phone_numbers?"
                   f"company_id=eq.{cid}&select=phone_number") or []
    setup = (_sb("GET", f"/rest/v1/company_phone_setup?id=eq.{cid}"
                 "&select=agent_phone_1") or [None])[0]
    if existing or (setup and setup.get("agent_phone_1")):
        print(f"[{name}] already has a line "
              f"({existing or setup.get('agent_phone_1')}) — refusing "
              "(one dispatcher line per client; a second is a human call)")
        return 1
    found = _n8n("find-twilio-numbers",
                 {"companyId": cid, "search": "", "type": "tollFree",
                  "timestamp": datetime.now(timezone.utc).isoformat()},
                 timeout=60)
    nums = []
    if isinstance(found, list) and found and isinstance(found[0], dict) \
            and "value" in found[0]:
        nums = found
    elif isinstance(found, list) and found and isinstance(found[0], dict):
        nums = found[0].get("numbers") or []
    elif isinstance(found, dict):
        nums = found.get("numbers") or []
    elif isinstance(found, list):
        nums = found
    if not nums:
        print(f"[{name}] no toll-free numbers returned by search")
        return 1
    pick = nums[0]["value"] if isinstance(nums[0], dict) else nums[0]
    print(f"[{name}] picked {pick}")
    if not args.apply:
        print("  [dry-run] would provision via n8n phone-number-setup "
              "(subaccount + trunk + purchase + Retell) and write the "
              "primary company_phone_numbers row")
        return 0
    res = _n8n("phone-number-setup",
               {"companyId": cid, "phone": pick, "isInitialLine": True,
                "timestamp": datetime.now(timezone.utc).isoformat()})
    print(f"  n8n phone-number-setup -> {str(res)[:120]}")
    _sb("POST", "/rest/v1/company_phone_numbers", {
        "company_id": cid, "phone_number": pick, "is_primary": True,
        "label": "Main Line",
        "transfer_primary": comp.get("transfer_primary"),
        "transfer_secondary": comp.get("transfer_secondary"),
        "transfer_third": comp.get("transfer_third"),
        "standard_outcome": "book_appointment",
        "emergency_outcome": "immediate_dispatch",
        "book_appointments_enabled": True,
        "verify_insurance_enabled": True,
        "mention_ai_identity_enabled": False,
        "collect_email_enabled": False,
        "call_acceptance_protocol": None,
        "rapid_disqualification_enabled": False,
    }, prefer="return=minimal")
    after = (_sb("GET", f"/rest/v1/company_phone_setup?id=eq.{cid}"
                 "&select=agent_phone_1,twilio_subaccount_sid") or [None])[0]
    print(f"  phone_setup after: agent_phone_1={after and after.get('agent_phone_1')} "
          f"subaccount={'yes' if after and after.get('twilio_subaccount_sid') else 'NO'}")
    return 0


# ---------------------------------------------------------- auto-resubmission

MAX_AUTO_RESUBMITS = 2

# rejection-reason keyword -> (strategy name, one-line description).
# ORDER MATTERS: first match wins. ein-identifier sits before legal-name so
# the dominant 30527 class ("Business Registration Number Missing/Invalid")
# gets the field-level fix — resubmits used to send only the strategy field,
# so the identifier the 09-08 fresh-submit fix added never reached rows
# already in the ladder (DIS re-rejected 09-09 exactly this way).
_STRATEGIES = [
    (("opt in", "opt-in", "optin", "consent", "image"),
     "optin-v2", "richer opt-in evidence: step-by-step consent-flow card"),
    (("website", "url", "web site"),
     "website-fix", "normalized/verified BusinessWebsite variant"),
    (("sample", "use case", "usecase", "message"),
     "usecase-detail", "expanded UseCaseSummary + explicit flow description"),
    (("registration", "ein", "tax", "30527"),
     "ein-identifier", "re-stamp EIN as BusinessRegistrationNumber with "
                       "Identifier=EIN (the 30527 fix)"),
    (("business name", "legal", "invalid", "official records", "30484"),
     "legal-name", "swap to the vaulted legal business name (invalid-EIN "
                   "class is usually an EIN/legal-name mismatch)"),
]


def _pick_strategy(reason: str, used: list[str]) -> tuple[str, str] | None:
    low = (reason or "").lower()
    for keys, sname, desc in _STRATEGIES:
        if sname in used:
            continue
        if any(k in low for k in keys):
            return sname, desc
    return None


def _website_variant(website: str) -> str | None:
    """Return a reachable variant of the site URL (https, then www)."""
    base = (website or "").strip()
    if not base:
        return None
    host = re.sub(r"^https?://", "", base).strip("/")
    for cand in (f"https://{host}/", f"https://www.{host}/"):
        try:
            req = urllib.request.Request(cand, method="HEAD",
                headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status < 400:
                    return cand
        except Exception:  # noqa: BLE001
            continue
    return None


def attempt_auto_resubmit(r: dict, ver: dict, apply: bool) -> bool:
    """One rung of the resubmission ladder (Santino 2026-09-03): classify
    Twilio's rejection reason, apply the matching fix, and UPDATE the
    rejected verification in place (Twilio allows edits in TWILIO_REJECTED).
    Each strategy is used at most once and the ladder is capped at
    MAX_AUTO_RESUBMITS — after that (or on an unrecognized reason) the
    rejection escalates to a human. Returns True when a resubmit went in."""
    c = r["company"]
    cid, name = r["id"], (c.get("name") or "").strip()
    reason = str(ver.get("rejection_reason") or "")
    track = r.get("tollfree_resubmit") or {}
    attempts = track.get("attempts") or []
    if len(attempts) >= MAX_AUTO_RESUBMITS:
        print(f"  [{name}] resubmit ladder exhausted "
              f"({len(attempts)} attempts) — escalating")
        return False
    picked = _pick_strategy(reason, [a.get("strategy") for a in attempts])
    if not picked:
        print(f"  [{name}] no unused strategy matches the rejection reason "
              "— escalating")
        return False
    sname, desc = picked
    print(f"  [{name}] auto-resubmit strategy: {sname} ({desc})"
          + ("" if apply else "  [dry-run]"))
    if not apply:
        return True

    fields: dict[str, str] = {}
    if sname == "optin-v2":
        website = (c.get("website") or "").strip()
        if website and not website.startswith("http"):
            website = "https://" + website
        addr_line = (f"{c.get('address')}, {c.get('city')}, "
                     f"{c.get('state')} {c.get('postal_code')}")
        png = render_optin_card(name, _tf_display(r["agent_phone_1"]),
                                addr_line, website, variant=2)
        sb = os.environ["SUPABASE_URL"].rstrip("/")
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        path = f"branding/{cid}/compliance/sms-optin-consent-v2.png"
        req = urllib.request.Request(f"{sb}/storage/v1/object/{path}",
            method="POST", data=png,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "image/png", "x-upsert": "true"})
        urllib.request.urlopen(req)
        fields["OptInImageUrls"] = f"{sb}/storage/v1/object/public/{path}"
    elif sname == "website-fix":
        good = _website_variant(c.get("website") or "")
        if not good:
            print("  website-fix: no reachable variant — escalating")
            return False
        fields["BusinessWebsite"] = good
    elif sname == "usecase-detail":
        fields["UseCaseSummary"] = (
            f"{name} is a local property-restoration company. Customers "
            "call the business needing emergency or scheduled service; "
            "during the call the receptionist asks for and records verbal "
            "consent to text. Messages are strictly customer care for that "
            "customer's own job: appointment confirmations, technician "
            "arrival times, and service follow-ups. No marketing, no "
            "lists, opt-out honored instantly via STOP.")
    elif sname == "ein-identifier":
        ein9 = re.sub(r"\D", "",
                      str(r.get("business_ein") or c.get("ein") or ""))
        if len(ein9) != 9:
            print("  ein-identifier: no 9-digit EIN on file — escalating")
            return False
        fields["BusinessRegistrationNumber"] = f"{ein9[:2]}-{ein9[2:]}"
        fields["BusinessRegistrationAuthority"] = "EIN"
        fields["BusinessRegistrationIdentifier"] = "EIN"
        fields["BusinessRegistrationCountry"] = "US"
    elif sname == "legal-name":
        legal = (r.get("legal_business_name") or "").strip()
        # DryCor 2026-09-21: the vault can hold the DBA, which is exactly
        # what got rejected. The client's uploaded paperwork outranks it.
        harvested = _scan_docs_for_legal_name(r)
        if harvested and harvested.lower() != legal.lower():
            print(f"  legal-name: docs say '{harvested}' "
                  f"(vault had '{legal or '—'}') — using it and re-vaulting")
            legal = harvested
            _sb("PATCH", f"/rest/v1/company_phone_setup?id=eq.{cid}",
                {"legal_business_name": legal}, prefer="return=minimal")
        if not legal or legal.lower() == name.lower():
            print("  legal-name: no distinct legal name in vault or docs — "
                  "escalating")
            return False
        # DryCor 2026-10-01: legal name ALONE was rejected again (30484). The
        # brand must ride along as DoingBusinessAs with the trade-name note.
        import sms_compliance as smc
        fields.update(smc.tf_identity_fields(name, legal, c.get("website") or ""))

    auth = base64.b64encode(
        f"{r['twilio_subaccount_sid']}:{r['twilio_auth_token']}"
        .encode()).decode()
    req = urllib.request.Request(
        f"https://messaging.twilio.com/v1/Tollfree/Verifications/{ver['sid']}",
        data=urllib.parse.urlencode(fields).encode(),
        headers={"Authorization": "Basic " + auth,
                 "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req) as resp:
            res = json.load(resp)
    except urllib.error.HTTPError as e:
        print(f"  resubmit update REJECTED by API ({e.code}): "
              f"{e.read().decode()[:200]} — escalating")
        return False
    attempts.append({"at": datetime.now(timezone.utc).isoformat(),
                     "sid": ver["sid"], "strategy": sname,
                     "reason": reason[:300]})
    _sb("PATCH", f"/rest/v1/company_phone_setup?id=eq.{cid}", {
        "compliance_status": "pending",
        "tollfree_resubmit": {"attempts": attempts},
    }, prefer="return=minimal")
    try:
        _sb("POST", "/rest/v1/marketing_work_log", {
            "company_id": cid, "actor": "tollfree_autoreg",
            "category": "compliance",
            "action": "tollfree-verification-resubmitted",
            "detail": f"Rejection ('{reason[:120]}') auto-resubmitted with "
                      f"strategy {sname}; attempt "
                      f"{len(attempts)}/{MAX_AUTO_RESUBMITS}; now "
                      f"{res.get('status')}",
        }, prefer="return=minimal")
    except urllib.error.HTTPError:
        pass
    print(f"  resubmitted ({res.get('status')}) — attempt "
          f"{len(attempts)}/{MAX_AUTO_RESUBMITS}")
    return True


# ------------------------------------------------------------- doc EIN scan

_DOC_EXTS = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".png": "image/png", ".webp": "image/webp",
             ".pdf": "application/pdf"}


def _scan_docs_for_ein(r: dict) -> str | None:
    """Hub-uploaded paperwork answer to the EIN ask: list the client's docs
    folders, read the newest few files with Claude, extract the EIN.
    Read-only; the caller decides whether to write."""
    cid = r["id"]
    sb = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    akey = os.environ.get("ANTHROPIC_API_KEY")
    if not akey:
        return None
    files: list[str] = []
    for folder in (f"{cid}/docs/inbox", f"{cid}/docs/other", f"{cid}/docs"):
        req = urllib.request.Request(
            f"{sb}/storage/v1/object/list/branding", method="POST",
            data=json.dumps({"prefix": folder, "limit": 10,
                             "sortBy": {"column": "created_at",
                                        "order": "desc"}}).encode(),
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                for o in json.load(resp) or []:
                    name = o.get("name") or ""
                    ext = os.path.splitext(name)[1].lower()
                    if o.get("id") and ext in _DOC_EXTS:
                        files.append(f"{folder}/{name}")
        except Exception:  # noqa: BLE001
            continue
    for path in files[:5]:
        ext = os.path.splitext(path)[1].lower()
        media = _DOC_EXTS[ext]
        try:
            req = urllib.request.Request(
                f"{sb}/storage/v1/object/branding/{path}",
                headers={"Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                blob = resp.read()
        except Exception:  # noqa: BLE001
            continue
        if len(blob) > 8_000_000:
            continue
        block = ({"type": "document",
                  "source": {"type": "base64", "media_type": media,
                             "data": base64.b64encode(blob).decode()}}
                 if media == "application/pdf" else
                 {"type": "image",
                  "source": {"type": "base64", "media_type": media,
                             "data": base64.b64encode(blob).decode()}})
        body = {
            "model": "claude-haiku-4-5-20251001", "max_tokens": 200,
            "system": "You read one business document. Find the US federal "
                      "EIN (9 digits, usually XX-XXXXXXX). Reply with ONLY "
                      'a JSON object: {"ein": "XX-XXXXXXX"} or '
                      '{"ein": null}. Never guess digits.',
            "messages": [{"role": "user", "content": [
                block, {"type": "text", "text": "Extract the EIN."}]}],
        }
        try:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages", method="POST",
                data=json.dumps(body).encode(),
                headers={"x-api-key": akey,
                         "anthropic-version": "2023-06-01",
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                res = json.load(resp)
            text = "".join(b.get("text", "")
                           for b in res.get("content") or [])
            m = re.search(r"(\d{2})-?(\d{7})", text)
            if m and not m.group(1).startswith("00"):
                ein = f"{m.group(1)}-{m.group(2)}"
                print(f"  [{r['company']['name']}] EIN {ein} read from "
                      f"uploaded document {path.split('/')[-1]}")
                return ein
        except Exception as e:  # noqa: BLE001
            print(f"  (doc-scan {path.split('/')[-1]}: {str(e)[:80]})")
    return None


_LEGAL_SUFFIX_RE = re.compile(
    r"\b(LLC|L\.L\.C\.|Inc\.?|Incorporated|Corp\.?|Corporation|Ltd\.?|"
    r"LLP|PLLC|P\.?A\.?|Company|Co\.)\s*$", re.I)


def _scan_docs_for_legal_name(r: dict) -> str | None:
    """The DryCor 2026-09-21 lesson: toll-free/TCR reviewers validate
    BusinessName against the entity the EIN is registered to, and the vault
    often holds the DBA the client trades under ("DRYCOR RESTORE"), not the
    registered entity ("Showalter Construction & Restoration, LLC"). The
    client's own uploaded paperwork carries the real one — COI insured
    lines ("<Legal Entity, LLC> DBA <brand>"), IRS EIN letters, W-9s.
    Read the newest few docs with Claude and return a corporate-suffixed
    legal entity name, or None. Read-only; the caller decides writes."""
    cid = r["id"]
    sb = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    akey = os.environ.get("ANTHROPIC_API_KEY")
    if not akey:
        return None
    brand = (r["company"].get("name") or "").strip()

    def _ls(prefix: str) -> list[dict]:
        req = urllib.request.Request(
            f"{sb}/storage/v1/object/list/branding", method="POST",
            data=json.dumps({"prefix": prefix, "limit": 30,
                             "sortBy": {"column": "created_at",
                                        "order": "desc"}}).encode(),
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp) or []
        except Exception:  # noqa: BLE001
            return []

    # {cid}/docs plus every one of its immediate subfolders (insurance/,
    # other/, inbox/... — clients file paperwork anywhere) + compliance/.
    folders = [f"{cid}/docs", f"{cid}/compliance"]
    folders[1:1] = [f"{cid}/docs/{o['name']}" for o in _ls(f"{cid}/docs")
                    if not o.get("id")]
    files: list[str] = []
    for folder in folders:
        for o in _ls(folder):
            name = o.get("name") or ""
            ext = os.path.splitext(name)[1].lower()
            if o.get("id") and ext in _DOC_EXTS:
                files.append(f"{folder}/{name}")
    # PDFs first: legal paperwork (COIs, IRS letters, W-9s) is PDF; loose
    # images are mostly signatures/logos and each costs a vision call.
    files.sort(key=lambda p: 0 if p.lower().endswith(".pdf") else 1)
    for path in files[:6]:
        ext = os.path.splitext(path)[1].lower()
        media = _DOC_EXTS[ext]
        try:
            req = urllib.request.Request(
                f"{sb}/storage/v1/object/branding/{path}",
                headers={"Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                blob = resp.read()
        except Exception:  # noqa: BLE001
            continue
        if len(blob) > 8_000_000:
            continue
        block = ({"type": "document",
                  "source": {"type": "base64", "media_type": media,
                             "data": base64.b64encode(blob).decode()}}
                 if media == "application/pdf" else
                 {"type": "image",
                  "source": {"type": "base64", "media_type": media,
                             "data": base64.b64encode(blob).decode()}})
        body = {
            "model": "claude-haiku-4-5-20251001", "max_tokens": 200,
            "system": "You read one business document. Find the REGISTERED "
                      "LEGAL ENTITY NAME of the business — the entity that "
                      "owns its EIN. On insurance certificates it is the "
                      "INSURED line; the pattern '<Legal Entity, LLC> DBA "
                      "<brand name>' means the part BEFORE 'DBA' is the "
                      "legal entity. A bare brand/DBA name with no "
                      "corporate suffix (LLC, Inc, Corp...) is NOT the "
                      "answer. Reply with ONLY a JSON object: "
                      '{"legal_name": "..."} or {"legal_name": null}. '
                      "Copy the name exactly; never guess.",
            "messages": [{"role": "user", "content": [
                block,
                {"type": "text", "text":
                    f"The business trades as \"{brand}\". Extract its "
                    "registered legal entity name."}]}],
        }
        try:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages", method="POST",
                data=json.dumps(body).encode(),
                headers={"x-api-key": akey,
                         "anthropic-version": "2023-06-01",
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                res = json.load(resp)
            text = "".join(b.get("text", "")
                           for b in res.get("content") or [])
            m = re.search(r'"legal_name"\s*:\s*"([^"]{4,120})"', text)
            if m:
                cand = m.group(1).strip().rstrip(".")
                if _LEGAL_SUFFIX_RE.search(cand):
                    print(f"  [{brand}] legal name '{cand}' read from "
                          f"uploaded document {path.split('/')[-1]}")
                    return cand
        except Exception as e:  # noqa: BLE001
            print(f"  (legal-name doc-scan {path.split('/')[-1]}: "
                  f"{str(e)[:80]})")
    return None


# --------------------------------------------------------------------- watch

def _latest_verification(r: dict) -> dict | None:
    """The subaccount's verification row for this client's number, or None."""
    if not (r.get("twilio_subaccount_sid") and r.get("twilio_auth_token")):
        return None
    auth = base64.b64encode(
        f"{r['twilio_subaccount_sid']}:{r['twilio_auth_token']}".encode()).decode()
    req = urllib.request.Request(
        "https://messaging.twilio.com/v1/Tollfree/Verifications?PageSize=20",
        headers={"Authorization": "Basic " + auth})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            vs = json.load(resp).get("verifications") or []
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        return None
    mine = [v for v in vs
            if v.get("tollfree_phone_number") == r.get("agent_phone_1")]
    return mine[0] if mine else None


def sync_pending_statuses(fleet: list[dict], apply: bool) -> None:
    """Poll Twilio for every compliance_status=pending client and record the
    verdict. Approvals: stamp + work-log (the dispatch fn's self-heal handles
    the actual sender cutover with the mid-drip guard). Rejections: stamp +
    file a [TODO-SANTINO] row with Twilio's reason so a human decides the
    resubmission."""
    for r in fleet:
        # "rejected" included (2026-09-08, DIS): the twilio-status-callback
        # webhook can stamp compliance_status=rejected BEFORE this cycle ever
        # sees TWILIO_REJECTED — a pending-only filter meant those rows never
        # entered the resubmission ladder and never got the TODO note. The
        # ladder's own attempt cap keeps this from looping.
        if (r.get("compliance_status") or "") not in ("pending", "rejected"):
            continue
        if not (r.get("twilio_subaccount_sid") and r.get("twilio_auth_token")
                and r.get("agent_phone_1")):
            continue
        c = r["company"]
        auth = base64.b64encode(
            f"{r['twilio_subaccount_sid']}:{r['twilio_auth_token']}"
            .encode()).decode()
        req = urllib.request.Request(
            "https://messaging.twilio.com/v1/Tollfree/Verifications?PageSize=20",
            headers={"Authorization": "Basic " + auth})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                vs = json.load(resp).get("verifications") or []
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            continue
        mine = [v for v in vs
                if v.get("tollfree_phone_number") == r["agent_phone_1"]]
        if not mine:
            continue
        status = mine[0].get("status")
        if status == "TWILIO_APPROVED":
            print(f"[{c['name']}] {r['agent_phone_1']} APPROVED"
                  + ("" if apply else "  [dry-run]"))
            if apply:
                _sb("PATCH", f"/rest/v1/company_phone_setup?id=eq.{r['id']}",
                    {"compliance_status": "approved"},
                    prefer="return=minimal")
                _sb("POST", "/rest/v1/marketing_work_log", {
                    "company_id": r["id"], "actor": "tollfree_autoreg",
                    "category": "compliance",
                    "action": "tollfree-verification-approved",
                    "detail": f"Toll-free {r['agent_phone_1']} approved by "
                              "Twilio; sender cutover proceeds via dispatch "
                              "self-heal once no contacts are mid-drip",
                }, prefer="return=minimal")
        elif status == "TWILIO_REJECTED":
            reason = (mine[0].get("rejection_reason") or "no reason given")
            print(f"[{c['name']}] {r['agent_phone_1']} REJECTED: "
                  f"{str(reason)[:120]}" + ("" if apply else "  [dry-run]"))
            # resubmission ladder first — escalate only when it declines
            if attempt_auto_resubmit(r, mine[0], apply):
                continue
            # EIN-class rejection with NO EIN on file (Frontline 2026-09-10):
            # the ein-identifier strategy cannot re-stamp what does not exist,
            # so this used to dead-end at [TODO-SANTINO]. Route it to the
            # SAME Monica loop fresh submits use: scan their docs/threads,
            # else file the EIN-ASK — capture + resubmit then run on later
            # cycles without a human.
            low_reason = str(reason).lower()
            ein_class = any(k in low_reason for k in
                            ("registration", "ein", "tax", "30527"))
            have_ein = _ein_digits(r.get("business_ein")
                                   or c.get("ein") or "")
            ein_missing = ein_class and not have_ein
            # EIN present but Twilio calls it INVALID and the ladder is out
            # of moves: have Monica CONFIRM the EIN + exact IRS legal name
            # with the client (one ask); a corrected EIN resets the ladder.
            if ein_class and have_ein and apply:
                marker = f"EIN-CONFIRM-{r['id']}"
                prior = _sb("GET", "/rest/v1/marketing_ops_notes?"
                            f"company_id=eq.{r['id']}&body=like.*{marker}*"
                            "&select=id&limit=1") or []
                if not prior:
                    _sb("POST", "/rest/v1/marketing_ops_notes", {
                        "company_id": r["id"],
                        "body": f"[{marker}] The carrier flagged this "
                                f"client's EIN ({have_ein[:2]}-{have_ein[2:]}) "
                                "as invalid for texting verification. Ask them "
                                "to double-check two things from their IRS "
                                "paperwork (CP 575 letter): the exact EIN and "
                                "the exact legal business name it is "
                                "registered under. Casual, one message.",
                    }, prefer="return=minimal")
                    print(f"  [{c['name']}] EIN-CONFIRM ask filed for Monica")
            if ein_missing:
                found = _scan_docs_for_ein(r) or _scan_threads_for_ein(r)
                if found and apply:
                    _sb("PATCH", f"/rest/v1/company_phone_setup?id=eq.{r['id']}",
                        {"business_ein": found}, prefer="return=minimal")
                    r["business_ein"] = found
                    print(f"  [{c['name']}] EIN {found} recovered from their "
                          "docs/threads — resubmitting")
                    if attempt_auto_resubmit(r, mine[0], apply):
                        continue
                elif not found:
                    marker = f"EIN-ASK-{r['id']}"
                    prior = _sb("GET", "/rest/v1/marketing_ops_notes?"
                                f"company_id=eq.{r['id']}&body=like.*{marker}*"
                                "&select=id&limit=1") or []
                    if not prior and apply:
                        _sb("POST", "/rest/v1/marketing_ops_notes", {
                            "company_id": r["id"],
                            "body": f"[{marker}] Ask the client for their EIN "
                                    "(federal tax ID, format 12-3456789): their "
                                    "toll-free texting verification needs it. "
                                    "One question, keep it casual.",
                        }, prefer="return=minimal")
                        print(f"  [{c['name']}] EIN-ASK filed — Monica asks on "
                              "her next run; capture + resubmit are automatic")
                    if apply:
                        _sb("PATCH",
                            f"/rest/v1/company_phone_setup?id=eq.{r['id']}",
                            {"compliance_status": "rejected"},
                            prefer="return=minimal")
                    r["compliance_status"] = "rejected" if apply else "pending"
                    continue
            if apply:
                _sb("PATCH", f"/rest/v1/company_phone_setup?id=eq.{r['id']}",
                    {"compliance_status": "rejected"},
                    prefer="return=minimal")
                # one open note per rejection, not one per daily cycle
                dupe = _sb("GET", "/rest/v1/marketing_ops_notes?"
                           f"company_id=eq.{r['id']}&status=eq.open"
                           "&body=like.*verification%20REJECTED*"
                           "&select=id&limit=1")
                if not dupe:
                    _sb("POST", "/rest/v1/marketing_ops_notes", {
                        "company_id": r["id"],
                        "body": f"[TODO-SANTINO] Toll-free verification REJECTED "
                                f"for {c['name']} ({r['agent_phone_1']}). Twilio "
                                f"reason: {str(reason)[:300]}. Fix the flagged "
                                "item and resubmit via tollfree_autoreg submit "
                                f"--company {r['id']} --apply.",
                    }, prefer="return=minimal")
            # local update so this run's ASK/READY pass sees the rejection
            r["compliance_status"] = "rejected" if apply else "pending"


def cmd_watch(args) -> int:
    """The recurring loop (CI): for every active Rank AI client with a
    toll-free dispatcher line —
      * missing ONLY the EIN  -> file the Monica ask once (marker
        EIN-ASK-{cid}; re-ask no sooner than 30 days)
      * READY                 -> submit the Twilio verification
    EIN capture happens in client_concierge (_maybe_capture_ein) when the
    client texts it back; this cycle then finds them READY and submits."""
    fleet = fetch_fleet()
    sync_pending_statuses(fleet, args.apply)
    asked = submitted = 0
    for r in fleet:
        v, _missing = assess(r)
        c, cid = r["company"], r["id"]
        if v == "READY":
            if (r.get("compliance_status") or "") == "rejected":
                # EIN landed after a rejection: the fix is an in-place
                # UPDATE of the rejected verification, not a fresh submit.
                ver = _latest_verification(r)
                if ver and ver.get("status") == "TWILIO_REJECTED":
                    track = r.get("tollfree_resubmit") or {}
                    last_ein = _ein_digits(str(track.get("last_ein") or ""))
                    now_ein = _ein_digits(r.get("business_ein") or "")
                    if now_ein and last_ein and now_ein != last_ein:
                        # corrected EIN -> fresh ladder
                        if args.apply:
                            _sb("PATCH",
                                f"/rest/v1/company_phone_setup?id=eq.{r['id']}",
                                {"tollfree_resubmit": {"attempts": [],
                                                       "last_ein": now_ein}},
                                prefer="return=minimal")
                        r["tollfree_resubmit"] = {"attempts": [],
                                                  "last_ein": now_ein}
                    if attempt_auto_resubmit(r, ver, args.apply):
                        submitted += 1
                    continue
            if submit_one(r, args.apply):
                submitted += 1
            continue
        if v != "ASK-EIN":
            # Wizard "don't have it handy" tap (Santino 2026-09-09): chase
            # the EIN EARLY, before the number-activation stage exists —
            # ein_followup_requested + no EIN behaves like ASK-EIN.
            ints_f = c.get("integration_settings") or {}
            if isinstance(ints_f, str):
                try:
                    ints_f = json.loads(ints_f)
                except ValueError:
                    ints_f = {}
            ein_now = _ein_digits(r.get("business_ein") or c.get("ein") or "")
            if not (ints_f.get("ein_followup_requested") and not ein_now):
                continue
        # Before asking (or re-asking): maybe the answer is already sitting
        # in their uploaded documents or texted into ANY of their GHL
        # threads — never ask for what we hold (Angie/ProRestoration
        # 2026-09-09: she texted the EIN in direct reply to our ask and the
        # tracked-conversation capture missed it for five days).
        found = _scan_docs_for_ein(r) or _scan_threads_for_ein(r)
        if found:
            if args.apply:
                _sb("PATCH", f"/rest/v1/company_phone_setup?id=eq.{cid}",
                    {"business_ein": found}, prefer="return=minimal")
                _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}&ein=is.null",
                    {"ein": found}, prefer="return=minimal")
                _sb("POST", "/rest/v1/marketing_work_log", {
                    "company_id": cid, "actor": "tollfree_autoreg",
                    "category": "compliance", "action": "ein-captured",
                    "detail": f"EIN {found} found in their uploaded docs or "
                              "message threads; submitting toll-free "
                              "verification"},
                    prefer="return=minimal")
                r["business_ein"] = found
                if assess(r)[0] == "READY" and submit_one(r, True):
                    submitted += 1
            else:
                print(f"  [dry-run] would write EIN {found} and submit")
            continue
        marker = f"EIN-ASK-{cid}"
        prior = _sb("GET", "/rest/v1/marketing_ops_notes?"
                    f"company_id=eq.{cid}&body=like.*{marker}*"
                    "&select=id,created_at&order=created_at.desc&limit=1") or []
        if prior:
            ts = re.sub(r"\.\d+", "", prior[0]["created_at"]).replace(" ", "T")
            if ts.endswith("+00"):
                ts += ":00"
            age = (datetime.now(timezone.utc)
                   - datetime.fromisoformat(ts)).days
            if age < 30:
                continue
        card = owner_card(
            (c.get("integration_settings") or {}).get("contacts")) or {}
        first = card.get("first_name") or "there"
        body = (f"[FOR MONICA] Ask {first} for the business federal EIN "
                "(tax ID, the 9-digit XX-XXXXXXX number) so we can register "
                "their new business texting line with the phone carriers - "
                "it is a compliance requirement and takes them ten seconds. "
                "They can just text the number back here. "
                f"(ref {marker})")
        print(f"[{c['name']}] filing EIN ask"
              + ("" if args.apply else "  [dry-run]"))
        if args.apply:
            _sb("POST", "/rest/v1/marketing_ops_notes",
                {"company_id": cid, "body": body}, prefer="return=minimal")
            asked += 1
    print(f"\nwatch done: {submitted} submitted, {asked} EIN ask(s) filed")
    return 0


def _scan_threads_for_ein(r: dict) -> str | None:
    """Recent inbound GHL messages of EVERY contact card, scanned for an
    EIN. Two accepted shapes: XX-XXXXXXX anywhere in a message, or a short
    message whose digits total exactly 9 (Roy 2026-09-04 sent his as
    \"(452) 521-329\", phone-app formatted). Read-only; returns None
    without GHL creds (CI needs GHL_API_KEY + GHL_LOCATION_ID)."""
    key = os.environ.get("GHL_API_KEY")
    loc = os.environ.get("GHL_LOCATION_ID")
    if not (key and loc):
        return None
    ints = r["company"].get("integration_settings") or {}
    if isinstance(ints, str):
        try:
            ints = json.loads(ints)
        except ValueError:
            return None
    ids = [c.get("ghl_contact_id") for c in ints.get("contacts") or []
           if c.get("ghl_contact_id")]
    hdrs = {"Authorization": f"Bearer {key}", "Version": "2021-07-28",
            "Accept": "application/json",
            # GHL's edge 403s the default urllib UA
            "User-Agent": "rank-ai-tollfree-autoreg/1.0"}
    hyphen = re.compile(r"\b(\d{2})[- ](\d{7})\b")
    for gcid in ids:
        try:
            q = urllib.parse.urlencode(
                {"locationId": loc, "contactId": gcid, "limit": 5})
            req = urllib.request.Request(
                f"https://services.leadconnectorhq.com/conversations/search?{q}",
                headers=hdrs)
            convs = json.load(urllib.request.urlopen(req, timeout=30)
                              ).get("conversations") or []
            for cv in convs:
                req2 = urllib.request.Request(
                    "https://services.leadconnectorhq.com/conversations/"
                    f"{cv['id']}/messages?limit=60", headers=hdrs)
                data = json.load(urllib.request.urlopen(req2, timeout=30))
                for m in (data.get("messages") or {}).get("messages") or []:
                    if m.get("direction") != "inbound":
                        continue
                    body = str(m.get("body") or "")
                    hit = hyphen.search(body)
                    if hit and not hit.group(1).startswith("00"):
                        return f"{hit.group(1)}-{hit.group(2)}"
                    digits = re.sub(r"\D", "", body)
                    if (len(body) <= 40 and len(digits) == 9
                            and not digits.startswith("00")):
                        return f"{digits[:2]}-{digits[2:]}"
        except Exception:  # noqa: BLE001 — scan is best-effort per contact
            continue
    return None


# --------------------------------------------------------------------- audit

def cmd_audit(_args) -> int:
    fleet = fetch_fleet()
    groups: dict[str, list] = {"READY": [], "ASK-EIN": [], "SUBMITTED": [],
                               "SKIP": []}
    for r in fleet:
        v, missing = assess(r)
        groups[v].append((r, missing))
    print(f"toll-free auto-registration readiness — {len(fleet)} clients\n")
    for v in ("READY", "ASK-EIN", "SUBMITTED", "SKIP"):
        rows = groups[v]
        print(f"== {v} ({len(rows)}) ==")
        for r, missing in sorted(rows, key=lambda x: x[0]["company"]["name"]):
            c = r["company"]
            line = f"  {c['name'][:40]:40} {r.get('agent_phone_1') or '-':15}"
            if v == "READY":
                ein9 = _ein_digits(r.get("business_ein") or c.get("ein"))
                line += f" EIN {ein9[:2]}-{ein9[2:]}"
            elif missing:
                line += " missing: " + ", ".join(missing)
            print(line)
        print()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("audit")
    ps = sub.add_parser("submit")
    ps.add_argument("--company", required=True)
    ps.add_argument("--apply", action="store_true")
    pr = sub.add_parser("submit-ready")
    pr.add_argument("--apply", action="store_true")
    pv = sub.add_parser("provision")
    pv.add_argument("--company", required=True)
    pv.add_argument("--apply", action="store_true")
    pw = sub.add_parser("watch")
    pw.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if args.cmd == "provision":
        return cmd_provision(args)
    if args.cmd == "watch":
        return cmd_watch(args)
    if args.cmd in (None, "audit"):
        return cmd_audit(args)
    fleet = fetch_fleet()
    if args.cmd == "submit":
        rows = [r for r in fleet if r["id"] == args.company]
        if not rows:
            print(f"no phone setup for {args.company}")
            return 1
        v, missing = assess(rows[0])
        if v != "READY":
            print(f"{args.company} is {v} (missing: {', '.join(missing)})")
            return 1
        return 0 if submit_one(rows[0], args.apply) else 1
    if args.cmd == "submit-ready":
        ready = [r for r in fleet if assess(r)[0] == "READY"]
        print(f"submit-ready: {len(ready)} client(s)"
              + ("" if args.apply else "  [dry-run]"))
        fails = 0
        for r in ready:
            if not submit_one(r, args.apply):
                fails += 1
        print(f"\ndone: {len(ready) - fails} ok, {fails} failed")
        return 1 if fails else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
