#!/usr/bin/env python3
import os, sys, json, re, requests
from _http import HTTP
from datetime import date, datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auto_router as R  # reuse the Claude helper for AI summaries

BASE_DIR = os.environ.get("RAI_BASE") or os.path.expanduser("~/restoration-ai")
LOG_FILE = os.path.join(BASE_DIR, "auto_call_list.log")

def log(msg):
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# --- CONSTANTS ---
GHL_API_KEY     = os.environ.get("GHL_API_KEY") or "pit-c75a84bf-6d23-4a8a-a1ff-a88054b0e1bc"
GHL_LOCATION_ID = "Tx5eKisj3Xluq1SeZKe3"
GHL_BASE_URL    = "https://services.leadconnectorhq.com"
GHL_HEADERS     = {
    "Authorization": f"Bearer {GHL_API_KEY}",
    "Version":       "2021-07-28",
    "Content-Type":  "application/json",
}

NOTION_TOKEN   = os.environ.get("NOTION_TOKEN") or "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"
HOME_PAGE_ID   = "388d279c-0699-8181-a5bb-cc0d5aae51ea"
NOTION_HEADERS = {
    "Authorization":  f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type":   "application/json",
}

def load_env_value(key):
    # Canonical credential store: the rank-ai repo .env (gitignored).
    env_path = "/Users/santino/restoration-ai/.env"
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return os.environ.get(key, "")

# Email is sent via SendGrid (domain-authenticated restorationai.io). No Gmail/SMTP.
SENDGRID_API_KEY = load_env_value("SENDGRID_API_KEY")
MAIL_FROM        = "contact@restorationai.io"
MAIL_FROM_NAME   = "Restoration AI"
MAIL_TO          = "contact@getrestorationai.com"

CALL_STAGES = [
    {"pipeline_id": "hPnHBxO63YMecyG219V5", "stage_id": "fa184149-7644-4bc1-a4a8-0effeb29b590", "label": "Closing",         "stage_name": "Closing"},
    {"pipeline_id": "hPnHBxO63YMecyG219V5", "stage_id": "cf8e6e3a-ca9d-4ad4-a85e-a16e367bc413", "label": "New Leads",       "stage_name": "New Leads"},
    {"pipeline_id": "hPnHBxO63YMecyG219V5", "stage_id": "9fb3928a-33e3-4592-a080-56b3f353e56b", "label": "Sales",           "stage_name": "Ready For Follow Up"},
    {"pipeline_id": "OP4aWjh91AfikmEYKDHk", "stage_id": "892dfc0e-cec3-4b43-8a6e-0805348ee723", "label": "Secured Clients", "stage_name": "Follow Up Ready"},
    {"pipeline_id": "KRokx3RqJjNzUg8YCbWk", "stage_id": "ce155700-eb61-4d8b-899a-55baaa7d9a6e", "label": "Re-Igniting",     "stage_name": "Ready For Follow Up"},
]
SECTION_ICONS = {"Closing": "🔥", "New Leads": "🌱", "Sales": "🤝", "Secured Clients": "✅", "Re-Igniting": "🔁"}
LABEL_ORDER   = ["Closing", "New Leads", "Sales", "Secured Clients", "Re-Igniting"]
JUNK_NAMES    = {"test", "test s", "sc", "as", "asdf", "cc", "content", "demo", "no name", "benny"}

STATE_TZ = {
    'ME':'ET','NH':'ET','VT':'ET','MA':'ET','RI':'ET','CT':'ET','NY':'ET','NJ':'ET','PA':'ET',
    'DE':'ET','MD':'ET','DC':'ET','VA':'ET','WV':'ET','NC':'ET','SC':'ET','GA':'ET','FL':'ET',
    'OH':'ET','MI':'ET','IN':'ET',
    'WI':'CT','IL':'CT','MN':'CT','IA':'CT','MO':'CT','ND':'CT','SD':'CT','NE':'CT','KS':'CT',
    'OK':'CT','TX':'CT','AR':'CT','LA':'CT','MS':'CT','AL':'CT','TN':'CT','KY':'CT',
    'MT':'MT','ID':'MT','WY':'MT','CO':'MT','UT':'MT','AZ':'MT','NM':'MT',
    'WA':'PT','OR':'PT','CA':'PT','NV':'PT','AK':'PT','HI':'PT',
}
AREA_TZ = {
    **{c:'ET' for c in ['201','202','203','207','212','215','216','234','240','248','267','272',
       '276','301','302','304','305','321','330','336','339','347','351','352','404','407','410',
       '412','413','419','423','440','443','470','478','484','502','508','513','516','517','518',
       '540','551','561','570','571','585','603','607','609','610','614','615','616','617','631',
       '646','678','689','703','704','706','716','717','718','724','727','732','740','754','757',
       '762','770','772','774','781','786','787','803','804','810','813','828','843','845','850',
       '856','857','859','860','862','863','864','865','878','904','908','910','912','914','917',
       '919','929','931','937','941','954','973','978','980','984']},
    **{c:'CT' for c in ['205','214','217','218','219','224','225','228','251','254','256','262',
       '270','309','312','314','316','318','319','320','325','331','334','337','346','361','402',
       '405','414','417','430','432','469','479','501','504','507','512','515','563','573','580',
       '608','620','630','636','641','651','660','682','713','726','737','769','773','785','806',
       '815','816','817','830','832','847','870','903','913','920','936','940','952','972','979']},
    **{c:'MT' for c in ['303','307','385','406','435','505','520','575','602','623','720','775','801','928','970']},
    **{c:'PT' for c in ['206','209','213','253','310','323','360','408','415','424','442','503',
       '510','530','541','559','562','619','626','628','650','657','661','669','702','707','714',
       '747','760','805','818','831','858','909','916','925','949','951']},
}
TZ_ORDER   = {'ET':0,'CT':1,'MT':2,'PT':3}
WEEKDAYS   = ["monday","tuesday","wednesday","thursday","friday"]
MONTHS_MAP = {
    "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
    "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
}

