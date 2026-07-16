#!/usr/bin/env python3
"""
Restoration AI — Intelligent Pipeline Router  (Phase 1: PROPOSE-ONLY)

Scans OPEN opportunities across the 3 pipelines, uses cheap deterministic rules to
pick the small set of contacts whose situation actually changed / went stale, then
asks Claude (Haiku) to adjudicate  follow_up / cooloff / stay  for each — reading
the conversation the way a human would, distinguishing MANUAL outreach (source=app
+ userId) from AUTOMATED workflow blasts (source=workflow) and real LEAD inbound.

It writes router_suggestions.json + prints a report. It DOES NOT move anything in
GHL — suggestions only. The daily call-list page renders these at the top for you
to approve.

Flags:  --no-llm  (rule-only, no API cost)   --limit N (cap detail pulls)   --quiet
"""
import os, re, sys, json, time, argparse, urllib.request, urllib.error
import requests
from _http import HTTP
from datetime import datetime, date, timedelta

BASE_DIR   = os.environ.get("RAI_BASE") or os.path.expanduser("~/restoration-ai")
LOG_FILE   = os.path.join(BASE_DIR, "auto_router.log")
SUGG_FILE  = os.path.join(BASE_DIR, "router_suggestions.json")
STATE_FILE = os.path.join(BASE_DIR, "router_state.json")
ENV_FILE   = os.path.join(BASE_DIR, ".env")

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"; print(line)
    os.makedirs(BASE_DIR, exist_ok=True)
    with open(LOG_FILE, "a") as f: f.write(line + "\n")

# ---------------- GHL ----------------
GHL_API_KEY     = os.environ.get("GHL_API_KEY") or "pit-c75a84bf-6d23-4a8a-a1ff-a88054b0e1bc"
GHL_LOCATION_ID = "Tx5eKisj3Xluq1SeZKe3"
GHL_BASE        = "https://services.leadconnectorhq.com"
GHL_HEADERS     = {"Authorization": f"Bearer {GHL_API_KEY}", "Version": "2021-07-28",
                   "Content-Type": "application/json"}

PIPELINES = {"Sales": "hPnHBxO63YMecyG219V5",
             "Secured Clients": "OP4aWjh91AfikmEYKDHk",
             "Re-Igniting": "KRokx3RqJjNzUg8YCbWk"}
CALL_STAGE_IDS = {"9fb3928a-33e3-4592-a080-56b3f353e56b",
                  "892dfc0e-cec3-4b43-8a6e-0805348ee723",
                  "ce155700-eb61-4d8b-899a-55baaa7d9a6e"}
# Where each pipeline's "ready to call" stage lives (for follow_up suggestions).
FOLLOWUP_STAGE = {"Sales": "9fb3928a-33e3-4592-a080-56b3f353e56b",
                  "Secured Clients": "892dfc0e-cec3-4b43-8a6e-0805348ee723",
                  "Re-Igniting": "ce155700-eb61-4d8b-899a-55baaa7d9a6e"}
COOLOFF_PIPELINE = "Re-Igniting"
COOLOFF_STAGE_NAME = "One Month Reset Period"

# Lifecycle thresholds (user-chosen: patient)
COOLOFF_ATTEMPTS     = 5     # manual outreaches with zero inbound...
COOLOFF_SILENCE_DAYS = 14    # ...over this many days -> auto-park to cool-off
STALE_ACTIVE_DAYS    = 7     # active stage untouched this long -> take a look
COOLOFF_RESET_DAYS   = 30    # auto-resurface from cool-off after this many days
SNOOZE_DAYS          = 2     # after grace, an un-commented suggestion hides this long, then returns
COOLOFF_TRACKER = os.path.join(BASE_DIR, "cooloff_tracker.json")
SNOOZE_FILE     = os.path.join(BASE_DIR, "snooze.json")

PARKED_RE = re.compile(r"reset period|long nurture|signed up|trial complete|"
                       r"wants to cancel|placeholder|self sign|clients are live",
                       re.IGNORECASE)
JUNK_NAMES = {"test", "test s", "sc", "as", "asdf", "content", "demo", "no name"}

# ---------------- Anthropic (Haiku) ----------------
ANTHROPIC_API   = "https://api.anthropic.com/v1/messages"
# Fable 5 (Santino 2026-07-13): best-quality briefings/suggestions; one
# daily run so cost is negligible. Emits thinking blocks (no "text" key,
# harmless to the join below) and REJECTS the temperature param; needs
# max_tokens headroom for reasoning.
ANTHROPIC_MODEL = os.environ.get("CALLIST_MODEL", "claude-fable-5")

