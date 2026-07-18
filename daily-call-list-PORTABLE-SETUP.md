# RESTORATION AI — DAILY CALL LIST + AUTO NOTE-SYNC (PORTABLE SETUP)

Paste everything below the line into a fresh Claude Code session on the target Mac/account.
Claude will recreate the whole system: the 9am daily call-list email + the 6pm automatic
note-sync back to GHL, both on a 7-day macOS launchd schedule.

> **Requirements:** macOS (uses launchd), Python 3, internet. The Mac must be awake at
> 9am & 6pm local for the jobs to fire on time (if asleep, launchd runs them at next wake).

---

## ⚠️ BEFORE YOU RUN — TWO THINGS YOU MUST CUSTOMIZE

**1. `HOME_PAGE_ID` (required).** The daily pages are created as children of one Notion
"home" page. That home page must be (a) connected to the Notion integration whose token is
below, AND (b) viewable by the people who will open the email link. To get it:
   - In Notion, logged in as the account that should OWN this list, create a page (ideally
     inside a Teamspace everyone is in) named e.g. `📞 Daily Call List`.
   - Open it → **•••** (top-right) → **Connections** → **+ Add connections** → search the
     integration name (**"Team Ops Framework"** for the existing token) → confirm.
   - Copy the page ID from its URL: the 32 hex chars after the last `/` and before `?`
     (e.g. `notion.so/My-Page-388d279c0699...` → `388d279c-0699-...`). Put it in `HOME_PAGE_ID`.

**2. Notion token (`NOTION_TOKEN`).** The token embedded below belongs to the
**"Restoration AI 💧"** workspace (integration "Team Ops Framework").
   - **Same Notion workspace?** Keep the token as-is; just set `HOME_PAGE_ID` per step 1.
   - **Different Notion workspace?** Create a new internal integration in that workspace
     (notion.so → Settings → Connections → *Develop or manage integrations* → New integration),
     copy its Internal Integration Secret (`ntn_…`), and replace `NOTION_TOKEN` everywhere.

Optional: `MAIL_TO` (who receives the email, currently `contact@getrestorationai.com`),
`MAIL_FROM` (must be on a SendGrid domain-authenticated domain — currently
`contact@restorationai.io`), and the "Good morning, Santino" greeting in the email HTML.

---

## CREDENTIALS (already embedded in the files below)

| What | Value |
|---|---|
| GHL API key | `pit-c75a84bf-6d23-4a8a-a1ff-a88054b0e1bc` |
| GHL Location ID | `Tx5eKisj3Xluq1SeZKe3` |
| Notion token | `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` (workspace "Restoration AI 💧") |
| SendGrid key | embedded in `auto_daily_call_list.py` (domain-auth: restorationai.io) |
| Pipelines/stages | Sales / Secured Clients / Re-Igniting (in the scripts) |

---

## STEP 1 — Directories + dependency

```bash
mkdir -p ~/restoration-ai/workflows
mkdir -p ~/.claude/scheduled-tasks/daily-call-list
pip3 install requests --user --quiet || python3 -c "import requests"
```

## STEP 2 — Set up the Notion home page

Do the two customization steps above. You will paste the resulting `HOME_PAGE_ID` into the
script in Step 3 (replace `REPLACE_WITH_YOUR_PAGE_ID`).

## STEP 3 — Write `~/restoration-ai/workflows/auto_daily_call_list.py`

Write this file EXACTLY. Replace `REPLACE_WITH_YOUR_PAGE_ID` with your page ID from Step 2.

