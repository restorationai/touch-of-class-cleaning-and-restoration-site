#!/usr/bin/env python3
"""social_discovery.py — find each client's social profiles from their OWN
website footers (build queue: social discovery sweep, data pass).

WHY footers first: a link the business put on its own site is the strongest
NAP-match evidence there is — no name-collision risk (the web is full of
same-named restoration companies). Clients with no crawlable site are
reported for the web-search pass later, never guessed.

Writes citation_listings rows (kind='social', social_state='found',
status='created', listing_url=profile URL, source='site-footer discovery').
Idempotent: existing (company_id, directory) rows are NEVER overwritten —
a 'confirmed' or 'connected_to_gsc' row must survive re-runs.

Sources per company, first that answers:
  1. marketing_sites.domain when apex_live (our live build carries the
     client's real socials only if we put them there — still evidence)
  2. companies.website / clients/{slug}.json old-site domain
CLI: python3 scripts/social_discovery.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import requests

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
       or os.environ["SUPABASE_SERVICE_KEY"])
HDR = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# href patterns -> directory name. Share/intent/plugin URLs are NOT profiles.
SOCIAL_PATTERNS = {
    "facebook": re.compile(r"https?://(?:www\.)?facebook\.com/(?!sharer|share|plugins|dialog|login|events/|groups/|hashtag/)([A-Za-z0-9_.\-]+)/?", re.I),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/(?!p/|explore|reel)([A-Za-z0-9_.]+)/?", re.I),
    "linkedin": re.compile(r"https?://(?:www\.)?linkedin\.com/(company|in)/([A-Za-z0-9_\-%.]+)/?", re.I),
    "tiktok": re.compile(r"https?://(?:www\.)?tiktok\.com/@([A-Za-z0-9_.]+)/?", re.I),
    "youtube": re.compile(r"https?://(?:www\.)?youtube\.com/(@[A-Za-z0-9_.\-]+|channel/[A-Za-z0-9_\-]+|c/[A-Za-z0-9_\-]+)/?", re.I),
    "x": re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/(?!intent|share|search)([A-Za-z0-9_]+)/?", re.I),
}
GENERIC = {"pages", "profile", "home", "public", "sharer.php"}


def fetch(url: str) -> str:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=25,
                         allow_redirects=True)
        return r.text if r.ok else ""
    except Exception:  # noqa: BLE001
        return ""


def find_socials(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, pat in SOCIAL_PATTERNS.items():
        for m in pat.finditer(html or ""):
            handle = m.group(m.lastindex or 1).strip("/").lower()
            if handle in GENERIC or len(handle) < 2:
                continue
            out.setdefault(name, m.group(0).rstrip("/"))
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cos = requests.get(
        f"{SB}/rest/v1/companies?select=id,name,website&ilike=plan.rank%20ai"
        .replace("&ilike=plan.rank%20ai", "&plan=ilike.rank%20ai"),
        headers=HDR, timeout=30).json()
    sites = {s["company_id"]: s for s in requests.get(
        f"{SB}/rest/v1/marketing_sites?select=company_id,domain,apex_live",
        headers=HDR, timeout=30).json()}
    existing = {(r["company_id"], r["directory"]) for r in requests.get(
        f"{SB}/rest/v1/citation_listings?select=company_id,directory",
        headers=HDR, timeout=30).json()}

    rows, no_site = [], []
    for co in cos:
        cid = co["id"]
        candidates = []
        ms = sites.get(cid) or {}
        if ms.get("apex_live") and ms.get("domain") and ".invalid" not in ms["domain"]:
            candidates.append(f"https://{ms['domain']}/")
        if co.get("website"):
            w = co["website"]
            candidates.append(w if w.startswith("http") else f"https://{w}")
        found: dict[str, str] = {}
        for url in candidates:
            html = fetch(url)
            if html:
                found = find_socials(html)
                if found:
                    break
        if not candidates:
            no_site.append(co.get("name") or cid)
            continue
        for platform, purl in found.items():
            if (cid, platform) in existing:
                continue
            rows.append({
                "company_id": cid, "directory": platform, "kind": "social",
                "status": "created", "listing_url": purl,
                "social_state": "found", "correction": None, "note":
                    "Found on the client's own website — awaiting client "
                    "confirm, then GSC association.",
                "observed_name": None, "observed_address": None,
                "observed_phone": None, "source": "site-footer discovery"})
            print(f"  {co.get('name', cid)}: {platform} -> {purl}")

    print(f"\n{len(rows)} new social row(s); {len(no_site)} compan(ies) with "
          "no crawlable site (web-search pass later): "
          + ", ".join(no_site[:10]))
    if rows and not args.dry_run:
        r = requests.post(
            f"{SB}/rest/v1/citation_listings?on_conflict=company_id,directory",
            headers={**HDR, "Content-Type": "application/json",
                     "Prefer": "resolution=ignore-duplicates,return=minimal"},
            json=rows, timeout=60)
        print("write:", r.status_code, r.text[:120])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