def load_anthropic_key():
    k = os.environ.get("ANTHROPIC_API_KEY")
    if k: return k
    try:
        for line in open(ENV_FILE):
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return None

def anthropic_json(system, user, *, model=ANTHROPIC_MODEL, max_tokens=2500, retries=3):
    """Short non-streaming call that returns parsed JSON (or None)."""
    key = load_anthropic_key()
    if not key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY (rank-ai/.env)")
    body = json.dumps({"model": model, "max_tokens": max_tokens,
                       "system": system,
                       "messages": [{"role": "user", "content": user}]}).encode()
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(ANTHROPIC_API, data=body, method="POST",
                                         headers={"x-api-key": key,
                                                  "anthropic-version": "2023-06-01",
                                                  "content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                d = json.loads(resp.read().decode())
            txt = "".join(b.get("text", "") for b in d.get("content", []))
            m = re.search(r"\{.*\}", txt, re.DOTALL)
            return json.loads(m.group(0)) if m else None
        except Exception as e:
            if attempt == retries:
                log(f"  anthropic call failed: {e}")
                return None
            time.sleep(1.5 * attempt)

# ---------------- helpers ----------------
def strip(t): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t or "")).strip()
def d10(s):
    try: return date.fromisoformat(str(s)[:10])
    except Exception: return None

def get_pipelines():
    r = HTTP.get(f"{GHL_BASE}/opportunities/pipelines", headers=GHL_HEADERS,
                     params={"locationId": GHL_LOCATION_ID})
    out = {}
    for p in r.json().get("pipelines", []):
        out[p["id"]] = {"name": p.get("name"),
                        "id_to_name": {s["id"]: s["name"] for s in p.get("stages", [])},
                        "name_to_id": {s["name"]: s["id"] for s in p.get("stages", [])}}
    return out

def get_open_opps(pipeline_id):
    opps, start_after, start_after_id = [], None, None
    while True:
        params = {"location_id": GHL_LOCATION_ID, "pipeline_id": pipeline_id,
                  "status": "open", "limit": 100}
        if start_after:    params["startAfter"]   = start_after
        if start_after_id: params["startAfterId"] = start_after_id
        r = HTTP.get(f"{GHL_BASE}/opportunities/search", headers=GHL_HEADERS, params=params)
        j = r.json(); batch = j.get("opportunities", [])
        opps += batch
        meta = j.get("meta", {}) or {}
        if batch and meta.get("startAfterId") and meta.get("nextPageUrl"):
            start_after, start_after_id = meta.get("startAfter"), meta.get("startAfterId")
        else:
            break
    return opps

def get_messages(cid):
    r = HTTP.get(f"{GHL_BASE}/conversations/search", headers=GHL_HEADERS,
                     params={"locationId": GHL_LOCATION_ID, "contactId": cid})
    convos = r.json().get("conversations", []) if r.status_code == 200 else []
    out = []
    for cv in convos:
        cursor = None
        while True:
            params = {"limit": 100}
            if cursor: params["lastMessageId"] = cursor
            mr = HTTP.get(f"{GHL_BASE}/conversations/{cv['id']}/messages",
                              headers=GHL_HEADERS, params=params)
            if mr.status_code != 200: break
            block = mr.json().get("messages", {}); msgs = block.get("messages", [])
            out += msgs
            if block.get("nextPage") and msgs: cursor = msgs[-1].get("id")
            else: break
    # de-dup + chronological
    seen, uniq = set(), []
    for m in sorted(out, key=lambda x: x.get("dateAdded", "")):
        if m.get("id") in seen: continue
        seen.add(m.get("id")); uniq.append(m)
    return uniq

def get_appts(cid):
    r = HTTP.get(f"{GHL_BASE}/contacts/{cid}/appointments", headers=GHL_HEADERS)
    if r.status_code != 200: return []
    j = r.json(); return j.get("events", j.get("appointments", []))

def get_notes(cid):
    r = HTTP.get(f"{GHL_BASE}/contacts/{cid}/notes", headers=GHL_HEADERS)
    notes = r.json().get("notes", []) if r.status_code == 200 else []
    clean = [n for n in sorted(notes, key=lambda n: n.get("dateAdded", ""))
             if (n.get("body") or "").strip()
             and not (n.get("body") or "").startswith("--------- AI Call with:")]
    return " | ".join(f"[{n.get('dateAdded','')[:10]}] {strip(n.get('body'))}" for n in clean[-4:])

