#!/usr/bin/env python3
"""bing_webmaster.py - weekly Bing Webmaster Tools upkeep for every live site
(Santino 2026-10-01: "Same thing for bing search console?").

Until now Bing only ever heard from us through IndexNow pings on deploy
(build_site.indexnow_ping). No site was registered in Bing Webmaster Tools,
no sitemap was submitted there, and nobody looked at Bing's crawl/index
numbers, even though Bing's index is what ChatGPT search and Copilot
retrieve from. This script closes that loop through the Bing Webmaster API:

  1. ensure the site exists in the agency's Bing Webmaster account
     (AddSite; with --provision, verify it headlessly by placing Bing's
     CNAME  {AuthenticationCode}.{domain} -> verify.bing.com  in our
     Cloudflare zone, then VerifySite). The Mac Mini's one-time
     "Import from Google Search Console" in the BWT UI does the same thing
     in bulk; either path is fine and both are idempotent.
  2. submit sitemap-index.xml (SubmitFeed)
  3. submit a URL batch (SubmitUrlBatch), capped by GetUrlSubmissionQuota:
     pages the Google watchdog last saw NOT indexed first (ops_kv
     index-watch:{slug}), then the homepage, services and city pages
  4. read basic crawl/index stats (GetCrawlStats: pages crawled, pages in
     index, crawl errors) + open crawl issues, store them in ops_kv
     'bing-watch:{slug}' with an 8-run history, and write one
     client-readable marketing_work_log line.

KEY: BING_WEBMASTER_API_KEY (Bing Webmaster Tools > Settings > API access >
API Key, generated while signed in as the agency account). Without it every
command prints one line and exits 0, so the weekly job is safe to wire
before the key exists.

API: JSON endpoint https://ssl.bing.com/webmaster/api.svc/json/{Method}?apikey=
(reference: learn.microsoft.com/dotnet/api/microsoft.bing.webmaster.api.interfaces.iwebmasterapi).
Responses wrap the payload in {"d": ...}; dates come as "/Date(ms-tz)/".

Usage:
  python3 scripts/bing_webmaster.py status                    # key present? sites in account
  python3 scripts/bing_webmaster.py weekly --slug narestco [--provision] [--dry-run]
  python3 scripts/bing_webmaster.py weekly --all [--provision]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

API = "https://ssl.bing.com/webmaster/api.svc/json/"
KEY_ENV = "BING_WEBMASTER_API_KEY"
KV_PREFIX = "bing-watch:"
HISTORY_KEEP = 8
BATCH_CAP = 100          # never more than this per site per week, quota permitting


def load_env() -> None:
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def api_key() -> str:
    return (os.environ.get(KEY_ENV) or "").strip()


# ------------------------------------------------------------------ API core
class BingError(RuntimeError):
    pass


def call(method: str, *, params: dict | None = None, body: dict | None = None):
    """GET when body is None, else POST JSON. Returns the unwrapped 'd'."""
    q = {"apikey": api_key(), **(params or {})}
    url = API + method + "?" + urllib.parse.urlencode(q)
    for attempt in range(3):
        try:
            if body is None:
                r = requests.get(url, timeout=45)
            else:
                r = requests.post(url, json=body, timeout=45,
                                  headers={"Content-Type": "application/json; charset=utf-8"})
        except requests.RequestException as e:
            if attempt == 2:
                raise BingError(f"{method}: {e}") from e
            time.sleep(3 * (attempt + 1))
            continue
        if r.status_code >= 500 and attempt < 2:
            time.sleep(3 * (attempt + 1))
            continue
        if not r.ok:
            raise BingError(f"{method} HTTP {r.status_code}: {r.text[:200]}")
        try:
            data = r.json()
        except ValueError:
            return None
        return data.get("d") if isinstance(data, dict) and "d" in data else data
    raise BingError(f"{method}: retries exhausted")


_DATE = re.compile(r"/Date\((-?\d+)")


def bdate(v) -> str | None:
    m = _DATE.search(str(v or ""))
    if not m:
        return None
    return datetime.fromtimestamp(int(m.group(1)) / 1000, timezone.utc).date().isoformat()


# ------------------------------------------------------------------ helpers
def _sb(method: str, path: str, body=None, prefer: str = "return=representation"):
    url = os.environ["SUPABASE_URL"].rstrip("/") + path
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    r = requests.request(method, url, json=body, timeout=30, headers={
        "apikey": key, "Authorization": f"Bearer {key}",
        "Content-Type": "application/json", "Prefer": prefer})
    r.raise_for_status()
    return r.json() if r.content else None


def kv_get(k: str):
    rows = _sb("GET", f"/rest/v1/ops_kv?k=eq.{urllib.parse.quote(k)}&select=v") or []
    return rows[0].get("v") if rows else None


def kv_put(k: str, v) -> None:
    _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
        {"k": k, "v": v, "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        prefer="resolution=merge-duplicates,return=minimal")


def record(slug: str) -> dict:
    return json.loads((ROOT / "clients" / f"{slug}.json").read_text())


def _host(u: str) -> str:
    h = urllib.parse.urlparse(u if "//" in u else "https://" + u).netloc.lower()
    return h[4:] if h.startswith("www.") else h


def user_sites() -> dict[str, dict]:
    """{bare host: site entry} for every site in the agency BWT account."""
    out = {}
    for s in call("GetUserSites") or []:
        if s.get("Url"):
            out[_host(s["Url"])] = s
    return out


# ------------------------------------------------------------- provisioning
def _cf(method: str, path: str, body=None) -> dict:
    r = requests.request(method, "https://api.cloudflare.com/client/v4" + path,
                         json=body, timeout=30, headers={
                             "Authorization": "Bearer " + os.environ["CLOUDFLARE_API_TOKEN"],
                             "Content-Type": "application/json"})
    return r.json()


def provision(domain: str, site: dict | None) -> tuple[dict | None, str]:
    """AddSite (if missing) + CNAME verification through our Cloudflare zone."""
    site_url = f"https://{domain}/"
    if site is None:
        call("AddSite", body={"siteUrl": site_url})
        site = user_sites().get(domain)
        if site is None:
            return None, "AddSite returned but the site is not listed"
    if site.get("IsVerified"):
        return site, "already verified"
    code = (site.get("AuthenticationCode") or "").strip()
    if not code:
        return site, "no AuthenticationCode from Bing; verify via the Mini GSC import"
    if not os.environ.get("CLOUDFLARE_API_TOKEN"):
        return site, "CLOUDFLARE_API_TOKEN unset; cannot place verification CNAME"
    zones = _cf("GET", f"/zones?name={domain}").get("result") or []
    if not zones:
        return site, "no Cloudflare zone on our account; verify via the Mini GSC import"
    zid = zones[0]["id"]
    name = f"{code}.{domain}"
    have = _cf("GET", f"/zones/{zid}/dns_records?type=CNAME&name={name}").get("result") or []
    if not have:
        _cf("POST", f"/zones/{zid}/dns_records", {"type": "CNAME", "name": name,
                                                  "content": "verify.bing.com",
                                                  "proxied": False, "ttl": 300})
    for attempt in range(4):
        try:
            ok = call("VerifySite", body={"siteUrl": site.get("Url") or site_url})
        except BingError as e:
            ok = False
            last = str(e)[:100]
        else:
            last = ""
        if ok:
            site["IsVerified"] = True
            return site, "verified via CNAME"
        time.sleep(20 * (attempt + 1))
    return site, f"verification pending (CNAME placed; Bing will re-check) {last}".strip()


# ---------------------------------------------------------------- weekly
def batch_urls(slug: str, domain: str) -> list[str]:
    base = f"https://{domain}"
    urls: list[str] = []
    try:
        iw = kv_get("index-watch:" + slug) or {}
        urls += [r["url"] for r in (iw.get("not_indexed") or []) if r.get("url")]
    except Exception:  # noqa: BLE001
        pass
    urls.append(f"{base}/")
    try:
        import build_site  # noqa: PLC0415 (reuse the sitemap reader)
        sm = build_site.collect_live_urls(domain, cap=2000)
    except Exception:  # noqa: BLE001
        sm = []
    urls += [u for u in sm if re.fullmatch(r"/services/(?:[^/]+/)?", u[len(base):])]
    urls += [u for u in sm if re.fullmatch(r"/(?:service-areas|locations)/[^/]+/", u[len(base):])]
    seen, out = set(), []
    for u in urls:
        if u.startswith(base) and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def weekly(slug: str, *, provision_missing: bool, dry_run: bool) -> dict:
    rec = record(slug)
    domain = rec["domain"].strip().lower().rstrip("/")
    out = {"slug": slug, "domain": domain, "notes": []}
    sites = user_sites()
    site = sites.get(domain)
    if site is None or not site.get("IsVerified"):
        if not provision_missing:
            out["notes"].append("not registered/verified in Bing Webmaster Tools "
                                "(run with --provision or the Mini GSC import)")
            return out
        if dry_run:
            out["notes"].append("[dry-run] would AddSite + CNAME-verify")
            return out
        site, note = provision(domain, site)
        out["notes"].append(note)
        if not site or not site.get("IsVerified"):
            return out
    site_url = site.get("Url") or f"https://{domain}/"
    feed = f"https://{domain}/sitemap-index.xml"

    if dry_run:
        out["notes"].append(f"[dry-run] would SubmitFeed {feed}")
    else:
        try:
            call("SubmitFeed", body={"siteUrl": site_url, "feedUrl": feed})
            out["sitemap"] = "submitted"
        except BingError as e:
            out["sitemap"] = f"failed: {str(e)[:120]}"

    quota = None
    try:
        q = call("GetUrlSubmissionQuota", params={"siteUrl": site_url}) or {}
        quota = int(q.get("DailyQuota") or 0)
    except (BingError, ValueError, TypeError):
        pass
    urls = batch_urls(slug, domain)[: min(BATCH_CAP, quota if quota is not None else 10)]
    if urls and not dry_run:
        try:
            call("SubmitUrlBatch", body={"siteUrl": site_url, "urlList": urls})
            out["urls_submitted"] = len(urls)
        except BingError as e:
            out["urls_submitted"] = 0
            out["notes"].append(f"url batch failed: {str(e)[:120]}")
    elif urls:
        out["notes"].append(f"[dry-run] would submit {len(urls)} URL(s)")
    out["quota_daily"] = quota

    stats = {}
    try:
        rows = call("GetCrawlStats", params={"siteUrl": site_url}) or []
        rows = sorted(rows, key=lambda r: bdate(r.get("Date")) or "")
        if rows:
            last = rows[-1]
            stats = {"date": bdate(last.get("Date")),
                     "in_index": last.get("InIndex"),
                     "crawled_pages": last.get("CrawledPages"),
                     "crawl_errors": last.get("CrawlErrors"),
                     "in_links": last.get("InLinks"),
                     "blocked_by_robots": last.get("BlockedByRobotsTxt")}
    except BingError as e:
        out["notes"].append(f"crawl stats: {str(e)[:100]}")
    try:
        issues = call("GetCrawlIssues", params={"siteUrl": site_url}) or []
        stats["crawl_issues"] = len(issues)
    except BingError:
        pass
    out["stats"] = stats

    if not dry_run:
        _store(slug, out)
    return out


def _store(slug: str, out: dict) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        prev = kv_get(KV_PREFIX + slug) or {}
    except Exception:  # noqa: BLE001
        prev = {}
    hist = (prev.get("history") or []) + [{"checked_at": now, **(out.get("stats") or {})}]
    v = {"checked_at": now, "sitemap": out.get("sitemap"),
         "urls_submitted": out.get("urls_submitted", 0),
         "quota_daily": out.get("quota_daily"), "stats": out.get("stats"),
         "notes": out.get("notes"), "history": hist[-HISTORY_KEEP:]}
    try:
        kv_put(KV_PREFIX + slug, v)
    except Exception as e:  # noqa: BLE001
        print(f"  warn: ops_kv write failed ({str(e)[:80]})")
    try:
        from index_watchdog import company_id_for  # noqa: PLC0415
        from work_log import work_log  # noqa: PLC0415
        cid = company_id_for(slug)
        st = out.get("stats") or {}
        detail = "Submitted the sitemap to Bing Webmaster Tools"
        if out.get("urls_submitted"):
            detail += f" and asked Bing to crawl {out['urls_submitted']} page(s)"
        if st.get("in_index") is not None:
            detail += f"; Bing reports {st['in_index']} page(s) in its index"
        work_log(cid, "site", "bing-webmaster", detail + ".",
                 evidence={k: out.get(k) for k in ("sitemap", "urls_submitted", "stats")},
                 source="bing_webmaster")
    except Exception as e:  # noqa: BLE001
        print(f"  warn: work log failed ({str(e)[:80]})")


# ---------------------------------------------------------------------- CLI
def main() -> int:
    load_env()
    ap = argparse.ArgumentParser(description="Bing Webmaster Tools weekly upkeep")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    w = sub.add_parser("weekly")
    g = w.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true")
    w.add_argument("--provision", action="store_true",
                   help="AddSite + CNAME-verify sites missing from the account")
    w.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not api_key():
        print(f"{KEY_ENV} not set: Bing Webmaster upkeep skipped (IndexNow on "
              "deploy still runs). Ask: generate it in Bing Webmaster Tools > "
              "Settings > API access > API Key.")
        return 0

    if a.cmd == "status":
        try:
            sites = user_sites()
        except BingError as e:
            print(f"key present but the API rejected it: {e}")
            return 1
        print(f"key OK; {len(sites)} site(s) in the account")
        for h, s in sorted(sites.items()):
            print(f"  {h:40s} verified={s.get('IsVerified')}")
        return 0

    if a.all:
        from index_watchdog import live_slugs  # noqa: PLC0415
        slugs = live_slugs()
    else:
        slugs = [a.slug]
    rc = 0
    for s in slugs:
        try:
            r = weekly(s, provision_missing=a.provision, dry_run=a.dry_run)
        except Exception as e:  # noqa: BLE001 (one site never sinks the run)
            print(f"{s}: ERROR {type(e).__name__}: {str(e)[:160]}")
            rc = 1
            continue
        st = r.get("stats") or {}
        print(f"{s}: sitemap={r.get('sitemap', '-')} urls={r.get('urls_submitted', 0)} "
              f"in_index={st.get('in_index', '-')} crawled={st.get('crawled_pages', '-')} "
              f"errors={st.get('crawl_errors', '-')}"
              + (f" | {'; '.join(r['notes'])}" if r.get("notes") else ""))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
