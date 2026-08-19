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
import argparse, json, os, re, sys, random, time, requests
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
    # Fall back to the Google connection's place_id — Flood Fixers had a
    # month-old active connection but an empty brand.place_id, so every
    # scheduled post run skipped them silently (found 2026-08-01).
    place = brand.get("place_id") or gbp._place_id_from_connection(cid) or ""
    loc = gbp.find_location(tok, place)
    if not loc:
        raise SystemExit(f"{slug}: no GBP location for place_id {place or '(none)'}")
    return tok, acct, loc["name"].split("/")[-1], loc


def post_media_url(res):
    """Image URL of a localPost: prefer Google's hosted copy (googleUrl) over
    the sourceUrl we submitted (which Google may re-host or drop)."""
    media = res.get("media") or []
    for m in media:
        if m.get("googleUrl"):
            return m["googleUrl"]
    for m in media:
        if m.get("sourceUrl"):
            return m["sourceUrl"]
    return None


def record_post(slug, res, topic=None, source="rank-ai-manual"):
    """Ledger every post we create into Supabase marketing_gbp_posts (the app's
    'Recent Google posts' feed). Best-effort: a ledger failure must never fail
    the post itself (the post is already live on Google)."""
    try:
        cid = gbp.company_id_for(slug)
        cta = res.get("callToAction") or {}
        gbp._sb_upsert("marketing_gbp_posts", [{
            "company_id": cid, "post_name": res.get("name"),
            "posted_at": res.get("createTime"), "summary": res.get("summary"),
            "cta_type": cta.get("actionType"), "cta_url": cta.get("url"),
            "topic": topic, "source": source, "state": res.get("state"),
            "search_url": res.get("searchUrl"),
            "media_url": post_media_url(res),
        }], on_conflict="company_id,post_name")
    except Exception as e:
        print(f"  warn: posted OK but not recorded in marketing_gbp_posts ({e})")
    try:
        gbp.log_change(gbp.company_id_for(slug), "post",
                       f"Google post published: {(topic or res.get('summary') or '')[:90]}",
                       actor="automation" if source.startswith("rank-ai-sched") else "agency",
                       meta={"post_name": res.get("name"), "source": source})
    except Exception:
        pass


def _sb_headers():
    return {"apikey": gbp.SB_KEY, "Authorization": f"Bearer {gbp.SB_KEY}",
            "Content-Type": "application/json"}


def _list_photos(cid, sub):
    """Image files under branding/{cid}/job-photos/{sub}, oldest created_at first."""
    r = requests.post(
        f"{gbp.SB_URL}/storage/v1/object/list/branding",
        headers=_sb_headers(),
        json={"prefix": f"{cid}/job-photos/{sub}", "limit": 100,
              "sortBy": {"column": "created_at", "order": "asc"}})
    if not r.ok:
        return []
    out = []
    for f in r.json():
        created = f.get("created_at")
        mime = (f.get("metadata") or {}).get("mimetype", "")
        if created and mime.startswith("image/"):
            out.append((created, f["name"]))
    return sorted(out)


def _sb_move(src, dst):
    r = requests.post(f"{gbp.SB_URL}/storage/v1/object/move", headers=_sb_headers(),
                      json={"bucketId": "branding", "sourceKey": src, "destinationKey": dst})
    return r.ok


def next_job_photo(slug, dry_run=False):
    """Public URL of the job photo to attach, rotating so consecutive posts never
    reuse the same image. Fresh uploads (job-photos/ root — e.g. from the crew
    upload link) post first and are archived into posted/; when nothing is fresh,
    the least-recently-used photo in posted/ is recycled (its rename refreshes
    created_at, so posted/ behaves as an LRU queue). Dry runs pick without moving.
    None when the client has no photos — callers post text-only. Best-effort."""
    try:
        cid = gbp.company_id_for(slug)
        if not cid:
            return None
        fresh = _list_photos(cid, "")
        if fresh:
            _, name = fresh[0]
            src = f"{cid}/job-photos/{name}"
            dst = f"{cid}/job-photos/posted/{name}"
            path = dst if (not dry_run and _sb_move(src, dst)) else src
            return f"{gbp.SB_URL}/storage/v1/object/public/branding/{path}"
        used = _list_photos(cid, "posted/")
        if not used:
            return None
        # LRU order comes from the r{epoch}_ prefix stamped at each recycle —
        # NOT from created_at: Supabase's move/rename preserves created_at, so
        # sorting by it re-picks the same oldest file forever (NaRestCo posted
        # one photo for a month). No prefix = never recycled = posts first.
        def _last_posted(item):
            m = re.match(r"^r(\d+)_", item[1])
            return (int(m.group(1)) if m else 0, item[0])
        used.sort(key=_last_posted)
        _, name = used[0]
        base = re.sub(r"^r\d+_", "", name)
        src = f"{cid}/job-photos/posted/{name}"
        dst = f"{cid}/job-photos/posted/r{int(time.time())}_{base}"
        path = dst if (not dry_run and _sb_move(src, dst)) else src
        return f"{gbp.SB_URL}/storage/v1/object/public/branding/{path}"
    except Exception as e:
        print(f"  warn: job-photo rotation failed, posting text-only ({e})")
        return None


