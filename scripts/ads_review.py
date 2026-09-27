#!/usr/bin/env python3
"""
Rank AI — Weekly Google Ads review cron ("Paige for ads").

For every client with a live Google Ads account, pulls the last 7 days of
performance + search terms, runs the same diagnostics a media buyer does by hand
(impression-share bottleneck, conversion rate, spend pacing, anomalies, wasted
search terms), writes a short LLM analyst summary, and emails one report.

v1 is READ-ONLY: it analyses + flags actions, it does NOT change the account.
The flagged negative candidates are handed to the `ads-negative-search-terms`
skill for human-approved pruning; bid/budget/strategy changes are surfaced for a
human. (v2 may auto-apply ONLY search terms that match the vetted B.6 universal
junk patterns — the lowest-risk subset.)

Shares its junk-classification source of truth with the negatives skill: the
B.6 section of Ads/universal-negative-keywords.md.

Usage:
  python3 scripts/ads_review.py                 # all ads clients, email if key present
  python3 scripts/ads_review.py --slug narestco # one client
  python3 scripts/ads_review.py --dry-run       # analyse + print, never email

Env (Railway cron service): SENDGRID_API_KEY, ADS_REPORT_EMAIL (default
contact@restorationai.io), SENDGRID_FROM, ANTHROPIC_API_KEY (optional — LLM summary),
plus the Google Ads creds ads_manager already uses.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import ads_manager as am  # noqa: E402  (build_ads_client, gaql, get_customer_id, load_client)

DEFAULT_TO = "contact@restorationai.io"
ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-5"
B6_FILE = ROOT / "Ads" / "universal-negative-keywords.md"


# ---------------------------------------------------------------------------
# Shared junk-classification source (B.6 of the universal negatives list)
# ---------------------------------------------------------------------------

def load_b6_tokens() -> set[str]:
    """The B.6 restoration-DIY/product/symptom terms — the shared junk vocabulary."""
    if not B6_FILE.exists():
        return set()
    text = B6_FILE.read_text()
    m = re.search(r"### B\.6.*?```(.*?)```", text, re.S)
    if not m:
        return set()
    return {ln.strip().lower() for ln in m.group(1).splitlines() if ln.strip()}


def is_junk(term: str, b6: set[str]) -> bool:
    """A search term is junk if it contains any B.6 token/phrase (DIY/product/symptom)."""
    t = term.lower()
    return any(tok in t for tok in b6)


def _client_context(slug: str) -> tuple[list[str], list[str]]:
    try:
        p = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text())
        services = p.get("services", [])
        cities = [f"{a.get('city','')}, {a.get('state','')}" for a in p.get("service_areas", [])]
        return services, cities
    except Exception:
        return [], []


def _parse_verdict_array(raw: str) -> list[dict]:
    """Parse the LLM's JSON verdict array, tolerant of code fences and truncation.
    If the array doesn't parse whole (e.g. it was cut off mid-string), salvage every
    complete {...} object so we keep the verdicts we can rather than dropping all of
    them (the old behaviour, which silently kept every term unvetted)."""
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw).strip()
    try:
        return json.loads(raw)
    except Exception:
        out: list[dict] = []
        for m in re.finditer(r"\{[^{}]*\}", raw):
            try:
                out.append(json.loads(m.group(0)))
            except Exception:
                pass
        return out


def vet_search_terms(candidates: list[dict], services: list[str], cities: list[str]) -> list[dict]:
    """LLM vets each candidate term: negate (junk) or keep (lead). Conservative — keep when unsure.
    Returns [{term, negate, match_type, reason}]. Empty if no API key / no candidates."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or not candidates:
        return []
    terms = [c["term"] for c in candidates]
    prompt = (
        "You vet Google Ads search terms for a RESTORATION company. Decide, per term, whether to add it "
        "as a NEGATIVE keyword.\n\n"
        f"Services this company offers: {', '.join(services) or 'water / fire / mold damage restoration'}.\n"
        f"Service area: {', '.join(cities) or 'local metro'}.\n\n"
        "NEGATE (negate=true) ONLY if the searcher is clearly NOT a potential customer who would HIRE this company:\n"
        "  • DIY / self-treatment — 'does vinegar kill mold', 'how to remove mold yourself'\n"
        "  • product shopping — 'mold test kit', 'best mold remover', 'mold spray', 'concrobium'\n"
        "  • research / informational / symptoms / definitions — 'black mold symptoms', 'mold vs mildew', 'is mold dangerous'\n"
        "  • job seekers, training/courses, competitor BRAND names, or a service this company does NOT offer\n\n"
        "KEEP (negate=false) anything with commercial intent for a service offered — INCLUDING buyer-research terms "
        "like 'cost', 'price', 'near me', a city name, 'company', 'emergency', 'inspection', 'testing', 'remediation', 'restoration'.\n\n"
        "BIAS STRONGLY TO KEEP when uncertain — wrongly blocking a real lead is far worse than one wasted click. "
        "Only negate terms you are confident are non-customers.\n\n"
        "Terms:\n" + "\n".join(f"- {t}" for t in terms) +
        "\n\nALSO — dual use: a term that's junk for ADS can be GOLD for a BLOG. If a term is an "
        "INFORMATIONAL question a homeowner researches (how-to, symptoms, 'what is', cost/comparison, "
        "'signs of'), it may be a strong EVERGREEN blog topic that builds organic + AI-search authority "
        "(Gemini/ChatGPT/AI Overviews cite this). Set blog_candidate=true and suggest a concise blog_title. "
        "NOT blog candidates: competitor brand names, job-seeker queries, pure product-shopping ('best X to buy').\n\n"
        'Return ONLY a JSON array, no prose: '
        '[{"term":"...","negate":true,"match_type":"BROAD","reason":"...","blog_candidate":false,"blog_title":""}]'
    )
    # max_tokens must be large enough to hold a verdict object PER term, or the JSON
    # array truncates mid-string and the whole vet fails (every term then kept unvetted).
    # ~120 tokens/verdict; 8000 covers ~60 terms with headroom. Scale with the input.
    max_tokens = max(2000, min(8000, 200 + 140 * len(terms)))
    body = json.dumps({"model": ANTHROPIC_MODEL, "max_tokens": max_tokens,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    try:
        req = urllib.request.Request(ANTHROPIC_API, data=body, method="POST",
            headers={"content-type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = json.loads(resp.read())["content"][0]["text"].strip()
        return _parse_verdict_array(raw)
    except Exception as e:
        sys.stderr.write(f"  vet error: {str(e)[:120]}\n")
        return []


def clients_with_ads() -> list[str]:
    out = []
    for f in sorted((ROOT / "clients").glob("*.json")):
        try:
            rec = json.loads(f.read_text())
        except Exception:
            continue
        if rec.get("google_ads", {}).get("customer_id"):
            out.append(f.stem)
    return out


# ---------------------------------------------------------------------------
# Per-client review
# ---------------------------------------------------------------------------

def review_client(slug: str, b6: set[str], apply: bool = False) -> dict:
    """Pull 7d performance + search terms, vet wasted terms, optionally auto-negate.
    Never raises — returns a row."""
    try:
        client = am.build_ads_client(slug, login_as_mcc=True)
        cid = am.get_customer_id(am.load_client(slug), slug)
    except Exception as e:
        return {"slug": slug, "ok": False, "error": str(e)[:200]}

    # 1) per-campaign 7-day metrics
    camps = []
    cq = """SELECT campaign.name, campaign.status, campaign.bidding_strategy_type,
      metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions,
      metrics.search_impression_share, metrics.search_budget_lost_impression_share,
      metrics.search_rank_lost_impression_share
    FROM campaign WHERE segments.date DURING LAST_7_DAYS
    AND campaign.advertising_channel_type IN ('SEARCH','LOCAL_SERVICES')
    AND campaign.status='ENABLED' ORDER BY metrics.cost_micros DESC"""
    try:
        for r in am.gaql(client, cid, cq):
            c, m = r.campaign, r.metrics
            camps.append({
                "name": c.name, "strategy": c.bidding_strategy_type.name,
                "impr": m.impressions, "clicks": m.clicks, "cost": m.cost_micros / 1e6,
                "conv": m.conversions, "is": m.search_impression_share or 0,
                "lost_rank": m.search_rank_lost_impression_share or 0,
                "lost_budget": m.search_budget_lost_impression_share or 0,
            })
    except Exception as e:
        return {"slug": slug, "ok": False, "error": f"metrics: {str(e)[:150]}"}

    # 2) search terms (7d) -> junk vs candidate (capture campaign for precise negation)
    junk, junk_cost = [], 0.0
    stq = """SELECT search_term_view.search_term, campaign.resource_name,
      metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions
    FROM search_term_view WHERE segments.date DURING LAST_7_DAYS
    AND campaign.advertising_channel_type='SEARCH' AND campaign.status='ENABLED'
    AND metrics.clicks > 0 ORDER BY metrics.cost_micros DESC"""
    try:
        for r in am.gaql(client, cid, stq):
            t = r.search_term_view.search_term
            cost = r.metrics.cost_micros / 1e6
            if is_junk(t, b6) or (r.metrics.conversions == 0 and cost >= 5):
                junk.append({"term": t, "clicks": r.metrics.clicks, "cost": cost,
                             "matched_b6": is_junk(t, b6),
                             "campaign": r.campaign.resource_name})
                junk_cost += cost
    except Exception:
        pass

    # 2b) LLM-vet the wasted terms; auto-negate the confirmed-junk (campaign-level) if apply=True
    applied, kept, blog_topics = [], [], []
    if junk:
        services, cities = _client_context(slug)
        vmap = {v.get("term"): v for v in vet_search_terms(junk, services, cities)}
        by_campaign: dict[str, list[str]] = {}
        for j in junk:
            v = vmap.get(j["term"])
            if v and v.get("negate"):
                applied.append({**j, "reason": v.get("reason", "")})
                by_campaign.setdefault(j["campaign"], []).append(j["term"])
            else:
                kept.append({**j, "reason": (v or {}).get("reason", "kept (no verdict)")})
        # Dual use: surface informational terms as candidate evergreen blog topics
        # (ad-junk = content-gold). Human promotes the good ones to seed-blog-topics.json.
        seen_titles = set()
        for v in vmap.values():
            if v.get("blog_candidate") and v.get("blog_title"):
                key = v["blog_title"].lower()
                if key not in seen_titles:
                    seen_titles.add(key)
                    blog_topics.append({"term": v.get("term", ""), "title": v["blog_title"]})
        if apply and by_campaign:
            for camp_res, terms in by_campaign.items():
                try:
                    am.add_campaign_negatives(client, cid, camp_res, terms)
                except Exception as e:
                    sys.stderr.write(f"  apply negatives failed ({camp_res}): {str(e)[:120]}\n")

    # 3) diagnostics (deterministic)
    spend = sum(c["cost"] for c in camps)
    clicks = sum(c["clicks"] for c in camps)
    conv = sum(c["conv"] for c in camps)
    flags = []
    for c in camps:
        if c["cost"] > 0 and c["lost_rank"] > 0.5:
            flags.append(f"{c['name'][:34]}: losing {c['lost_rank']*100:.0f}% IS to RANK → bids likely too low")
        if c["lost_budget"] > 0.3:
            flags.append(f"{c['name'][:34]}: losing {c['lost_budget']*100:.0f}% IS to BUDGET → raise budget")
        if c["cost"] >= 20 and c["conv"] == 0:
            flags.append(f"{c['name'][:34]}: ${c['cost']:.0f} spent, 0 conversions")
    if applied:
        verb = "auto-negated" if apply else "would auto-negate"
        flags.append(f"{verb} {len(applied)} wasted search terms")
    if kept:
        flags.append(f"{len(kept)} borderline terms KEPT (lead-intent / uncertain) — see list")
    if blog_topics:
        flags.append(f"{len(blog_topics)} candidate evergreen blog topics (informational demand) — see list")

    return {
        "slug": slug, "ok": True, "campaigns": camps, "junk_cost": junk_cost,
        "applied": applied, "kept": kept, "blog_topics": blog_topics, "apply_mode": apply,
        "spend": spend, "clicks": clicks, "conv": conv,
        "cost_per_conv": (spend / conv) if conv else None, "flags": flags,
    }


# ---------------------------------------------------------------------------
# LLM analyst summary (optional)
# ---------------------------------------------------------------------------

def llm_summary(row: dict) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or not row.get("ok"):
        return ""
    facts = {
        "weekly_spend": round(row["spend"], 2), "clicks": row["clicks"],
        "conversions": round(row["conv"], 1), "cost_per_conversion": row["cost_per_conv"],
        "campaigns": [{k: cc[k] for k in ("name", "cost", "clicks", "conv", "lost_rank", "lost_budget")} for cc in row["campaigns"]],
        "auto_negated_sample": [j["term"] for j in row.get("applied", [])[:8]],
        "kept_borderline_sample": [j["term"] for j in row.get("kept", [])[:6]],
        "diagnostics": row["flags"],
    }
    prompt = (
        "You are a senior Google Ads analyst for a home-services (restoration) client. "
        "Given this week's data, write a tight 3-5 sentence summary: what's happening, the single "
        "biggest issue, and the top 2 concrete actions (bid/budget/negatives). Be direct, no fluff.\n\n"
        + json.dumps(facts, indent=2)
    )
    body = json.dumps({"model": ANTHROPIC_MODEL, "max_tokens": 400,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    try:
        req = urllib.request.Request(ANTHROPIC_API, data=body, method="POST",
            headers={"content-type": "application/json", "x-api-key": api_key,
                     "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())["content"][0]["text"].strip()
    except Exception as e:
        return f"(LLM summary unavailable: {str(e)[:80]})"


# ---------------------------------------------------------------------------
# Report + email
# ---------------------------------------------------------------------------

def render(rows: list[dict], when: str) -> str:
    L = [f"Rank AI — weekly ads review ({when})", "=" * 60, ""]
    for r in rows:
        L.append(f"### {r['slug']}")
        if not r["ok"]:
            L.append(f"  ERROR: {r['error']}\n"); continue
        cpc = f"${r['cost_per_conv']:.0f}/conv" if r["cost_per_conv"] else "no conversions"
        L.append(f"  7d: ${r['spend']:.0f} spend · {r['clicks']} clicks · {r['conv']:.0f} conv · {cpc}")
        prior = am.read_journal(r["slug"], limit=2)
        if prior:
            L.append("  prior journal (what we were watching):")
            for blk in prior:
                ln = blk.splitlines()
                hdr = ln[0].replace("## ", "")
                txt = (ln[1][:88] + "…") if len(ln) > 1 and len(ln[1]) > 89 else (ln[1] if len(ln) > 1 else "")
                L.append(f"    • {hdr} — {txt}")
        summary = r.get("summary")
        if summary:
            L += ["", "  " + summary.replace("\n", "\n  "), ""]
        if r["flags"]:
            L.append("  FLAGS:")
            for f in r["flags"]:
                L.append(f"    • {f}")
        if r.get("applied"):
            verb = "AUTO-NEGATED" if r.get("apply_mode") else "WOULD NEGATE (dry-run)"
            L.append(f"  {verb} — confirmed junk ({len(r['applied'])}):")
            for j in r["applied"][:12]:
                L.append(f"    ✕ {j['term'][:38]:38} ${j['cost']:.2f}  — {j.get('reason','')[:46]}")
        if r.get("kept"):
            L.append(f"  KEPT — lead-intent / uncertain ({len(r['kept'])}):")
            for j in r["kept"][:8]:
                L.append(f"    ✓ {j['term'][:38]:38} ${j['cost']:.2f}  — {j.get('reason','')[:46]}")
        if r.get("blog_topics"):
            L.append(f"  CANDIDATE EVERGREEN BLOG TOPICS — promote good ones to seed-blog-topics.json (AI-search authority):")
            for b in r["blog_topics"][:8]:
                L.append(f"    ✎ {b['title'][:52]:52}  (search: \"{b['term'][:28]}\")")
        L.append("")
    return "\n".join(L)


def send_email(subject: str, body: str, dry_run: bool) -> None:
    api_key = os.environ.get("SENDGRID_API_KEY")
    if dry_run or not api_key:
        print(f"\n[email skipped: {'dry-run' if dry_run else 'no SENDGRID_API_KEY'}] — report above.")
        return
    to_addr = os.environ.get("ADS_REPORT_EMAIL", DEFAULT_TO)
    payload = {"personalizations": [{"to": [{"email": to_addr}]}],
               "from": {"email": os.environ.get("SENDGRID_FROM", DEFAULT_TO), "name": "Rank AI Ads Review"},
               "subject": subject, "content": [{"type": "text/plain", "value": body}]}
    try:
        req = urllib.request.Request("https://api.sendgrid.com/v3/mail/send",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as resp:
            print(f"\n[email sent -> {to_addr}] status {resp.status}")
    except Exception as e:
        print(f"\n[email FAILED -> {to_addr}]: {e}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Rank AI weekly ads review")
    ap.add_argument("--slug", help="One client (default: all with a google_ads customer_id)")
    ap.add_argument("--dry-run", action="store_true", help="Analyse + print, never email")
    ap.add_argument("--no-llm", action="store_true", help="Skip the LLM analyst summary")
    ap.add_argument("--apply", action="store_true",
                    help="AUTO-APPLY the LLM-vetted negatives to the account (the cron uses this). "
                         "Without it, runs dry — vets + reports what it WOULD negate, changes nothing.")
    args = ap.parse_args()

    when = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    b6 = load_b6_tokens()
    slugs = [args.slug] if args.slug else clients_with_ads()
    print(f"==> Ads review: {len(slugs)} client(s): {', '.join(slugs) or '(none)'} | B.6 tokens: {len(b6)}\n")

    print(f"    mode: {'AUTO-APPLY negatives' if args.apply else 'dry (vet + report only)'}\n")
    rows = []
    for s in slugs:
        r = review_client(s, b6, apply=args.apply)
        if r["ok"] and not args.no_llm:
            r["summary"] = llm_summary(r)
        rows.append(r)

    report = render(rows, when)
    print(report)
    flagged = sum(1 for r in rows if r.get("ok") and r.get("flags"))
    send_email(f"Rank AI ads review — {len(slugs)} clients, {flagged} need attention ({when})",
               report, args.dry_run)

    # Append this week's outcome to each client's ads journal (real runs only, so
    # dry-run vetting doesn't pollute the log). This is how the cron leaves a trail
    # of "what to look at next time" — read back at the top of the next review/report.
    if args.apply:
        for r in rows:
            if not r.get("ok"):
                continue
            cpc = f"${r['cost_per_conv']:.0f}/conv" if r["cost_per_conv"] else "no conv"
            line = (f"Weekly review: ${r['spend']:.0f} / {r['clicks']} clicks / "
                    f"{r['conv']:.0f} conv ({cpc}). Auto-negated {len(r.get('applied', []))} junk term(s).")
            if r.get("flags"):
                line += " Flags: " + "; ".join(r["flags"][:2]) + "."
            try:
                am.append_journal(r["slug"], line, kind="review", author="ads-review-cron")
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
