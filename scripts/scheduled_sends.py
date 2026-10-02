#!/usr/bin/env python3
"""scheduled_sends.py — exact-text client messages sent at a set time, in the cloud.

Santino 2026-09-28: "it's too late to be sending anything out today, queue
them for tomorrow." Monica's scheduled notes let HER write the message and the
Mac launchd one-shots need the laptop awake; this is the missing piece: a
queue of EXACT messages (the words Santino approved) that the Railway ops
worker sends at `send_at`, through the same path as monica_oneoff.py
(Monica's sender, machine-sent ledger, [CONTEXT] note so she can handle the
reply). First building block of the promise tracker.

Queue = ops_kv rows `scheduled-send:{id}` =
  {company_id, contact_id, channel, body, context, send_at (ISO UTC),
   status: queued|sent|failed|cancelled, created_by, sent_at, message_id,
   error, allow_extra_recipient (bool: recipient not on Monica's allowlist,
   explicitly approved by Santino for this one message)}

CLI:
  scheduled_sends.py add --company CO-.. --contact-id X --send-at 2026-09-29T13:30:00Z \
      --body "..." --context "..." [--channel sms|email] [--allow-extra-recipient]
  scheduled_sends.py list            # queued + recent
  scheduled_sends.py cancel --id ID
  scheduled_sends.py run             # send everything due (ops worker, every 5 min)
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import client_concierge as cc  # noqa: E402

PREFIX = "scheduled-send:"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def cmd_add(a) -> int:
    if "—" in a.body or "–" in a.body:
        sys.exit("refusing: em/en dash in client copy")
    send_at = datetime.fromisoformat(a.send_at.replace("Z", "+00:00"))
    sid = uuid.uuid4().hex[:10]
    row = {"company_id": a.company, "contact_id": a.contact_id, "channel": a.channel,
           "body": a.body, "context": a.context, "subject": a.subject,
           "send_at": send_at.astimezone(timezone.utc).isoformat(),
           "status": "queued", "created_by": "claude-macbook",
           "created_at": _now().isoformat(),
           "allow_extra_recipient": bool(a.allow_extra_recipient),
           "arm_rename": bool(a.arm_rename),
           "cc": list(a.cc or [])}
    cc.kv_set(PREFIX + sid, row)
    print(f"queued {sid} for {row['send_at']} -> {a.company}/{a.contact_id}")
    return 0


def cmd_list(_a) -> int:
    rows = cc.kv_prefix(PREFIX) or {}
    for k, v in sorted(rows.items(), key=lambda kv: kv[1].get("send_at", "")):
        print(f"{k[len(PREFIX):]}  {v.get('status'):9} {v.get('send_at')}  "
              f"{v.get('company_id')}  {v.get('body', '')[:70]!r}")
    return 0


def cmd_cancel(a) -> int:
    k = PREFIX + a.id
    v = cc.kv_get(k)
    if not v:
        sys.exit("no such id")
    v["status"] = "cancelled"
    cc.kv_set(k, v)
    print("cancelled", a.id)
    return 0


def _send(v: dict) -> dict:
    comp = cc.fetch_companies([v["company_id"]]).get(v["company_id"])
    if not comp:
        raise RuntimeError("unknown company")
    raw = (cc._ghl("GET", f"/contacts/{v['contact_id']}") or {}).get("contact") or {}
    contact = {"id": v["contact_id"], **raw}
    if v.get("allow_extra_recipient"):
        # Santino approved this one message to a contact outside Monica's
        # standing allowlist (e.g. the owner when the office manager is the
        # starred contact). Scoped to this send only.
        num = contact.get("phone") or ""
        cur = os.environ.get("CONCIERGE_ALLOWLIST", "")
        os.environ["CONCIERGE_ALLOWLIST"] = f"{cur},{num}" if cur else num
        cc._ALLOW_CACHE.clear()
    _extra = {"cc": v["cc"]} if v.get("cc") else {}
    r = cc.send_message(contact, v.get("channel") or "sms", v["body"],
                        subject=v.get("subject"), company=comp,
                        human_hold_exempt=True, **_extra)
    state = cc.load_state()
    cc.record_sent_message(state, r)
    cc.save_state(state, dry_run=False)
    if v.get("arm_rename"):
        # Rename options sent outside the pitch worker must still arm the
        # rename flow, or Monica answers the pick without RENAME_TRUTH
        # (Michael/Katofsky 2026-09-29).
        cc.kv_set(f"rename-convo:{v['company_id']}", {
            "stage": "options", "last_outbound": v["body"],
            "at": _now().isoformat(), "notes": "armed by scheduled_sends"})
    who = contact.get("firstName") or contact["id"]
    cc._sb("POST", "/rest/v1/marketing_ops_notes",
           {"company_id": v["company_id"], "author": "scheduled-send",
            "status": "open",
            "body": (f"[CONTEXT] Scheduled message sent to {who}: \"{v['body']}\" | "
                     f"{v.get('context', '')}")[:1900]}, prefer="return=minimal")
    return r


def cmd_run(_a) -> int:
    rows = cc.kv_prefix(PREFIX) or {}
    due = [(k, v) for k, v in rows.items()
           if v.get("status") == "queued"
           and datetime.fromisoformat(v["send_at"]) <= _now()]
    if not due:
        print("scheduled-sends: nothing due")
        return 0
    for k, v in due:
        # claim first so a concurrent pass cannot double-send
        v["status"] = "sending"
        cc.kv_set(k, v)
        try:
            r = _send(v)
            v.update(status="sent", sent_at=_now().isoformat(),
                     message_id=(r or {}).get("messageId"))
            print(f"scheduled-sends: SENT {k} -> {v['company_id']}")
        except Exception as e:  # noqa: BLE001 — one failure never blocks the rest
            v.update(status="failed", error=str(e)[:300])
            print(f"scheduled-sends: FAILED {k}: {str(e)[:160]}")
            try:
                cc._sb("POST", "/rest/v1/marketing_ops_notes",
                       {"company_id": v["company_id"], "author": "scheduled-send",
                        "status": "open",
                        "body": f"[FLAG] Scheduled message FAILED to send: {str(e)[:200]} | {v['body'][:300]}"},
                       prefer="return=minimal")
            except Exception:  # noqa: BLE001
                pass
        cc.kv_set(k, v)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    ad = sub.add_parser("add")
    ad.add_argument("--company", required=True)
    ad.add_argument("--contact-id", required=True)
    ad.add_argument("--send-at", required=True, help="ISO time, UTC (…Z)")
    ad.add_argument("--body", required=True)
    ad.add_argument("--context", required=True)
    ad.add_argument("--subject")
    ad.add_argument("--channel", default="sms", choices=("sms", "email"))
    ad.add_argument("--allow-extra-recipient", action="store_true")
    ad.add_argument("--cc", action="append", default=[],
                    help="email CC address (repeatable; owner on vendor threads)")
    ad.add_argument("--arm-rename", action="store_true",
                    help="this message offers name options: arm Monica's rename "
                         "conversation (stage=options) when it sends")
    ad.set_defaults(func=cmd_add)
    sub.add_parser("list").set_defaults(func=cmd_list)
    ca = sub.add_parser("cancel")
    ca.add_argument("--id", required=True)
    ca.set_defaults(func=cmd_cancel)
    sub.add_parser("run").set_defaults(func=cmd_run)
    a = ap.parse_args()
    cc.load_env()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
