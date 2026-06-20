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
ANTHROPIC_MODEL = "claude-sonnet-4-6"
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

def review_client(slug: str, b6: set[str]) -> dict:
    """Pull 7d performance + search terms, diagnose. Never raises — returns a row."""
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

    # 2) search terms (7d) -> junk vs candidate
    junk, junk_cost = [], 0.0
    stq = """SELECT search_term_view.search_term, metrics.impressions, metrics.clicks,
      metrics.cost_micros, metrics.conversions
    FROM search_term_view WHERE segments.date DURING LAST_7_DAYS
    AND campaign.advertising_channel_type='SEARCH' AND campaign.status='ENABLED'
    AND metrics.clicks > 0 ORDER BY metrics.cost_micros DESC"""
    try:
        for r in am.gaql(client, cid, stq):
            t = r.search_term_view.search_term
            cost = r.metrics.cost_micros / 1e6
            if is_junk(t, b6) or (r.metrics.conversions == 0 and cost >= 5):
                junk.append({"term": t, "clicks": r.metrics.clicks, "cost": cost,
                             "matched_b6": is_junk(t, b6)})
                junk_cost += cost
    except Exception:
        pass

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
    if junk:
        flags.append(f"{len(junk)} wasted/irrelevant search terms (${junk_cost:.0f}) → run ads-negative-search-terms")

    return {
        "slug": slug, "ok": True, "campaigns": camps, "junk": junk[:12], "junk_cost": junk_cost,
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
        "wasted_terms_sample": [j["term"] for j in row["junk"][:8]], "diagnostics": row["flags"],
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
        summary = r.get("summary")
        if summary:
            L += ["", "  " + summary.replace("\n", "\n  "), ""]
        if r["flags"]:
            L.append("  FLAGS:")
            for f in r["flags"]:
                L.append(f"    • {f}")
        if r["junk"]:
            L.append(f"  Top wasted search terms (review for negatives):")
            for j in r["junk"][:8]:
                tag = " [B.6]" if j["matched_b6"] else ""
                L.append(f"    - {j['term'][:44]:44} {j['clicks']}clk ${j['cost']:.2f}{tag}")
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
    args = ap.parse_args()

    when = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    b6 = load_b6_tokens()
    slugs = [args.slug] if args.slug else clients_with_ads()
    print(f"==> Ads review: {len(slugs)} client(s): {', '.join(slugs) or '(none)'} | B.6 tokens: {len(b6)}\n")

    rows = []
    for s in slugs:
        r = review_client(s, b6)
        if r["ok"] and not args.no_llm:
            r["summary"] = llm_summary(r)
        rows.append(r)

    report = render(rows, when)
    print(report)
    flagged = sum(1 for r in rows if r.get("ok") and r.get("flags"))
    send_email(f"Rank AI ads review — {len(slugs)} clients, {flagged} need attention ({when})",
               report, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
