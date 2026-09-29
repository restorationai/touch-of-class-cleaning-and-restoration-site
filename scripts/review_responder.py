#!/usr/bin/env python3
"""review_responder.py — reply to Google reviews for every connected client.

Google's own local-ranking guidance tells businesses to respond to reviews;
responsiveness also drives future review volume (count/recency ARE ranking
factors). This closes the loop automatically:

  4-5 star  -> reply drafted (Monica-quality, human voice) and POSTED to the
               GBP automatically (capped per run)
  1-3 star  -> reply DRAFTED ONLY and parked in the app's Action Plan for
               human approval — negative replies never auto-post

Works directly off the GBP v4 reviews API (authoritative reviewId + whether
a reply exists) — the marketing_gbp_reviews table is DataForSEO-sourced and
its ids can't be used for posting.

Reply voice: 1-3 sentences, greet by first name, echo one specific detail
from their own words, never keyword-stuff (stuffed replies read robotic to
the NEXT customer), no em dashes. Negative replies: empathetic, never argue,
never admit fault, invite the conversation offline with the real phone.

Usage:
  python3 scripts/review_responder.py --slug narestco [--dry-run]
  python3 scripts/review_responder.py --all [--limit-per-client 5]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

import requests

import gbp  # noqa: E402  get_access_token, find_location, company_id_for, _g, ACCT_API
import lead_audit as la  # noqa: E402  _claude, claude_json

GBP_V4 = "https://mybusiness.googleapis.com/v4"

REPLY_SYSTEM = """\
You write owner replies to Google reviews for a local restoration company.
Voice: a warm, real human from the company. Never use em dashes or en dashes.

Rules:
- 1-3 sentences. Greet the reviewer by FIRST NAME when available.
- Echo ONE specific detail from their own words (the crew member they named,
  the problem fixed, the thing they appreciated). Never invent details.
- Copy every person's name EXACTLY as the reviewer spelled it, character for
  character. Never "correct" an unusual spelling: a reply that renames the
  staff member the customer praised is worse than no reply (Sarha at Air
  Care was auto-"corrected" to Sarah, 2026-09-02).
- Mention the service or city ONLY if the reviewer themselves mentioned it —
  never bolt on keywords; a stuffed reply reads robotic to the next customer.
- Vary sentence openings; do not start every reply with "Thank you".
- FOR 1-3 STAR REVIEWS: lead with empathy, never argue, never admit fault or
  liability, never make excuses, invite them to call the owner directly at
  the phone number provided to make it right.
- No emojis, no exclamation marks stacked, no corporate cliches
  ("we strive to...", "your feedback is important to us").

