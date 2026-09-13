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

HANDS_OFF = {"paul-davis-charleston", "go-green-restoration-of-nc",
             "kenneth-w-talbot-jr"}
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
            continue
        setup = (_sb("GET", "/rest/v1/company_phone_setup"
                     f"?id=eq.{c['company_id']}"
                     "&select=compliance_status,twilio_subaccount_sid,"
                     "twilio_auth_token,agent_phone_1") or [{}])[0]
        if not (setup.get("compliance_status") == "approved"
                and setup.get("twilio_subaccount_sid")
                and setup.get("twilio_auth_token")
                and setup.get("agent_phone_1")):
            skipped += 1
            print(f"  [{slug}] no approved own toll-free, no SMS alert "
                  f"(call {c['id'][:8]})")
            continue
        target = messaging_target(company)
        to = (target.get("cell") or "").strip()
        if not to:
            skipped += 1
            print(f"  [{slug}] no owner cell on file")
            continue
        body = compose(kind, c["from_number"], _ago(c["started_at"], tz),
                       c["analysis"], c.get("source") or "")
        print(f"  [{slug}] {kind} -> {to} from {setup['agent_phone_1']}:\n"
              f"    {body}")
        if dry_run:
            sent += 1
            continue
        ok, ref = _twilio_send(setup, to, body)
        if not ok:
            print(f"    !! twilio send failed: {ref}")
            continue
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": key, "v": {"at": datetime.now(timezone.utc).isoformat(),
                             "kind": kind, "sid": ref}},
            prefer="resolution=merge-duplicates")
        try:
            from work_log import work_log
            work_log(c["company_id"], "calls", "missed-call-alert",
                     f"Texted you a heads up about a {'callback request' if kind == 'callback' else 'missed opportunity'} "
                     f"call from {_fmt_phone(c['from_number'])}",
                     {"call_id": c["id"], "kind": kind})
        except Exception as e:  # noqa: BLE001
            print(f"    (work log warn: {str(e)[:80]})")
        sent += 1
    print(f"call alerts: {sent} {'would send' if dry_run else 'sent'}, "
          f"{held} held for morning, {skipped} skipped (no own line/cell)")
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
