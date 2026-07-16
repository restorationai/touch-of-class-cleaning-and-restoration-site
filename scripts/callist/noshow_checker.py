#!/usr/bin/env python3
"""
Restoration AI — Daily No-Show Checker.

Scans open opps in the meeting-booked stages ("Demo Meeting Booked",
"Follow-Up Meeting Booked") whose appointment has PASSED, and decides show vs
no-show using this ladder:
   1. appointment already marked showed/no-show  -> trust it
   2. a Fathom recording matching this person + date exists -> SHOWED
   3. a real note dated on/after the appointment  -> SHOWED (safety override)
   4. none of the above  -> NO-SHOW

Actions:
   NO-SHOW -> move opp to "No-Show (Long Nurture)" + mark appointment no-show + note
   SHOWED  -> mark appointment 'showed' (for show-rate analytics); leave the opp

Runs daily. Safe: only auto-buries when Fathom has no recording AND there's no note.
Flags: --dry-run
"""
import os, sys, re, json, argparse
from datetime import datetime, timezone, timedelta, date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auto_router as R
from _http import HTTP

BASE_DIR = os.environ.get("RAI_BASE") or os.path.expanduser("~/restoration-ai")
LOG_FILE = os.path.join(BASE_DIR, "noshow_checker.log")
GHL_BASE = R.GHL_BASE; GHL_H = R.GHL_HEADERS; LOC = R.GHL_LOCATION_ID

MEETING_STAGES = ["Demo Meeting Booked", "Follow-Up Meeting Booked"]
NOSHOW_STAGE   = "No-Show (Long Nurture)"
FATHOM_LOOKBACK_DAYS = 21

def log(m):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S"); line = f"[{ts}] {m}"; print(line)
    with open(LOG_FILE, "a") as f: f.write(line + "\n")

def strip(t): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t or "")).strip()

# ---------------- Fathom ----------------
def fathom_key():
    if os.environ.get("FATHOM_API_KEY"):        # Railway service variable
        return os.environ["FATHOM_API_KEY"]
    try:
        for line in open(os.path.expanduser("~/restoration-ai/.env")):
            if line.startswith("FATHOM_API_KEY="): return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""

def fathom_meetings(since):
    key = fathom_key()
    if not key: return []
    out, cursor = [], None
    for _ in range(20):
        params = {"created_after": since.strftime("%Y-%m-%dT%H:%M:%SZ"), "include_transcript": "true"}
        if cursor: params["cursor"] = cursor
        r = HTTP.get("https://api.fathom.ai/external/v1/meetings",
                     headers={"X-Api-Key": key}, params=params, timeout=60)
        if r.status_code != 200:
            log(f"  Fathom fetch HTTP {r.status_code}: {r.text[:150]}"); break
        d = r.json()
        items = d.get("items") or d.get("data") or d.get("meetings") or []
        out += items
        cursor = d.get("next_cursor") or d.get("cursor") or (d.get("pagination") or {}).get("next_cursor")
        if not cursor or not items: break
    return out

def fathom_match(name, email, cid, appt_date, meetings):
    """Return the Fathom meeting matching this person around the appointment, else None."""
    toks = [t for t in (name or "").lower().split() if len(t) > 1]
    for m in meetings:
        title = (m.get("title") or m.get("meeting_title") or "").lower()
        md = R.d10(m.get("recording_start_time") or m.get("scheduled_start_time") or m.get("created_at"))
        if md and appt_date and abs((md - appt_date).days) > 1:
            continue
        if toks and all(t in title for t in toks):
            return m
        blob = json.dumps(m.get("crm_matches") or []) + json.dumps(m.get("calendar_invitees") or [])
        if cid and cid in blob:
            return m
        if email and email.lower() in blob.lower():
            return m
    return None

CLOSING_STAGE_NAMES = ["Closing", "Hot Leads (Interested)"]
WAITING_STAGE_NAME  = "Waiting For Follow Up Date"
ROUTE_SYS = (
 "You read a sales DEMO (transcript + the rep's notes) for a water-damage-restoration SaaS. "
 "The prospect ATTENDED but hasn't signed. Pick the next step — and if they want follow-up at a "
 "specific/later time, give the date:\n"
 "- 'schedule': interested but wants follow-up on a FUTURE date ('call me in two weeks', 'after I "
 "get paid', 'next month'). ALSO return followup_date.\n"
 "- 'closing': interested AND ready to proceed NOW / call right away, no waiting.\n"
 "- 'lost': clear no / bad fit.  - 'cooloff': went cold / revisit much later, no clear date.\n"
 "- 'flag': unclear or the meeting went sideways — a human should decide.\n"
 "Resolve relative timing to an absolute date using the provided TODAY. Prefer 'schedule' whenever "
 "they named a future timeframe. Reply ONLY JSON: "
 '{"route":"schedule|closing|lost|cooloff|flag","followup_date":"YYYY-MM-DD or null",'
 '"reason":"short","note":"one-line CRM note: outcome + next step"}')