```python
#!/usr/bin/env python3
import os, json, re, requests
from datetime import date, datetime, timedelta

BASE_DIR = os.path.expanduser("~/restoration-ai")
LOG_FILE = os.path.join(BASE_DIR, "auto_call_list.log")

def log(msg):
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# --- CONSTANTS ---
GHL_API_KEY     = "pit-c75a84bf-6d23-4a8a-a1ff-a88054b0e1bc"
GHL_LOCATION_ID = "Tx5eKisj3Xluq1SeZKe3"
GHL_BASE_URL    = "https://services.leadconnectorhq.com"
GHL_HEADERS     = {
    "Authorization": f"Bearer {GHL_API_KEY}",
    "Version":       "2021-07-28",
    "Content-Type":  "application/json",
}

NOTION_TOKEN   = "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"
HOME_PAGE_ID   = "REPLACE_WITH_YOUR_PAGE_ID"
NOTION_HEADERS = {
    "Authorization":  f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type":   "application/json",
}

# Email via SendGrid (sender domain must be SendGrid domain-authenticated).
SENDGRID_API_KEY = "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"
MAIL_FROM        = "contact@restorationai.io"
MAIL_FROM_NAME   = "Restoration AI"
MAIL_TO          = "contact@getrestorationai.com"

CALL_STAGES = [
    {"pipeline_id": "hPnHBxO63YMecyG219V5", "stage_id": "9fb3928a-33e3-4592-a080-56b3f353e56b", "label": "Sales",           "stage_name": "Ready For Follow Up"},
    {"pipeline_id": "OP4aWjh91AfikmEYKDHk", "stage_id": "892dfc0e-cec3-4b43-8a6e-0805348ee723", "label": "Secured Clients", "stage_name": "Follow Up Ready"},
    {"pipeline_id": "KRokx3RqJjNzUg8YCbWk", "stage_id": "ce155700-eb61-4d8b-899a-55baaa7d9a6e", "label": "Re-Igniting",     "stage_name": "Ready For Follow Up"},
]
SECTION_ICONS = {"Sales": "🤝", "Secured Clients": "✅", "Re-Igniting": "🔥"}
LABEL_ORDER   = ["Sales", "Secured Clients", "Re-Igniting"]

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
                    target = date(today.year + 1, month_num, day)
                return target
            except ValueError:
                pass
    if 'tomorrow' in body and note_date_str:
        try:
            return date.fromisoformat(note_date_str) + timedelta(days=1)
        except ValueError:
            pass
    for i, day_name in enumerate(WEEKDAYS):
        if re.search(rf'\b{day_name}\b', body) and note_date_str:
            try:
                note_date = date.fromisoformat(note_date_str)
                return next_weekday_on_or_after(note_date + timedelta(days=1), i)
            except ValueError:
                pass
    return None

def should_call_today(contact, today):
    note_body = contact.get('latest_note_body', '')
    note_date  = contact.get('latest_note_date', '')
    # Daily full list: include every open contact every day. The only exception
    # is a contact explicitly pushed to a FUTURE date — hidden until that date.
    if not note_body:
        return True
    target = parse_target_date(note_body, note_date, today)
    if target is None:       return True
    if target == today:      return True
    if target < today:       return True
    return False

def filter_for_today(results, today):
    filtered = {}
    for label, stages in results.items():
        filtered_stages = {}
        for stage_name, contacts in stages.items():
            kept = [c for c in contacts if should_call_today(c, today)]
            if kept:
                filtered_stages[stage_name] = kept
        if filtered_stages:
            filtered[label] = filtered_stages
    return filtered

def get_opps(pipeline_id, stage_id):
    params = {'location_id': GHL_LOCATION_ID, 'pipeline_id': pipeline_id, 'status': 'open', 'limit': 50}
    if stage_id: params['pipeline_stage_id'] = stage_id
    r = requests.get(f'{GHL_BASE_URL}/opportunities/search', headers=GHL_HEADERS, params=params)
    return r.json().get('opportunities', [])

def get_notes(contact_id):
    r = requests.get(f'{GHL_BASE_URL}/contacts/{contact_id}/notes', headers=GHL_HEADERS)
    return r.json().get('notes', []) if r.status_code == 200 else []

def get_last_contact(contact_id):
    r = requests.get(f'{GHL_BASE_URL}/conversations/search', headers=GHL_HEADERS,
                     params={'locationId': GHL_LOCATION_ID, 'contactId': contact_id})
    if r.status_code != 200: return None, None
    convos = r.json().get('conversations', [])
    if not convos: return None, None
    mr = requests.get(f'{GHL_BASE_URL}/conversations/{convos[0]["id"]}/messages', headers=GHL_HEADERS)
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

    blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [
        {"type": "text", "text": {"content": "📝 Notes: "}, "annotations": {"bold": True}},
        {"type": "text", "text": {"content": notes}},
    ]}})

    last_str = f"{last_date} — {last_summary}" if last_date else "No two-way contact found."
    blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [
        {"type": "text", "text": {"content": "🕓 Last real contact: "}, "annotations": {"bold": True}},
        {"type": "text", "text": {"content": last_str}},
    ]}})

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
    r       = requests.post("https://api.notion.com/v1/pages", headers=NOTION_HEADERS, json=body)
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
                East Coast contacts are at the top. Start there first.
              </p>
              <a href="{page_url}" style="display:inline-block;background-color:#c9a98a;color:#ffffff;text-decoration:none;font-size:15px;padding:14px 36px;border-radius:30px;letter-spacing:0.5px;font-family:Georgia,serif;">
                View My Call List &rarr;
              </a>
              <p style="margin:32px 0 0 0;font-size:13px;color:#b0a090;line-height:1.7;">
                After your calls, add your notes in Notion. They sync to GHL automatically at 6pm.
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
        # Link the button straight to Notion — do not rewrite through SendGrid click tracking.
        "tracking_settings": {
            "click_tracking": {"enable": False, "enable_text": False},
            "open_tracking":  {"enable": False},
        },
    }
    r = requests.post(
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

def build_blocks(results, today_str_display, total):
    blocks = []
    blocks.append(make_text_block(
        "Refreshes every morning at 9am PT · Open status contacts only · Sorted East Coast first",
        color="gray"
    ))
    blocks.append(make_divider())
    blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [
        {"type": "text", "text": {"content": f"{total} people to call today"}, "annotations": {"bold": True}}
    ]}})
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
    blocks.append(make_text_block(
        'Add your notes under each contact. They sync to GHL automatically at 6pm (or say "sync my notes").'
    ))
    return blocks

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

    blocks  = build_blocks(results, today_str_display, total)
    archive_old_page()
    page_id = create_notion_page(today_str_display, total, blocks)
    send_email(page_id, today_str_display, total)
    mark_complete(today_str_key)
    log("=== Done ===")

if __name__ == "__main__":
    main()
```

