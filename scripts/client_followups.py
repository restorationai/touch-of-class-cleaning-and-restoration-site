#!/usr/bin/env python3
"""client_followups.py — nothing a client is waiting on, or owes us, goes quiet.

Santino 2026-10-01 (Katofsky): Michael got his site preview by hand on 09-26,
said the photos looked "way too AI" and that he'd go get real photos for
every service, and then nothing followed up. Two blind spots:

  1. A preview shared BY HAND was never recorded. The site-preview-feedback
     row only exists when the automated reveal sends it, so the system still
     read Katofsky as "not revealed" (and would have re-sent it at day 10).
  2. Things the CLIENT said they would do ("I'll get you photos", "I'll put
     more", "I'll file it this week") were tracked nowhere. promise_tracker
     records only OUR promises, and Monica only follows up on asks that
     exist as rows, so with no row she reads "nothing outstanding".

PREVIEW   any outbound message (Monica or a human) that carries the client's
          preview link (rankai-{slug}.pages.dev) or says "preview" next to
          their domain marks the preview as shared: a completed
          site-preview-feedback row (the reveal gates never re-send) plus a
          work-log line.
OWES      one Claude pass over the client's recent INBOUND messages (only
          when something new arrived) lists what they said they would
          send or do and have not yet delivered. Each new item becomes a
          planned client_input ask ("FOLLOW UP: ...") after a 2-day grace,
          so Monica follows up on her normal cadence (quiet hours, cooldowns,
          nudge caps all apply). Delivered/answered asks resolve through
          Monica's usual ask handling.

Per client, ops worker every 6h. CLI:
    python3 scripts/client_followups.py [--send] [--slug SLUG]
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import client_concierge as cc  # noqa: E402
from client_concierge import _sb, anthropic_json, kv_get, kv_set  # noqa: E402

GRACE_DAYS = 2           # give the client time to deliver before we ask
LOOKBACK_DAYS = 21
STATE_KEY = "client-followups:{cid}"
MODEL = "claude-sonnet-5"
SKIP_SLUGS = {"tdi-builders", "mcc-restoration", "mold-solutionz-24-7-llc"}  # hands off / dead
# the rename pipeline already chases DBA filings; a second ask would double up
OWNED_ELSEWHERE = re.compile(r"\bDBA\b|fictitious|trade name|assumed name|filing", re.I)

OWES_SYSTEM = """\
You read a text/email thread between a marketing agency (outbound, "US") and
its client (inbound, "CLIENT"). List what the CLIENT said THEY would send or
do for the agency and has NOT clearly delivered later in the thread.

Count: "I'll get you photos of every job", "I'll put more", "I'll send the
customer list Monday", "I'll file the DBA", "let me check with my wife and
get back to you". Do NOT count: things the agency promised, questions the
client asked, things already delivered further down the thread (a later
upload confirmation like "Got 5 photos, thank you" counts as delivered),
refusals, or vague moods ("sounds good").

For each item:
- what: imperative follow-up for the agency, plain words, naming the thing
  ("Follow up on the real job photos Michael said he'd take for each service")
