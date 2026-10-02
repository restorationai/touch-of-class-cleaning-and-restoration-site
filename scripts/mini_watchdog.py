#!/usr/bin/env python3
"""mini_watchdog.py — keep the Mac Mini working without a human noticing.

Santino 2026-10-02: the TDI BBB claim was ANSWERED ("Yes, claim it") on
09-30 but never ran, and the Mini sat idle all of 10-02 with two items it had
itself deferred to "10-02 daytime". Sessions only start when something pushes
clients/_ops/mini-trigger; nothing checked that answered work actually
happened. "I don't want us to only catch this when you mention it to me."

Runs in GitHub Actions every 30 min (independent of the MacBook):

  1. OUTSTANDING WORK
     - open inbox items (`- [ ] **...` in mini-inbox.md)
     - FOLLOW-THROUGH GAPS: an answered Need ([x]) whose ANSWER tells the
       Mini to act (claim / retry / resume / create / submit / run ...) but
       the ledger has no line for that client on or after the answer date.
       Each gap is re-queued ONCE as an inbox item quoting the answer
       verbatim (the Mini's own supervision rules still apply to it).
  2. WAKE: daytime PT (8am-7pm, the Mini's citation window), work is
     outstanding, no session in the last 90 min, and no unconsumed trigger
     younger than 25 min -> write a fresh trigger token (capped per day).
  3. DEAD-MINI ALARM: a trigger older than 30 min with no heartbeat after
     it means the Mini is off, asleep or wedged -> ops card + SMS to Santino
     (once per trigger token; SMS only 7am-9pm PT).
  4. STUCK ITEMS: an inbox item open > 48h -> one ops card per item, ever.

State: ops_kv `mini-watchdog`. Never edits the Mini's standing orders, never
contacts clients. Fail-open: every external call is best-effort.

CLI: python3 scripts/mini_watchdog.py [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

OPS = ROOT / "clients" / "_ops"
INBOX = OPS / "mini-inbox.md"
NEEDS = OPS / "mini-needs.md"
LEDGER = OPS / "mini-ledger.md"
HEARTBEAT = OPS / "mini-heartbeat.md"
TRIGGER = OPS / "mini-trigger"
KV = "mini-watchdog"
PT = ZoneInfo("America/Los_Angeles")

WAKE_HOURS = (8, 19)          # PT, matches the Mini's daytime citation window
SMS_HOURS = (7, 21)           # PT, when Santino may be texted
IDLE_BEFORE_WAKE = 90 * 60    # no session for this long -> wake if work exists
TRIGGER_GRACE = 25 * 60       # a fresh trigger is still being picked up
DEAD_AFTER = 30 * 60          # trigger this old with no heartbeat -> alarm
STUCK_AFTER = 48 * 3600
MAX_WAKES_PER_DAY = 6
FOLLOWUP_WINDOW_DAYS = 10

ACTION_RE = re.compile(
    r"\b(claim it|do one|do it|retry|resume|re-?run|run (?:it|the)|open |create|submit|"
    r"re-?test|finish|go ahead|proceed|yes,)", re.I)
NO_ACTION_RE = re.compile(
    r"\b(hold\b|nothing to do|no action|do not|don't|never create|park it|"
    r"stand down|skip it|wait for)", re.I)


# ------------------------------------------------------------------ helpers
def _sb():
    from client_ops_sync import _sb as sb  # lazy: keeps --dry-run offline-safe
    return sb


def kv_get() -> dict:
    try:
        rows = _sb()("GET", f"/rest/v1/ops_kv?k=eq.{KV}&select=v") or []
        return (rows[0].get("v") if rows else {}) or {}
    except Exception as e:  # noqa: BLE001
        print(f"  kv read failed (fresh state): {e}")
        return {}


def kv_set(v: dict) -> None:
    try:
        _sb()("POST", "/rest/v1/ops_kv?on_conflict=k", {"k": KV, "v": v},
              prefer="resolution=merge-duplicates")
    except Exception as e:  # noqa: BLE001
        print(f"  kv write failed: {e}")


def ops_card(body: str) -> None:
    try:
        _sb()("POST", "/rest/v1/marketing_ops_notes",
              {"company_id": None, "author": "mini-watchdog", "status": "open",
               "body": body[:1800]}, prefer="return=minimal")
    except Exception as e:  # noqa: BLE001
        print(f"  ops card failed: {e}")


def text_santino(body: str) -> None:
    try:
        from client_concierge import send_message, OPS_PING_CONTACT_ID, OPS_PING_CELL
        send_message({"id": OPS_PING_CONTACT_ID, "phone": OPS_PING_CELL}, "sms", body[:600])
        print("  -> SMS to Santino")
    except Exception as e:  # noqa: BLE001
        print(f"  SMS failed: {str(e)[:120]}")


def last_heartbeat() -> float:
    best = 0.0
    if HEARTBEAT.exists():
        for line in HEARTBEAT.read_text().splitlines():
            m = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z?\s*\|", line)
            if m:
                ts = datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc).timestamp()
                best = max(best, ts)
    return best


def trigger_state() -> tuple[str, float]:
    """(token, epoch it was issued). Tokens end in a unix epoch by convention
    (responder-<epoch>, groupb-fb-<epoch>, watchdog-<epoch>)."""
    if not TRIGGER.exists():
        return "", 0.0
    tok = (TRIGGER.read_text().splitlines() or [""])[0].strip()
    m = re.search(r"(\d{10})\s*$", tok)
    return tok, float(m.group(1)) if m else 0.0


def open_inbox_items() -> list[dict]:
    items = []
    for line in INBOX.read_text().splitlines() if INBOX.exists() else []:
        if not line.startswith("- [ ] "):
            continue
        title = re.sub(r"\*\*", "", line[6:]).strip()
        low = line.lower()
        supervised = ("supervised" in low and "unattended ok" not in low
                      and "no longer supervised" not in low)
        items.append({"id": hashlib.sha256(title[:160].encode()).hexdigest()[:12],
                      "title": title[:160], "supervised": supervised})
    return items


def _answer_date(head: str, year: int) -> date | None:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", head)
    if m:
        return date.fromisoformat(m.group(1))
    m = re.search(r"\b(\d{2})-(\d{2})\b", head)
    if m:
        try:
            return date(year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
    return None


def ledger_dates_by_client() -> dict[str, date]:
    """Latest ledger date per client slug."""
    out: dict[str, date] = {}
    for line in LEDGER.read_text().splitlines() if LEDGER.exists() else []:
        m = re.match(r"(\d{4}-\d{2}-\d{2})\s*\|\s*([\w.-]+)\s*\|", line)
        if m:
            d = date.fromisoformat(m.group(1))
            if d > out.get(m.group(2), date.min):
                out[m.group(2)] = d
    return out


def followup_gaps(today: date) -> list[dict]:
    """Answered Needs that told the Mini to act, with no ledger line for that
    client on/after the answer date."""
    if not NEEDS.exists():
        return []
    lines = NEEDS.read_text().splitlines()
    led = ledger_dates_by_client()
    gaps = []
    for i, line in enumerate(lines):
        m = re.match(r"- \[x\] (NEED-[\w-]+)\s*\|(.*)$", line)
        if not m:
            continue
        cm = re.search(r"client=([\w.-]+)", m.group(2))
        client = cm.group(1) if cm else ""
        if not client or client.startswith("_"):
            continue
        # the LAST answer for this need decides
        answer, j = None, i + 1
        while j < len(lines) and lines[j].startswith("  "):
            s = lines[j].strip()
            if s.startswith("- ANSWER") or s.startswith("- RESOLVED"):
                answer = s
            j += 1
        if not answer or answer.startswith("- RESOLVED"):
            continue
        head, _, text = answer.partition("):")
        ad = _answer_date(head, today.year)
        if not ad or (today - ad).days > FOLLOWUP_WINDOW_DAYS:
            continue
        if not ACTION_RE.search(text) or NO_ACTION_RE.search(text[:200]):
            continue
        if led.get(client, date.min) >= ad:
            continue
        gaps.append({"need": m.group(1), "client": client, "answered": ad.isoformat(),
                     "answer": text.strip()[:900]})
    return gaps


# --------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    dry = args.dry_run

    now = time.time()
    now_pt = datetime.now(PT)
    today = now_pt.date()
    st = {} if dry else kv_get()
    st.setdefault("requeued", {})
    st.setdefault("first_seen", {})
    st.setdefault("stuck_flagged", {})
    st.setdefault("dead_alarmed", {})
    wakes = st.get("wakes", {})
    wakes_today = int(wakes.get(today.isoformat(), 0))

    hb = last_heartbeat()
    tok, tok_at = trigger_state()
    print(f"mini-watchdog {now_pt:%Y-%m-%d %H:%M} PT | last heartbeat "
          f"{(now - hb) / 60:.0f} min ago | trigger {tok or '-'}"
          f"{f' ({(now - tok_at) / 60:.0f} min old)' if tok_at else ''}")

    # 1a. follow-through gaps -> re-queue once each
    gaps = followup_gaps(today)
    new_items, seen_answers = [], set()
    for g in gaps:
        if g["need"] in st["requeued"]:
            continue
        akey = (g["client"], g["answer"][:300])
        if akey in seen_answers:      # two Needs, one instruction -> one item
            st["requeued"][g["need"]] = "dup-of-same-answer"
            continue
        seen_answers.add(akey)
        new_items.append(
            f"- [ ] **FOLLOW-THROUGH (auto-requeued by mini_watchdog "
            f"{now_pt:%Y-%m-%d %H:%M} PT): {g['need']} — {g['client']}.** "
            f"This Need was answered {g['answered']} but the ledger shows no "
            f"{g['client']} activity since. Do what the answer says (your "
            f"standing orders and its supervision rules still apply), ledger "
            f"the outcome, and if it cannot be done post a Need saying why. "
            f"Answer, verbatim: {g['answer']}")
        st["requeued"][g["need"]] = now_pt.isoformat(timespec="minutes")
        print(f"  requeue: {g['need']} ({g['client']}, answered {g['answered']})")
    if new_items and not dry:
        text = INBOX.read_text()
        m = re.search(r"^- \[[ x~!]\] ", text, re.M)
        cut = m.start() if m else len(text)
        INBOX.write_text(text[:cut] + "\n".join(new_items) + "\n" + text[cut:])

    # 1b. open inbox work
    items = open_inbox_items()
    actionable = [i for i in items if not i["supervised"]]
    for it in items:
        st["first_seen"].setdefault(it["id"], now)
    open_ids = {i["id"] for i in items}
    st["first_seen"] = {k: v for k, v in st["first_seen"].items() if k in open_ids}
    print(f"  inbox: {len(items)} open ({len(actionable)} unattended-runnable)"
          f"{f', +{len(new_items)} requeued' if new_items else ''}")

    # 3. dead-Mini alarm: a trigger nobody picked up
    if tok_at and hb < tok_at and now - tok_at > DEAD_AFTER and tok not in st["dead_alarmed"]:
        mins = int((now - tok_at) / 60)
        msg = (f"MAC MINI NOT RESPONDING: trigger '{tok}' was pushed {mins} min ago "
               f"and no session started (last heartbeat "
               f"{datetime.fromtimestamp(hb, PT):%m-%d %H:%M} PT). Check the Mini is "
               f"on, awake, online and logged in; launchd check_trigger runs every "
               f"5 min. {len(items)} inbox item(s) waiting.")
        print("  ALARM:", msg)
        if not dry:
            ops_card(msg)
            if SMS_HOURS[0] <= now_pt.hour < SMS_HOURS[1]:
                text_santino(msg)
            st["dead_alarmed"][tok] = now_pt.isoformat(timespec="minutes")

    # 2. wake the Mini when there is work and it is idle
    work = bool(actionable or new_items)
    daytime = WAKE_HOURS[0] <= now_pt.hour < WAKE_HOURS[1]
    pending = tok_at and hb < tok_at and now - tok_at < TRIGGER_GRACE
    idle = now - hb > IDLE_BEFORE_WAKE
    if work and daytime and idle and not pending and wakes_today < MAX_WAKES_PER_DAY:
        token = f"watchdog-{int(now)}"
        print(f"  WAKE: {token} (wake {wakes_today + 1}/{MAX_WAKES_PER_DAY} today)")
        if not dry:
            TRIGGER.write_text(token + "\n")
            wakes[today.isoformat()] = wakes_today + 1
    else:
        why = ("no runnable work" if not work else "outside daytime window" if not daytime
               else "a trigger is still being picked up" if pending
               else "Mini active recently" if not idle else "daily wake cap reached")
        print(f"  no wake: {why}")
    st["wakes"] = {k: v for k, v in wakes.items() if k >= (today - timedelta(days=7)).isoformat()}

    # 4. stuck items: one card per item, ever
    for it in items:
        age = now - st["first_seen"].get(it["id"], now)
        if age > STUCK_AFTER and it["id"] not in st["stuck_flagged"]:
            msg = (f"MINI INBOX ITEM STUCK {age / 3600:.0f}h"
                   f"{' (supervised: needs Santino present)' if it['supervised'] else ''}: "
                   f"{it['title']} | Either the Mini can't finish it (look for a Need/report) "
                   f"or it should be closed/edited in clients/_ops/mini-inbox.md.")
            print("  STUCK:", msg[:140])
            if not dry:
                ops_card(msg)
                st["stuck_flagged"][it["id"]] = now_pt.isoformat(timespec="minutes")

    st["last_run"] = now_pt.isoformat(timespec="minutes")
    if not dry:
        kv_set(st)
    return 0


if __name__ == "__main__":
    sys.exit(main())