def create_local_post(slug, summary, cta_type="LEARN_MORE", cta_url=None, dry_run=False,
                      topic=None, source="rank-ai-manual"):
    tok, acct, locid, loc = _resolve(slug)
    body = {"languageCode": "en-US", "summary": summary.strip(), "topicType": "STANDARD"}
    if cta_type and cta_type != "NONE":
        cta = {"actionType": cta_type}
        if cta_type != "CALL":
            cta["url"] = cta_url or loc.get("websiteUri")
        body["callToAction"] = cta
    # Attach a rotating job photo (public Storage URL) — posts with images get
    # materially better engagement, and rotation keeps the feed from looking
    # frozen when a client has few photos. Text-only when none exist.
    photo = next_job_photo(slug, dry_run=dry_run)
    if photo:
        body["media"] = [{"mediaFormat": "PHOTO", "sourceUrl": photo}]
        print(f"  photo: {photo}")
    if dry_run:
        print("  [dry-run] would post:\n   ", summary.strip()[:200])
        return None
    url = f"{GBP_V4}/{acct}/locations/{locid}/localPosts"
    r = requests.post(url, headers={"Authorization": f"Bearer {tok}"}, json=body)
    if r.status_code not in (200, 201):
        raise SystemExit(f"  POST failed HTTP {r.status_code}: {r.text[:300]}")
    res = r.json()
    print(f"  ✓ posted -> {res.get('name')}  (state: {res.get('state')})")
    record_post(slug, res, topic=topic, source=source)
    return res


# --- AI draft -------------------------------------------------------------
TOPICS = {
    "services": "Spotlight one specific service this company offers and why local homeowners call them for it.",
    "tip": "Give one practical, genuinely useful homeowner tip related to water/fire/mold damage prevention or what to do first.",
    "seasonal": "Tie the message to the current season/weather risk in this service area.",
    "review": "Reinforce trust using the company's strong reputation (5-star reviews) without quoting a specific review.",
}


def _live_base(slug):
    """https://{domain} when the site is LIVE on its apex, else None.
    Deep links must never point at a parked/legacy domain (pre-cutover the
    GBP websiteUri is the safe default)."""
    try:
        rows = gbp._sb(f"marketing_sites?rank_ai_slug=eq.{slug}"
                       "&apex_live=eq.true&select=domain") or []
        dom = (rows[0].get("domain") or "").strip() if rows else ""
        return f"https://{dom}" if dom else None
    except Exception:
        return None


def ai_draft(slug, topic="services", service=None):
    rec = json.loads((ROOT / "clients" / f"{slug}.json").read_text())
    brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
    city = rec.get("plan", {}).get("primary_city") or brand.get("primary_city", "")
    name = rec.get("display_name", slug)
    from datetime import datetime, timezone
    month = datetime.now(timezone.utc).strftime("%B")
    state = brand.get("primary_state") or rec.get("plan", {}).get("primary_state") or ""
    sysmsg = ("You write Google Business Profile posts for a local restoration company. "
              "Constraints: 60-180 words, plain and trustworthy (no hype/emojis), one clear value point, "
              "end with a soft call to action. Return ONLY the post text. "
              f"It is currently {month}. The company is in {city}, {state} - any seasonal or regional "
              "framing MUST match that month and that region (no winter/freeze content in July, no "
              "wrong-region weather like 'Mid-Atlantic' for a Pacific Northwest company).")
    focus = (f"Spotlight this ONE service and why local homeowners call them "
             f"for it: {service}." if service
             else TOPICS.get(topic, TOPICS['services']))
    user = (f"Company: {name} ({city}, {state}). {focus} "
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
    pd = sub.add_parser("due", help="scheduler: post for due clients (3x/week cadence: Mon/Wed/Thu)")
    pd.add_argument("--all", action="store_true")
    pd.add_argument("--slug")
    pd.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.cmd == "post":
        summary, topic = a.summary, None
        if a.auto or not summary:
            topic = a.topic or random.choice(list(TOPICS))
            print(f"  drafting ({topic})...")
            summary = ai_draft(a.slug, topic)
            print("  draft:\n   ", summary[:300])
        create_local_post(a.slug, summary, a.cta_type, a.cta_url, a.dry_run,
                          topic=topic, source="rank-ai-manual")

    elif a.cmd == "due":
        slugs = ([a.slug] if a.slug else
                 list(json.loads((ROOT / "clients" / "company_map.json").read_text()).keys()))
        # 3x/week: Mon + Thu (weekly-maintenance) + Wed (gbp-posts-midweek)
        for slug in slugs:
            try:
                topic = random.choice(list(TOPICS))
                service = None
                cta_url = None
                if topic == "services":
                    # DEEP LINK (2026-08-19, video-adoption batch): a post that
                    # spotlights a service links THAT service's page, never the
                    # homepage — but only once the site is live on its apex,
                    # and only after the URL answers 200 (FireDEX dead-link
                    # lesson: nothing of ours ships unfetched).
                    svcs = []
                    for cand in (ROOT / "clients" / slug / "plan" / "plan-input.json",
                                 ROOT / "clients" / slug / "plan-input.json"):
                        try:
                            raw = json.loads(cand.read_text()).get("services") or []
                            svcs = [x.get("slug") if isinstance(x, dict) else str(x)
                                    for x in raw]
                            if svcs:
                                break
                        except (OSError, json.JSONDecodeError):
                            continue
                    base = _live_base(slug)
                    if svcs and base:
                        svc_slug = random.choice(svcs)
                        candidate = f"{base}/services/{svc_slug}/"
                        try:
                            ok = requests.get(candidate, timeout=15).status_code == 200
                        except requests.RequestException:
                            ok = False
                        if ok:
                            service = svc_slug.replace("-", " ")
                            cta_url = candidate
                s = ai_draft(slug, topic, service=service)
                print(f"== {slug} ({topic}"
                      + (f" -> {cta_url}" if cta_url else "") + ") ==")
                create_local_post(slug, s, cta_url=cta_url, dry_run=a.dry_run,
                                  topic=topic, source="rank-ai-cron")
            except SystemExit as e:
                print(f"  {slug}: skip — {e}")


if __name__ == "__main__":
    main()