def strip_html(t):
    t = re.sub(r'<br\s*/?>', ' ', t, flags=re.IGNORECASE)
    t = re.sub(r'<[^>]+>', '', t)
    return re.sub(r'\s+', ' ', t).strip()

def get_tz(c):
    s = (c.get('state') or '').strip().upper()
    if s in STATE_TZ: return STATE_TZ[s]
    p = ''.join(filter(str.isdigit, c.get('phone') or ''))
    if p.startswith('1'): p = p[1:]
    return AREA_TZ.get(p[:3], 'ET') if len(p) >= 3 else 'ET'

def next_weekday_on_or_after(ref_date, weekday_idx):
    days_ahead = weekday_idx - ref_date.weekday()
    if days_ahead < 0:
        days_ahead += 7
    return ref_date + timedelta(days=days_ahead)

def parse_target_date(note_body, note_date_str, today):
    body = note_body.lower()
    for month_name, month_num in MONTHS_MAP.items():
        m = re.search(rf'\b{month_name}\s+(\d{{1,2}})(?:st|nd|rd|th)?\b', body)
        if m:
            day = int(m.group(1))
            try:
                target = date(today.year, month_num, day)
                if target < today:
                    # Only treat a past month-day as "next year" near a year
                    # boundary (Dec note saying "call Jan 5"). Otherwise it is
                    # a PAST reference inside the note ("(July 7)" written on
                    # July 6, read July 13): the contact is DUE NOW, not
                    # deferred a year. (Bug found 2026-07-13: hid Shawn Nunez
                    # until 2027.)
                    if (today - target).days > 300:
                        return date(today.year + 1, month_num, day)
                return target
            except ValueError:
                pass
    if 'tomorrow' in body and note_date_str:
        try:
            return date.fromisoformat(note_date_str) + timedelta(days=1)
        except ValueError:
            pass
    INTENT_RE = r'\b(call|text|follow|reach|try|ring|schedule|meet|talk|demo|touch base|check in)\w*\b'
    for i, day_name in enumerate(WEEKDAYS):
        if note_date_str:
            for sentence in re.split(r'[.!?\n]', body):
                # A bare weekday ("was unavailable on Monday") is a PAST
                # reference; only defer when the same sentence shows intent
                # to reach out that day ("call him back Tuesday").
                if re.search(rf'\b{day_name}\b', sentence) and re.search(INTENT_RE, sentence):
                    try:
                        note_date = date.fromisoformat(note_date_str)
                        return next_weekday_on_or_after(note_date + timedelta(days=1), i)
                    except ValueError:
                        pass
    return None

NO_ANSWER_RETRY_DAYS = 3
# Phrases meaning "I tried but didn't reach a live person." Such a note (with no
# explicit future date) bumps the contact NO_ANSWER_RETRY_DAYS days out instead of
# reappearing every single day. Repeated no-answers re-space by 3 days each time.
NO_ANSWER_RE = re.compile(
    r"\b(no\s*answer|no\s*ans|did\s*n.?t\s*answer|no\s*pick\s*up|did\s*n.?t\s*pick\s*up|"
    r"no\s*response|left\s*(a\s*)?(voicemail|vm|message|msg)|vm\s*left|left\s*vm|"
    r"went\s*to\s*voicemail|voicemail|no\s*vm)\b",
    re.IGNORECASE,
)

def is_no_answer(note_body):
    return bool(NO_ANSWER_RE.search(note_body or ""))

# A "remove from list" / "do not call" note ANYWHERE in a contact's GHL note history
# permanently drops them from the call list. Undo by deleting that note in GHL.
REMOVE_RE = re.compile(
    r"(remove\s+(me\s+)?from\s+(the\s+)?(call\s+)?list|"
    r"take\s+(me\s+)?off\s+(the\s+)?(call\s+)?list|"
    r"\boff\s+the\s+(call\s+)?list\b|\bdo\s*not\s*call\b|\bdon.?t\s*call\b|"
    r"\bdnc\b|\bstop\s+calling\b)",
    re.IGNORECASE,
)

def is_removed(notes_blob):
    return bool(REMOVE_RE.search(notes_blob or ""))


REMOVED_FILE = os.path.join(BASE_DIR, "removed.json")


def _kv(method, key, payload=None):
    """Tiny ops_kv client — SHARED store so Mac runs and Railway agree.
    Returns None (and callers fall back to the local file) without env."""
    url = os.environ.get("SUPABASE_URL"); k = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not (url and k):
        return None
    h = {"apikey": k, "Authorization": f"Bearer {k}", "Content-Type": "application/json"}
    try:
        if method == "GET":
            r = HTTP.get(f"{url.rstrip('/')}/rest/v1/ops_kv",
                         params={"k": f"eq.{key}", "select": "v"}, headers=h)
            rows = r.json() if r.status_code == 200 else []
            return rows[0]["v"] if rows else {}
        HTTP.post(f"{url.rstrip('/')}/rest/v1/ops_kv?on_conflict=k",
                  json={"k": key, "v": payload},
                  headers={**h, "Prefer": "resolution=merge-duplicates,return=minimal"})
        return payload
    except Exception as e:
        print(f"[kv] {method} {key} failed: {e}")
        return None


def load_removed() -> set:
    kv = _kv("GET", "callist-removed")
    if kv is not None:
        return set(kv.get("ids", []))
    try:
        return set(json.load(open(REMOVED_FILE)))
    except Exception:
        return set()

# GHL tag that marks a contact as off the call list. Applied automatically when a
# removal is captured, and honored directly — so Santino can also just add the tag
# in the GHL UI to drop someone. Remove the tag there to undo.
REMOVE_TAG = "remove-from-call-list"