# ---- cool-off lifecycle (auto-park / auto-resurface) + snooze ----
def _jload(path, default):
    try: return json.load(open(path))
    except Exception: return default

def move_opp(opp_id, pipeline_id, stage_id):
    r = HTTP.put(f"{GHL_BASE}/opportunities/{opp_id}", headers=GHL_HEADERS,
                     json={"pipelineId": pipeline_id, "pipelineStageId": stage_id, "status": "open"})
    return r.status_code == 200

def post_note(cid, body):
    r = HTTP.post(f"{GHL_BASE}/contacts/{cid}/notes", headers=GHL_HEADERS, json={"body": body})
    return r.status_code in (200, 201)

def resurface_cooloffs(pipes, today):
    """Auto-return contacts parked 30+ days ago to 'Ready For Follow Up' (with a GHL note)."""
    tracker = _jload(COOLOFF_TRACKER, {})
    if not tracker: return 0
    reignite = PIPELINES["Re-Igniting"]; ready = FOLLOWUP_STAGE["Re-Igniting"]
    done = []
    for opp_id, info in tracker.items():
        try: parked = date.fromisoformat(str(info.get("parked", ""))[:10])
        except Exception: continue
        if (today - parked).days >= COOLOFF_RESET_DAYS:
            if move_opp(opp_id, reignite, ready):
                if info.get("cid"):
                    post_note(info["cid"], f"🔄 Cool-off complete — returned to 'Ready For Follow "
                              f"Up' on {today} after {COOLOFF_RESET_DAYS}-day reset.")
                done.append(opp_id); log(f"  resurfaced {info.get('name', opp_id)} from cool-off")
    for k in done: tracker.pop(k, None)
    json.dump(tracker, open(COOLOFF_TRACKER, "w"))
    return len(done)

def autopark(c, pipes, today):
    """Move a clear-cut going-dark lead into 30-day cool-off, with a GHL audit note."""
    opp = c["opp"]; opp_id = opp.get("id"); contact = opp.get("contact", {}) or {}
    cid = contact.get("id"); name = contact.get("name", "?")
    reignite = PIPELINES["Re-Igniting"]
    reset = pipes.get(reignite, {}).get("name_to_id", {}).get(COOLOFF_STAGE_NAME)
    if not reset:
        log(f"  ! cannot park {name}: '{COOLOFF_STAGE_NAME}' stage not found"); return False
    if not move_opp(opp_id, reignite, reset):
        log(f"  ! FAILED to park {name}"); return False
    if cid:
        back = (today + timedelta(days=COOLOFF_RESET_DAYS)).isoformat()
        post_note(cid, f"🅿️ Auto-parked into {COOLOFF_RESET_DAYS}-day cool-off on {today} — reason: "
                  f"{COOLOFF_ATTEMPTS}+ manual outreach attempts, no reply, {COOLOFF_SILENCE_DAYS}+ days "
                  f"silent. Scheduled to auto-resurface to 'Ready For Follow Up' ~{back}.")
    tracker = _jload(COOLOFF_TRACKER, {})
    tracker[opp_id] = {"parked": today.isoformat(), "cid": cid, "name": name}
    json.dump(tracker, open(COOLOFF_TRACKER, "w"))
    log(f"  auto-parked {name} -> cool-off (GHL note added)")
    return True

def load_snoozed(today):
    out = set()
    for opp_id, until in _jload(SNOOZE_FILE, {}).items():
        try:
            if date.fromisoformat(str(until)[:10]) > today: out.add(opp_id)
        except Exception: pass
    return out

# A "remove from list" / "do not call" note anywhere in a contact's history means the user
# told us to drop them — honor it in the suggestions too (not just the call list).
REMOVE_RE = re.compile(
    r"(remove\s+(me\s+)?from\s+(the\s+)?(call\s+)?list|"
    r"take\s+(me\s+)?off\s+(the\s+)?(call\s+)?list|"
    r"\boff\s+the\s+(call\s+)?list\b|\bdo\s*not\s*call\b|\bdon.?t\s*call\b|"
    r"\bdnc\b|\bstop\s+calling\b)", re.IGNORECASE)

