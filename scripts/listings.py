#!/usr/bin/env python3
"""listings.py — immediate listing-URL write-back (Santino 2026-08-02).

When the browser agent (or any pipeline) CREATES a directory listing and
verifies its public URL, the URL must show up in the app's client-facing
Business Listings card immediately — not wait for the monthly citations
audit. record_listing() writes exactly what the card reads
(app AIMarketing.tsx, user_integrations provider='citations'):

  connection_metadata.citation_urls[platform] = url    -> fills the input
  connection_metadata.nap_audit[platform] = {"status": "found", "url", "checked_at"}
      -> renders "Found automatically — confirm this is your listing."
         (same shape scripts/citations_audit.py writes for a found listing)

The slot is deliberately NOT added to auto_slots: auto_slots marks SERP
guesses the monthly audit may replace or drop, but a browser-agent-verified
URL is trusted like a human entry — citations_audit keeps it, and its SERP
variance guard reconciles via a direct page fetch when Google hasn't indexed
the brand-new listing yet (instead of dropping it as "missing").

Also appends one client-readable marketing_work_log line item
(category 'citations'), e.g.
  "New business listing created for you on Houzz: {url}"

FAIL-OPEN BY CONTRACT: record_listing never raises — a write-back failure
must never break the playbook run that created the listing. On any error it
prints a warning and returns False.

Usage (module):   from listings import record_listing
                  record_listing(company_id, "houzz", url)
Usage (CLI):      listings.py --slug narestco --platform houzz --url https://...
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# key -> (label, accepted domains). Keys/domains MUST match the app's
# CITATION_PLATFORMS (AIMarketing.tsx) so the URL lands in the right slot
# and survives the card's own Save validation.
PLATFORMS: dict[str, tuple[str, tuple[str, ...]]] = {
    "yelp": ("Yelp", ("yelp.com",)),
    "bing_places": ("Bing Places", ("bing.com",)),
    "apple_maps": ("Apple Maps", ("apple.com",)),
    "bbb": ("BBB", ("bbb.org",)),
    "angi": ("Angi", ("angi.com", "angieslist.com")),
    "homeadvisor": ("HomeAdvisor", ("homeadvisor.com",)),
    "thumbtack": ("Thumbtack", ("thumbtack.com",)),
    "expertise": ("Expertise.com", ("expertise.com",)),
    "facebook": ("Facebook", ("facebook.com", "fb.com")),
    "nextdoor": ("Nextdoor", ("nextdoor.com",)),
    "houzz": ("Houzz", ("houzz.com",)),
    "porch": ("Porch", ("porch.com",)),
    "homeguide": ("HomeGuide", ("homeguide.com",)),
    "yellowpages": ("YellowPages", ("yellowpages.com",)),
}


def record_listing(company_id: str, platform: str, url: str,
                   status: str = "found", extra: dict | None = None) -> bool:
    """Write a verified listing URL into the app's Business Listings card +
    one work-ledger line. Fail-open: never raises, returns success bool.

    extra: optional audit-shape fields the caller verified on the live page
    (phone_found, phone_matches, address_matches, website_matches) — only
    claim phone_matches when the companies row actually has a canonical
    phone to match, mirroring citations_audit."""
    try:
        label, domains = PLATFORMS.get(platform, (None, ()))
        if not label:
            print(f"  [listings] warn: unknown platform '{platform}' — "
                  f"one of: {', '.join(PLATFORMS)}")
            return False
        url = (url or "").strip()
        if not url.startswith("https://") or not any(d in url.lower() for d in domains):
            print(f"  [listings] warn: '{url[:80]}' doesn't look like a "
                  f"{label} URL ({domains[0]}) — not recorded")
            return False
        if not company_id:
            print(f"  [listings] warn: no company_id — {label} URL not recorded")
            return False

        from client_ops_sync import _sb  # late import: keep failures inside the try
        now = datetime.now(timezone.utc).isoformat()
        entry = {"status": status, "url": url, "checked_at": now,
                 "source": "browser_agent", **(extra or {})}

        rows = _sb("GET", f"/rest/v1/user_integrations?client_id=eq.{company_id}"
                   "&provider=eq.citations&select=id,connection_metadata",
                   prefer="return=representation") or []
        if rows:
            md = rows[0].get("connection_metadata") or {}
            urls = dict(md.get("citation_urls") or {})
            auto = set(md.get("auto_slots") or [])
            existing = (urls.get(platform) or "").strip()
            if existing and existing != url and platform not in auto:
                # A human (or a verified earlier run) owns this slot — never
                # clobber it. The creation still gets its ledger line below.
                print(f"  [listings] keeping existing {label} URL "
                      f"({existing[:60]}) — new URL not written: {url[:60]}")
            else:
                urls[platform] = url
                # Verified URL is trusted like a human entry — release the
                # slot from auto_slots so the monthly audit never drops it.
                auto.discard(platform)
                md["citation_urls"] = urls
                md["auto_slots"] = sorted(auto)
                md["nap_audit"] = {**(md.get("nap_audit") or {}), platform: entry}
                _sb("PATCH", f"/rest/v1/user_integrations?id=eq.{rows[0]['id']}",
                    {"connection_metadata": md, "updated_at": now})
                print(f"  [listings] {label} -> {url[:80]} (status {status})")
        else:
            _sb("POST", "/rest/v1/user_integrations", {
                "client_id": company_id, "provider": "citations",
                "status": "active",
                "connection_metadata": {"citation_urls": {platform: url},
                                        "auto_slots": [],
                                        "nap_audit": {platform: entry}}})
            print(f"  [listings] {label} -> {url[:80]} (new citations row)")

        # Work ledger (itself fail-open) — client-readable line item.
        from work_log import work_log
        work_log(company_id, "citations", "listing-created",
                 f"New business listing created for you on {label}: {url}",
                 evidence={"platform": platform, "url": url, "status": status},
                 source="listings.py")
        return True
    except Exception as e:  # noqa: BLE001 — fail-open by contract
        print(f"  [listings] warn: {platform} URL not recorded "
              f"({str(e)[:120]})")
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--company-id")
    ap.add_argument("--platform", required=True, choices=sorted(PLATFORMS))
    ap.add_argument("--url", required=True)
    ap.add_argument("--status", default="found")
    a = ap.parse_args()
    cid = a.company_id
    if not cid:
        from work_log import company_id_for_slug
        cid = company_id_for_slug(a.slug)
        if not cid:
            print(f"{a.slug}: no company mapping")
            return 1
    return 0 if record_listing(cid, a.platform, a.url, a.status) else 1


if __name__ == "__main__":
    sys.exit(main())
