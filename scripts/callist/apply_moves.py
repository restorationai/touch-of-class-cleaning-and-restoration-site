#!/usr/bin/env python3
"""
Restoration AI — Apply Moves  (executes YOUR written decisions, not the AI's guesses)

Reads today's Notion call-list page, finds the "🔀 Suggested Moves" section, and for
every suggestion where YOU typed something on the "✍️ Your call:" line, interprets
your note (via Claude) and makes the move in GHL:
   approve   -> do the move the router suggested
   follow_up -> move to that pipeline's "Ready For Follow Up"
   cooloff   -> move to Re-Igniting "One Month Reset Period"
   lost/drop -> mark the opportunity lost (former client, not interested, etc.)
   remove    -> post a "remove from list" note (drops from the call list, keeps the deal)
   stay      -> do nothing (blank or unclear notes are ALWAYS left alone)

Blank boxes are never touched. Idempotent via applied_moves.json. Safe to re-run.
Run standalone with --dry-run to preview. Called automatically by the 6pm sync job.
"""
import os, re, sys, json, hashlib, argparse, requests
from _http import HTTP
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auto_router as R   # reuse GHL + Anthropic helpers (no side effects on import)

BASE_DIR    = os.environ.get("RAI_BASE") or os.path.expanduser("~/restoration-ai")
LOG_FILE    = os.path.join(BASE_DIR, "apply_moves.log")
PAGE_FILE   = os.path.join(BASE_DIR, "notion_page_id.txt")
SUGG_FILE   = os.path.join(BASE_DIR, "router_suggestions.json")
APPLIED_FILE= os.path.join(BASE_DIR, "applied_moves.json")

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"; print(line)
    with open(LOG_FILE, "a") as f: f.write(line + "\n")

def notion_token():
    """Single source of truth: auto_daily_call_list.NOTION_TOKEN (env first, then
    the embedded literal).

    This used to scrape the token out of `{BASE_DIR}/workflows/auto_daily_call_list.py`
    on disk — a path that only existed on Santino's Mac. On Railway it returned ""
    and every Notion read 401'd, so NO written "✍️ Your call" decision was ever
    applied; the morning repaint then wiped them (found 2026-08-04).
    """
    from auto_daily_call_list import NOTION_TOKEN as _tok
    return _tok
NOTION_HEADERS = {"Authorization": f"Bearer {notion_token()}", "Notion-Version": "2022-06-28",
                  "Content-Type": "application/json"}

def block_text(b):
    t = b.get("type", ""); node = b.get(t, {})
    rts = node.get("rich_text", []) if isinstance(node, dict) else []
    return "".join(r.get("plain_text", "") for r in rts)

def get_children(page_id):
    def fetch(pid):
        out, cursor = [], None
        while True:
            url = f"https://api.notion.com/v1/blocks/{pid}/children?page_size=100"
            if cursor: url += f"&start_cursor={cursor}"
            r = HTTP.get(url, headers=NOTION_HEADERS)
            if r.status_code != 200: break
            d = r.json(); out += d.get("results", [])
            if d.get("has_more"): cursor = d.get("next_cursor")
            else: break
        return out
    blocks = []
    for b in fetch(page_id):
        blocks.append(b)
        # cool-off suggestion cards live INSIDE a collapsed toggle — pull them up so
        # their move-ref + "Your call" boxes get read too.
        if b.get("type") == "toggle" and b.get("has_children"):
            blocks += fetch(b["id"])
    return blocks

def parse_directives(blocks):
    """Return {opp_id: directive_text} for every suggestion with a non-empty note."""
    out, cur, collecting = {}, None, False
    for b in blocks:
        typ = b.get("type", ""); txt = block_text(b); s = txt.strip()
        if s.startswith("move-ref:"):
            if cur and cur["parts"]:
                out[cur["opp"]] = "\n".join(cur["parts"]).strip()
            cur = {"opp": s[len("move-ref:"):].strip(), "parts": []}; collecting = False
            continue
        if cur is None:
            continue
        if "Your call:" in txt:
            collecting = True
            after = txt.split("Your call:", 1)[-1].strip()
            if after: cur["parts"].append(after)
            continue
        if typ.startswith("heading") or typ in ("divider", "toggle"):
            if cur["parts"]: out[cur["opp"]] = "\n".join(cur["parts"]).strip()
            cur, collecting = None, False
            continue
        if collecting and s:
            cur["parts"].append(s)
    if cur and cur["parts"]:
        out[cur["opp"]] = "\n".join(cur["parts"]).strip()
    return {k: v for k, v in out.items() if v}

