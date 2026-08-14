#!/usr/bin/env python3
"""index_watchdog.py — weekly Google index-coverage watchdog for the live fleet.

A page we built but Google refuses to index is work the client pays for and
nobody can find. This script samples each LIVE client's most valuable URLs
through the GSC URL Inspection API, stores a per-client coverage trend in
ops_kv, and (with --apply) fires the cheap remediation ladder:

  1. re-submit the sitemap index via the Search Console API (always safe),
  2. IndexNow-ping the specific not-indexed URLs (Bing feeds ChatGPT retrieval),
  3. for URLs Google reports "Crawled - currently not indexed" on 2+
     CONSECUTIVE runs, seed ONE consolidated SUGGESTION card per client via
     client_ops_sync.insert_plan_row (idempotent seed key "index-watchdog") —
     chronic refusal is a content-quality signal, not a plumbing problem.

  We deliberately do NOT use Google's Indexing API: it is scoped to JobPosting
  / BroadcastEvent pages only, and hammering it with regular pages is exactly
  the off-label pattern Google has been revoking access over. Sitemap
  re-submission + IndexNow + fixing the content is the whole legitimate menu.

QUOTA REALITY (developers.google.com/webmaster-tools/limits, checked
2026-08-14): the URL Inspection API allows 2,000 queries/day PER PROPERTY and
600 queries/minute per property, plus a 10,000,000/day / 15,000/min
project-level ceiling. Our cap of 50 inspections per client per run is 2.5%
of one property's daily quota (and each client is its own property), with a
0.35s pause between calls (~170/min, well under the 600 QPM). Weekly cadence
makes this unmissable.

Candidate URLs, priority order (capped at --cap, default 50):
  (a) pages published in the last 60 days:
      - marketing_page_requests rows with status=built (built_at within 60d)
      - blog posts / case studies in sites/{slug}/src/content/blog with
        frontmatter published_at/generated_at within 60d
      (kept only if present in the live sitemap, when the sitemap is readable)
  (b) money pages: homepage, /services/ hub + service landings, then city
      pages (/service-areas/{city}/ or /locations/{city}/) in sitemap order.

State: ops_kv key 'index-watch:{slug}' — latest run fields (checked_at,
sampled, indexed, rate, not_indexed with verdicts) plus a compact `history`
of the last 8 runs for trend + chronic detection.

Ledger: one client-readable marketing_work_log line per client per run
(category 'routine') — feeds the monthly report automatically.

Usage:
    python3 scripts/index_watchdog.py --slug narestco
    python3 scripts/index_watchdog.py --all --apply
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, .gsc-agency-token.json in repo
root (CI writes it from the GSC_AGENCY_TOKEN secret).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = ROOT / "clients"
SITES_DIR = ROOT / "sites"
sys.path.insert(0, str(ROOT / "scripts"))

import build_site  # noqa: E402 — collect_live_urls + INDEXNOW_ENDPOINT (reuse, don't fork)
from gsc_client import GSCClient  # noqa: E402
from work_log import work_log  # noqa: E402 — fail-open ledger

DEFAULT_CAP = 50          # per client per run — 2.5% of the 2,000/day per-property quota
INSPECT_PAUSE_S = 0.35    # ~170/min, far under the 600 QPM per-property limit
RECENT_DAYS = 60
HISTORY_KEEP = 8
KV_PREFIX = "index-watch:"
CARD_SEED = "index-watchdog"

# Not-indexed verdict buckets (from URL Inspection coverageState strings).
CRAWLED = "crawled_not_indexed"        # "Crawled - currently not indexed"
DISCOVERED = "discovered_not_indexed"  # "Discovered - currently not indexed"
UNKNOWN = "unknown"                    # "URL is unknown to Google"
EXCLUDED = "excluded"                  # noindex / duplicate / redirect / etc.


def load_env() -> None:
    """Fail-soft .env loader (matches master_scheduler.py) — never overrides CI env."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _sb(method: str, path: str, body=None, prefer: str = "return=representation"):
    url = os.environ["SUPABASE_URL"].rstrip("/") + path
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    resp = requests.request(method, url, json=body, timeout=30, headers={
        "apikey": key, "Authorization": f"Bearer {key}",
        "Content-Type": "application/json", "Prefer": prefer})
    resp.raise_for_status()
    return resp.json() if resp.content else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------- fleet
def load_record(slug: str) -> dict:
    return json.loads((CLIENTS_DIR / f"{slug}.json").read_text())