def set_followup_date(cid, iso_date):
    val = datetime.fromisoformat(iso_date).strftime("%m-%d-%Y 09:00 AM")
    r = HTTP.put(f"{GHL_BASE}/contacts/{cid}", headers=GHL_H,
                 json={"customFields": [{"id": "n87p94Zb8oGN44feoL5S", "value": val}]})
    return r.status_code in (200, 201)

def transcript_text(meeting):
    tr = (meeting or {}).get("transcript")
    if isinstance(tr, list):
        return "\n".join(f"{(s.get('speaker') or {}).get('display_name', '?')}: {s.get('text', '')}"
                         for s in tr)
    return str(tr or "")

def route_demo(meeting, name, notes, today):
    txt = transcript_text(meeting)
    # the CLOSE of a demo is the most telling for interest/objections/next steps — weight to the end
    excerpt = (txt[:2500] + "\n...\n" + txt[-10000:]) if len(txt) > 12500 else txt
    content = (f"TODAY is {today.isoformat()}.\nRep's notes: {(notes or '(none)')[:1500]}\n\n"
               f"Meeting summary: {((meeting or {}).get('default_summary') or '(none)')}\n"
               f"Transcript:\n{excerpt if txt else '(no transcript available)'}")
    out = R.anthropic_json(ROUTE_SYS, f"Lead: {name}\n\n{content}", max_tokens=400)
    if not out or out.get("route") not in {"schedule", "closing", "lost", "cooloff", "flag"}:
        return {"route": "closing", "followup_date": None, "reason": "defaulted",
                "note": "Attended demo → move to Closing."}
    return out

# ---------------- GHL helpers ----------------
def get_appts(cid):
    r = HTTP.get(f"{GHL_BASE}/contacts/{cid}/appointments", headers=GHL_H)
    if r.status_code != 200: return []
    return r.json().get("events", r.json().get("appointments", []))

def get_notes_dated(cid):
    r = HTTP.get(f"{GHL_BASE}/contacts/{cid}/notes", headers=GHL_H)
    out = []
    if r.status_code == 200:
        for n in r.json().get("notes", []):
            b = strip(n.get("body"))
            if b and not b.startswith("--------- AI Call with:"):
                out.append((R.d10(n.get("dateAdded")), b))
    return out

def note_on_or_after(cid, appt_date):
    # a real, human-ish note dated on/after the appointment => a conversation happened
    for nd, b in get_notes_dated(cid):
        if nd and appt_date and nd >= appt_date and "via daily call-list directive" not in b \
           and "Auto-parked" not in b and "Auto-moved to No-Show" not in b:
            return b
    return None

def mark_appt(aid, status):
    r = HTTP.put(f"{GHL_BASE}/calendars/events/appointments/{aid}",
                 headers=GHL_H, json={"appointmentStatus": status})
    return r.status_code in (200, 201)

def move_opp(opp_id, pid, sid):
    r = HTTP.put(f"{GHL_BASE}/opportunities/{opp_id}", headers=GHL_H,
                 json={"pipelineId": pid, "pipelineStageId": sid, "status": "open"})
    return r.status_code == 200

