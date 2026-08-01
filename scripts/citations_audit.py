#!/usr/bin/env python3
"""Citations discovery + NAP audit (Santino 2026-07-28, priority build).

For a client: take the CANONICAL business info (companies row — the app's
Business Information source-of-truth card), search each major directory for
their listing via DataForSEO SERP (site: queries), pre-populate the found
URLs into the app's Business Listings slots (user_integrations
provider='citations' connection_metadata.citation_urls — same keys the
Connect tab renders), and record a per-platform audit:

  found + phone matches      -> ok
  found + different phone    -> discrepancy (the Connect tab shows the diff)
  not found                  -> missing (amber slot in the app)

Phone extraction is best-effort (SERP snippet + page fetch where the
directory allows it); platforms that block bots still get URL discovery.
Results land in connection_metadata.nap_audit for the app to render.

Usage: citations_audit.py --slug crew-restoration-construction
       citations_audit.py --slug X --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from client_ops_sync import _sb, slug_map  # noqa: E402
from lead_audit import _dfs, _dfs_auth  # noqa: E402

DFS_SERP = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"

# key -> (site: filter, human label). Keys MUST match the app's
# CITATION_PLATFORMS so prepopulated URLs land in the right slots.
PLATFORMS = {
    "yelp": ("yelp.com/biz", "Yelp"),
    "bbb": ("bbb.org", "BBB"),
    "angi": ("angi.com", "Angi"),
    "homeadvisor": ("homeadvisor.com", "HomeAdvisor"),
    "thumbtack": ("thumbtack.com", "Thumbtack"),
    "facebook": ("facebook.com", "Facebook"),
    "apple_maps": ("maps.apple.com", "Apple Maps"),
    "bing_places": ("bing.com/maps", "Bing Places"),
    # Free application, AI-answer-cited listicles; we apply on the client's
    # behalf (us_create in the ledger, unlike the owner-identity platforms).
    "expertise": ("expertise.com", "Expertise.com"),
    # Round-out set (Santino 2026-07-31) — matches the app's Connect tab.
    "nextdoor": ("nextdoor.com", "Nextdoor"),
    "houzz": ("houzz.com", "Houzz"),
    "porch": ("porch.com", "Porch"),
    "homeguide": ("homeguide.com", "HomeGuide"),
    "yellowpages": ("yellowpages.com", "YellowPages"),
}

PHONE_RE = re.compile(r"\(?\b(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})\b")


def _norm_phone(s: str | None) -> str:
    d = re.sub(r"\D", "", s or "")
    return d[-10:] if len(d) >= 10 else d


def _page_scan(url: str, street_no: str, postal: str, domain: str) -> dict:
    """Best-effort NAP read from the listing page (many directories block
    bots — a None here means 'could not verify', never 'wrong'). Address and
    website checks only ever CONFIRM (True) or stay unknown (None): raw HTML
    is too unreliable to raise a mismatch alarm on."""
    out: dict = {"phone": None, "address_matches": None, "website_matches": None}
    try:
        r = requests.get(url, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"})
        if r.status_code != 200:
            return out
        html = r.text
        m = PHONE_RE.search(html)
        if m:
            out["phone"] = "".join(m.groups())
        if street_no and postal and street_no in html and postal in html:
            out["address_matches"] = True
        if domain and domain in html.lower():
            out["website_matches"] = True
    except Exception:
        pass
    return out


def _name_tokens(name: str) -> set:
    return {t for t in re.findall(r"[a-z]+", name.lower()) if len(t) > 3}


def _guard_ok(hay: str, toks: set) -> bool:
    """The business name's significant tokens must appear in the haystack
    (title+url) or it's not their listing."""
    hay = hay.lower()
    need = min(2, len(toks)) or 1
    return sum(1 for t in toks if t in hay) >= need