## STEP 4 — Write `~/restoration-ai/workflows/auto_sync_notes.py`

```python
#!/usr/bin/env python3
"""
Automatic end-of-day note sync for the Restoration AI daily call list.
Reads TODAY's Notion call-list page, pulls the text typed under
"✍️ Your notes for today:" for every contact, and POSTs real notes back to
that contact's GHL notes. Idempotent; never changes pipeline stages.
"""
import os, re, json, requests
from datetime import date, datetime

BASE_DIR  = os.path.expanduser("~/restoration-ai")
LOG_FILE  = os.path.join(BASE_DIR, "auto_sync_notes.log")
PAGE_FILE = os.path.join(BASE_DIR, "notion_page_id.txt")
SYNC_FILE = os.path.join(BASE_DIR, "synced_notes.json")

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

GHL_API_KEY     = "pit-c75a84bf-6d23-4a8a-a1ff-a88054b0e1bc"
GHL_LOCATION_ID = "Tx5eKisj3Xluq1SeZKe3"
GHL_BASE_URL    = "https://services.leadconnectorhq.com"
GHL_HEADERS     = {
    "Authorization": f"Bearer {GHL_API_KEY}",
    "Version":       "2021-07-28",
    "Content-Type":  "application/json",
}

def _notion_token():
    # Reuse the token embedded in the daily-call-list script (single source of truth).
    try:
        src = open(os.path.join(BASE_DIR, "workflows", "auto_daily_call_list.py"), encoding="utf-8").read()
        m = re.search(r'NOTION_TOKEN\s*=\s*"(ntn_[A-Za-z0-9]+)"', src)
        if m:
            return m.group(1)
    except Exception:
        pass
    return ""

NOTION_TOKEN   = _notion_token()
NOTION_HEADERS = {
    "Authorization":  f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type":   "application/json",
}

CALL_STAGES = [
    {"pipeline_id": "hPnHBxO63YMecyG219V5", "stage_id": "9fb3928a-33e3-4592-a080-56b3f353e56b"},
    {"pipeline_id": "OP4aWjh91AfikmEYKDHk", "stage_id": "892dfc0e-cec3-4b43-8a6e-0805348ee723"},
    {"pipeline_id": "KRokx3RqJjNzUg8YCbWk", "stage_id": "ce155700-eb61-4d8b-899a-55baaa7d9a6e"},
]

NO_ACTION = {"", "noaction", "noactionneeded", "none", "na", "nothing", "nonotes",
             "noactiontoday", "nothingtoday", "skip", "noupdate", "noupdates"}

def block_plain_text(b):
    t = b.get("type", "")
    node = b.get(t, {})
    rts = node.get("rich_text", []) if isinstance(node, dict) else []
    return "".join(rt.get("plain_text", "") for rt in rts)

def get_page(page_id):
    r = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=NOTION_HEADERS)
    return r.json() if r.status_code == 200 else None

def get_all_children(page_id):
    blocks, cursor = [], None
    while True:
        url = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        r = requests.get(url, headers=NOTION_HEADERS)
        if r.status_code != 200:
            break
        d = r.json()
        blocks.extend(d.get("results", []))
        if d.get("has_more"):
            cursor = d.get("next_cursor")
        else:
            break
    return blocks

def page_title(page):
    for v in (page or {}).get("properties", {}).values():
        if v.get("type") == "title":
            return "".join(x.get("plain_text", "") for x in v["title"])
    return ""

def normalize_phone(s):
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else digits

def build_phone_map():
    pmap = {}
    for st in CALL_STAGES:
        params = {"location_id": GHL_LOCATION_ID, "pipeline_id": st["pipeline_id"],
                  "pipeline_stage_id": st["stage_id"], "status": "open", "limit": 50}
        r = requests.get(f"{GHL_BASE_URL}/opportunities/search", headers=GHL_HEADERS, params=params)
        for opp in r.json().get("opportunities", []):
            c = opp.get("contact", {})
            ph, cid = normalize_phone(c.get("phone") or ""), c.get("id")
            if ph and cid:
                pmap[ph] = cid
    return pmap

def post_note(contact_id, body):
    r = requests.post(f"{GHL_BASE_URL}/contacts/{contact_id}/notes",
                      headers=GHL_HEADERS, json={"body": body})
    return r.status_code in (200, 201)

def extract_phone_from_header(txt):
    if "📞" not in txt:
        return ""
    after = txt.split("📞", 1)[1]
    after = after.split("·")[0]
    return normalize_phone(after)

def parse_contacts(blocks):
    contacts, cur = [], None
    for b in blocks:
        typ = b.get("type", "")
        txt = block_plain_text(b)
        stripped = txt.strip()
        if "📞" in txt:
            if cur:
                contacts.append(cur)
            cur = {"cid": None, "phone": extract_phone_from_header(txt),
                   "note_parts": [], "collecting": False}
            continue
        if cur is None:
            continue
        if stripped.startswith("ref:"):
            cur["cid"] = stripped[4:].strip()
            continue
        if typ.startswith("heading") or typ == "divider":
            contacts.append(cur); cur = None
            continue
        if "Your notes for today" in txt:
            cur["collecting"] = True
            after = txt.split("Your notes for today:", 1)[-1].strip()
            if after:
                cur["note_parts"].append(after)
            continue
        if cur["collecting"] and stripped:
            cur["note_parts"].append(stripped)
    if cur:
        contacts.append(cur)
    out = []
    for c in contacts:
        note = "\n".join(c["note_parts"]).strip()
        out.append({"cid": c["cid"], "phone": c["phone"], "note": note})
    return out

def is_no_action(note):
    collapsed = re.sub(r"[^a-z]", "", note.lower())
    return collapsed in NO_ACTION

def load_synced():
    try:
        return json.load(open(SYNC_FILE))
    except Exception:
        return {}

def save_synced(data):
    json.dump(data, open(SYNC_FILE, "w"))

def main():
    today = date.today()
    today_display = today.strftime("%B %-d, %Y")
    log(f"=== Auto note sync for {today} ===")

    try:
        page_id = open(PAGE_FILE).read().strip()
    except Exception:
        page_id = ""
    if not page_id:
        log("No current page id on file. Nothing to sync. Exiting."); return

    page = get_page(page_id)
    if not page:
        log(f"Could not fetch page {page_id}. Exiting."); return
    if page.get("archived"):
        log("Current page is archived (no list created today). Exiting."); return
    title = page_title(page)
    if today_display not in title:
        log(f"Page title '{title}' is not today's list. Exiting without syncing."); return

    blocks   = get_all_children(page_id)
    contacts = parse_contacts(blocks)
    log(f"Parsed {len(contacts)} contact blocks from the page")

    need_fallback = any(not c["cid"] and c["phone"] for c in contacts)
    pmap = build_phone_map() if need_fallback else {}
    if need_fallback:
        log(f"Built phone fallback map ({len(pmap)} contacts) for blocks missing ref ids")

    synced = load_synced()
    already = set(synced.get(page_id, []))

    posted = skipped_noaction = skipped_empty = skipped_done = unresolved = failed = 0
    for c in contacts:
        cid = c["cid"] or pmap.get(c["phone"])
        note = c["note"]
        if not note:
            skipped_empty += 1; continue
        if is_no_action(note):
            skipped_noaction += 1; continue
        if not cid:
            unresolved += 1
            log(f"  ! Could not resolve a contact_id (phone={c['phone']}) — note left unsynced"); continue
        if cid in already:
            skipped_done += 1; continue
        if post_note(cid, note):
            posted += 1; already.add(cid)
            log(f"  ✓ Posted note to contact {cid} ({len(note)} chars)")
        else:
            failed += 1
            log(f"  ✗ FAILED to post note to contact {cid}")

    synced[page_id] = sorted(already)
    save_synced(synced)
    log(f"Done. posted={posted} already_synced={skipped_done} empty={skipped_empty} "
        f"no_action={skipped_noaction} unresolved={unresolved} failed={failed}")

if __name__ == "__main__":
    main()
```

