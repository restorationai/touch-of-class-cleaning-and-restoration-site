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

GOOGLE LISTING as a first-class source (Santino 2026-08-03): the client's
own GBP NAP is audited too — nap_audit gains a 'google_listing' entry (live
GBP API via their token, or the clients/{slug}.json gbp snapshot when not
yet OAuth-connected). A GBP-vs-card mismatch becomes the TOP-LINE of the
analysis text and demotes 'consistent' directory claims, because Google is
what customers and AI assistants see first (HomeLyft incident: GBP showed
228-325-1496 / 3200 B Ave while card+Yelp/BBB/Facebook showed 228-284-5200 /
1311 Spring St and the analysis said 'verified and consistent').

Usage: citations_audit.py --slug crew-restoration-construction
       citations_audit.py --slug X --dry-run
"""
from __future__ import annotations

import argparse
import json
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


def _google_listing_nap(slug: str, cid: str) -> dict | None:
    """The client's GOOGLE LISTING NAP — first-class audit source (Santino
    2026-08-03: the audit compared directories against the Business
    Information card but never against the GBP itself; HomeLyft's GBP showed
    228-325-1496 / 3200 B Ave while the card + Yelp/BBB/Facebook showed
    228-284-5200 / 1311 Spring St and the analysis still said 'verified and
    consistent'). Google is what customers and AI assistants see first, so
    its NAP is compared like a listing — and a mismatch outranks everything.

    Source order:
      1. live GBP API via the client's own business.manage token
         (gbp.find_location — same pattern as setup_ledger's gbp-verified
         card) for connected clients;
      2. clients/{slug}.json 'gbp' block (DataForSEO-checked snapshot with
         listing_phone/listing_address) for claimed-but-not-connected
         clients (HomeLyft's exact state);
      3. None when we have no GBP identity at all (no entry written).
    """
    rec: dict = {}
    rec_path = ROOT / "clients" / f"{slug}.json"
    if rec_path.exists():
        try:
            rec = json.loads(rec_path.read_text()).get("gbp") or {}
        except (json.JSONDecodeError, OSError):
            rec = {}
    try:
        import gbp as _gbp
        place = _gbp._place_id_from_connection(cid)
        if not place:
            pi = ROOT / "clients" / slug / "plan-input.json"
            if pi.exists():
                place = (json.loads(pi.read_text()).get("brand") or {}).get("place_id")
        place = place or rec.get("place_id")
        tok = _gbp.get_access_token(cid) if place else None
        loc = _gbp.find_location(tok, place) if tok and place else None
        if loc:
            addr = loc.get("storefrontAddress") or {}
            lines = [ln for ln in (addr.get("addressLines") or []) if ln]
            street = ", ".join(lines)
            locality = ", ".join(p for p in (addr.get("locality"),
                                             addr.get("administrativeArea"),
                                             addr.get("postalCode")) if p)
            return {"source": "gbp_api",
                    "phone": (loc.get("phoneNumbers") or {}).get("primaryPhone"),
                    "address": ", ".join(p for p in (street, locality) if p) or None,
                    "url": (loc.get("metadata") or {}).get("mapsUri")
                           or rec.get("listing_url")}
    except Exception:
        pass  # token refresh / API hiccup -> fall through to the snapshot
    if rec.get("listing_phone") or rec.get("listing_address"):
        return {"source": "client_record",
                "phone": rec.get("listing_phone"),
                "address": rec.get("listing_address"),
                "url": rec.get("listing_url")}
    return None


def _pretty(ph: str | None) -> str:
    return (f"({ph[:3]}) {ph[3:6]}-{ph[6:]}" if ph and len(ph) == 10
            else (ph or "a different number"))


def _name_tokens(name: str) -> set:
    return {t for t in re.findall(r"[a-z]+", name.lower()) if len(t) > 3}


def _guard_ok(hay: str, toks: set) -> bool:
    """The business name's significant tokens must appear in the haystack
    (title+url) or it's not their listing."""
    hay = hay.lower()
    need = min(2, len(toks)) or 1
    return sum(1 for t in toks if t in hay) >= need


def _summary_text(name: str, results: dict, canon_phone: str,
                  canon_addr: str = "") -> str:
    """Plain-English analysis for the Connect tab: what we found, what we
    entered, what happens next. Client-facing voice. The GOOGLE LISTING
    verdict is the TOP-LINE whenever it disagrees with the card (Santino
    2026-08-03) — Google is what customers and AI assistants see first, so
    a GBP mismatch outranks every directory finding below it."""
    label = {k: v[1] for k, v in PLATFORMS.items()}
    dirs = {k: r for k, r in results.items() if k in label}
    ok = [label[k] for k, r in dirs.items() if r.get("status") == "found"
          and r.get("phone_matches")]
    unver = [label[k] for k, r in dirs.items() if r.get("status") == "found"
             and not r.get("phone_matches")]
    disc = [(label[k], r.get("phone_found")) for k, r in dirs.items()
            if r.get("status") == "discrepancy"]
    missing = [label[k] for k, r in dirs.items() if r.get("status") == "missing"]
    extra_ok = sum(1 for r in dirs.values()
                   if r.get("address_matches") or r.get("website_matches"))

    g = results.get("google_listing") or {}
    g_mismatch = g.get("status") == "discrepancy"

    found_n = len(ok) + len(unver) + len(disc)
    parts = []
    if g_mismatch:
        g_shows = " / ".join(p for p in (
            _pretty(g.get("phone_found")) if g.get("phone_found") else None,
            g.get("address_found")) if p)
        card_shows = " / ".join(p for p in (
            _pretty(canon_phone) if canon_phone else None,
            canon_addr or None) if p)
        parts.append(
            "THE FIRST THING TO FIX: your Google listing shows a different "
            "phone/address than your other listings. Google currently shows "
            f"{g_shows}, while your Business Information"
            + (f" (and {', '.join(ok)})" if ok else "")
            + f" shows {card_shows}. Google is what customers and AI "
            "assistants see first, so this is the top priority — we'll "
            "confirm with you which version is current, then align your "
            "Google listing and every directory below to that one answer.")
    elif g.get("status") == "found" and (g.get("phone_matches")
                                         or g.get("address_matches")):
        parts.append("Your Google listing matches your Business Information — "
                     "the anchor customers and AI assistants see first is "
                     "consistent.")
    parts.append(f"We scanned the {len(PLATFORMS)} major directories for {name} "
                 f"and found {found_n} existing "
                 f"listing{'s' if found_n != 1 else ''}.")
    if ok:
        line = ("Consistent with your Business Information: " + ", ".join(ok)
                + " — the phone number matches your Business Information"
                + (" (address/website spot-checks passed too)" if extra_ok else "") + ".")
        if g_mismatch:
            line += (" Note: because your Google listing shows different "
                     "details (see above), these can't count as fully "
                     "consistent until Google agrees.")
        parts.append(line)
    if disc:
        for lbl, ph in disc:
            parts.append(f"Needs a fix: {lbl} shows {_pretty(ph)}, which doesn't match "
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
    _ints = co.get("integration_settings") or {}
    if isinstance(_ints, str):
        try:
            _ints = json.loads(_ints)
        except ValueError:
            _ints = {}
    # call_tracking values are nested dicts on newer rows ({"gbp": {"number":
    # ...}}) and bare strings on older ones — flood-fixers crashed the audit
    # 2026-08-03 when a dict hit _norm_phone directly.
    _ct = _ints.get("call_tracking") if isinstance(_ints.get("call_tracking"), dict) else {}
    _ct_nums = [(v.get("number") or "") if isinstance(v, dict) else str(v or "")
                for v in (_ct or {}).values()]
    ok_phones = {canon_phone} | {_norm_phone(v) for v in _ct_nums if _norm_phone(v)}
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

    # ---- GOOGLE LISTING first (first-class source, Santino 2026-08-03) ----
    google = _google_listing_nap(slug, cid)
    g_phone = ""
    if google:
        g_phone = _norm_phone(google.get("phone"))
        g_addr = (google.get("address") or "").strip()
        g_no = (g_addr.split(" ") or [""])[0]
        g_no = g_no if g_no.isdigit() else ""
        addr_matches = (g_no == street_no) if (street_no and g_no) else None
        g_entry: dict = {"status": "found", "source": google["source"],
                         "checked_at": datetime.now(timezone.utc).isoformat()}
        if google.get("url"):
            g_entry["url"] = google["url"]
        if g_phone:
            g_entry["phone_found"] = g_phone
            g_entry["phone_matches"] = (g_phone in ok_phones) if canon_phone else None
        if g_addr:
            g_entry["address_found"] = g_addr
        if addr_matches is not None:
            g_entry["address_matches"] = addr_matches
        if (canon_phone and g_phone and g_phone not in ok_phones) \
                or addr_matches is False:
            g_entry["status"] = "discrepancy"
            lines.append(f"  {'Google':12s} MISMATCH: GBP shows "
                         f"{_pretty(g_phone) if g_phone else '?'}"
                         + (f" / {g_addr}" if g_addr else "")
                         + f" vs card {_pretty(canon_phone)} [{google['source']}]")
        else:
            lines.append(f"  {'Google':12s} ok ({g_phone or 'no phone read'}) "
                         f"[{google['source']}]")
        results["google_listing"] = g_entry
    else:
        lines.append(f"  {'Google':12s} no GBP identity known (not connected, "
                     "no gbp block) — skipped")
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
        # CITY GUARD (2026-09-13, All Pro: SERP matched three different
        # same-name companies in other cities/states — name tokens can't
        # tell twins apart, geography can).
        from citations_sync import city_guard as _cg, client_cities as _cc
        conflict = _cg(url, _cc(slug) | ({city} if city else set()), state)
        if conflict:
            results[key] = {"status": "wrong_entity", "url": url,
                            "note": f"city guard: {conflict}",
                            "checked_at": datetime.now(timezone.utc).isoformat()}
            lines.append(f"  {label:12s} WRONG ENTITY ({conflict})  {url[:60]}")
            continue
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

    # Mark which directory phones agree with the GOOGLE LISTING itself — the
    # app can render "consistent with your card but not with Google" states.
    if g_phone:
        for k, r in results.items():
            if k != "google_listing" and r.get("phone_found"):
                r["matches_google_listing"] = (r["phone_found"] == g_phone)

    if not dry_run:
        rows = _sb("GET", f"/rest/v1/user_integrations?client_id=eq.{cid}"
                   "&provider=eq.citations&select=id,connection_metadata",
                   prefer="return=representation") or []
        if rows:
            md = rows[0].get("connection_metadata") or {}
            existing_urls = md.get("citation_urls") or {}
            prev_nap = md.get("nap_audit") or {}
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
                    # ok_phones (canonical + our tracking numbers), matching
                    # the main loop — a reconciled listing showing OUR
                    # call-tracking number is accepted policy, not a
                    # discrepancy (same rule as the SERP path above).
                    entry["phone_matches"] = (scan["phone"] in ok_phones) if canon_phone else None
                    if g_phone:
                        entry["matches_google_listing"] = (scan["phone"] == g_phone)
                    if canon_phone and scan["phone"] not in ok_phones:
                        entry["status"] = "discrepancy"
                if scan["address_matches"]:
                    entry["address_matches"] = True
                if scan["website_matches"]:
                    entry["website_matches"] = True
                results[k] = entry
                lines.append(f"  reconciled {k} from stored URL (search missed it)")
            # PROVENANCE PRESERVATION (Santino 2026-08-04: the 08-03 fleet
            # audit rewrote HomeLyft's homeguide entry via the reconcile path
            # and DROPPED source:"browser_agent" — the app's "Created by
            # Rank AI" label had nothing to match). Fresh audit entries carry
            # audit facts only; creation provenance written by
            # listings.record_listing (source, created_at) must survive every
            # re-found/reconcile update. checked_at stays fresh (it means
            # "last checked"); the ORIGINAL creation stamp is preserved as
            # created_at — seeded from the prior entry's checked_at the first
            # time a browser_agent entry is rewritten without one.
            for k, prev in prev_nap.items():
                if k == "google_listing" or not isinstance(prev, dict):
                    continue  # google_listing's 'source' is per-run (gbp_api/
                    #           client_record) — never carried forward
                cur = results.get(k)
                if not isinstance(cur, dict):
                    continue
                # WRONG-ENTITY STICKINESS (2026-09-13): a slot marked
                # wrong_entity stays wrong for that URL forever — the next
                # audit re-finding the SAME name-twin listing must never
                # resurrect it as "found" (that re-pollutes sameAs). A
                # DIFFERENT url may claim the slot (a real listing appeared).
                if (prev.get("status") == "wrong_entity"
                        and str(cur.get("url") or "").rstrip("/")
                        == str(prev.get("url") or "").rstrip("/")):
                    results[k] = prev
                    continue
                if prev.get("source") and not cur.get("source"):
                    cur["source"] = prev["source"]
                created = prev.get("created_at") or (
                    prev.get("checked_at")
                    if prev.get("source") == "browser_agent" else None)
                if created and not cur.get("created_at"):
                    cur["created_at"] = created
            md["citation_urls"] = merged
            md["auto_slots"] = sorted(k for k in merged if k not in keep)
            md["nap_audit"] = results
            md["nap_audit_summary"] = {
                "text": _summary_text(name, results, canon_phone,
                                      (co.get("address") or "").strip()),
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
                                            "text": _summary_text(
                                                name, results, canon_phone,
                                                (co.get("address") or "").strip()),
                                            "generated_at": datetime.now(timezone.utc).isoformat()}}})
    dir_results = {k: r for k, r in results.items() if k != "google_listing"}
    found = sum(1 for r in dir_results.values() if r.get("status") in ("found", "discrepancy"))
    disc = sum(1 for r in dir_results.values() if r.get("status") == "discrepancy")
    missing = sum(1 for r in dir_results.values() if r.get("status") == "missing")
    g_mismatch = (results.get("google_listing") or {}).get("status") == "discrepancy"
    lines.append(f"  -> {found}/{len(PLATFORMS)} found, {disc} discrepancy(ies)"
                 + (", GOOGLE LISTING MISMATCH (top fix)" if g_mismatch else "")
                 + (" [dry-run, not saved]" if dry_run else " [saved to app]"))
    if not dry_run:
        # Work ledger (fail-open): one audit-run line item per client.
        from work_log import work_log
        detail = (("Google listing NAP mismatch flagged as the top fix. "
                   if g_mismatch else "")
                  + f"Directory listings audit across {len(PLATFORMS)} major "
                  f"platforms: {found} listing(s) found, {missing} still to "
                  f"build")
        detail += (f", {disc} with mismatched details flagged for correction."
                   if disc else ".")
        work_log(cid, "citations", "audit-run", detail,
                 evidence={"slug": slug, "found": found, "missing": missing,
                           "discrepancies": disc,
                           "platforms": {k: r.get("status")
                                         for k, r in results.items()}},
                 source="citations_audit.py")
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
