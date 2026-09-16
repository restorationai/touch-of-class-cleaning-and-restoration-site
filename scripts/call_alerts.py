#!/usr/bin/env python3
"""call_alerts.py — missed-opportunity / callback alerts to the client
(queue #6, 2026-09-14).

call_intel.py already labels every tracked call's outcome; nothing told
the client, so a missed job could die quietly. This closes that gap:

  WHAT     marketing_tracked_calls whose analysis says outcome=
           missed_opportunity, or callback_needed=true (and the call is
           not spam/wrong number/booked) -> one SMS alert to the owner.
  SENDER   the CLIENT'S OWN approved toll-free (company_phone_setup:
           compliance_status=approved + twilio_subaccount_sid +
           twilio_auth_token + agent_phone_1), sent through THEIR Twilio
           subaccount. HARD RULE (Santino 2026-09-12): never our
           concierge or company numbers, and no universal fallback —
           a client without an approved own line gets no SMS alert
           (the ops note still records it).
  WHEN     within the client's local 07:00-21:00; overnight calls hold
           and deliver next morning (the pass re-checks; nothing marks
           alerted until actually sent). Cron: rides call-intel.yml
           (every 30 min), so alerts land near-real-time.
  DEDUPE   ops_kv call-alerted:{call_id}, plus a 24h lookback cap.
  LEDGER   one marketing_work_log row per alert -> monthly report.

Message templates are DETERMINISTIC (alerts are receipts; receipts never
hallucinate). No em dashes anywhere (house law).

CLI:
    python3 scripts/call_alerts.py --dry-run [--hours 24] [--slug X]
    python3 scripts/call_alerts.py --send
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import requests  # noqa: E402

from client_ops_sync import _sb, slug_map  # noqa: E402

HANDS_OFF = {"paul-davis-charleston", "go-green-restoration-of-nc"}
ALERT_HOUR_START, ALERT_HOUR_END = 7, 21


def _fmt_phone(e164: str) -> str:
    d = re.sub(r"\D", "", e164 or "")
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return f"({d[:3]}) {d[3:6]}-{d[6:]}" if len(d) == 10 else (e164 or "?")


def _ago(started_at: str, tz: str) -> str:
    try:
        t = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except ValueError:
        return "recently"
    delta = datetime.now(timezone.utc) - t
    mins = int(delta.total_seconds() // 60)
    if mins < 90:
        return f"{max(mins, 1)} min ago"
    local = t.astimezone(ZoneInfo(tz))
    if delta < timedelta(hours=20):
        return f"at {local.strftime('%-I:%M%p').lower()}"
    return f"{local.strftime('%A %-I:%M%p').lower()}"


# Sign-off brand: env-overridable so a company rename (Ignite Systems?)
# is one Railway/workflow variable, not a code change.
import os as _os
BRAND = _os.environ.get("RANKAI_BRAND_NAME", "Restoration AI")


def compose(kind: str, caller: str, ago: str, analysis: dict,
            source: str = "") -> str:
    svc = (analysis.get("service") or "a job").strip()
    summary = str(analysis.get("summary") or "").split(". ")[0].strip()
    if len(summary) > 150:
        summary = summary[:150].rsplit(" ", 1)[0]
    if summary and not summary.endswith("."):
        summary += "."
    n = _fmt_phone(caller)
    # Source attribution (Santino 2026-09-14): naming the line that rang is
    # standing proof of where their leads come from (the DNI program).
    src = {"gbp": "your Google listing", "website": "your website"}.get(
        (source or "").lower(), "your tracked line")
    if kind == "callback":
        return (f"Callback alert from {src}: {n} called {ago} "
                f"about {svc} and is waiting on a call back. {summary} "
                f"Their number: {n}\n- {BRAND}")
    return (f"Missed job alert from {src}: {n} called {ago} "
            f"about {svc} and did not get booked. {summary} "
            f"They may still be shopping. Worth a quick call back: {n}"
            f"\n- {BRAND}")


def _sendgrid_email(to_addrs: list[str], subject: str,
                    body: str) -> tuple[bool, str]:
    """Plain-text alert email via SendGrid (same API the digest and lead
    reports use). Returns (ok, ref)."""
    import os
    key = os.environ.get("SENDGRID_API_KEY", "").strip()
    if not key or not to_addrs:
        return False, "no-sendgrid-key" if not key else "no-recipients"
    r = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        json={"personalizations": [{"to": [{"email": a} for a in to_addrs]}],
              "from": {"email": "contact@restorationai.io",
                       "name": "Restoration AI"},
              "subject": subject,
              "content": [{"type": "text/plain", "value": body}]},
        timeout=30)
    return r.status_code in (200, 202), str(r.status_code)


def alert_recipients(company: dict) -> tuple[list[str], list[str]]:
    """(sms_numbers, emails) for call alerts — D14 (Santino 2026-09-16):
    the SAME client-managed Lead Notifications lists the estimate form
    uses, both channels optional. SMS falls back to the owner cell
    (previous behavior) when the list is empty; email always includes the
    company's main address, mirroring the lead-email contract."""
    from client_concierge import messaging_target
    ints = company.get("integration_settings") or {}
    sms = [str(x).strip() for x in (ints.get("lead_notify_sms") or [])
           if str(x).strip()]
    if not sms:
        cell = (messaging_target(company).get("cell") or "").strip()
        if cell:
            sms = [cell]
    emails = [str(x).strip().lower() for x in
              (ints.get("lead_notify_emails") or []) if str(x).strip()]
    main = (company.get("email") or "").strip().lower()
    if main and main not in emails:
        emails.insert(0, main)
    return sms, emails