## STEP 5 — Write the manual companion skill `~/.claude/scheduled-tasks/daily-call-list/SKILL.md`

Substitute your `HOME_PAGE_ID` where indicated.

```markdown
---
name: daily-call-list
description: Restoration AI daily call list — pull from GHL, create Notion page, sync notes back to GHL.
---

You are running the daily call list automation. Follow these rules exactly.

GHL CREDENTIALS:
- API Key: pit-c75a84bf-6d23-4a8a-a1ff-a88054b0e1bc
- Location ID: Tx5eKisj3Xluq1SeZKe3
- Base URL: https://services.leadconnectorhq.com
- Headers: Authorization: Bearer {API_KEY}, Version: 2021-07-28

NOTION:
- Use the Notion REST API directly with the token in ~/restoration-ai/workflows/auto_daily_call_list.py (NOTION_TOKEN).
- API base: https://api.notion.com/v1, header Notion-Version: 2022-06-28
- HOME_PAGE_ID: REPLACE_WITH_YOUR_PAGE_ID
- Today's page ID lives at: ~/restoration-ai/notion_page_id.txt

CALL STAGES (only these three, only open opportunities):
- Sales: pipeline hPnHBxO63YMecyG219V5, stage 9fb3928a-33e3-4592-a080-56b3f353e56b
- Secured Clients: pipeline OP4aWjh91AfikmEYKDHk, stage 892dfc0e-cec3-4b43-8a6e-0805348ee723
- Re-Igniting: pipeline KRokx3RqJjNzUg8YCbWk, stage ce155700-eb61-4d8b-899a-55baaa7d9a6e

HARD RULES:
- Only pull opportunities with status = open.
- Sort within each section: ET, CT, MT, PT (default ET).
- Ignore any note starting with "--------- AI Call with:".

SCHEDULING — daily full list (runs every day, 9am local):
- Include EVERY open contact every day, EXCEPT contacts whose latest note pushes them to a FUTURE date (hidden until that date).

"sync my notes":
1. Read today's page (ID in ~/restoration-ai/notion_page_id.txt).
2. For each contact, read text under "✍️ Your notes for today:".
3. Skip empty / "no action needed" (any variation).
4. POST real notes to https://services.leadconnectorhq.com/contacts/{contact_id}/notes with {"body":"..."}, exactly as written.
5. Never change pipeline stages.

IDEMPOTENCY: an automatic sync runs daily at 6pm (job io.restorationai.sync-notes). Both manual + auto record posts in ~/restoration-ai/synced_notes.json {page_id:[contact_id,...]}. Skip contacts already listed under the current page_id; append each one you post.

NOTE: the 9am email is sent by ~/restoration-ai/workflows/auto_daily_call_list.py via SendGrid. Do NOT send email when running this skill manually.
```