def live_slugs() -> list[str]:
    """LIVE = client record has cut_over_at / apex_cutover.completed_at, OR
    marketing_sites.apex_live is true (the flag alone is known-unreliable in
    BOTH directions — client_ops_sync 2026-08 — so we union the two)."""
    apex: set[str] = set()
    try:
        rows = _sb("GET", "/rest/v1/marketing_sites?apex_live=eq.true"
                   "&select=rank_ai_slug") or []
        apex = {r["rank_ai_slug"] for r in rows if r.get("rank_ai_slug")}
    except Exception as e:  # noqa: BLE001 — repo records still decide
        print(f"  warn: marketing_sites read failed ({str(e)[:80]})")
    out = []
    for f in sorted(CLIENTS_DIR.glob("*.json")):
        if f.name == "company_map.json":
            continue
        try:
            rec = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if not rec.get("domain"):
            continue
        if (rec.get("cut_over_at")
                or (rec.get("apex_cutover") or {}).get("completed_at")
                or f.stem in apex):
            out.append(f.stem)
    return out


def company_id_for(slug: str) -> str | None:
    rec = CLIENTS_DIR / f"{slug}.json"
    if rec.exists():
        cid = json.loads(rec.read_text()).get("company_id")
        if cid:
            return cid
    cmap = CLIENTS_DIR / "company_map.json"
    return json.loads(cmap.read_text()).get(slug) if cmap.exists() else None


# ---------------------------------------------------------------- candidates
_FM_DATE = re.compile(
    r'^(published_at|generated_at):\s*"?(\d{4}-\d{2}-\d{2})', re.M)


def _blog_recent(slug: str, base: str, cutoff: str) -> list[str]:
    """Blog posts + case studies (case-study*.md lives in the blog collection)
    with frontmatter published_at/generated_at in the last RECENT_DAYS."""
    blog = SITES_DIR / slug / "src" / "content" / "blog"
    dated: list[tuple[str, str]] = []
    for md in sorted(blog.glob("*.md")) if blog.is_dir() else []:
        try:
            head = md.read_text(errors="replace")[:6000]
        except OSError:
            continue
        dates = {m.group(1): m.group(2) for m in _FM_DATE.finditer(head)}
        date = dates.get("published_at") or dates.get("generated_at")
        if date and date >= cutoff:
            dated.append((date, f"{base}/blog/{md.stem}/"))
    dated.sort(reverse=True)  # newest first
    return [u for _, u in dated]


def _built_pages_recent(cid: str | None, base: str, cutoff: str) -> list[str]:
    if not cid:
        return []
    try:
        rows = _sb("GET", "/rest/v1/marketing_page_requests"
                   f"?company_id=eq.{cid}&status=eq.built"
                   f"&built_at=gte.{cutoff}&select=service_slug,built_at"
                   "&order=built_at.desc") or []
    except Exception:  # noqa: BLE001 — candidates degrade, run continues
        return []
    return [f"{base}/services/{r['service_slug']}/"
            for r in rows if r.get("service_slug")]


def gather_candidates(slug: str, rec: dict, cid: str | None,
                      cap: int) -> tuple[list[str], int]:
    """Priority-ordered candidate URLs + total live-sitemap size (0 = unread)."""
    domain = rec["domain"].strip().rstrip("/")
    base = f"https://{domain}"
    try:
        sitemap = build_site.collect_live_urls(domain, cap=2000)
    except Exception as e:  # noqa: BLE001
        print(f"  warn: sitemap unreadable for {domain} ({str(e)[:80]})")
        sitemap = []
    smset = set(sitemap)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)).date().isoformat()

    # (a) recent publications — only URLs the live sitemap confirms exist
    # (when we could read it; a scaffolded-but-unrendered stub never counts).
    recent = _built_pages_recent(cid, base, cutoff) + _blog_recent(slug, base, cutoff)
    if smset:
        recent = [u for u in recent if u in smset]

    # (b) money pages from the live sitemap: homepage, services hub +
    # landings, then city pages in sitemap order.
    money = [f"{base}/"]
    for u in sitemap:
        if re.fullmatch(r"/services/(?:[^/]+/)?", u[len(base):]):
            money.append(u)
    for u in sitemap:
        if re.fullmatch(r"/(?:service-areas|locations)/[^/]+/", u[len(base):]):
            money.append(u)

    seen: set[str] = set()
    out = []
    for u in recent + money:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:cap], len(sitemap)


# ---------------------------------------------------------------- inspection
def classify(res: dict) -> str:
    cov = (res.get("coverage_state") or "").lower()
    if "crawled" in cov and "not indexed" in cov:
        return CRAWLED
    if "discovered" in cov and "not indexed" in cov:
        return DISCOVERED
    if res.get("index_status") == "PASS":
        return "indexed"
    if "unknown to google" in cov or not cov:
        return UNKNOWN
    return EXCLUDED  # noindex / duplicate / redirect / alternate canonical …


