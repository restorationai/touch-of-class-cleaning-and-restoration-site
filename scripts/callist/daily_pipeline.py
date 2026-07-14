#!/usr/bin/env python3
"""
Restoration AI — Daily Pipeline (single 8am job).

Replaces the old 3-job setup (router + call-list + 6pm sync/apply). Runs ONE stable
Notion page, repainted in place each morning. Sequence:

  1. Get the persistent page.
  2. Read yesterday's notes off it (call-list notes + "Your call" decisions).
  3. Apply your written move-decisions to GHL.
  4. Snooze any suggestion you left blank (hidden ~SNOOZE_DAYS).
  5. Sync your call-list notes to GHL.
  6. Re-scan the pipeline: auto-resurface finished cool-offs, auto-park clear-cut
     going-dark leads (with GHL audit notes), and produce fresh suggestions.
  7. Repaint the same page (stable URL).
  8. Email the link.

Run with --dry-run to do everything EXCEPT GHL writes (still repaints the page).
"""
import os, sys, json, argparse
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auto_router as R
import auto_daily_call_list as L
import apply_moves as A
import auto_sync_notes as S

BASE_DIR    = os.environ.get("RAI_BASE") or os.path.expanduser("~/restoration-ai")
LOG_FILE    = os.path.join(BASE_DIR, "daily_pipeline.log")
SNOOZE_FILE = R.SNOOZE_FILE
GRACE_FILE  = os.path.join(BASE_DIR, "grace.json")
GRACE_DAYS  = 2   # keep showing a blank suggestion this many read-days before hiding it

def log(m):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S"); line = f"[{ts}] {m}"
    print(line)
    with open(LOG_FILE, "a") as f: f.write(line + "\n")

def all_move_refs(blocks):
    out = []
    for b in blocks:
        t = b.get("type", ""); node = b.get(t, {})
        txt = "".join(x.get("plain_text", "") for x in
                      (node.get("rich_text", []) if isinstance(node, dict) else []))
        if txt.strip().startswith("move-ref:"):
            out.append(txt.strip()[len("move-ref:"):].strip())
    return out

def process_blanks(blank_ids, acted_ids, today):
    """Grace then snooze. A blank suggestion keeps showing for GRACE_DAYS read-days;
    only after that (still no comment) does it hide for R.SNOOZE_DAYS, then return.
    Commenting on one clears its grace + snooze."""
    grace  = R._jload(GRACE_FILE, {})
    snooze = R._jload(SNOOZE_FILE, {})
    for oid in acted_ids:                 # you commented -> stop tracking it
        grace.pop(oid, None); snooze.pop(oid, None)
    hidden = 0
    for oid in blank_ids:
        if not oid: continue
        first = grace.get(oid)
        if first is None:                 # first time seen blank -> start grace, keep showing
            grace[oid] = today.isoformat(); continue
        try: fd = date.fromisoformat(str(first)[:10])
        except Exception: fd = today
        if (today - fd).days >= GRACE_DAYS:   # grace used up -> hide for a while
            snooze[oid] = (today + timedelta(days=R.SNOOZE_DAYS)).isoformat()
            grace.pop(oid, None); hidden += 1
        # else: still within grace -> leave it showing
    json.dump(grace, open(GRACE_FILE, "w"))
    json.dump(snooze, open(SNOOZE_FILE, "w"))
    return hidden

def sync_call_notes(pid):
    """Post call-list 'Your notes for today' text to GHL (no date guard; persistent page)."""
    blocks = S.get_all_children(pid)
    contacts = S.parse_contacts(blocks)
    need = any(not c["cid"] and c["phone"] for c in contacts)
    pmap = S.build_phone_map() if need else {}
    import hashlib
    synced = S.load_synced(); already = set(synced.get(pid, []))
    posted = 0
    for c in contacts:
        cid = c["cid"] or pmap.get(c["phone"]); note = c["note"]
        if not note or S.is_no_action(note) or not cid:
            continue
        # Dedupe on contact+note-text: the page is persistent, so a bare-cid
        # key meant "this contact synced once EVER" and silently dropped every
        # later note about the same lead (bug found 2026-07-13, 0-posted x5d).
        key = f"{cid}:{hashlib.sha1(note.encode()).hexdigest()[:10]}"
        if key in already:
            continue
        if L.REMOVE_RE.search(note):
            L.add_removed(cid)   # durable even if the GHL note post fails
            log(f"  remove-from-list captured for {cid}")
        if S.post_note(cid, note):
            already.add(key); posted += 1
    synced[pid] = sorted(already); S.save_synced(synced)
    log(f"Call notes synced to GHL: {posted} posted")

def main(dry_run=False):
    today = date.today(); disp = today.strftime("%B %-d, %Y")
    log(f"=== Daily pipeline {today} ({'DRY RUN' if dry_run else 'live'}) ===")

    # 1. persistent page + keep notion_page_id.txt pointed at it
    pid = L.get_or_create_persistent_page(disp)
    with open(os.path.join(BASE_DIR, "notion_page_id.txt"), "w") as f: f.write(pid)
    log(f"Persistent page: {pid}")

    # 2. read yesterday's content BEFORE we touch anything
    blocks = A.get_children(pid)
    refs   = set(all_move_refs(blocks))
    acted  = set(A.parse_directives(blocks).keys())

    # 3. apply your written move-decisions
    if not dry_run:
        try: A.run(dry_run=False)
        except Exception as e: log(f"apply_moves failed: {e}")
    else:
        log(f"[dry] would apply {len(acted)} written decision(s)")

    # 4. grace/snooze: keep blanks for a grace window, hide only after
    hidden = process_blanks(refs - acted, acted, today)
    log(f"Grace pass: {len(refs - acted)} blank, {hidden} hidden after {GRACE_DAYS}d grace")

    # 5. sync your call-list notes
    if not dry_run:
        try: sync_call_notes(pid)
        except Exception as e: log(f"note sync failed: {e}")

    # 6. re-scan: resurface + auto-park + fresh suggestions (snooze-filtered)
    if not dry_run:
        try: R.run(quiet=True)
        except Exception as e: log(f"router failed: {e}")
    else:
        log("[dry] skipping live re-scan (would auto-park / resurface)")

    # 6.5 inbox triage — unanswered inbound + drafted replies (📬 Needs a Response)
    if not dry_run:
        try:
            import inbox_triage
            inbox_triage.run(dry_run=False)
        except Exception as e:
            log(f"inbox triage failed: {e}")

    # 7. repaint the same page
    pid, total = L.rebuild_persistent(today)
    log(f"Repainted page with call list of {total}")

    # 8. email the stable link
    if not dry_run:
        try: L.send_email(pid, disp, total)
        except Exception as e: log(f"email failed: {e}")

    log("=== Daily pipeline done ===")
    return pid

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    main(dry_run=a.dry_run)