def _stamp_alert(call_id: str, analysis: dict, state: dict) -> None:
    """Write alert delivery state onto the call row (analysis.alert) —
    what the app's Call Alerts card renders. Whole-json merge because
    analysis is a plain jsonb column."""
    a = dict(analysis or {})
    a["alert"] = state
    _sb("PATCH", f"/rest/v1/marketing_tracked_calls?id=eq.{call_id}",
        {"analysis": a}, prefer="return=minimal")


def _twilio_send(setup: dict, to: str, body: str) -> tuple[bool, str]:
    sid = setup["twilio_subaccount_sid"]
    r = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        auth=(sid, setup["twilio_auth_token"]),
        data={"From": setup["agent_phone_1"], "To": to, "Body": body},
        timeout=30)
    return r.ok, (r.json().get("sid", "") if r.ok else r.text[:200])


def run(dry_run: bool, hours: int, only_slug: str | None) -> int:
    cid_to_slug = slug_map()  # {company_id: slug}
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)) \
        .isoformat().replace("+00:00", "Z")  # '+' breaks the query string
    calls = _sb("GET", "/rest/v1/marketing_tracked_calls"
                f"?started_at=gte.{since}"
                "&select=id,company_id,from_number,started_at,analysis,source"
                "&order=started_at.desc&limit=200") or []
    sent = held = skipped = 0
    from client_concierge import fetch_companies, messaging_target, \
        resolve_timezone, company_inactive
    wanted = []
    for c in calls:
        a = c.get("analysis")
        if not isinstance(a, dict):
            continue
        out = (a.get("outcome") or "").lower()
        if out == "missed_opportunity":
            kind = "missed"
        elif a.get("callback_needed") and out not in (
                "booked", "spam", "wrong_number", "voicemail", "too_short"):
            kind = "callback"
        else:
            continue
        if not c.get("from_number"):
            continue
        slug = cid_to_slug.get(c["company_id"])
        if only_slug and slug != only_slug:
            continue
        if slug in HANDS_OFF:
            continue
        wanted.append((c, kind, slug))
    if not wanted:
        print("no missed/callback calls in the window")
        return 0
    companies = fetch_companies(sorted({c["company_id"] for c, _, _ in wanted}))
    for c, kind, slug in wanted:
        key = f"call-alerted:{c['id']}"
        if (_sb("GET", f"/rest/v1/ops_kv?k=eq.{key}&select=k") or []):
            continue
        company = companies.get(c["company_id"])
        if not company or company_inactive(company):
            continue
        tz, _src = resolve_timezone(company, None)
        hour = datetime.now(timezone.utc).astimezone(ZoneInfo(tz)).hour
        if not (ALERT_HOUR_START <= hour < ALERT_HOUR_END):
            held += 1
            print(f"  [{slug}] hold (local {hour}h): {c['id'][:8]}")
            # D14: the hold is now VISIBLE — the app's Call Alerts card
            # renders analysis.alert. Stamp once; the pass re-checks and
            # delivers at local morning.
            if not dry_run and \
                    ((c.get("analysis") or {}).get("alert") or {}) \
                    .get("status") != "held_quiet_hours":
                _stamp_alert(c["id"], c.get("analysis"),
                             {"status": "held_quiet_hours", "kind": kind,
                              "local_hour": hour,
                              "delivers_at_local": f"{ALERT_HOUR_START}:00"})
            continue
        setup = (_sb("GET", "/rest/v1/company_phone_setup"
                     f"?id=eq.{c['company_id']}"
                     "&select=compliance_status,twilio_subaccount_sid,"
                     "twilio_auth_token,agent_phone_1") or [{}])[0]
        sms_ok_to_send = bool(setup.get("compliance_status") == "approved"
                              and setup.get("twilio_subaccount_sid")
                              and setup.get("twilio_auth_token")
                              and setup.get("agent_phone_1"))
        sms_to, email_to = alert_recipients(company)
        body = compose(kind, c["from_number"], _ago(c["started_at"], tz),
                       c["analysis"], c.get("source") or "")
        print(f"  [{slug}] {kind}: sms->{sms_to if sms_ok_to_send else '(no approved sender)'} "
              f"email->{email_to}")
        if dry_run:
            sent += 1
            continue

        # D14 (Santino 2026-09-16): two channels, both from the client's
        # Lead Notifications lists, each optional. Email is NOT gated on
        # the toll-free approval — that constraint only ever applied to
        # the SMS sender — so a missed job reaches the office even while
        # their number is in compliance review.
        delivered: list[str] = []
        sms_sids: list[str] = []
        if sms_ok_to_send:
            for to in sms_to:
                ok, ref = _twilio_send(setup, to, body)
                if ok:
                    delivered.append(f"sms:{to}")
                    sms_sids.append(ref)
                else:
                    print(f"    !! twilio send failed ({to}): {ref}")
        subj = (f"{'Callback request' if kind == 'callback' else 'Missed job alert'}: "
                f"{_fmt_phone(c['from_number'])} — {company.get('name', slug)}")
        eok, eref = _sendgrid_email(email_to, subj, body)
        if eok:
            delivered += [f"email:{a}" for a in email_to]
        elif email_to:
            print(f"    !! email send failed: {eref}")

        if not delivered:
            # Nothing reached the client on any channel — the old
            # ops-note backstop (surfaces in Ops Attention + digest).
            skipped += 1
            _sb("POST", "/rest/v1/marketing_ops_notes",
                {"company_id": c["company_id"], "status": "open",
                 "author": "call_alerts",
                 "body": (f"[CALL ALERT UNDELIVERED] {slug}: no working "
                          f"channel (SMS approved: {sms_ok_to_send}, "
                          f"emails: {len(email_to)}). The alert:\n{body}")},
                prefer="return=minimal")
            _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
                {"k": key,
                 "v": {"at": datetime.now(timezone.utc).isoformat(),
                       "kind": kind, "held": "no_channel"}},
                prefer="resolution=merge-duplicates")
            _stamp_alert(c["id"], c.get("analysis"),
                         {"status": "undeliverable", "kind": kind,
                          "at": datetime.now(timezone.utc).isoformat()})
            continue

        _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": key, "v": {"at": datetime.now(timezone.utc).isoformat(),
                             "kind": kind, "delivered": delivered}},
            prefer="resolution=merge-duplicates")
        _stamp_alert(c["id"], c.get("analysis"),
                     {"status": "sent", "kind": kind,
                      "at": datetime.now(timezone.utc).isoformat(),
                      "to": delivered})
        try:
            from work_log import work_log
            # Activity feed (Santino 2026-09-14: every alert send is a
            # logged ACTION) — same marketing_work_log the app's activity
            # view, monthly summary and report all read.
            n_sms = len([d for d in delivered if d.startswith("sms:")])
            n_em = len([d for d in delivered if d.startswith("email:")])
            how = " and ".join(x for x in (
                f"texted {n_sms} number(s)" if n_sms else "",
                f"emailed {n_em} address(es)" if n_em else "") if x)
            work_log(c["company_id"], "calls", "missed-call-alert",
                     f"Sent a heads up about a {'callback request' if kind == 'callback' else 'missed opportunity'} "
                     f"call from {_fmt_phone(c['from_number'])} ({how})",
                     {"call_id": c["id"], "kind": kind,
                      "delivered": delivered, "twilio_sids": sms_sids,
                      "body": body[:400]})
        except Exception as e:  # noqa: BLE001
            print(f"    (work log warn: {str(e)[:80]})")
        sent += 1
    print(f"call alerts: {sent} {'would send' if dry_run else 'sent'}, "
          f"{held} held for morning, {skipped} undeliverable")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--slug")
    a = ap.parse_args()
    return run(not a.send, a.hours, a.slug)


if __name__ == "__main__":
    sys.exit(main())