def _summary_text(name: str, results: dict, canon_phone: str) -> str:
    """Plain-English analysis for the Connect tab: what we found, what we
    entered, what happens next. Client-facing voice."""
    label = {k: v[1] for k, v in PLATFORMS.items()}
    ok = [label[k] for k, r in results.items() if r.get("status") == "found"
          and r.get("phone_matches")]
    unver = [label[k] for k, r in results.items() if r.get("status") == "found"
             and not r.get("phone_matches")]
    disc = [(label[k], r.get("phone_found")) for k, r in results.items()
            if r.get("status") == "discrepancy"]
    missing = [label[k] for k, r in results.items() if r.get("status") == "missing"]
    extra_ok = sum(1 for r in results.values()
                   if r.get("address_matches") or r.get("website_matches"))

    found_n = len(ok) + len(unver) + len(disc)
    parts = [f"We scanned the 8 major directories for {name} and found "
             f"{found_n} existing listing{'s' if found_n != 1 else ''}."]
    if ok:
        parts.append("Verified and consistent: " + ", ".join(ok)
                     + " — the phone number matches your Business Information"
                     + (" (address/website spot-checks passed too)" if extra_ok else "") + ".")
    if disc:
        for lbl, ph in disc:
            pretty = f"({ph[:3]}) {ph[3:6]}-{ph[6:]}" if ph and len(ph) == 10 else (ph or "a different number")
            parts.append(f"Needs a fix: {lbl} shows {pretty}, which doesn't match "
                         "your main number — inconsistent phone numbers dilute "
                         "your local rankings, so we'll get this corrected.")
    if unver:
        parts.append("Found but not yet verified (the directory blocks automated "
                     "checks): " + ", ".join(unver) + " — worth a quick look to "
                     "confirm the details match.")
    if missing:
        parts.append("Not found (yet): " + ", ".join(missing) + ". These are part "
                     "of our citations build-out — each new consistent listing "
                     "strengthens how Google and AI assistants verify your business.")
    if not canon_phone:
        parts.append("One thing we need from you: confirm your Business "
                     "Information above (especially the phone number) so every "
                     "listing can be checked against a single source of truth.")
    parts.append("Next steps: we re-audit monthly, fix any drift, and build out "
                 "the missing listings in priority order.")
    return "\n".join(parts)