_REMOVED_CACHE = None
def _removed_ids():
    """Durable removed ledger (shared KV) — lazy import avoids a circular import
    with auto_daily_call_list, which imports this module at load time."""
    global _REMOVED_CACHE
    if _REMOVED_CACHE is None:
        try:
            import auto_daily_call_list as _L
            _REMOVED_CACHE = _L.load_removed()
        except Exception:
            _REMOVED_CACHE = set()
    return _REMOVED_CACHE

def is_removed(notes_blob):
    return bool(REMOVE_RE.search(notes_blob or ""))

MANUAL_TYPES = {"TYPE_SMS", "TYPE_CALL", "TYPE_EMAIL"}

def signals(messages, appts, today):
    last_inbound = None; last_inbound_txt = ""; last_msg_id = None
    manual_dates = []
    for m in messages:
        last_msg_id = m.get("id") or last_msg_id
        mt = str(m.get("messageType") or "")
        dirn = m.get("direction"); src = m.get("source"); uid = m.get("userId")
        dt = d10(m.get("dateAdded"))
        if dirn == "inbound":
            if dt and (last_inbound is None or dt >= last_inbound):
                last_inbound = dt; last_inbound_txt = strip(m.get("body"))[:160]
        elif dirn == "outbound" and src == "app" and uid and mt in MANUAL_TYPES:
            if dt: manual_dates.append(dt)
    attempts_since = len([d for d in manual_dates if last_inbound is None or d > last_inbound])
    last_manual = max(manual_dates) if manual_dates else None
    days_silent = (today - last_inbound).days if last_inbound else None
    # appointments
    upcoming = False; last_past = None; last_past_status = None; cancelled_noshow = False
    for a in appts:
        ad = d10(a.get("startTime")); st = str(a.get("appointmentStatus") or a.get("status") or "").lower()
        if "cancel" in st or "no-show" in st or "noshow" in st or "no_show" in st:
            cancelled_noshow = True
        if ad and ad >= today and "cancel" not in st:
            upcoming = True
        if ad and ad < today and (last_past is None or ad >= last_past):
            last_past, last_past_status = ad, st
    return {"last_inbound": last_inbound, "last_inbound_txt": last_inbound_txt,
            "attempts_since_inbound": attempts_since, "last_manual": last_manual,
            "days_silent": days_silent, "upcoming_appt": upcoming,
            "last_past_appt": last_past, "last_past_status": last_past_status,
            "cancelled_noshow": cancelled_noshow, "last_msg_id": last_msg_id}

def rules_for(stage_name, is_call, sig, days_since_update):
    booked = "booked" in (stage_name or "").lower()
    hits = []
    if booked and not sig["upcoming_appt"]:
        hits.append("meeting_stage_no_upcoming")
    if sig["cancelled_noshow"] and not sig["upcoming_appt"]:
        hits.append("appt_cancelled_or_noshow")
    if (sig["attempts_since_inbound"] >= COOLOFF_ATTEMPTS
            and (sig["days_silent"] or 0) >= COOLOFF_SILENCE_DAYS):
        hits.append("going_dark")
    if (not booked and not is_call and days_since_update is not None
            and days_since_update >= STALE_ACTIVE_DAYS and not sig["upcoming_appt"]
            and not sig["last_inbound"]):
        hits.append("stale_in_stage")
    if is_call:
        # already on the call list — only a cool-off recommendation is new info
        hits = [h for h in hits if h == "going_dark"]
    return hits

def digest(opp, label, stage_name, sig, messages):
    name = (opp.get("contact", {}) or {}).get("name", "?")
    company = (opp.get("contact", {}) or {}).get("companyName") or ""
    lines = [f"Lead: {name}" + (f" ({company})" if company else ""),
             f"Pipeline: {label} | Current stage: {stage_name} | Value: ${opp.get('monetaryValue', 0)}",
             f"Upcoming appointment: {'YES' if sig['upcoming_appt'] else 'no'}",
             f"Last past appointment: {sig['last_past_appt']} status={sig['last_past_status']}"
             if sig["last_past_appt"] else "Last past appointment: none",
             f"Last LEAD inbound: {sig['last_inbound']} ({sig['days_silent']} days ago): "
             f"\"{sig['last_inbound_txt']}\"" if sig["last_inbound"] else "Last LEAD inbound: none on record",
             f"Manual outreach attempts since their last reply: {sig['attempts_since_inbound']}",
             "", "Recent thread (LEAD = them, ME = manual by you, AUTO = automation):"]
    # last ~12 meaningful messages (skip pure activities)
    show = [m for m in messages if str(m.get("messageType") or "").startswith("TYPE_")
            and "ACTIVITY" not in str(m.get("messageType"))][-12:]
    for m in show:
        dirn = m.get("direction"); src = m.get("source"); uid = m.get("userId")
        who = "LEAD" if dirn == "inbound" else ("ME" if (src == "app" and uid) else "AUTO")
        body = strip(m.get("body"))[:140] or f"[{m.get('messageType')}]"
        lines.append(f"  {str(m.get('dateAdded'))[:10]} {who}: {body}")
    return "\n".join(lines)