def inspect_client(slug: str, rec: dict, urls: list[str]) -> tuple[list[dict], str | None]:
    """Inspect each URL. Returns (results, abort_note). abort_note is set when
    the client can't be checked at all (no GSC access / repeated API errors)."""
    prop = ((rec.get("gsc") or {}).get("property_url")
            or rec.get("gsc_property_url"))
    client = GSCClient(slug, rec["domain"], property_url=prop)
    results: list[dict] = []
    consec_errors = 0
    for u in urls:
        try:
            res = client.inspect(u)
        except Exception as e:  # noqa: BLE001 — transient API error
            consec_errors += 1
            results.append({"url": u, "verdict": "error",
                            "state": str(e)[:120]})
            if consec_errors >= 3:
                return results, "aborted after 3 consecutive API errors (quota/transient?)"
            time.sleep(2.0)
            continue
        if res is None:
            # 403 / token missing — permanent for this run; whole client skips.
            return results, ("no GSC access to the property (add "
                             "contact@restorationai.io or run gsc_register.py)")
        consec_errors = 0
        results.append({"url": u, "verdict": classify(res),
                        "state": res.get("coverage_state") or ""})
        time.sleep(INSPECT_PAUSE_S)
    return results, None


# ------------------------------------------------------------------- ops_kv
def kv_get(key: str):
    rows = _sb("GET", f"/rest/v1/ops_kv?k=eq.{urllib.parse.quote(key)}&select=v") or []
    return rows[0].get("v") if rows else None


def kv_put(key: str, value) -> None:
    _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
        {"k": key, "v": value, "updated_at": _now_iso()},
        prefer="resolution=merge-duplicates,return=minimal")


def store_run(slug: str, sampled: int, indexed: int,
              not_indexed: list[dict]) -> list[dict]:
    """Append this run to 'index-watch:{slug}'. Returns the PRIOR runs
    (newest last) so the caller can do chronic detection."""
    key = KV_PREFIX + slug
    prev = None
    try:
        prev = kv_get(key)
    except Exception as e:  # noqa: BLE001
        print(f"  warn: ops_kv read failed ({str(e)[:80]})")
    hist = list((prev or {}).get("history") or [])
    prior = hist[:]
    entry = {
        "checked_at": _now_iso(),
        "sampled": sampled,
        "indexed": indexed,
        "rate": round(indexed / sampled, 3) if sampled else None,
        # compact in history: url + verdict is all chronic detection needs
        "not_indexed": [{"url": r["url"], "verdict": r["verdict"]}
                        for r in not_indexed],
    }
    hist.append(entry)
    hist = hist[-HISTORY_KEEP:]
    value = {
        "checked_at": entry["checked_at"], "sampled": sampled,
        "indexed": indexed, "rate": entry["rate"],
        "not_indexed": not_indexed,  # full detail (verdict + coverage state)
        "history": hist,
    }
    try:
        kv_put(key, value)
    except Exception as e:  # noqa: BLE001 — state loss must not kill the sweep
        print(f"  warn: ops_kv write failed ({str(e)[:80]})")
    return prior


def chronic_urls(current: list[dict], prior_runs: list[dict]) -> list[str]:
    """URLs 'Crawled - currently not indexed' this run AND in the immediately
    previous run (>= 2 consecutive runs) — the content-quality signal."""
    if not prior_runs:
        return []
    last = prior_runs[-1]
    prev_crawled = {r["url"] for r in (last.get("not_indexed") or [])
                    if r.get("verdict") == CRAWLED}
    return [r["url"] for r in current
            if r["verdict"] == CRAWLED and r["url"] in prev_crawled]


# -------------------------------------------------------------- remediation
def resubmit_sitemap(slug: str, rec: dict) -> bool:
    """Re-submit the sitemap index through the Search Console API. Cheap and
    always safe — it nudges a fresh crawl pass without any off-label API."""
    domain = rec["domain"].strip().rstrip("/")
    prop = ((rec.get("gsc") or {}).get("property_url")
            or rec.get("gsc_property_url"))
    try:
        client = GSCClient(slug, domain, property_url=prop)
        svc = client._ensure_service()
        svc.sitemaps().submit(
            siteUrl=client.site_url,
            feedpath=f"https://{domain}/sitemap-index.xml").execute()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  sitemap resubmit failed: {str(e)[:120]}")
        return False


