#!/usr/bin/env python3
"""reply_binding_audit.py — post-hoc conflation detector (Jim Salsbury
2026-09-24: Monica pitched LSA, Jim asked "How much is it?", the answer
came back about the DBA filing fee from a three-day-old thread).

For every concierge send in the lookback window that answered a client
message (reply_to stamped in the outbox), reconstruct the triple:

    OUR QUESTION  ->  their short reply  ->  OUR ANSWER

and have Haiku judge whether the answer addresses the reply IN THE TOPIC
OF the question it responded to. Mismatch = the composer conflated
threads; print an alarm line the fix-watcher loop surfaces.

Read-only. Run: python3 scripts/reply_binding_audit.py [--hours 36]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from client_concierge import (  # noqa: E402
    anthropic_json, fetch_history, kv_get, load_env, resolve_contact, _sb,
)

JUDGE = """You audit an SMS assistant for thread conflation. You get three
messages from one conversation:
  OUR_EARLIER: the assistant's message (often a question or pitch)
  CLIENT_REPLY: the client's reply to it (often short: "how much is it?")
  OUR_ANSWER: what the assistant answered
Decide whether OUR_ANSWER addresses CLIENT_REPLY *in the topic of
OUR_EARLIER*. If the answer clearly talks about a DIFFERENT topic than the
message the client was replying to, that is conflation.
Return STRICT JSON: {"conflated": true|false, "why": "<one line>"}"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=36)
    a = ap.parse_args()
    load_env()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=a.hours)
    outbox = kv_get("concierge-outbox") or {}
    checked = flagged = 0
    for cid, sends in outbox.items():
        recent = []
        for s in (sends or []):
            try:
                at = datetime.fromisoformat(str(s.get("at")))
            except (ValueError, TypeError):
                continue
            if at >= cutoff and s.get("reply_to"):
                recent.append(s)
        if not recent:
            continue
        comp = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}&select=*")
                or [None])[0]
        if not comp:
            continue
        try:
            contact = resolve_contact(comp)
            hist = fetch_history(contact["id"], 30)
        except Exception:  # noqa: BLE001
            continue
        for s in recent:
            body = (s.get("body") or "").strip()
            # locate OUR_ANSWER in history, then the client reply just
            # before it, then our message just before that
            ai = next((i for i, m in enumerate(hist)
                       if m.get("direction") == "out"
                       and (m.get("body") or "").strip()[:80] == body[:80]),
                      None)
            if ai is None:
                continue
            ri = next((i for i in range(ai + 1, len(hist))
                       if hist[i].get("direction") == "in"
                       and (hist[i].get("body") or "").strip()), None)
            if ri is None:
                continue
            qi = next((i for i in range(ri + 1, len(hist))
                       if hist[i].get("direction") == "out"
                       and (hist[i].get("body") or "").strip()), None)
            if qi is None:
                continue
            reply = (hist[ri].get("body") or "").strip()
            if len(reply) > 120:      # long replies carry their own topic
                continue
            checked += 1
            try:
                v = anthropic_json(JUDGE, json.dumps({
                    "OUR_EARLIER": (hist[qi].get("body") or "")[:400],
                    "CLIENT_REPLY": reply[:200],
                    "OUR_ANSWER": body[:400]}), max_tokens=200)
            except Exception:  # noqa: BLE001
                continue
            if v.get("conflated"):
                flagged += 1
                print(f"!! CONFLATION {comp.get('name')}: client replied "
                      f"{reply[:60]!r} to {(hist[qi].get('body') or '')[:60]!r} "
                      f"but we answered {body[:60]!r} — {v.get('why', '')[:90]}")
    print(f"reply-binding audit: {checked} triple(s) checked, "
          f"{flagged} conflation(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
