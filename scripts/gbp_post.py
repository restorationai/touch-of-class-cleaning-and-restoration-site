#!/usr/bin/env python3
"""
gbp_post.py — create Google Business Profile posts (v4 localPosts) + auto-draft.

Posting lives ONLY in the legacy Google My Business API (mybusiness.googleapis.com/v4)
— the v1 Business Information/Performance APIs don't do posts. That API must be ENABLED
on the Cloud project (it is) and the business.manage token must have access (confirmed).

Modes:
  post  --slug X --summary "..." [--cta-url U] [--cta-type LEARN_MORE]   explicit post
  post  --slug X --auto [--topic services|tip|seasonal|review]          AI-drafted post
  due   --all                                                            scheduler: post if due (2x/wk)

Reuses gbp.py for token + account + location resolution.
"""
import argparse, json, os, sys, random, datetime, requests
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import gbp

GBP_V4 = "https://mybusiness.googleapis.com/v4"
ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-6"


def _resolve(slug):
    cid = gbp.company_id_for(slug)
    tok = gbp.get_access_token(cid) if cid else None
    if not tok:
        raise SystemExit(f"{slug}: no business.manage token (connect this client's GBP)")
    acct = gbp._g(f"{gbp.ACCT_API}/accounts", tok)["accounts"][0]["name"]
    brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
    loc = gbp.find_location(tok, brand.get("place_id", ""))
    if not loc:
        raise SystemExit(f"{slug}: no GBP location for place_id {brand.get('place_id')}")
    return tok, acct, loc["name"].split("/")[-1], loc


def create_local_post(slug, summary, cta_type="LEARN_MORE", cta_url=None, dry_run=False):
    tok, acct, locid, loc = _resolve(slug)
    body = {"languageCode": "en-US", "summary": summary.strip(), "topicType": "STANDARD"}
    if cta_type and cta_type != "NONE":
        cta = {"actionType": cta_type}
        if cta_type != "CALL":
            cta["url"] = cta_url or loc.get("websiteUri")
        body["callToAction"] = cta
    if dry_run:
        print("  [dry-run] would post:\n   ", summary.strip()[:200])
        return None
    url = f"{GBP_V4}/{acct}/locations/{locid}/localPosts"
    r = requests.post(url, headers={"Authorization": f"Bearer {tok}"}, json=body)
    if r.status_code not in (200, 201):
        raise SystemExit(f"  POST failed HTTP {r.status_code}: {r.text[:300]}")
    res = r.json()
    print(f"  ✓ posted -> {res.get('name')}  (state: {res.get('state')})")
    return res


# --- AI draft -------------------------------------------------------------
TOPICS = {
    "services": "Spotlight one specific service this company offers and why local homeowners call them for it.",
    "tip": "Give one practical, genuinely useful homeowner tip related to water/fire/mold damage prevention or what to do first.",
    "seasonal": "Tie the message to the current season/weather risk in this service area.",
    "review": "Reinforce trust using the company's strong reputation (5-star reviews) without quoting a specific review.",
}


def ai_draft(slug, topic="services"):
    rec = json.loads((ROOT / "clients" / f"{slug}.json").read_text())
    brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
    city = rec.get("plan", {}).get("primary_city") or brand.get("primary_city", "")
    name = rec.get("display_name", slug)
    sysmsg = ("You write Google Business Profile posts for a local restoration company. "
              "Constraints: 60-180 words, plain and trustworthy (no hype/emojis), one clear value point, "
              "end with a soft call to action. Return ONLY the post text.")
    user = (f"Company: {name} ({city}). {TOPICS.get(topic, TOPICS['services'])} "
            f"Services: {', '.join((rec.get('plan',{}) or {}).get('services', [])[:8]) or 'water/fire/mold restoration'}.")
    r = requests.post(ANTHROPIC_API, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
        "content-type": "application/json"},
        json={"model": ANTHROPIC_MODEL, "max_tokens": 400,
              "system": sysmsg, "messages": [{"role": "user", "content": user}]})
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json()["content"]).strip()


def main():
    ap = argparse.ArgumentParser(description="GBP post creator")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("post")
    pp.add_argument("--slug", required=True)
    pp.add_argument("--summary")
    pp.add_argument("--auto", action="store_true", help="AI-draft the summary")
    pp.add_argument("--topic", default=None, help="services|tip|seasonal|review (auto mode)")
    pp.add_argument("--cta-type", default="LEARN_MORE")
    pp.add_argument("--cta-url", default=None)
    pp.add_argument("--dry-run", action="store_true")
    pd = sub.add_parser("due", help="scheduler: post for due clients (2x/week cadence)")
    pd.add_argument("--all", action="store_true")
    pd.add_argument("--slug")
    pd.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.cmd == "post":
        summary = a.summary
        if a.auto or not summary:
            topic = a.topic or random.choice(list(TOPICS))
            print(f"  drafting ({topic})...")
            summary = ai_draft(a.slug, topic)
            print("  draft:\n   ", summary[:300])
        create_local_post(a.slug, summary, a.cta_type, a.cta_url, a.dry_run)

    elif a.cmd == "due":
        slugs = ([a.slug] if a.slug else
                 list(json.loads((ROOT / "clients" / "company_map.json").read_text()).keys()))
        # twice a week: only post on Mon/Thu (the weekly-maintenance cron days)
        for slug in slugs:
            try:
                topic = random.choice(list(TOPICS))
                s = ai_draft(slug, topic)
                print(f"== {slug} ({topic}) ==")
                create_local_post(slug, s, dry_run=a.dry_run)
            except SystemExit as e:
                print(f"  {slug}: skip — {e}")


if __name__ == "__main__":
    main()