def indexnow_ping_urls(slug: str, rec: dict, urls: list[str]) -> tuple[int, int]:
    """Ping IndexNow with SPECIFIC URLs (unlike build_site.indexnow_ping, which
    submits the whole live sitemap). Reuses the client's existing key — if the
    record has none we skip rather than mint one here (minting belongs to the
    deploy pipeline, which also ships the proof file)."""
    domain = rec["domain"].strip().rstrip("/")
    key = (rec.get("indexnow_key") or "").strip()
    if not (key and urls):
        return (0, 0)
    key_url = f"https://{domain}/{key}.txt"
    try:  # never ping unless the proof file is verifiably live (Bing caches verdicts)
        with urllib.request.urlopen(urllib.request.Request(
                key_url, headers={"User-Agent": "rank-ai-indexnow/1.0"}),
                timeout=15) as r:
            if not (r.status == 200 and r.read(200).decode().strip() == key):
                return (0, 0)
    except Exception:  # noqa: BLE001
        return (0, 0)
    req = urllib.request.Request(
        build_site.INDEXNOW_ENDPOINT,
        data=json.dumps({"host": domain, "key": key, "keyLocation": key_url,
                         "urlList": urls}).encode(),
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return (r.status, len(urls))
    except urllib.error.HTTPError as e:
        return (e.code, len(urls))
    except Exception:  # noqa: BLE001
        return (0, 0)


def seed_chronic_card(slug: str, cid: str, chronic: list[str],
                      by_url_state: dict[str, str], apply: bool) -> bool:
    from client_ops_sync import action_key, insert_plan_row  # noqa: PLC0415
    from client_ops_sync import _sb as ops_sb  # noqa: PLC0415
    lines = "\n".join(f"- {u} ({by_url_state.get(u, 'crawled, not indexed')})"
                      for u in chronic[:20])
    if len(chronic) > 20:
        lines += f"\n- …and {len(chronic) - 20} more (full list in ops_kv 'index-watch:{slug}')"
    title = f"SUGGESTION: {len(chronic)} page(s) Google refuses to index"
    rationale = (
        f"The indexing watchdog found these URLs reported 'Crawled - "
        f"currently not indexed' on 2+ consecutive weekly checks — Google has "
        f"SEEN them and is choosing not to index them, so re-pinging will not "
        f"fix it:\n{lines}\n\n"
        "Likely causes, in order of frequency on our template sites: THIN or "
        "near-duplicate content (city pages sharing boilerplate with only the "
        "place name swapped), ORPHANED pages (too few internal links pointing "
        "at them), or low perceived value for the query space. Fix by "
        "differentiating the copy (local proof points, photos, reviews, "
        "case-study links), adding internal links from indexed money pages, "
        "or consolidating overlapping pages into one stronger URL. Sitemap "
        "re-submission + IndexNow pings already fired automatically.")
    created = insert_plan_row(
        cid, slug, CARD_SEED, title=title, rationale=rationale,
        action_type="technical_fix", target=f"site:{slug}",
        impact="medium", effort="medium", dry_run=not apply)
    if not created and apply:
        # insert_plan_row refreshes only the TITLE of an open row; keep the
        # URL list in the rationale current too (planned rows only).
        try:
            ops_sb("PATCH", "/rest/v1/marketing_action_plan"
                   f"?company_id=eq.{cid}"
                   f"&action_key=eq.{action_key(cid, CARD_SEED)}"
                   "&status=eq.planned", {"rationale": rationale})
        except Exception as e:  # noqa: BLE001
            print(f"  card rationale refresh failed: {str(e)[:100]}")
    return created


# ---------------------------------------------------------------- per-client
def run_client(slug: str, apply: bool, cap: int) -> dict:
    rec = load_record(slug)
    cid = company_id_for(slug)
    out = {"slug": slug, "sampled": 0, "indexed": 0, "rate": None,
           "crawled": 0, "discovered": 0, "unknown": 0, "excluded": 0,
           "errors": 0, "note": None, "remediation": []}

    urls, sitemap_n = gather_candidates(slug, rec, cid, cap)
    if not urls:
        out["note"] = "no candidate URLs (site unreachable?)"
        return out

    results, abort_note = inspect_client(slug, rec, urls)
    if abort_note and not results:
        out["note"] = abort_note
        return out
    if abort_note:
        out["note"] = abort_note

    graded = [r for r in results if r["verdict"] != "error"]
    not_indexed = [r for r in graded if r["verdict"] != "indexed"]
    out["sampled"] = len(graded)
    out["indexed"] = len(graded) - len(not_indexed)
    out["rate"] = round(out["indexed"] / len(graded), 3) if graded else None
    out["errors"] = len(results) - len(graded)
    for r in not_indexed:
        out[{CRAWLED: "crawled", DISCOVERED: "discovered",
             UNKNOWN: "unknown", EXCLUDED: "excluded"}[r["verdict"]]] += 1

    prior_runs = store_run(slug, out["sampled"], out["indexed"], not_indexed)

    # ---- remediation (only URLs Google could plausibly still pick up:
    # excluded-by-design states like noindex/redirect are not re-pushed)
    actionable = [r["url"] for r in not_indexed
                  if r["verdict"] in (CRAWLED, DISCOVERED, UNKNOWN)]
    if apply and actionable:
        if resubmit_sitemap(slug, rec):
            out["remediation"].append("sitemap re-submitted")
        status, n = indexnow_ping_urls(slug, rec, actionable)
        if status in (200, 202):
            out["remediation"].append(f"IndexNow pinged {n} URL(s)")
        elif n:
            out["remediation"].append(f"IndexNow ping HTTP {status} (not accepted)")

    chronic = chronic_urls(not_indexed, prior_runs)
    if chronic and cid:
        states = {r["url"]: r["state"] for r in not_indexed}
        if seed_chronic_card(slug, cid, chronic, states, apply):
            out["remediation"].append(f"card seeded ({len(chronic)} chronic)")
        else:
            out["remediation"].append(f"card already open ({len(chronic)} chronic)")
    out["chronic"] = len(chronic)

    # ---- one client-readable ledger line per run
    if cid and out["sampled"]:
        detail = (f"Checked Google's index coverage: {out['indexed']} of "
                  f"{out['sampled']} sampled pages indexed")
        if apply and actionable:
            detail += (f"; re-submitted the sitemap and asked search engines "
                       f"to re-crawl {len(actionable)} page(s)")
        detail += "."
        work_log(cid, "routine", "index-watch", detail,
                 evidence={"sampled": out["sampled"], "indexed": out["indexed"],
                           "rate": out["rate"], "sitemap_urls": sitemap_n,
                           "remediation": out["remediation"]},
                 source="index_watchdog")
    return out


# ---------------------------------------------------------------------- main
def main() -> int:
    load_env()
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")):
        print("ERROR: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required.", file=sys.stderr)
        return 1
    ap = argparse.ArgumentParser(description="GSC index-coverage watchdog")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true",
                    help="fire remediation (sitemap resubmit + IndexNow + chronic cards)")
    ap.add_argument("--cap", type=int, default=DEFAULT_CAP,
                    help=f"max URL inspections per client (default {DEFAULT_CAP})")
    args = ap.parse_args()

    slugs = live_slugs() if args.all else [args.slug]
    print(f"index watchdog — {len(slugs)} live client(s), cap {args.cap}/client, "
          f"apply={args.apply}")
    rows = []
    for slug in slugs:
        print(f"== {slug}")
        try:
            r = run_client(slug, args.apply, args.cap)
        except Exception as e:  # noqa: BLE001 — one client must not sink the fleet
            r = {"slug": slug, "sampled": 0, "indexed": 0, "rate": None,
                 "crawled": 0, "discovered": 0, "unknown": 0, "excluded": 0,
                 "errors": 0, "chronic": 0, "remediation": [],
                 "note": f"ERROR {type(e).__name__}: {str(e)[:100]}"}
        rows.append(r)
        rate = f"{r['rate']:.0%}" if r.get("rate") is not None else "—"
        line = (f"   {r['sampled']} sampled, {r['indexed']} indexed ({rate}); "
                f"crawled-not-indexed {r['crawled']}, discovered {r['discovered']}, "
                f"unknown {r['unknown']}, excluded {r['excluded']}")
        if r.get("remediation"):
            line += " | " + ", ".join(r["remediation"])
        if r.get("note"):
            line += f" | NOTE: {r['note']}"
        print(line)

    print(f"\n{'client':42s} {'sampled':>7s} {'indexed':>7s} {'rate':>6s} "
          f"{'crawl':>5s} {'disc':>5s} {'unk':>4s} {'excl':>4s}")
    for r in rows:
        rate = f"{r['rate']:.0%}" if r.get("rate") is not None else "—"
        print(f"{r['slug']:42s} {r['sampled']:7d} {r['indexed']:7d} {rate:>6s} "
              f"{r['crawled']:5d} {r['discovered']:5d} {r['unknown']:4d} "
              f"{r['excluded']:4d}"
              + (f"   {r['note']}" if r.get("note") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