## STEP 6 — Write both launchd jobs (9am list + 6pm sync, every day)

Run this exactly — it injects your real home directory automatically:

```bash
cat > ~/Library/LaunchAgents/io.restorationai.daily-call-list.plist <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>io.restorationai.daily-call-list</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string>
    <string>$HOME/restoration-ai/workflows/auto_daily_call_list.py</string>
  </array>
  <key>StartCalendarInterval</key><array>
    <dict><key>Weekday</key><integer>0</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>6</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
  </array>
  <key>StandardOutPath</key><string>$HOME/restoration-ai/auto_call_list.log</string>
  <key>StandardErrorPath</key><string>$HOME/restoration-ai/auto_call_list_error.log</string>
  <key>RunAtLoad</key><false/>
</dict></plist>
EOF

cat > ~/Library/LaunchAgents/io.restorationai.sync-notes.plist <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>io.restorationai.sync-notes</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string>
    <string>$HOME/restoration-ai/workflows/auto_sync_notes.py</string>
  </array>
  <key>StartCalendarInterval</key><array>
    <dict><key>Weekday</key><integer>0</integer><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>6</integer><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
  </array>
  <key>StandardOutPath</key><string>$HOME/restoration-ai/auto_sync_notes.log</string>
  <key>StandardErrorPath</key><string>$HOME/restoration-ai/auto_sync_notes_error.log</string>
  <key>RunAtLoad</key><false/>
</dict></plist>
EOF
echo "plists written"
```