SYSTEM = (
 "You are a sales pipeline router for a water-damage-restoration SaaS (Rank AI). "
 "You decide whether a lead should be surfaced for a follow-up call, parked to cool "
 "off, or left alone. CRITICAL: only LEAD inbound messages count as engagement; "
 "messages marked ME are manual human outreach (attempts), AUTO are automated "
 "workflow blasts and mean nothing about interest. Be conservative. "
 "Recommend follow_up when a booked meeting clearly fell through / didn't happen, or "
 "a previously-engaged lead has gone quiet and is worth a live call. Recommend "
 "cooloff only when there have been many manual attempts and long silence (dead air). "
 "Recommend stay when there is an upcoming appointment or the lead recently replied "
 "and is mid-conversation. Reply with ONLY JSON: "
 '{"action":"follow_up|cooloff|stay","priority":"high|medium|low","confidence":0.0-1.0,'
 '"reason":"one short sentence"}')

def decide_llm(dg, rule_hits):
    user = (f"Deterministic rules that fired: {', '.join(rule_hits) or 'none'}\n\n{dg}\n\n"
            "Given the thread and rules, return the JSON decision.")
    out = anthropic_json(SYSTEM, user)
    if not out or out.get("action") not in {"follow_up", "cooloff", "stay"}:
        return None
    return out

def decide_rules(rule_hits):
    if "going_dark" in rule_hits:
        return {"action": "cooloff", "priority": "low", "confidence": 0.6,
                "reason": f"{COOLOFF_ATTEMPTS}+ manual attempts, {COOLOFF_SILENCE_DAYS}+ days silent."}
    if rule_hits:
        return {"action": "follow_up", "priority": "medium", "confidence": 0.6,
                "reason": "Booked meeting with no upcoming appointment / went stale."}
    return {"action": "stay", "priority": "low", "confidence": 0.5, "reason": ""}