def tag_removed(contact_id: str) -> bool:
    r = HTTP.post(f"{GHL_BASE_URL}/contacts/{contact_id}/tags",
                  headers=GHL_HEADERS, json={"tags": [REMOVE_TAG]})
    return r.status_code in (200, 201)

def has_remove_tag(contact) -> bool:
    tags = (contact.get('meta') or {}).get('tags') or []
    return REMOVE_TAG in (str(t).strip().lower() for t in tags)

def add_removed(contact_id: str) -> None:
    """Durable removal, independent of whether the GHL note posts. The old
    flow lost 'remove from list' notes to a sync bug (2026-07-14) and people
    Santino had removed kept reappearing. Also tags the contact in GHL so the
    removal is visible in the CRM and survives any state loss."""
    ids = load_removed(); ids.add(contact_id)
    if _kv("POST", "callist-removed", {"ids": sorted(ids)}) is None:
        json.dump(sorted(ids), open(REMOVED_FILE, "w"))
    try:
        tag_removed(contact_id)
    except Exception as e:
        print(f"[remove-tag] {contact_id} failed: {e}")

def call_decision(contact, today):
    """(show, reason) — reason explains WHY someone is hidden so the daily
    email can list them (a silently missing warm lead cost us Shawn Nunez
    for a week, 2026-07-13)."""
    if has_remove_tag(contact):
        return False, "removed (GHL tag)"
    if contact.get('contact_id') in load_removed():
        return False, "removed (do-not-call list)"
    if is_removed(contact.get('notes', '')):
        return False, "removed (do-not-call note)"
    note_body = contact.get('latest_note_body', '')
    note_date = contact.get('latest_note_date', '')
    if not note_body:
        return True, None
    target = parse_target_date(note_body, note_date, today)
    if target is None and note_date and is_no_answer(note_body):
        try:
            target = date.fromisoformat(note_date) + timedelta(days=NO_ANSWER_RETRY_DAYS)
        except ValueError:
            target = None
        if target and target > today:
            return False, f"no-answer retry, back {target.strftime('%b %-d')}"
    if target is None or target <= today:
        return True, None
    return False, f"note says {target.strftime('%b %-d')}"


def should_call_today(contact, today):
    # (0) Hard removal: a "remove from list" / "do not call" note anywhere in the
    #     contact's note history suppresses them for good (delete the GHL note to undo).
    if is_removed(contact.get('notes', '')):
        return False
    note_body = contact.get('latest_note_body', '')
    note_date  = contact.get('latest_note_date', '')
    # Daily full list: include every open contact every day, with two exceptions —
    # (1) a contact explicitly pushed to a FUTURE date is hidden until that date;
    # (2) a "no answer" note (no explicit date) bumps them NO_ANSWER_RETRY_DAYS days
    #     out so we don't call the same unreachable person every single day.
    if not note_body:
        return True
    target = parse_target_date(note_body, note_date, today)
    if target is None and note_date and is_no_answer(note_body):
        try:
            target = date.fromisoformat(note_date) + timedelta(days=NO_ANSWER_RETRY_DAYS)
        except ValueError:
            target = None
    if target is None:       return True
    if target <= today:      return True
    return False

HIDDEN_TODAY = []   # (name, company, reason) collected by filter_for_today

def filter_for_today(results, today):
    HIDDEN_TODAY.clear()
    filtered = {}
    for label, stages in results.items():
        filtered_stages = {}
        for stage_name, contacts in stages.items():
            kept = []
            for c in contacts:
                ok, why = call_decision(c, today)
                if ok:
                    kept.append(c)
                elif why and "removed" not in why:
                    HIDDEN_TODAY.append((c.get('name', '?'), c.get('company', ''), why))
            if kept:
                filtered_stages[stage_name] = kept
        if filtered_stages:
            filtered[label] = filtered_stages
    return filtered

def get_opps(pipeline_id, stage_id):
    params = {'location_id': GHL_LOCATION_ID, 'pipeline_id': pipeline_id, 'status': 'open', 'limit': 50}
    if stage_id: params['pipeline_stage_id'] = stage_id
    r = HTTP.get(f'{GHL_BASE_URL}/opportunities/search', headers=GHL_HEADERS, params=params)
    return r.json().get('opportunities', [])

def get_notes(contact_id):
    r = HTTP.get(f'{GHL_BASE_URL}/contacts/{contact_id}/notes', headers=GHL_HEADERS)
    return r.json().get('notes', []) if r.status_code == 200 else []

def get_convo_context(contact_id):
    """Full recent-conversation picture for scheduling context and the
    briefing: last message each direction + an unanswered-inbound flag."""
    out = {"last_in": None, "last_in_body": "", "last_out": None,
           "unanswered": False}
    r = HTTP.get(f'{GHL_BASE_URL}/conversations/search', headers=GHL_HEADERS,
                 params={'locationId': GHL_LOCATION_ID, 'contactId': contact_id})
    if r.status_code != 200:
        return out
    for convo in r.json().get('conversations', [])[:2]:
        mr = HTTP.get(f'{GHL_BASE_URL}/conversations/{convo["id"]}/messages',
                      headers=GHL_HEADERS, params={'limit': 30})
        if mr.status_code != 200:
            continue
        for msg in mr.json().get('messages', {}).get('messages', []):
            d = (msg.get('dateAdded') or '')[:10]
            body = strip_html((msg.get('body') or '')[:180])
            if msg.get('direction') == 'inbound':
                if not out["last_in"] or d > out["last_in"]:
                    out["last_in"], out["last_in_body"] = d, body
            else:
                if not out["last_out"] or d > out["last_out"]:
                    out["last_out"] = d
    out["unanswered"] = bool(out["last_in"] and
                             (not out["last_out"] or out["last_in"] > out["last_out"]))
    return out