- quote: the client's VERBATIM words
- said_at: the timestamp of that inbound message as given
Return ONLY JSON: {"items": [{"what": str, "quote": str, "said_at": str}]}"""


def _when(m: dict) -> datetime:
    w = m.get("when")
    return w if isinstance(w, datetime) else datetime.fromisoformat(str(w))


def _thread(company: dict) -> list[dict]:
    c = cc.resolve_contact(company)
    if not c:
        return []
    return cc.fetch_history(c["id"], max_msgs=140) or []


def _site(cid: str) -> dict:
    rows = _sb("GET", "/rest/v1/marketing_sites?company_id=eq." + cid
               + "&select=rank_ai_slug,domain,apex_live,cloudflare_pages_url&limit=1") or []
    return rows[0] if rows else {}


def record_manual_preview(company: dict, msgs: list[dict], dry_run: bool) -> str | None:
    cid = company["id"]
    site = _site(cid)
    slug = site.get("rank_ai_slug")
    if not slug or site.get("apex_live"):
        return None
    key = f"site-preview-feedback-{slug}"
    if _sb("GET", "/rest/v1/marketing_action_plan?company_id=eq." + cid
           + f"&action_key=eq.{key}&select=id&limit=1") or []:
        return None
    dom = re.escape(str(site.get("domain") or "").lower()) if site.get("domain") \
        and not str(site.get("domain")).endswith(".invalid") else None
    link_re = re.compile(rf"rankai-{re.escape(slug)}\.pages\.dev"
                         + (rf"|{dom}" if dom else ""), re.I)
    hit = next((m for m in sorted(msgs, key=_when)
                if m.get("direction") == "out"
                and link_re.search(str(m.get("body") or ""))
                and re.search(r"preview|new (web)?site|website", str(m.get("body") or ""), re.I)),
               None)
    if not hit:
        return None
    when = _when(hit)
    line = (f"{slug}: preview was shared by hand {when:%Y-%m-%d} "
            f"({'Santino' if hit.get('user_id') else 'Monica'}); recorded so the "
            "reveal never re-sends it")
    if dry_run:
        return "[dry-run] " + line
    _sb("POST", "/rest/v1/marketing_action_plan", [{
        "company_id": cid, "rank_ai_slug": slug, "action_key": key,
        "action_type": "client_input", "status": "completed", "priority": 1,
        "impact": "high", "effort": "low",
        "title": "Take a look at your new website preview and tell us your thoughts",
        "target": site.get("cloudflare_pages_url") or f"https://staging.rankai-{slug}.pages.dev",
        "rationale": f"Shared by hand on {when:%Y-%m-%d} (detected by client_followups.py): "
                     + str(hit.get("body") or "")[:300]}])
    try:
        from work_log import work_log
        work_log(cid, "site", "preview-shared",
                 f"Website preview shared with the client on {when:%b %-d}.",
                 evidence={"message": str(hit.get("body") or "")[:300]},
                 source="client_followups.py")
    except Exception:  # noqa: BLE001
        pass
    return line


def client_owes(company: dict, msgs: list[dict], dry_run: bool) -> list[str]:
    cid = company["id"]
    since = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    recent = [m for m in sorted(msgs, key=_when) if _when(m) >= since]
    inbound = [m for m in recent if m.get("direction") == "in" and str(m.get("body") or "").strip()]
    if not inbound:
        return []
    state = kv_get(STATE_KEY.format(cid=cid)) or {}
    newest_in = max(_when(m) for m in inbound).isoformat()
    seen = state.get("seen") or {}
    if state.get("scanned_through") != newest_in:
        lines = [f"[{_when(m):%Y-%m-%d %H:%M} UTC] "
                 f"{'CLIENT' if m.get('direction') == 'in' else 'US'}: "
                 f"{str(m.get('body') or '')[:500]}" for m in recent]
        out = anthropic_json(OWES_SYSTEM, f"Client: {company.get('name')}\n\n"
                             + "\n".join(lines), max_tokens=4000, model=MODEL)
        pending = state.get("pending") or {}
        for it in out.get("items") or []:
            if not isinstance(it, dict) or not str(it.get("what") or "").strip():
                continue
            if OWNED_ELSEWHERE.search(it["what"] + " " + str(it.get("quote") or "")):
                continue
            h = hashlib.sha1(str(it.get("quote") or it["what"]).lower().encode()).hexdigest()[:12]
            if h in seen or h in pending:
                continue
            pending[h] = {"what": it["what"][:200], "quote": str(it.get("quote") or "")[:300],
                          "said_at": str(it.get("said_at") or "")}
        state["pending"] = pending
        state["scanned_through"] = newest_in
    filed = []
    now = datetime.now(timezone.utc)
    site = _site(cid)
    for h, it in list((state.get("pending") or {}).items()):
        try:
            said = datetime.fromisoformat(it["said_at"][:16].replace(" ", "T") + ":00+00:00")
        except ValueError:
            said = now
        if now - said < timedelta(days=GRACE_DAYS):
            continue
        title = "ASK CLIENT: FOLLOW UP: " + it["what"]
        filed.append(f"{company.get('name')}: {it['what'][:100]}")
        if not dry_run:
            _sb("POST", "/rest/v1/marketing_action_plan", [{
                "company_id": cid, "rank_ai_slug": site.get("rank_ai_slug"),
                "action_key": f"client-owes-{h}", "action_type": "client_input",
                "status": "planned", "priority": 2, "impact": "medium", "effort": "low",
                "title": title[:240],
                "rationale": (f"On {it['said_at'][:10]} they said: \"{it['quote']}\". Nothing "
                              "has arrived since. Follow up warmly, make it easy (upload link "
                              "if it is files), never nag twice in a row.")}])
        seen[h] = now.isoformat()
        state["pending"].pop(h, None)
    state["seen"] = seen
    if not dry_run:
        kv_set(STATE_KEY.format(cid=cid), state)
    return filed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--slug")
    a = ap.parse_args()
    dry = not a.send
    from client_ops_sync import slug_map
    inv = slug_map()
    comps = _sb("GET", "/rest/v1/companies?status=ilike.active&plan=eq.Rank%20AI"
                "&select=id,name,integration_settings,phone,email") or []
    for co in comps:
        slug = inv.get(co["id"])
        if a.slug and slug != a.slug:
            continue
        if slug in SKIP_SLUGS:
            continue
        try:
            msgs = _thread(co)
            if not msgs:
                continue
            p = record_manual_preview(co, msgs, dry)
            if p:
                print("  PREVIEW " + p)
            for f in client_owes(co, msgs, dry):
                print("  OWES    " + f)
        except Exception as e:  # noqa: BLE001 — one client never stops the sweep
            print(f"  [{slug or co['id']}] failed: {str(e)[:140]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