def audit(slug: str, dry_run: bool = False) -> str:
    inv = {s: c for c, s in slug_map().items()}
    cid = inv.get(slug)
    if not cid:
        return f"{slug}: no company mapping"
    co = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}"
              "&select=name,phone,city,state,address,postal_code,website,integration_settings",
              prefer="return=representation") or [{}])[0]
    name = (co.get("name") or "").strip()
    canon_phone = _norm_phone(co.get("phone"))
    # OUR call-tracking numbers are valid matches too (Santino 2026-08-01:
    # Bing syncs from the GBP, whose primary IS the tracking number — that's
    # accepted policy, not a discrepancy).
    import json as _json
    _ints = co.get("integration_settings") or {}
    if isinstance(_ints, str):
        try:
            _ints = _json.loads(_ints)
        except ValueError:
            _ints = {}
    ok_phones = {canon_phone} | {
        _norm_phone(v) for v in ((_ints.get("call_tracking") or {}).values()
                                 if isinstance(_ints.get("call_tracking"), dict) else [])
        if _norm_phone(str(v))}
    ok_phones.discard("")
    city, state = (co.get("city") or "").strip(), (co.get("state") or "").strip()
    street_no = ((co.get("address") or "").strip().split(" ") or [""])[0]
    street_no = street_no if street_no.isdigit() else ""
    postal = (co.get("postal_code") or "").strip()
    domain = re.sub(r"^https?://(www\.)?", "", (co.get("website") or "").strip().lower()).split("/")[0]
    if not name:
        return f"{slug}: no company name"

    auth = _dfs_auth()
    results: dict = {}
    urls: dict = {}
    lines = [f"== {name} ({city}, {state}) — canonical phone {canon_phone or '?'}"]
    for key, (site, label) in PLATFORMS.items():
        q = f'site:{site} "{name}" {city}'
        try:
            items, cost, _ = _dfs(DFS_SERP, [{
                "keyword": q[:700], "location_code": 2840,
                "language_code": "en", "depth": 10}], auth)
        except Exception as e:
            results[key] = {"status": "error", "error": str(e)[:80]}
            continue
        organic = [i for i in items if isinstance(i, dict)
                   and i.get("type") == "organic" and i.get("url")]
        # NAME GUARD (first run: HomeAdvisor matched a different company and
        # Angi returned a category page).
        toks = _name_tokens(name)
        organic = [i for i in organic if _guard_ok(
            str(i.get("title") or "") + " " + str(i.get("url") or ""), toks)]
        if not organic:
            results[key] = {"status": "missing",
                            "checked_at": datetime.now(timezone.utc).isoformat()}
            lines.append(f"  {label:12s} NOT FOUND")
            continue
        best = organic[0]
        url = best["url"]
        urls[key] = url
        # phone: SERP snippet first, page fetch second (page fetch also
        # spot-checks address + website when the directory lets us read it)
        snippet = " ".join(str(best.get(k) or "") for k in ("description", "title"))
        m = PHONE_RE.search(snippet)
        scan = _page_scan(url, street_no, postal, domain)
        phone = "".join(m.groups()) if m else scan["phone"]
        entry = {"status": "found", "url": url,
                 "checked_at": datetime.now(timezone.utc).isoformat()}
        if scan["address_matches"]:
            entry["address_matches"] = True
        if scan["website_matches"]:
            entry["website_matches"] = True
        if phone:
            entry["phone_found"] = phone
            entry["phone_matches"] = (phone in ok_phones) if canon_phone else None
            if canon_phone and phone not in ok_phones:
                entry["status"] = "discrepancy"
                lines.append(f"  {label:12s} DISCREPANCY: shows {phone}, canonical {canon_phone}  {url[:60]}")
            else:
                lines.append(f"  {label:12s} ok ({phone})  {url[:60]}")
        else:
            lines.append(f"  {label:12s} found (phone unverifiable)  {url[:60]}")
        results[key] = entry

    if not dry_run:
        rows = _sb("GET", f"/rest/v1/user_integrations?client_id=eq.{cid}"
                   "&provider=eq.citations&select=id,connection_metadata",
                   prefer="return=representation") or []
        if rows:
            md = rows[0].get("connection_metadata") or {}
            existing_urls = md.get("citation_urls") or {}
            prev_auto = set(md.get("auto_slots") or [])
            toks = _name_tokens(name)
            keep: dict = {}
            for k, v in existing_urls.items():
                if not v:
                    continue
                if k in prev_auto:
                    continue  # ours — the fresh audit result replaces or drops it
                # Legacy self-heal: rows saved before auto_slots existed can hold
                # pre-name-guard relics (wrong company / category pages). If the
                # fresh audit says the listing is MISSING and the stored URL fails
                # the name guard, it was one of ours — drop it. A human-entered
                # URL for a real listing would have been found by the audit.
                if (results.get(k, {}).get("status") == "missing"
                        and not _guard_ok(v, toks)):
                    lines.append(f"  dropped stale auto URL for {k}: {v[:60]}")
                    continue
                keep[k] = v
            merged = {**urls, **keep}  # human URLs always win their slot
            # SERP variance guard: a slot we trust (kept URL) can come back
            # "missing" on a flaky search pass. Verify the stored URL directly
            # instead of alarming the client with a false NOT FOUND.
            for k, v in keep.items():
                if results.get(k, {}).get("status") != "missing":
                    continue
                scan = _page_scan(v, street_no, postal, domain)
                entry = {"status": "found", "url": v, "reconciled": True,
                         "checked_at": datetime.now(timezone.utc).isoformat()}
                if scan["phone"]:
                    entry["phone_found"] = scan["phone"]
                    entry["phone_matches"] = (scan["phone"] == canon_phone) if canon_phone else None
                    if canon_phone and scan["phone"] != canon_phone:
                        entry["status"] = "discrepancy"
                if scan["address_matches"]:
                    entry["address_matches"] = True
                if scan["website_matches"]:
                    entry["website_matches"] = True
                results[k] = entry
                lines.append(f"  reconciled {k} from stored URL (search missed it)")
            md["citation_urls"] = merged
            md["auto_slots"] = sorted(k for k in merged if k not in keep)
            md["nap_audit"] = results
            md["nap_audit_summary"] = {
                "text": _summary_text(name, results, canon_phone),
                "generated_at": datetime.now(timezone.utc).isoformat()}
            _sb("PATCH", f"/rest/v1/user_integrations?id=eq.{rows[0]['id']}",
                {"connection_metadata": md})
        else:
            _sb("POST", "/rest/v1/user_integrations", {
                "client_id": cid, "provider": "citations", "status": "active",
                "connection_metadata": {"citation_urls": urls,
                                        "auto_slots": sorted(urls),
                                        "nap_audit": results,
                                        "nap_audit_summary": {
                                            "text": _summary_text(name, results, canon_phone),
                                            "generated_at": datetime.now(timezone.utc).isoformat()}}})
    found = sum(1 for r in results.values() if r.get("status") in ("found", "discrepancy"))
    disc = sum(1 for r in results.values() if r.get("status") == "discrepancy")
    lines.append(f"  -> {found}/{len(PLATFORMS)} found, {disc} discrepancy(ies)"
                 + (" [dry-run, not saved]" if dry_run else " [saved to app]"))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    print(audit(a.slug, a.dry_run))
    return 0


if __name__ == "__main__":
    sys.exit(main())