Return ONLY JSON: {"reply": "..."}"""

REPLY_SCHEMA = {"type": "object", "additionalProperties": False,
                "properties": {"reply": {"type": "string"}},
                "required": ["reply"]}

STAR_NUM = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}


def _sb(method, path, body=None):
    import os
    import urllib.request
    req = urllib.request.Request(
        os.environ["SUPABASE_URL"] + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"apikey": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
                 "Authorization": "Bearer " + os.environ["SUPABASE_SERVICE_ROLE_KEY"],
                 "Content-Type": "application/json", "Prefer": "return=minimal"})
    import urllib.request as ur
    with ur.urlopen(req, timeout=30) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


def _sb_get(path):
    import os
    import urllib.request as ur
    req = ur.Request(os.environ["SUPABASE_URL"] + path, headers={
        "apikey": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        "Authorization": "Bearer " + os.environ["SUPABASE_SERVICE_ROLE_KEY"]})
    with ur.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def respond_for(slug: str, limit: int = 5, dry_run: bool = False) -> str:
    cid = gbp.company_id_for(slug)
    if not cid:
        return f"{slug}: not in company_map — skip"
    token = gbp.get_access_token(cid)
    if not token:
        return f"{slug}: no Google token — skip"
    try:
        brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
    except Exception:
        brand = {}
    loc = gbp.find_location(token, brand.get("place_id", ""))
    if not loc:
        return f"{slug}: no matching GBP location — skip"
    acct = gbp._g(f"{gbp.ACCT_API}/accounts", token)["accounts"][0]["name"]
    biz = brand.get("display_name", slug)
    phone = brand.get("phone", "")

    reviews = gbp._g(f"{GBP_V4}/{acct}/{loc['name']}/reviews?pageSize=50", token).get("reviews", [])
    unreplied = [r for r in reviews if not r.get("reviewReply")]
    if not unreplied:
        return f"{slug}: all {len(reviews)} recent reviews already have replies"

    posted, parked = 0, 0
    replied_to: list[str] = []
    for r in unreplied[:limit]:
        stars = STAR_NUM.get(r.get("starRating", ""), 0)
        reviewer = ((r.get("reviewer") or {}).get("displayName") or "").strip()
        first = reviewer.split()[0] if reviewer else ""
        comment = (r.get("comment") or "").strip()
        user = ("BUSINESS: {} (phone {})\nREVIEWER FIRST NAME: {}\nSTARS: {}\n"
                "REVIEW TEXT:\n{}".format(biz, phone, first or "(none)", stars,
                                          comment or "(rating only, no text)"))
        copy, _ = la.claude_json(la._claude(), REPLY_SYSTEM, user,
                                 max_tokens=500, schema=REPLY_SCHEMA)
        reply = (copy.get("reply") or "").strip().replace("—", ", ").replace("–", ", ")
        if not reply:
            continue

        if stars >= 4:
            print(f"  [{slug}] {stars}★ {reviewer[:24]}: POST -> {reply[:90]}")
            if not dry_run:
                requests.put(
                    f"{GBP_V4}/{acct}/{loc['name']}/reviews/{r['reviewId']}/reply",
                    headers={"Authorization": f"Bearer {token}",
                             "Content-Type": "application/json"},
                    json={"comment": reply}, timeout=30).raise_for_status()
                replied_to.append(f"{first or 'a customer'} ({stars} stars)")
            posted += 1
        else:
            key = "review-reply-" + str(r.get("reviewId", ""))[:16]
            print(f"  [{slug}] {stars}★ {reviewer[:24]}: PARKED for approval")
            if not dry_run:
                existing = _sb_get(
                    "/rest/v1/marketing_action_plan?company_id=eq.{}"
                    "&action_key=eq.{}&select=id".format(cid, key))
                if not existing:
                    _sb("POST", "/rest/v1/marketing_action_plan", [{
                        "company_id": cid, "rank_ai_slug": slug,
                        "action_key": key, "action_type": "review_reply",
                        "status": "planned", "priority": 1, "pinned": True,
                        "impact": "high", "effort": "low",
                        "title": "APPROVE reply to {}-star review from {}".format(
                            stars, reviewer or "a customer"),
                        "rationale": ("REVIEW ({}★): {}\n\nPROPOSED REPLY: {}"
                                      .format(stars, comment[:400], reply))}])
            parked += 1
    if replied_to:
        # Reports tab (2026-09-29, every client action logs): one change-log
        # row per run; the monthly summary files review_reply under Reviews.
        # gbp.log_change is fail-soft and never breaks the replies.
        n = len(replied_to)
        gbp.log_change(cid, "review_reply",
                       f"Replied to {n} new Google review{'s' if n != 1 else ''} on your "
                       f"profile: {', '.join(replied_to[:6])}"
                       + (" and more" if n > 6 else "") + ".",
                       actor="automation", meta={"replies": n})
    return f"{slug}: {posted} replied, {parked} parked for approval ({len(unreplied)} unreplied found)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit-per-client", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    slugs = ([args.slug] if args.slug else
             list(json.loads((ROOT / "clients" / "company_map.json").read_text()).keys()))
    for slug in slugs:
        try:
            print(respond_for(slug, args.limit_per_client, args.dry_run))
        except Exception as e:  # noqa: BLE001 — one client never kills the run
            print(f"{slug}: ERROR {str(e)[:140]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