def get_last_contact(contact_id):
    r = HTTP.get(f'{GHL_BASE_URL}/conversations/search', headers=GHL_HEADERS,
                     params={'locationId': GHL_LOCATION_ID, 'contactId': contact_id})
    if r.status_code != 200: return None, None
    convos = r.json().get('conversations', [])
    if not convos: return None, None
    mr = HTTP.get(f'{GHL_BASE_URL}/conversations/{convos[0]["id"]}/messages', headers=GHL_HEADERS)
    if mr.status_code != 200: return None, None
    for msg in mr.json().get('messages', {}).get('messages', []):
        direction = msg.get('direction', '')
        mtype     = str(msg.get('type', '')).upper()
        status    = str(msg.get('status', '')).lower()
        d         = (msg.get('dateAdded') or '')[:10]
        body      = strip_html((msg.get('body') or '')[:200])
        if direction == 'inbound':
            channel = 'text' if ('SMS' in mtype or 'EMAIL' in mtype) else 'call'
            return d, f'they responded via {channel}: {body}' if body else f'they responded via {channel}'
        if 'CALL' in mtype and status in ['answered', 'completed']:
            return d, f'answered call: {body}' if body else 'answered call'
    return None, None

def pull_contacts():
    log("Pulling GHL contacts...")
    results = {}
    for stage in CALL_STAGES:
        contacts = []
        for opp in get_opps(stage['pipeline_id'], stage['stage_id']):
            c   = opp.get('contact', {})
            cid = c.get('id')
            if not cid: continue
            nm = (c.get('name') or '').strip().lower()
            if not nm or nm in JUNK_NAMES or '@' in nm or len(nm) <= 2 \
                    or 'deleteme' in nm or nm.startswith('claude test'):
                continue  # skip test/junk CRM entries
            notes       = get_notes(cid)
            all_notes   = sorted(notes, key=lambda n: n.get('dateAdded', ''))
            clean_notes = [n for n in all_notes
                           if (n.get('body') or '').strip()
                           and not (n.get('body') or '').startswith('--------- AI Call with:')]
            notes_text = ' | '.join(
                f"[{n.get('dateAdded','')[:10]}] {strip_html((n.get('body') or '').strip())}"
                for n in clean_notes
            ) or 'No notes on file.'
            latest_note_body = strip_html((clean_notes[-1].get('body') or '').strip()) if clean_notes else ''
            latest_note_date = clean_notes[-1].get('dateAdded', '')[:10] if clean_notes else ''
            last_date, last_summary = get_last_contact(cid)
            tz = get_tz(c)
            contacts.append({
                'name':             c.get('name', 'No name'),
                'company':          c.get('companyName') or opp.get('name', ''),
                'phone':            c.get('phone', 'No phone'),
                'contact_id':       cid,
                'tz':               tz,
                'tz_order':         TZ_ORDER.get(tz, 0),
                'notes':            notes_text,
                'latest_note_body': latest_note_body,
                'latest_note_date': latest_note_date,
                'last_date':        last_date,
                'last_summary':     last_summary,
                'convo':            get_convo_context(cid),
                'meta':             get_contact_meta(cid),
            })
        contacts.sort(key=lambda x: x['tz_order'])
        label = stage['label']
        if label not in results:
            results[label] = {}
        results[label][stage['stage_name']] = contacts
    total = sum(len(c) for s in results.values() for c in s.values())
    log(f"Pulled {total} contacts from GHL")
    return results

def make_text_block(text, bold=False, color=None):
    rt = {"type": "text", "text": {"content": text}}
    if bold or color:
        rt['annotations'] = {}
        if bold:  rt['annotations']['bold']  = True
        if color: rt['annotations']['color'] = color
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [rt]}}

def make_heading(text, level=2):
    htype = f"heading_{level}"
    return {"object": "block", "type": htype, htype: {"rich_text": [{"type": "text", "text": {"content": text}}]}}

def make_divider():
    return {"object": "block", "type": "divider", "divider": {}}

SUMMARY_SYS = (
 "You write a tight 2-3 sentence briefing for a salesperson about to phone a lead at a "
 "water-damage-restoration SaaS. If lead-source / quiz info is given, START with how they came in "
 "(ad platform, campaign, offer) and the key qualifiers (business, revenue, prior agency, access). "
 "Then where things stand, and END with the single most useful focus for today's call. "
 "Use the given 'Came in (date)' for recency — do NOT infer age from tag or campaign text. "
 "No preamble. Reply ONLY JSON: {\"summary\":\"...\"}")

_CF_MAP = None
def get_cf_map():
    """id -> field name for all location custom fields (fetched once)."""
    global _CF_MAP
    if _CF_MAP is None:
        try:
            r = HTTP.get(f"{GHL_BASE_URL}/locations/{GHL_LOCATION_ID}/customFields", headers=GHL_HEADERS)
            _CF_MAP = {f["id"]: f.get("name", "") for f in r.json().get("customFields", [])} \
                      if r.status_code == 200 else {}
        except Exception:
            _CF_MAP = {}
    return _CF_MAP

def get_contact_meta(cid):
    """Lead source (UTM), tags, and LABELED quiz/funnel answers for the summary."""
    try:
        c = HTTP.get(f"{GHL_BASE_URL}/contacts/{cid}", headers=GHL_HEADERS).json().get("contact", {})
    except Exception:
        return {}
    cfmap = get_cf_map()
    labeled = {}
    for f in c.get("customFields", []):
        nm = cfmap.get(f.get("id"), ""); v = f.get("value")
        if nm and v and str(v).strip():
            labeled[nm] = str(v)
    us, um = labeled.get("UTM Source"), labeled.get("UTM Medium")
    uc, uco = labeled.get("UTM Campaign"), labeled.get("UTM Content")
    ad = ""
    if us or um:
        plat = {"fb": "Facebook", "ig": "Instagram", "google": "Google"}.get((us or "").lower(), us or "")
        ad = f"{(um or '').strip()} {plat} ad".strip()
        if uc: ad += f" — campaign '{uc}'" + (f" ({uco})" if uco else "")
    skip = {"UTM Source", "UTM Medium", "UTM Campaign", "UTM Content", "UTM Term", "Business Name"}
    quiz = [f"{k}: {v}" for k, v in labeled.items() if k not in skip]
    return {"source": c.get("source") or "", "ad": ad, "tags": c.get("tags") or [],
            "biz": labeled.get("Business Name", ""), "quiz": quiz,
            "added": (c.get("dateAdded") or "")[:10]}

