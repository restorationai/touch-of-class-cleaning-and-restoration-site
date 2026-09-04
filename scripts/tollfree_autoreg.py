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
INACTIVE = {"inactive", "cancelled", "canceled", "suspended"}


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
               "twilio_auth_token,twilio_phone_number_sid,opt_in_image_url"
               "&limit=1000") or []
    comps = {c["id"]: c for c in (_sb("GET", "/rest/v1/companies?select=id,"
             "name,status,ein,address,city,state,postal_code,website,phone,"
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
    if (r.get("compliance_status") or "not_started") in ("approved", "pending"):
        return "SUBMITTED", []
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
                      website: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1200, 1660
    img = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(img)

    def F(size, bold=False):
        return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc",
                                  size, index=1 if bold else 0)

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
        "BusinessName": name,
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
    _sb("POST", "/rest/v1/marketing_work_log", {
        "company_id": cid, "kind": "tollfree-verification-submitted",
        "summary": f"Toll-free SMS verification submitted for {tf} "
                   f"({res.get('sid')})",
    }, prefer="return=minimal")
    return True


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
    args = ap.parse_args()
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