def run(dry_run=False):
    today = date.today()
    log(f"=== No-Show Checker {today} ({'DRY RUN' if dry_run else 'live'}) ===")
    pipes = R.get_pipelines()
    reignite_pid = R.PIPELINES["Re-Igniting"]
    cooloff_id = pipes.get(reignite_pid, {}).get("name_to_id", {}).get("One Month Reset Period")
    # per pipeline: meeting stages + no-show + "Closing" + "Waiting For Follow Up Date"
    targets = []  # (pid, ms_name, ms_id, noshow_id, closing_id, waiting_id)
    for pid, info in pipes.items():
        n2i = info.get("name_to_id", {})
        noshow = n2i.get(NOSHOW_STAGE)
        closing = next((n2i[n] for n in CLOSING_STAGE_NAMES if n in n2i), None)
        waiting = n2i.get(WAITING_STAGE_NAME)
        for ms in MEETING_STAGES:
            if ms in n2i:
                targets.append((pid, ms, n2i[ms], noshow, closing, waiting))
    meetings = fathom_meetings(datetime.now(timezone.utc) - timedelta(days=FATHOM_LOOKBACK_DAYS))
    log(f"Pulled {len(meetings)} Fathom meetings; scanning {len(targets)} meeting-stage(s)")

    counts = {"noshow": 0, "schedule": 0, "closing": 0, "lost": 0, "cooloff": 0, "flag": 0,
              "skip_upcoming": 0, "skip_noappt": 0}
    for pid, ms_name, ms_id, noshow_id, closing_id, waiting_id in targets:
        r = HTTP.get(f"{GHL_BASE}/opportunities/search", headers=GHL_H,
                     params={"location_id": LOC, "pipeline_id": pid, "pipeline_stage_id": ms_id,
                             "status": "open", "limit": 100})
        for opp in r.json().get("opportunities", []):
            c = opp.get("contact", {}) or {}
            cid = c.get("id"); name = c.get("name", "?"); email = c.get("email", "")
            if not cid: continue
            appts = get_appts(cid)
            upcoming = [a for a in appts if (R.d10(a.get("startTime")) or today) >= today
                        and "cancel" not in str(a.get("appointmentStatus") or a.get("status") or "").lower()]
            if upcoming:
                counts["skip_upcoming"] += 1; continue
            past = [a for a in appts if (R.d10(a.get("startTime")) or today) < today]
            if not past:
                counts["skip_noappt"] += 1; continue
            appt = sorted(past, key=lambda a: str(a.get("startTime")))[-1]
            aid = appt.get("id"); appt_date = R.d10(appt.get("startTime"))
            st = str(appt.get("appointmentStatus") or appt.get("status") or "").lower()

            # ---- show vs no-show ----
            meeting = None
            if "noshow" in st or "no-show" in st:
                verdict, why = "noshow", "appointment already marked no-show"
            elif "showed" in st:
                verdict, why = "showed", "appointment already marked showed"
                meeting = fathom_match(name, email, cid, appt_date, meetings)
            else:
                meeting = fathom_match(name, email, cid, appt_date, meetings)
                if meeting:
                    verdict, why = "showed", "Fathom recording found"
                elif note_on_or_after(cid, appt_date):
                    verdict, why = "showed", "note on/after appointment"
                else:
                    verdict, why = "noshow", "no Fathom recording, no post-appointment note"

            if verdict == "noshow":
                log(f"  {name} [{ms_name}] appt {appt_date} -> NO-SHOW ({why})")
                if dry_run: continue
                if noshow_id and move_opp(opp.get("id"), pid, noshow_id):
                    if aid: mark_appt(aid, "noshow")
                    R.post_note(cid, f"🚫 Auto-moved to No-Show: no Fathom recording for the "
                                f"{appt_date} appointment and no note logged → confirmed no-show.")
                    counts["noshow"] += 1
                else:
                    log(f"    ! could not move {name} (no No-Show stage?)")
                continue

            # ---- showed: route the post-demo lead via the Fathom transcript + rep notes ----
            decision = route_demo(meeting, name, R.get_notes(cid), today)
            route = decision["route"]; rnote = decision.get("note", "")
            log(f"  {name} [{ms_name}] appt {appt_date} -> SHOWED, route={route} ({decision.get('reason','')})")
            if dry_run: continue
            if aid: mark_appt(aid, "showed")
            if route == "lost":
                HTTP.put(f"{GHL_BASE}/opportunities/{opp.get('id')}/status", headers=GHL_H,
                         json={"status": "lost"})
                R.post_note(cid, f"✅ Attended demo → not a fit (marked lost): {rnote}")
                counts["lost"] += 1
            elif route == "cooloff" and cooloff_id:
                move_opp(opp.get("id"), reignite_pid, cooloff_id)
                R.post_note(cid, f"✅ Attended demo → parked to cool-off: {rnote}")
                counts["cooloff"] += 1
            elif route == "schedule":
                fdate = decision.get("followup_date") or (today + timedelta(days=14)).isoformat()
                set_followup_date(cid, fdate)
                if waiting_id: move_opp(opp.get("id"), pid, waiting_id)
                R.post_note(cid, f"📅 Attended demo → interested, follow up {fdate} (parked in "
                            f"Waiting For Follow Up Date): {rnote}")
                counts["schedule"] += 1
            else:  # closing or flag
                if closing_id:
                    move_opp(opp.get("id"), pid, closing_id)
                prefix = ("🔥 Attended demo → Closing" if route == "closing"
                          else "⚠️ Attended demo → Closing (REVIEW — outcome unclear)")
                R.post_note(cid, f"{prefix}: {rnote}")
                counts["closing" if route == "closing" else "flag"] += 1
    log(f"Done. {counts}")
    return counts

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(dry_run=a.dry_run)