def contact_summary(notes, last_summary, meta=None, convo=None):
    meta = meta or {}
    convo = convo or {}
    parts = []
    if convo.get("last_in"):
        parts.append(f"Their last message ({convo['last_in']}): "
                     f"{convo.get('last_in_body') or '(no text)'}"
                     + ("  [STILL UNANSWERED BY US]" if convo.get("unanswered") else ""))
    if meta.get("biz"):      parts.append(f"Business: {meta['biz']}")
    if meta.get("ad"):       parts.append(f"Came from: {meta['ad']}")
    elif meta.get("source"): parts.append(f"Source: {meta['source']}")
    if meta.get("added"):    parts.append(f"Came in (date): {meta['added']}")
    if meta.get("quiz"):     parts.append("Quiz answers — " + " | ".join(meta['quiz'][:10]))
    meta_str = "\n".join(parts)
    has_notes = notes and notes.strip() not in ("", "No notes on file.")
    if not has_notes and not meta_str:
        return "No info on file yet — treat as a fresh outreach."
    try:
        out = R.anthropic_json(SUMMARY_SYS,
              f"{meta_str}\nNotes history: {notes[:5000] if has_notes else '(none yet)'}\n"
              f"Last two-way contact: {last_summary or 'none'}", max_tokens=1500)
        s = (out or {}).get("summary")
        if s: return s
    except Exception:
        pass
    return (notes.split(" | ")[-1])[:280] if has_notes else (meta.get("ad") or meta.get("source") or "Fresh lead.")

def make_contact_blocks(contact):
    blocks      = []
    name        = contact['name']
    company     = contact.get('company', '')
    phone       = contact.get('phone', 'No phone on file')
    tz          = contact.get('tz', 'ET')
    notes       = contact.get('notes', 'No notes on file.')
    last_date   = contact.get('last_date')
    last_summary = contact.get('last_summary')

    rich_text = []
    if company:
        rich_text.append({"type": "text", "text": {"content": f"{company} · "}, "annotations": {"bold": True}})
    rich_text.append({"type": "text", "text": {"content": f"{name} · 📞 {phone} · {tz}"}, "annotations": {"bold": True}})
    blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": rich_text}})

    # Hidden-ish reference so the automatic note sync can map this block back to GHL.
    blocks.append(make_text_block(f"ref:{contact.get('contact_id', '')}", color="gray"))

    meta = contact.get('meta') or {}
    # AI summary — the at-a-glance line.
    blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [
        {"type": "text", "text": {"content": "🤖 Summary: "}, "annotations": {"bold": True}},
        {"type": "text", "text": {"content": contact_summary(notes, last_summary, meta, contact.get('convo'))}},
    ]}})
    convo = contact.get('convo') or {}
    if convo.get('unanswered'):
        blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [
            {"type": "text", "text": {"content": f"📬 They texted {convo['last_in']} and are STILL WAITING on us: "},
             "annotations": {"bold": True, "color": "red"}},
            {"type": "text", "text": {"content": (convo.get('last_in_body') or '')[:160]}},
        ]}})
    elif convo.get('last_in'):
        blocks.append(make_text_block(
            f"💬 Last two-way: them {convo['last_in']}: {(convo.get('last_in_body') or '')[:120]}",
            color="gray"))

    # Guaranteed source line — always shown when we know where the lead came from.
    src_bits = []
    if meta.get('ad'):       src_bits.append(meta['ad'])
    elif meta.get('source'): src_bits.append(meta['source'])
    if meta.get('added'):    src_bits.append(f"in {meta['added']}")
    if meta.get('tags'):     src_bits.append("tags: " + ", ".join(meta['tags'][:3]))
    blocks.append(make_text_block(
        ("📍 Source: " + " · ".join(src_bits)) if src_bits else "📍 Source: unknown / not tagged",
        color="gray"))

    # Full notes + history (and funnel/quiz answers) tucked in a collapsed toggle.
    last_str = f"{last_date} — {last_summary}" if last_date else "No two-way contact found."
    note_items = [n for n in (notes.split(" | ") if notes and notes != "No notes on file." else []) if n.strip()]
    toggle_children = [make_text_block(n[:1990]) for n in note_items] or [make_text_block("No notes on file.")]
    if meta.get('quiz'):
        toggle_children.append(make_text_block(
            ("🧾 Funnel/quiz: " + " | ".join(meta['quiz'][:12]))[:1990], color="gray"))
    toggle_children.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [
        {"type": "text", "text": {"content": "🕓 Last real contact: "}, "annotations": {"bold": True}},
        {"type": "text", "text": {"content": last_str}},
    ]}})
    blocks.append({"object": "block", "type": "toggle", "toggle": {
        "rich_text": [{"type": "text", "text": {"content": "📝 Notes & history"}}],
        "children": toggle_children,
    }})

    blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [
        {"type": "text", "text": {"content": "✍️ Your notes for today:"}, "annotations": {"bold": True}},
    ]}})
    blocks.append(make_text_block(""))
    return blocks