## STEP 7 — State files

```bash
echo '{}' > ~/restoration-ai/last_run_dates.json
echo '{}' > ~/restoration-ai/synced_notes.json
: > ~/restoration-ai/notion_page_id.txt
```

## STEP 8 — Load both jobs

```bash
for J in daily-call-list sync-notes; do
  P=~/Library/LaunchAgents/io.restorationai.$J.plist
  plutil -lint "$P"
  launchctl unload "$P" 2>/dev/null || true
  launchctl load -w "$P"
done
launchctl list | grep io.restorationai
```

You should see both jobs with exit status `0`.

## STEP 9 — Verify end to end

Ask Claude to: (a) confirm `requests` imports and both scripts compile; (b) confirm the Notion
token reaches the right workspace (`GET https://api.notion.com/v1/users/me`); (c) confirm the
`HOME_PAGE_ID` page is reachable by the integration; (d) run
`python3 ~/restoration-ai/workflows/auto_daily_call_list.py` once to send today's list and
verify the email lands + the Notion link opens for the intended viewers.

---

## HOW IT RUNS (summary)

- **9:00am local, every day** → `auto_daily_call_list.py`: pulls open opps from 3 GHL stages,
  builds a Notion page under `HOME_PAGE_ID`, emails the link via SendGrid (tracking off).
- **6:00pm local, every day** → `auto_sync_notes.py`: reads today's page, posts each contact's
  "✍️ Your notes for today:" text to GHL, idempotently. Never changes stages.
- Each contact block carries a gray `ref:{contact_id}` line so the sync maps notes to the right
  GHL contact (phone-match fallback if missing).
- State: `last_run_dates.json`, `notion_page_id.txt`, `synced_notes.json` in `~/restoration-ai/`.
- Logs: `auto_call_list.log`, `auto_sync_notes.log` in `~/restoration-ai/`.