INTERP_SYSTEM = (
 "You convert a salesperson's short freeform note about a sales lead into exactly ONE action. "
 "Options: approve (do the move the system already suggested); follow_up ('call today', 'call "
 "them', 'put on the call list', 'keep working', 'don't cool off' => queue them for a call now); "
 "cooloff ('park', 'cool off', 'rest them' => one-month break); lost (drop the deal — former "
 "client, not interested, dead, 'things went south'); remove (take off the call list but keep the "
 "deal); stay (do nothing — note is unclear or a question). Be conservative: if unsure, choose "
 'stay. Reply ONLY JSON: {"action":"approve|follow_up|cooloff|lost|remove|stay","reason":"short"}')

def interpret(directive, suggested_action, suggested_target):
    user = (f'System already suggested: {suggested_action} -> {suggested_target}.\n'
            f'Salesperson wrote: "{directive}"\nPick the single action.')
    out = R.anthropic_json(INTERP_SYSTEM, user)
    act = (out or {}).get("action")
    if act not in {"approve", "follow_up", "cooloff", "lost", "remove", "stay"}:
        return {"action": "stay", "reason": "unclear note — left alone"}
    return out

# ---- GHL execution ----
def move_stage(opp_id, pipeline_id, stage_id):
    r = HTTP.put(f"{R.GHL_BASE}/opportunities/{opp_id}", headers=R.GHL_HEADERS,
                     json={"pipelineId": pipeline_id, "pipelineStageId": stage_id, "status": "open"})
    return r.status_code == 200

def mark_lost(opp_id):
    r = HTTP.put(f"{R.GHL_BASE}/opportunities/{opp_id}/status", headers=R.GHL_HEADERS,
                     json={"status": "lost"})
    return r.status_code in (200, 201)

def post_remove_note(contact_id):
    r = HTTP.post(f"{R.GHL_BASE}/contacts/{contact_id}/notes", headers=R.GHL_HEADERS,
                      json={"body": "remove from list (via daily call-list directive)"})
    return r.status_code in (200, 201)

def run(dry_run=False):
    today = date.today()
    log(f"=== Apply Moves {today} ({'DRY RUN' if dry_run else 'live'}) ===")
    try:
        page_id = open(PAGE_FILE).read().strip()
    except Exception:
        page_id = ""
    if not page_id:
        log("No current page id. Nothing to apply."); return
    try:
        sugg = {s["opp_id"]: s for s in json.load(open(SUGG_FILE)).get("suggestions", [])}
    except Exception:
        sugg = {}
    directives = parse_directives(get_children(page_id))
    log(f"Found {len(directives)} suggestion(s) with your notes written in")
    if not directives:
        return

    pipes = R.get_pipelines()
    reignite_pid = R.PIPELINES[R.COOLOFF_PIPELINE]
    cooloff_stage = pipes.get(reignite_pid, {}).get("name_to_id", {}).get(R.COOLOFF_STAGE_NAME)

    applied = {}
    try: applied = json.load(open(APPLIED_FILE))
    except Exception: pass
    done = set(applied.get(page_id, []))

    counts = {"moved": 0, "lost": 0, "removed": 0, "stay": 0, "skip_done": 0, "fail": 0}
    for opp_id, directive in directives.items():
        s = sugg.get(opp_id, {})
        sig = hashlib.md5((opp_id + "|" + directive).encode()).hexdigest()[:10]
        if sig in done:
            counts["skip_done"] += 1; continue
        decision = interpret(directive, s.get("action", "?"), s.get("target_stage", "?"))
        act = decision["action"]
        name = s.get("name", opp_id)
        label = s.get("current_pipeline")
        pid = R.PIPELINES.get(label)

        # resolve concrete action
        if act == "approve":
            act = s.get("action", "stay")  # the router's own suggestion (follow_up / cooloff)

        plan = None
        if act == "follow_up" and pid:
            plan = ("move", pid, R.FOLLOWUP_STAGE.get(label))
        elif act == "cooloff" and cooloff_stage:
            plan = ("move", reignite_pid, cooloff_stage)
        elif act == "lost":
            plan = ("lost",)
        elif act == "remove" and s.get("contact_id"):
            plan = ("remove", s["contact_id"])
        else:
            plan = ("stay",)

        log(f"  {name}: you wrote \"{directive[:60]}\" -> {act} ({decision.get('reason','')})")
        if plan[0] == "stay":
            counts["stay"] += 1; done.add(sig); continue
        if dry_run:
            continue
        ok = False
        if plan[0] == "move" and plan[2]:
            ok = move_stage(opp_id, plan[1], plan[2]); counts["moved"] += int(ok)
        elif plan[0] == "lost":
            ok = mark_lost(opp_id); counts["lost"] += int(ok)
        elif plan[0] == "remove":
            ok = post_remove_note(plan[1]); counts["removed"] += int(ok)
        if ok:
            done.add(sig)
        else:
            counts["fail"] += 1; log(f"    ! FAILED to apply for {name}")

    if not dry_run:
        applied[page_id] = sorted(done)
        json.dump(applied, open(APPLIED_FILE, "w"))
    log(f"Done. {counts}")
    return counts

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(dry_run=a.dry_run)