def archive_old_page():
    page_id_file = os.path.join(BASE_DIR, "notion_page_id.txt")
    try:
        with open(page_id_file) as f:
            old_id = f.read().strip()
        if old_id:
            requests.patch(f"https://api.notion.com/v1/pages/{old_id}",
                           headers=NOTION_HEADERS, json={"archived": True})
            log(f"Archived old page {old_id}")
    except Exception:
        pass

def create_notion_page(today_str_display, total, blocks):
    body = {
        "parent": {"page_id": HOME_PAGE_ID},
        "icon":   {"type": "emoji", "emoji": "📞"},
        "properties": {"title": {"title": [{"type": "text", "text": {"content": f"📞 Daily Call List — {today_str_display}"}}]}},
    }
    r       = HTTP.post("https://api.notion.com/v1/pages", headers=NOTION_HEADERS, json=body)
    page_id = r.json()['id']
    log(f"Created Notion page {page_id}")

    page_id_file = os.path.join(BASE_DIR, "notion_page_id.txt")
    with open(page_id_file, 'w') as f:
        f.write(page_id)

    for i in range(0, len(blocks), 100):
        requests.patch(f"https://api.notion.com/v1/blocks/{page_id}/children",
                       headers=NOTION_HEADERS, json={"children": blocks[i:i+100]})
    log(f"Appended {len(blocks)} blocks")
    return page_id

def send_email(page_id, today_str_display, total):
    if os.environ.get("RANK_NO_EMAIL"):
        log("Email suppressed (RANK_NO_EMAIL set)")
        return
    hidden_line = ""
    if HIDDEN_TODAY:
        items = " · ".join(f"{nm} ({why})" for nm, _co, why in HIDDEN_TODAY[:6])
        more = f" +{len(HIDDEN_TODAY) - 6} more" if len(HIDDEN_TODAY) > 6 else ""
        hidden_line = (f"<br><span style=\"font-size:12px;color:#b0a090;\">"
                       f"Hidden today: {items}{more}</span>")
    page_url = f"https://www.notion.so/{page_id.replace('-', '')}"
    subject  = f"📞 Your Call List is Ready — {today_str_display}"
    html = f"""
    <html><body style="margin:0;padding:0;background-color:#faf7f4;font-family:'Georgia',serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#faf7f4;padding:40px 20px;">
        <tr><td align="center">
          <table width="560" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.06);">
            <tr><td style="background-color:#f2ebe3;padding:36px 40px 28px 40px;text-align:center;">
              <p style="margin:0;font-size:28px;">📞</p>
              <h1 style="margin:10px 0 4px 0;font-size:22px;color:#5c4a3a;font-weight:normal;letter-spacing:0.5px;">Good morning, Santino</h1>
              <p style="margin:0;font-size:14px;color:#9c8575;">{today_str_display}</p>
            </td></tr>
            <tr><td style="padding:36px 40px 28px 40px;text-align:center;">
              <p style="margin:0 0 24px 0;font-size:16px;color:#7a6555;line-height:1.7;">
                Your call list for today is ready — {total} contacts.<br>
                East Coast contacts are at the top. Start there first.{hidden_line}
              </p>
              <a href="{page_url}" style="display:inline-block;background-color:#c9a98a;color:#ffffff;text-decoration:none;font-size:15px;padding:14px 36px;border-radius:30px;letter-spacing:0.5px;font-family:Georgia,serif;">
                View My Call List &rarr;
              </a>
              <p style="margin:32px 0 0 0;font-size:13px;color:#b0a090;line-height:1.7;">
                After your calls, add your notes in Notion, then tell Claude "sync my notes."
              </p>
            </td></tr>
            <tr><td style="background-color:#faf7f4;padding:20px 40px;text-align:center;border-top:1px solid #ede8e2;">
              <p style="margin:0;font-size:12px;color:#c4b8ac;">Restoration AI · Daily Workflow</p>
            </td></tr>
          </table>
        </td></tr>
      </table>
    </body></html>
    """
    payload = {
        "personalizations": [{"to": [{"email": MAIL_TO}]}],
        "from":    {"email": MAIL_FROM, "name": MAIL_FROM_NAME},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}],
        # Link the button straight to Notion — don't rewrite through SendGrid's
        # click-tracking domain (url4155.restorationai.io is not resolving in DNS).
        "tracking_settings": {
            "click_tracking": {"enable": False, "enable_text": False},
            "open_tracking":  {"enable": False},
        },
    }
    r = HTTP.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
        json=payload,
    )
    if r.status_code in (200, 201, 202):
        log(f"Email sent to {MAIL_TO} via SendGrid (status {r.status_code})")
    else:
        log(f"SendGrid send FAILED status {r.status_code}: {r.text[:300]}")

def mark_complete(today_str):
    run_file = os.path.join(BASE_DIR, "last_run_dates.json")
    try:
        with open(run_file) as f:
            data = json.load(f)
    except Exception:
        data = {}
    data['daily-call-list'] = today_str
    with open(run_file, 'w') as f:
        json.dump(data, f)
    log(f"Marked complete for {today_str}")

