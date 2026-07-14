#!/usr/bin/env python3
"""
Restoration AI — Post-Call Autopilot.

Finds new completed calls > MIN_DUR seconds, transcribes them (OpenAI gpt-4o-transcribe,
auto-chunking calls longer than OpenAI's ~23-min cap), has Claude read the conversation,
and updates GHL hands-free:
  • writes a call-summary note (only for REAL conversations — voicemail/no-speech is skipped)
  • if the lead committed to a follow-up AND has no upcoming appointment, records the
    follow-up date (so your GHL date automation moves them to Ready For Follow Up)

Appointment-aware: if a meeting is already booked, it's note-only (no redundant date).
Idempotent via call_autopilot_state.json. Safe to re-run.

Flags:  --dry-run   --hours N (lookback, default 72)   --limit N   --enable-date-set
"""
import os, sys, json, time, glob, shutil, tempfile, subprocess, argparse
from datetime import datetime, timezone, timedelta, date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auto_router as R
from _http import HTTP

# launchd runs with a minimal PATH that excludes Homebrew — resolve absolute paths.
FFMPEG  = shutil.which("ffmpeg")  or "/opt/homebrew/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"

BASE_DIR   = os.path.expanduser("~/restoration-ai")
LOG_FILE   = os.path.join(BASE_DIR, "call_autopilot.log")
STATE_FILE = os.path.join(BASE_DIR, "call_autopilot_state.json")

GHL_BASE = R.GHL_BASE; GHL_H = R.GHL_HEADERS; LOC = R.GHL_LOCATION_ID
MIN_DUR       = 30
CHUNK_SEC     = 1100                 # under OpenAI's 1400s/file cap, with margin
OPENAI_MODEL  = "gpt-4o-transcribe"
# Inferred follow-up-date custom field (value looked like "06/10/2026 09:00 AM").
# Date-setting stays OFF until confirmed and --enable-date-set is passed.
FOLLOWUP_DATE_FIELD = "n87p94Zb8oGN44feoL5S"

def log(m):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S"); line = f"[{ts}] {m}"; print(line)
    with open(LOG_FILE, "a") as f: f.write(line + "\n")

def openai_key():
    for line in open(os.path.expanduser("~/restoration-ai/.env")):
        if line.startswith("OPENAI_API_KEY="): return line.split("=", 1)[1].strip()
    return ""

# ---------- discovery ----------
def find_new_calls(hours, processed):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    convos, start = [], None
    for _ in range(60):
        p = {"locationId": LOC, "limit": 100, "sortBy": "last_message_date", "sort": "desc"}
        if start: p["startAfterDate"] = start
        r = HTTP.get(f"{GHL_BASE}/conversations/search", headers=GHL_H, params=p)
        if r.status_code != 200: break
        batch = r.json().get("conversations", [])
        if not batch: break
        convos += batch
        lm = batch[-1].get("lastMessageDate") or batch[-1].get("dateUpdated")
        # stop once the oldest in this page is older than the lookback
        try:
            if datetime.fromtimestamp(int(str(lm)[:13]) / 1000, tz=timezone.utc) < cutoff: break
        except Exception: pass
        start = lm
        if len(batch) < 100: break
    calls = []
    for cv in convos:
        mr = HTTP.get(f"{GHL_BASE}/conversations/{cv['id']}/messages", headers=GHL_H,
                      params={"limit": 100})
        if mr.status_code != 200: continue
        for m in mr.json().get("messages", {}).get("messages", []):
            if "CALL" not in str(m.get("messageType", "")).upper(): continue
            if m.get("id") in processed: continue
            try: dt = datetime.fromisoformat((m.get("dateAdded") or "").replace("Z", "+00:00"))
            except Exception: continue
            if dt < cutoff: continue
            dur = (m.get("meta", {}).get("call", {}) or {}).get("duration", 0) or 0
            if dur < MIN_DUR: continue
            calls.append({"cid": cv.get("contactId"),
                          "name": cv.get("fullName") or cv.get("contactName") or cv.get("contactId"),
                          "msg_id": m.get("id"), "dur": dur, "date": (m.get("dateAdded") or "")[:10]})
    calls.sort(key=lambda x: x["date"])
    return calls

# ---------- transcription ----------
def transcribe(msg_id):
    tmp = tempfile.mkdtemp()
    wav = os.path.join(tmp, "call.wav"); mp3 = os.path.join(tmp, "call.mp3")
    rec = HTTP.get(f"{GHL_BASE}/conversations/messages/{msg_id}/locations/{LOC}/recording",
                   headers=GHL_H)
    open(wav, "wb").write(rec.content)
    if len(rec.content) < 10000:
        return None  # no usable recording
    subprocess.run([FFMPEG, "-y", "-i", wav, "-ac", "1", "-ar", "16000", "-b:a", "64k", mp3],
                   capture_output=True)
    # duration
    try:
        dur = float(subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
              "-of", "default=nw=1:nk=1", mp3], capture_output=True, text=True).stdout.strip())
    except Exception:
        dur = 0
    key = openai_key()
    def one(path):
        r = HTTP.post("https://api.openai.com/v1/audio/transcriptions",
                      headers={"Authorization": f"Bearer {key}"},
                      files={"file": ("c.mp3", open(path, "rb"), "audio/mpeg")},
                      data={"model": OPENAI_MODEL, "response_format": "text"}, timeout=300)
        return r.text if r.status_code == 200 else ""
    if dur <= CHUNK_SEC:
        return one(mp3).strip()
    # chunk long calls
    subprocess.run([FFMPEG, "-y", "-i", mp3, "-f", "segment", "-segment_time", str(CHUNK_SEC),
                    "-c", "copy", os.path.join(tmp, "chunk_%03d.mp3")], capture_output=True)
    parts = sorted(glob.glob(os.path.join(tmp, "chunk_*.mp3")))
    return " ".join(one(p).strip() for p in parts).strip()