def run(no_llm=False, limit=None, quiet=False):
    today = date.today()
    log(f"=== Router scan {today} (propose-only{', no-llm' if no_llm else ''}) ===")
    pipes = get_pipelines()
    resurfaced = resurface_cooloffs(pipes, today)
    if resurfaced: log(f"Auto-resurfaced {resurfaced} contact(s) from cool-off")
    snoozed = load_snoozed(today)
    state = {}
    try: state = json.load(open(STATE_FILE))
    except Exception: pass

    candidates = []
    scanned = detailed = 0
    for label, pid in PIPELINES.items():
        for opp in get_open_opps(pid):
            scanned += 1
            sid = opp.get("pipelineStageId")
            stage_name = pipes.get(pid, {}).get("id_to_name", {}).get(sid, sid)
            is_call = sid in CALL_STAGE_IDS
            booked = "booked" in (stage_name or "").lower()
            parked = bool(PARKED_RE.search(stage_name or ""))
            upd = d10(opp.get("updatedAt") or opp.get("lastStatusChangeAt") or opp.get("dateUpdated"))
            days_upd = (today - upd).days if upd else None
            # cheap gate: skip parked, and skip clearly-fresh plain-active opps
            if parked:
                continue
            if not booked and not is_call and (days_upd is None or days_upd < STALE_ACTIVE_DAYS):
                continue
            contact = opp.get("contact", {}) or {}
            cid = contact.get("id")
            if not cid:
                continue
            # skip obvious test/junk CRM entries
            nm = (contact.get("name") or "").strip().lower()
            if (not nm or nm in JUNK_NAMES or "@" in nm or len(nm) <= 2):
                continue
            if limit and detailed >= limit:
                continue
            detailed += 1
            msgs = get_messages(cid); appts = get_appts(cid)
            sig = signals(msgs, appts, today)
            hits = rules_for(stage_name, is_call, sig, days_upd)
            if not hits:
                continue
            candidates.append({"opp": opp, "label": label, "pid": pid, "sid": sid,
                               "stage_name": stage_name, "sig": sig, "msgs": msgs,
                               "hits": hits})
    log(f"Scanned {scanned} open opps; pulled detail on {detailed}; {len(candidates)} candidates after rules")

    suggestions = []
    parked = 0
    for c in candidates:
        opp = c["opp"]; cid = opp.get("contact", {}).get("id"); opp_id = opp.get("id")
        # Auto-park clear-cut going-dark leads (deterministic — no LLM, no approval).
        if "going_dark" in c["hits"]:
            if autopark(c, pipes, today): parked += 1
            continue
        # Skip suggestions you recently ignored (snoozed).
        if opp_id in snoozed:
            continue
        sig = c["sig"]
        signature = f"{c['sid']}|{sig['last_msg_id']}|{today.isoformat() if 'going_dark' in c['hits'] or 'stale_in_stage' in c['hits'] else ''}"
        cached = state.get(cid, {})
        if cached.get("signature") == signature and "decision" in cached:
            decision = cached["decision"]
        elif no_llm:
            decision = decide_rules(c["hits"])
        else:
            dg = digest(opp, c["label"], c["stage_name"], sig, c["msgs"])
            decision = decide_llm(dg, c["hits"]) or decide_rules(c["hits"])
        state[cid] = {"signature": signature, "decision": decision,
                      "ts": datetime.now().isoformat()}
        if decision["action"] == "stay":
            continue
        contact = opp.get("contact", {}) or {}
        if decision["action"] == "cooloff":
            tgt_label, tgt_stage = COOLOFF_PIPELINE, COOLOFF_STAGE_NAME
        else:
            tgt_label = c["label"]
            tgt_stage = "Follow Up Ready" if c["label"] == "Secured Clients" else "Ready For Follow Up"
        notes_full = get_notes(cid)
        # Honor a "remove from list" / "do not call" directive — stop re-suggesting them.
        # Checks the note history, the durable removed ledger, AND the GHL tag.
        _ctags = [str(t).strip().lower() for t in (contact.get("tags") or [])]
        if is_removed(notes_full) or cid in _removed_ids() or "remove-from-call-list" in _ctags:
            log(f"  skipping suggestion for {contact.get('name','?')} — 'remove from list' on file")
            continue
        last_reply = (f"{sig['last_inbound']}: {sig['last_inbound_txt']}"
                      if sig.get("last_inbound") else "")
        suggestions.append({
            "contact_id": cid, "opp_id": opp.get("id"),
            "name": contact.get("name", "?"), "company": contact.get("companyName") or "",
            "phone": contact.get("phone", ""), "value": opp.get("monetaryValue", 0),
            "current_pipeline": c["label"], "current_stage": c["stage_name"],
            "action": decision["action"], "target_pipeline": tgt_label, "target_stage": tgt_stage,
            "priority": decision["priority"], "confidence": decision["confidence"],
            "reason": decision["reason"], "rules": c["hits"],
            "last_reply": last_reply[:240], "notes": notes_full[:700]})

    order = {"high": 0, "medium": 1, "low": 2}
    suggestions.sort(key=lambda s: (order.get(s["priority"], 3), -float(s["confidence"] or 0)))
    json.dump({"generated_at": datetime.now().isoformat(), "date": today.isoformat(),
               "suggestions": suggestions}, open(SUGG_FILE, "w"), indent=2)
    json.dump(state, open(STATE_FILE, "w"))
    log(f"Wrote {len(suggestions)} suggestions ({parked} auto-parked to cool-off) -> {SUGG_FILE}")

    if not quiet:
        print("\n=== SUGGESTED MOVES (propose-only) ===")
        if not suggestions: print("  (none)")
        for s in suggestions:
            arrow = "Ready For Follow Up" if s["action"] == "follow_up" else "One Month Reset (cool-off)"
            print(f"\n  • {s['name']} ({s['company']}) — ${s['value']} [{s['priority']}/{s['confidence']}]")
            print(f"      {s['current_pipeline']} / {s['current_stage']}  →  {s['target_pipeline']} / {arrow}")
            print(f"      {s['reason']}   (rules: {','.join(s['rules'])})")
    return suggestions

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    run(no_llm=a.no_llm, limit=a.limit, quiet=a.quiet)