def suggestion_blocks(today_str_key):
    """Render the AI router's 'Suggested Moves' section (propose-only) at the top of
    the page. Reads router_suggestions.json; shows nothing if it's missing or stale."""
    sugg_file = os.path.join(BASE_DIR, "router_suggestions.json")
    try:
        data = json.load(open(sugg_file))
    except Exception:
        return []
    if data.get("date") != today_str_key:
        return []
    sugg = data.get("suggestions", [])
    if not sugg:
        return []
    PRI = {"high": "🔴", "medium": "🟡", "low": "🔵"}
    follow = [s for s in sugg if s.get("action") != "cooloff"]   # 🔴/🟡 — need a real decision
    cool   = [s for s in sugg if s.get("action") == "cooloff"]   # 🔵 — dead-air, bulk-park

    blocks = [make_divider(),
              make_heading(f"🔀 PIPELINE SUGGESTIONS — review, NOT calls ({len(sugg)})", level=1),
              make_text_block('These leads are in the WRONG stage and the AI suggests moving them — '
                              'this is housekeeping, not your call list. On the ones below write your '
                              'decision on the "✍️ Your call" line (approve · skip · "old client, drop him" · '
                              '"remove from list"); it applies automatically overnight.', color="gray")]
    for s in follow[:25]:
        head = f"{PRI.get(s.get('priority'),'')} {s.get('name','?')}"
        if s.get("company"): head += f" · {s['company']}"
        if s.get("value"):   head += f" · ${s['value']}"
        # marker FIRST — it cleanly delimits each suggestion so an empty box reads as empty
        blocks.append(make_text_block(f"move-ref:{s.get('opp_id','')}", color="gray"))
        blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [
            {"type": "text", "text": {"content": head}, "annotations": {"bold": True}}]}})
        blocks.append(make_text_block(
            f"{s.get('current_pipeline')} / {s.get('current_stage')}  →  Ready For Follow Up   ·   {s.get('reason','')}",
            color="gray"))
        if s.get("last_reply"):
            blocks.append(make_text_block(f"💬 Last reply — {s['last_reply']}", color="gray"))
        if s.get("notes"):
            blocks.append(make_text_block(f"📝 Notes: {s['notes']}", color="gray"))
        blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [
            {"type": "text", "text": {"content": "✍️ Your call: "}, "annotations": {"bold": True}}]}})
        blocks.append(make_text_block(""))

    # 🔵 cool-offs — collapsed toggle, but each has its OWN "Your call" box.
    if cool:
        CAP = 18  # Notion caps a block's children ~100; 18 cards x5 + intro stays under
        children = [make_text_block('The AI suggests parking these for 30 days. Under each, write your '
                    'call: "park" to cool off · "call today" to put them on today\'s call list · blank to '
                    'skip. Applies overnight (or say "apply moves").', color="gray")]
        for s in cool[:CAP]:
            head = f"🔵 {s.get('name','?')}"
            if s.get("company"): head += f" · {s['company']}"
            if s.get("value"):   head += f" · ${s['value']}"
            children.append(make_text_block(f"move-ref:{s.get('opp_id','')}", color="gray"))
            children.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [
                {"type": "text", "text": {"content": head}, "annotations": {"bold": True}}]}})
            children.append(make_text_block(
                f"{s.get('current_pipeline')} / {s.get('current_stage')}  ·  {s.get('reason','')}", color="gray"))
            children.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [
                {"type": "text", "text": {"content": "✍️ Your call: "}, "annotations": {"bold": True}}]}})
            children.append(make_text_block(""))
        if len(cool) > CAP:
            children.append(make_text_block(f'+{len(cool)-CAP} more — reply "park the rest" to cool them off.',
                                            color="gray"))
        blocks.append({"object": "block", "type": "toggle", "toggle": {
            "rich_text": [{"type": "text", "text": {"content":
                f"🔵 Cool-off suggestions ({len(cool)}) — expand to park or call each"}}],
            "children": children}})
    blocks.append(make_divider())
    return blocks

def needs_response_blocks(today_str_key):
    """Render the '📬 Needs a Response' section (unanswered inbound + drafted replies) atop the page."""
    try:
        data = json.load(open(os.path.join(BASE_DIR, "inbox_needs_response.json")))
    except Exception:
        return []
    items = data.get("items", [])
    if not items:
        return []
    blocks = [make_heading(f"📬 NEEDS A RESPONSE — {len(items)} left on read", level=1),
              make_text_block('Leads who messaged us and we haven\'t replied. A drafted reply is under each '
                              '— say "send to <name>" to send it (or edit first).', color="gray")]
    for it in items[:20]:
        head = f"📬 {it.get('name','?')} · {it.get('channel','')}"
        if it.get('inbound_date'): head += f" · since {it['inbound_date']}"
        blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [
            {"type": "text", "text": {"content": head}, "annotations": {"bold": True}}]}})
        blocks.append(make_text_block(f"💬 They said: {it.get('inbound_text','')[:400]}", color="gray"))
        draft = (f"[{it['subject']}] " if it.get('subject') else "") + (it.get('draft', '') or '')
        blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [
            {"type": "text", "text": {"content": "✏️ Drafted reply: "}, "annotations": {"bold": True}},
            {"type": "text", "text": {"content": draft[:1200]}}]}})
        blocks.append(make_text_block(f"send-ref:{it.get('contact_id','')}", color="gray"))
    blocks.append(make_divider())
    return blocks

def monica_activity_blocks():
    """Cross-feed from the client concierge (Supabase concierge_escalations,
    last 24h) so client-side events show up next to the sales list. Silent
    no-op when Supabase env is absent (e.g., bare-Mac runs)."""
    url = os.environ.get("SUPABASE_URL"); key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not (url and key):
        return []
    try:
        since = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
        r = HTTP.get(f"{url.rstrip('/')}/rest/v1/concierge_escalations",
                     params={"select": "created_at,company_name,reason",
                             "created_at": f"gte.{since}",
                             "order": "created_at.desc", "limit": "12"},
                     headers={"apikey": key, "Authorization": f"Bearer {key}"})
        rows = r.json() if r.status_code == 200 else []
    except Exception:
        return []
    out = []
    for row in rows:
        reason = (row.get("reason") or "").replace("\n", " ")
        if "deferred" in reason:      # informational noise, skip on the page
            continue
        out.append(make_text_block(
            f"{row.get('created_at','')[:16].replace('T',' ')} · "
            f"{row.get('company_name') or 'OPS'} — {reason[:160]}", color="gray"))
    return out[:8]