# ---------- appointment guard ----------
def has_upcoming_appt(cid, today):
    r = HTTP.get(f"{GHL_BASE}/contacts/{cid}/appointments", headers=GHL_H)
    if r.status_code != 200: return False
    for a in r.json().get("events", r.json().get("appointments", [])):
        ad = R.d10(a.get("startTime")); st = str(a.get("appointmentStatus") or a.get("status") or "").lower()
        if ad and ad >= today and "cancel" not in st:
            return True
    return False

# ---------- analysis ----------
ANALYZE_SYS = (
 "You analyze a transcribed sales/CRM phone call for a water-damage-restoration SaaS (Rank AI). "
 "First decide if it's a REAL two-way business conversation (not voicemail, hold music, "
 "gibberish, or a wrong number). If not real, set is_real_conversation=false and stop. "
 "If real, write a concise CRM note and extract any concrete follow-up commitment. "
 "If the lead/agent agreed to follow up or meet on a specific day, resolve it to an absolute "
 "date using the provided TODAY. Reply ONLY JSON: "
 '{"is_real_conversation": true|false, "kind": "lead|client|internal|other", '
 '"followup_date": "YYYY-MM-DD" or null, "note": "one short paragraph CRM note summarizing '
 'what happened + the clear next step", "recommended": "one short line, e.g. move to Ready For '
 'Follow Up / already booked / onboarding / no action"}')

def analyze(transcript, name, company, today):
    who = f"{name}" + (f" ({company})" if company else "")
    user = (f"TODAY is {today.isoformat()} ({today.strftime('%A')}).\nContact: {who}\n\n"
            f"Transcript:\n{transcript[:12000]}")
    out = R.anthropic_json(ANALYZE_SYS, user, max_tokens=600)
    return out or {"is_real_conversation": False}

# ---------- GHL writes ----------
def set_followup_date(cid, iso_date):
    # GHL date field expects MM-DD-YYYY HH:MM AM (e.g. 07-03-2026 09:00 AM)
    val = datetime.fromisoformat(iso_date).strftime("%m-%d-%Y 09:00 AM")
    r = HTTP.put(f"{GHL_BASE}/contacts/{cid}", headers=GHL_H,
                 json={"customFields": [{"id": FOLLOWUP_DATE_FIELD, "value": val}]})
    return r.status_code in (200, 201), val

def run(dry_run=False, hours=72, limit=None, enable_date_set=False):
    today = date.today()
    log(f"=== Call Autopilot {today} ({'DRY RUN' if dry_run else 'live'}, lookback {hours}h) ===")
    state = R._jload(STATE_FILE, {}); processed = set(state.get("processed", []))
    calls = find_new_calls(hours, processed)
    log(f"Found {len(calls)} new call(s) > {MIN_DUR}s")
    counts = {"noted": 0, "dated": 0, "skipped_novoice": 0, "no_rec": 0, "note_only_appt": 0}
    for c in calls[: (limit or len(calls))]:
        cid, name = c["cid"], c["name"]
        transcript = transcribe(c["msg_id"])
        if not transcript:
            log(f"  {name} ({c['dur']}s): no usable recording — skip"); counts["no_rec"] += 1
            processed.add(c["msg_id"]); continue
        # company from contact
        company = ""
        try:
            company = (HTTP.get(f"{GHL_BASE}/contacts/{cid}", headers=GHL_H).json()
                       .get("contact", {}).get("companyName") or "")
        except Exception: pass
        a = analyze(transcript, name, company, today)
        if not a.get("is_real_conversation"):
            log(f"  {name} ({c['dur']}s): not a real conversation — skip (no note)")
            counts["skipped_novoice"] += 1; processed.add(c["msg_id"]); continue
        note = a.get("note", "").strip()
        fdate = a.get("followup_date")
        appt = has_upcoming_appt(cid, today)
        line = f"  {name} ({c['dur']}s): {a.get('recommended','')}"
        if fdate: line += f" | followup {fdate}" + (" [appt exists -> note only]" if appt else "")
        log(line)
        if dry_run:
            log(f"      [dry] note: {note[:120]}")
            continue
        if note:
            R.post_note(cid, f"📞 {note}"); counts["noted"] += 1
        if fdate and appt:
            counts["note_only_appt"] += 1
        elif fdate and not appt:
            if enable_date_set:
                ok, val = set_followup_date(cid, fdate)
                log(f"      set follow-up date -> {val} ({'ok' if ok else 'FAIL'})")
                counts["dated"] += int(ok)
            else:
                log(f"      would set follow-up date {fdate} (date-set disabled)")
        processed.add(c["msg_id"])
    if not dry_run:
        state["processed"] = sorted(processed); json.dump(state, open(STATE_FILE, "w"))
    log(f"Done. {counts}")
    return counts

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--hours", type=int, default=72)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--enable-date-set", action="store_true")
    a = ap.parse_args()
    run(dry_run=a.dry_run, hours=a.hours, limit=a.limit, enable_date_set=a.enable_date_set)
