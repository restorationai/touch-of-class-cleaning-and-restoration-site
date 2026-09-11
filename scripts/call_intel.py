#!/usr/bin/env python3
"""Transcribe + analyze tracked calls (Santino 2026-09-10, promised on the
Icatch call: CallRail-style call intelligence, receptionist-style panel).

Every marketing_tracked_calls row with a recording and no transcript gets:
  1. the recording downloaded from Twilio (master creds),
  2. Whisper transcription (OpenAI, ~$0.006/min),
  3. a Claude analysis (outcome, service, urgency, summary, lead or not),
stored on the row (transcript, analysis, transcribed_at). The app's Calls
tab renders both in the call drawer, and the CSV export includes them.

Runs from the call-intel workflow: recording webhook fires a
workflow_dispatch for ~1-minute latency, cron backstops every 30 min.
Idempotent, cost-capped per run. Calls under MIN_SECONDS (rings, hangups)
are stamped with an empty analysis so they are never re-fetched.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

import requests

SB = "https://nyscciinkhlutvqkgyvq.supabase.co"
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}",
     "Content-Type": "application/json"}
MIN_SECONDS = 8
MAX_PER_RUN = 40

ANALYSIS_PROMPT = """You analyze a phone call to a home-services business
(plumbing/restoration/HVAC). From the transcript, reply ONLY with JSON:
{"summary": "2-3 sentence plain-language summary",
 "outcome": one of "booked" | "quote_requested" | "info_only" |
            "missed_opportunity" | "voicemail" | "spam" | "wrong_number" | "other",
 "service": the service discussed or null,
 "urgency": one of "emergency" | "soon" | "routine" | null,
 "caller_name": name if stated else null,
 "is_lead": true/false (a real potential customer),
 "callback_needed": true/false,
 "sentiment": one of "positive" | "neutral" | "frustrated"}"""


def sb(method: str, path: str, body=None, prefer=None):
    h = dict(H)
    if prefer:
        h["Prefer"] = prefer
    req = urllib.request.Request(f"{SB}/rest/v1/{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers=h)
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode()
        return json.loads(raw) if raw else None


def transcribe(audio: bytes) -> str:
    r = requests.post(
        "https://api.openai.com/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        files={"file": ("call.mp3", io.BytesIO(audio), "audio/mpeg")},
        data={"model": "whisper-1"}, timeout=180)
    r.raise_for_status()
    return (r.json().get("text") or "").strip()


def analyze(transcript: str, duration: int, source: str) -> dict:
    r = requests.post(
        "https://api.anthropic.com/v1/messages", timeout=120,
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                 "anthropic-version": "2023-06-01",
                 "Content-Type": "application/json"},
        json={"model": "claude-haiku-4-5-20251001", "max_tokens": 700,
              "system": ANALYSIS_PROMPT,
              "messages": [{"role": "user", "content":
                            f"Call source: {source}. Duration: {duration}s.\n"
                            f"Transcript:\n{transcript[:12000]}"}]})
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json().get("content", [])
                   if b.get("type") == "text")
    import re
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


def main() -> int:
    sid = os.environ["TWILIO_MASTER_ACCOUNT_SID"]
    tok = os.environ["TWILIO_MASTER_AUTH_TOKEN"]
    auth = base64.b64encode(f"{sid}:{tok}".encode()).decode()
    rows = sb("GET", "marketing_tracked_calls?recording_url=not.is.null"
              "&transcript=is.null&order=started_at.desc"
              f"&limit={MAX_PER_RUN}"
              "&select=id,call_sid,recording_url,duration_seconds,source") or []
    print(f"==> {len(rows)} call(s) pending intel")
    done = short = failed = 0
    for row in rows:
        rid = row["id"]
        try:
            if (row.get("duration_seconds") or 0) < MIN_SECONDS:
                sb("PATCH", f"marketing_tracked_calls?id=eq.{rid}",
                   {"transcript": "", "analysis": {"outcome": "too_short"},
                    "transcribed_at": datetime.now(timezone.utc).isoformat()},
                   prefer="return=minimal")
                short += 1
                continue
            req = urllib.request.Request(row["recording_url"],
                                         headers={"Authorization": f"Basic {auth}"})
            with urllib.request.urlopen(req, timeout=120) as r:
                audio = r.read()
            if len(audio) < 2000:
                raise RuntimeError("recording payload too small")
            text = transcribe(audio)
            analysis = analyze(text, row.get("duration_seconds") or 0,
                               row.get("source") or "website") if text else {}
            sb("PATCH", f"marketing_tracked_calls?id=eq.{rid}",
               {"transcript": text, "analysis": analysis,
                "transcribed_at": datetime.now(timezone.utc).isoformat()},
               prefer="return=minimal")
            done += 1
            print(f"  {row['call_sid'][-8:]}: {len(text)} chars, "
                  f"outcome={analysis.get('outcome')}")
        except Exception as e:  # noqa: BLE001 — one bad call never stops the run
            failed += 1
            print(f"  {row.get('call_sid', rid)[-8:]}: FAILED {str(e)[:100]}")
    print(f"==> analyzed {done}, skipped-short {short}, failed {failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