def build_blocks(results, today_str_display, total):
    blocks = []
    blocks.append(make_heading(f"📞 CALL TODAY — {total} to phone", level=1))
    blocks.append(make_text_block(
        "The people to actually call today (already in 'Ready For Follow Up'), East Coast first. "
        "Jot outcomes in each ✍️ box — they sync to GHL. Pipeline suggestions are further down.",
        color="gray"
    ))
    blocks.append(make_divider())
    for label in LABEL_ORDER:
        if label not in results: continue
        stages = results[label]
        n      = sum(len(v) for v in stages.values())
        icon   = SECTION_ICONS.get(label, "")
        blocks.append(make_heading(f"{icon} {label} · {n} contacts", level=2))
        for stage_name, contacts in stages.items():
            blocks.append(make_heading(stage_name, level=3))
            for contact in contacts:
                blocks.extend(make_contact_blocks(contact))
    blocks.append(make_divider())
    if HIDDEN_TODAY:
        blocks.append(make_heading(f"🙈 Hidden today ({len(HIDDEN_TODAY)}) — why they're not on the list", level=2))
        for nm, co, why in HIDDEN_TODAY[:25]:
            label_txt = f"{nm}" + (f" ({co})" if co else "") + f" — {why}"
            blocks.append(make_text_block(label_txt, color="gray"))
    monica = monica_activity_blocks()
    if monica:
        blocks.append(make_heading(f"🤖 Monica (client concierge) — last 24h", level=2))
        blocks.extend(monica)
    blocks.append(make_divider())
    blocks.append(make_text_block(
        'When you are done with your calls, tell Claude "sync my notes" and all updates will be pushed to GHL automatically.'
    ))
    blocks.append(make_text_block(
        'Note shortcuts: "no answer" → retry in 3 days · a date like "call July 5" → hidden until then · '
        '"remove from list" → dropped for good.',
        color="gray"
    ))
    return blocks

PERSIST_FILE = os.path.join(BASE_DIR, "persistent_page_id.txt")

def get_or_create_persistent_page(today_str_display):
    """One stable page reused forever. Returns its id, creating it once if needed."""
    try:
        pid = open(PERSIST_FILE).read().strip()
    except Exception:
        pid = ""
    if pid:
        r = HTTP.get(f"https://api.notion.com/v1/pages/{pid}", headers=NOTION_HEADERS)
        if r.status_code == 200 and not r.json().get("archived"):
            return pid
    body = {"parent": {"page_id": HOME_PAGE_ID}, "icon": {"type": "emoji", "emoji": "📞"},
            "properties": {"title": {"title": [{"type": "text",
                           "text": {"content": "📞 Daily Call List"}}]}}}
    pid = HTTP.post("https://api.notion.com/v1/pages", headers=NOTION_HEADERS, json=body).json()["id"]
    with open(PERSIST_FILE, "w") as f: f.write(pid)
    log(f"Created persistent page {pid}")
    return pid

def repaint_page(page_id, today_str_display, blocks):
    """Clear the persistent page and repaint it in place (stable URL)."""
    ids, cursor = [], None
    while True:
        url = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
        if cursor: url += f"&start_cursor={cursor}"
        r = HTTP.get(url, headers=NOTION_HEADERS)
        if r.status_code != 200: break
        d = r.json(); ids += [b["id"] for b in d.get("results", [])]
        if d.get("has_more"): cursor = d.get("next_cursor")
        else: break
    for bid in ids:
        HTTP.delete(f"https://api.notion.com/v1/blocks/{bid}", headers=NOTION_HEADERS)
    requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=NOTION_HEADERS,
                   json={"properties": {"title": {"title": [{"type": "text",
                         "text": {"content": f"📞 Daily Call List — {today_str_display}"}}]}}})
    for i in range(0, len(blocks), 100):
        requests.patch(f"https://api.notion.com/v1/blocks/{page_id}/children",
                       headers=NOTION_HEADERS, json={"children": blocks[i:i+100]})
    with open(os.path.join(BASE_DIR, "notion_page_id.txt"), "w") as f:
        f.write(page_id)
    log(f"Repainted persistent page {page_id} with {len(blocks)} blocks")

def rebuild_persistent(today):
    """Build suggestions + call list and repaint the stable page. Returns (page_id, total)."""
    today_str_key = str(today); disp = today.strftime("%B %-d, %Y")
    raw_results = pull_contacts()
    results     = filter_for_today(raw_results, today)
    total       = sum(len(c) for s in results.values() for c in s.values())
    blocks = (needs_response_blocks(today_str_key) + build_blocks(results, disp, total)
              + suggestion_blocks(today_str_key))
    pid = get_or_create_persistent_page(disp)
    repaint_page(pid, disp, blocks)
    return pid, total

def main():
    today             = date.today()
    today_str_key     = str(today)
    today_str_display = today.strftime("%B %-d, %Y")

    run_file = os.path.join(BASE_DIR, "last_run_dates.json")
    try:
        with open(run_file) as f:
            last_run = json.load(f)
    except Exception:
        last_run = {}
    if last_run.get('daily-call-list') == today_str_key:
        log("Already ran today. Exiting.")
        return

    log(f"=== Starting daily call list for {today_str_key} ===")
    raw_results = pull_contacts()
    results     = filter_for_today(raw_results, today)
    total       = sum(len(c) for s in results.values() for c in s.values())
    log(f"{total} contacts scheduled for today ({today.strftime('%A')})")

    if total == 0:
        log("No contacts scheduled for today. Exiting without creating a page.")
        mark_complete(today_str_key)
        return

    blocks  = build_blocks(results, today_str_display, total) + suggestion_blocks(today_str_key)
    archive_old_page()
    page_id = create_notion_page(today_str_display, total, blocks)
    send_email(page_id, today_str_display, total)
    mark_complete(today_str_key)
    log("=== Done ===")

if __name__ == "__main__":
    main()
