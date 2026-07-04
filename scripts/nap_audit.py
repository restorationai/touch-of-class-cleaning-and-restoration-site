#!/usr/bin/env python3
"""
Rank AI — NAP consistency audit (name / address / phone across listings).

Canonical NAP comes from clients/{slug}/plan-input.json (brand block) plus the
client domain from clients/{slug}.json. Listing sources to check live in
clients/{slug}/citations.json (seeded manually; grow it as get_listed actions
complete). For each client the audit:

  1. Google Maps — DataForSEO /v3/serp/google/maps/live/advanced at the client's
     lat/lng searching the brand name; the client's own listing is matched by
     place_id / cid and its title/phone/address compared to canonical.
  2. GBP snapshot — marketing_gbp_profiles row (phone/address) vs canonical.
  3. Each citations.json URL — plain fetch with a browser UA first; bot-blocked
     sites (Yelp/BBB/HomeAdvisor 403 everything, incl. DataForSEO's crawler) fall
     back through DataForSEO /v3/on_page/content_parsing/live → the Google SERP
     snippet for the exact URL (what searchers/AI actually see) → the newest
     Wayback 200 capture. Phone numbers are extracted by regex, normalized to 10
     digits and frequency-ranked; addresses are matched on street number +
     street-name token overlap.
  4. Duplicate detection — two citations.json entries on the same platform.

Output: a per-client table, clients/{slug}/nap-audit.json (read by
`master_scheduler.py coverage` — fresh <35d + zero unresolved mismatches = OK),
and one marketing_action_plan action per NEW mismatch (action_type
'ai_citation_fix', idempotent via the same sha1 action_key scheme strategist.py
uses, so re-runs and strategist runs never duplicate or resurrect actions).

Usage:
  python3 scripts/nap_audit.py --slug narestco
  python3 scripts/nap_audit.py --all
  python3 scripts/nap_audit.py --slug narestco --dry-run   # no file/Supabase writes

Env (rank-ai/.env or CI secrets): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
(optional — GBP compare + action upsert skipped without them), DATAFORSEO_USERNAME
/ DATAFORSEO_PASSWORD (falls back to the MCP creds in ~/.claude.json locally).

Cost: 1 DFS maps call per client (~$0.002) + 1 content_parsing call per
bot-blocked listing (~$0.0006). Monthly cadence via weekly-maintenance.yml.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import geogrid_scan as gs  # noqa: E402  (load_dfs_creds)

DFS = "https://api.dataforseo.com"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

NAP_MAX_AGE_DAYS = 35  # keep in sync with COVERAGE_NAP_MAX_DAYS in master_scheduler.py

# Street-suffix / directional noise words dropped when tokenizing a street name.
_ADDR_NOISE = {"n", "s", "e", "w", "ne", "nw", "se", "sw", "north", "south", "east",
               "west", "st", "street", "ave", "avenue", "rd", "road", "dr", "drive",
               "blvd", "boulevard", "ln", "lane", "ct", "court", "hwy", "highway",
               "pl", "place", "way", "ste", "suite", "unit", "#"}

PHONE_RE = re.compile(r"(?:\+?1[\s\-\.\)]{0,2})?\(?\b([2-9]\d{2})\)?[\s\-\.\)]{0,2}([2-9]\d{2})[\s\-\.]{0,2}(\d{4})\b")


def _load_env_file() -> None:
    """Fail-soft .env loader (matches master_scheduler.py) — never overrides CI env."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


_load_env_file()


# ---------------------------------------------------------------- small helpers
def norm_phone(s: str) -> str:
    d = re.sub(r"\D", "", s or "")
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return d


def find_phones(text: str) -> list[str]:
    """Distinct US 10-digit phones in text, normalized to digit strings and
    ordered by frequency (a listing repeats the business phone; footer/org
    numbers appear once — e.g. BBB office numbers on a BBB profile)."""
    counts: dict[str, int] = {}
    for m in PHONE_RE.finditer(text or ""):
        d = "".join(m.groups())
        if len(d) == 10:
            counts[d] = counts.get(d, 0) + 1
    return sorted(counts, key=lambda d: -counts[d])


def street_parts(street_address: str) -> tuple[str, list[str]]:
    """('1530', ['dash', 'point']) — number + significant name tokens."""
    toks = re.findall(r"[a-z0-9#]+", (street_address or "").lower())
    number = toks[0] if toks and toks[0].isdigit() else ""
    names = [t for t in toks[1:] if t not in _ADDR_NOISE and not t.isdigit()]
    return number, names


def address_in_text(canonical_street: str, text: str) -> bool | None:
    """True = street number + a street-name token both present; None = nothing
    address-like found (unverifiable, not treated as a mismatch); False = number
    or name present without the other (suspicious partial)."""
    number, names = street_parts(canonical_street)
    low = (text or "").lower()
    num_hit = bool(number) and re.search(rf"\b{re.escape(number)}\b", low) is not None
    name_hit = any(re.search(rf"\b{re.escape(n)}\b", low) for n in names)
    if num_hit and (name_hit or not names):
        return True
    if not num_hit and not name_hit:
        return None
    return False


def norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower().replace("&", "and")).strip()


def name_matches(canonical: str, found: str) -> bool:
    ca, fo = norm_name(canonical), norm_name(found)
    if not (ca and fo):
        return False
    ca_t, fo_t = set(ca.split()), set(fo.split())
    core = ca_t - {"llc", "inc", "corp", "co", "the"}
    return core.issubset(fo_t | {"llc", "inc"}) or ca in fo or fo in ca


def platform_of(entry: dict) -> str:
    if entry.get("platform"):
        return entry["platform"].lower()
    host = urllib.parse.urlparse(entry.get("url", "")).netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def fmt_phone(d: str) -> str:
    return f"({d[:3]}) {d[3:6]}-{d[6:]}" if len(d) == 10 else (d or "—")


# ---------------------------------------------------------------- data access
def load_client(slug: str) -> dict:
    rec_p = ROOT / "clients" / f"{slug}.json"
    pi_p = ROOT / "clients" / slug / "plan-input.json"
    if not pi_p.exists():
        sys.exit(f"ERROR: {pi_p} not found.")
    rec = json.loads(rec_p.read_text()) if rec_p.exists() else {}
    pi = json.loads(pi_p.read_text())
    brand = pi.get("brand", {})
    primary = next((a for a in pi.get("service_areas", []) if a.get("primary")),
                   (pi.get("service_areas") or [{}])[0])
    return {
        "slug": slug,
        "company_id": rec.get("company_id") or _company_map().get(slug),
        "domain": rec.get("domain") or f"{slug}.com",
        "name": brand.get("display_name") or "",
        "legal_name": brand.get("legal_name") or "",
        "phone": brand.get("phone") or "",
        "phone_digits": norm_phone(brand.get("phone") or ""),
        "street_address": brand.get("street_address") or "",
        "city": primary.get("city") or "",
        "state": primary.get("state") or "",
        "postal_code": brand.get("postal_code") or "",
        "lat": brand.get("lat"), "lng": brand.get("lng"),
        "place_id": brand.get("place_id"), "google_cid": brand.get("google_cid"),
    }


def _company_map() -> dict:
    try:
        return json.loads((ROOT / "clients" / "company_map.json").read_text())
    except Exception:
        return {}


def _sb(method: str, path: str, body=None):
    """Supabase PostgREST call; None when creds are missing or the call fails."""
    sb = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not (sb and key):
        return None
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(sb + path, data=data, method=method, headers={
        "apikey": key, "Authorization": f"Bearer {key}",
        "Content-Type": "application/json", "Prefer": "return=minimal",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else []
    except Exception as e:  # noqa: BLE001
        print(f"    [warn] Supabase {method} {path.split('?')[0]} failed: {str(e)[:120]}",
              file=sys.stderr)
        return None


def _dfs_post(path: str, body: list) -> dict:
    u, p = gs.load_dfs_creds()
    auth = base64.b64encode(f"{u}:{p}".encode()).decode()
    req = urllib.request.Request(DFS + path, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def _http_get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return raw.decode("utf-8", errors="replace")


def _norm_url(u: str) -> str:
    p = urllib.parse.urlparse((u or "").lower())
    host = p.netloc.replace("www.", "").replace("m.yelp", "yelp")
    return host + p.path.rstrip("/")


def _serp_snippet(url: str) -> str | None:
    """Google's indexed snippet for the exact page (title + description often
    carry the listing's NAP even when the page itself bot-blocks everything —
    and it's what searchers/AI actually see). One DFS SERP call (~$0.002)."""
    resp = _dfs_post("/v3/serp/google/organic/live/advanced", [{
        "keyword": url, "location_code": 2840, "language_code": "en", "depth": 10}])
    task = (resp.get("tasks") or [{}])[0]
    if task.get("status_code") != 20000:
        return None
    items = ((task.get("result") or [{}])[0] or {}).get("items") or []
    hit = next((i for i in items if i.get("type") == "organic"
                and _norm_url(i.get("url", "")) == _norm_url(url)), None)
    if hit is None:
        return None
    return " | ".join(filter(None, [hit.get("title"), hit.get("description"),
                                    json.dumps(hit.get("extended_snippet") or "")]))


def _wayback_text(url: str) -> tuple[str, str] | None:
    """(text, 'wayback:YYYY-MM-DD') from the newest 200-status Wayback capture."""
    cdx = ("https://web.archive.org/cdx/search/cdx?output=json&limit=-1"
           "&filter=statuscode:200&url=" + urllib.parse.quote(url, safe=""))
    try:
        rows = json.loads(_http_get(cdx, timeout=60) or "[]")
        if len(rows) < 2:
            return None
        ts = rows[-1][1]
        text = _http_get(f"https://web.archive.org/web/{ts}/{url}", timeout=60)
        return text, f"wayback:{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
    except Exception:  # noqa: BLE001
        return None


def fetch_candidates(url: str, errs: list[str]):
    """Yield (text, fetch_method) per successful tier: plain browser-UA fetch →
    DataForSEO content_parsing → Google SERP snippet for the exact URL → newest
    Wayback 200 capture. The caller stops at the first tier that carries a NAP
    signal (a later tier may have it when an earlier one is thin — e.g. BBB's
    SERP snippet has no phone but its Wayback capture does). Failed tiers are
    recorded in errs."""
    try:
        yield _http_get(url), "http"
    except Exception as e:  # noqa: BLE001 — 403/999/timeout → next tier
        errs.append(f"http {getattr(e, 'code', type(e).__name__)}")
    try:
        resp = _dfs_post("/v3/on_page/content_parsing/live",
                         [{"url": url, "custom_user_agent": UA}])
        task = (resp.get("tasks") or [{}])[0]
        result = (task.get("result") or [{}])[0] or {}
        if task.get("status_code") == 20000 and (result.get("items_count") or 0) > 0:
            # Flatten the structured page_content to one searchable string.
            yield json.dumps(result.get("items")), "dfs_content_parsing"
        else:
            errs.append("dfs_content_parsing "
                        + str(result.get("crawl_status") or task.get("status_message")))
    except Exception as e:  # noqa: BLE001
        errs.append(f"dfs_content_parsing {type(e).__name__}")
    try:
        snippet = _serp_snippet(url)
        if snippet:
            yield snippet, "google_serp_snippet"
        else:
            errs.append("google_serp_snippet: page not indexed")
    except Exception as e:  # noqa: BLE001
        errs.append(f"google_serp_snippet {type(e).__name__}")
    wb = _wayback_text(url)
    if wb:
        yield wb
    else:
        errs.append("wayback: no 200 capture")


# ---------------------------------------------------------------- checks
def check_google_maps(c: dict) -> dict:
    r = {"platform": "google-maps", "url": f"https://www.google.com/maps?cid={c['google_cid']}"
         if c.get("google_cid") else None, "source": "dataforseo maps live"}
    try:
        resp = _dfs_post("/v3/serp/google/maps/live/advanced", [{
            "keyword": c["name"], "language_code": "en", "device": "desktop", "depth": 20,
            "location_coordinate": f"{c['lat']},{c['lng']},14z",
        }])
        task = (resp.get("tasks") or [{}])[0]
        if task.get("status_code") != 20000:
            raise RuntimeError(task.get("status_message"))
        items = ((task.get("result") or [{}])[0] or {}).get("items") or []
    except Exception as e:  # noqa: BLE001
        r.update(status="error", notes=f"maps lookup failed: {str(e)[:140]}")
        return r
    hit = next((i for i in items if i.get("place_id") == c.get("place_id")
                or str(i.get("cid") or "") == str(c.get("google_cid") or "")), None)
    if hit is None:
        hit = next((i for i in items if name_matches(c["name"], i.get("title", ""))), None)
        if hit is None:
            r.update(status="not_found",
                     notes=f"listing not found in top {len(items)} maps results for brand query")
            return r
        r["notes"] = "matched by name only (place_id/cid did not match plan-input)"
    found_phone = norm_phone(hit.get("phone") or "")
    r.update(status="ok",
             found_name=hit.get("title"), found_phone=fmt_phone(found_phone),
             found_address=hit.get("address"),
             name_match=name_matches(c["name"], hit.get("title", "")),
             phone_match=(found_phone == c["phone_digits"]) if found_phone else None,
             address_match=address_in_text(c["street_address"], hit.get("address") or ""))
    return r


def check_gbp_profile(c: dict) -> dict | None:
    if not c.get("company_id"):
        return None
    rows = _sb("GET", "/rest/v1/marketing_gbp_profiles?company_id=eq."
               + urllib.parse.quote(c["company_id"]) + "&select=title,phone,address")
    if rows is None:
        return None  # Supabase unreachable / no creds — skip silently (coverage handles GBP)
    if not rows:
        return {"platform": "gbp-profile", "source": "marketing_gbp_profiles",
                "status": "not_found", "notes": "no marketing_gbp_profiles row"}
    row = rows[0]
    found_phone = norm_phone(row.get("phone") or "")
    return {"platform": "gbp-profile", "source": "marketing_gbp_profiles", "status": "ok",
            "found_name": row.get("title"), "found_phone": fmt_phone(found_phone),
            "found_address": row.get("address"),
            "name_match": name_matches(c["name"], row.get("title") or ""),
            "phone_match": (found_phone == c["phone_digits"]) if found_phone else None,
            "address_match": address_in_text(c["street_address"], row.get("address") or "")}


def check_citation(c: dict, entry: dict) -> dict:
    url = entry["url"]
    r = {"platform": platform_of(entry), "url": url}
    errs: list[str] = []
    phones: list[str] = []
    addr_match: bool | None = None
    method = None
    for text, tier in fetch_candidates(url, errs):
        tier_phones = find_phones(text)
        tier_addr = address_in_text(c["street_address"], text)
        if method is None or tier_phones:
            phones, method = tier_phones, tier
        if tier_addr is not None and addr_match is None:
            addr_match = tier_addr
        if tier_phones:  # this tier carries the NAP signal — stop here
            break
    if method is None:
        note = "unverifiable — every fetch tier failed (" + "; ".join(errs)[:200] + ")"
        if entry.get("note"):
            note = entry["note"] + "; " + note
        r.update(status="unverified", notes=note)
        return r
    r.update(status="ok", fetch=method,
             phones_found=[fmt_phone(p) for p in phones[:6]],
             phone_match=(c["phone_digits"] in phones) if phones else None,
             address_match=addr_match)
    notes = []
    if entry.get("note"):
        notes.append(entry["note"])
    if method == "google_serp_snippet":
        notes.append("via Google snippet (page bot-blocked)")
    elif method.startswith("wayback:"):
        notes.append(f"via Wayback capture {method.split(':', 1)[1]} (page bot-blocked)")
    if not phones:
        notes.append("no phone number found on page")
    elif c["phone_digits"] not in phones:
        notes.append("canonical phone absent; page shows " +
                     ", ".join(fmt_phone(p) for p in phones[:3]))
    if r["address_match"] is None:
        notes.append("canonical street address not found on page")
    r["notes"] = "; ".join(notes)
    return r


# ---------------------------------------------------------------- action upsert
def action_key(action_type: str, target: str, dedupe: str) -> str:
    # strategist.py's sha1 scheme, namespaced with "nap:" so strategist's weekly
    # planned-row refresh (which deletes only its own unprefixed keys) never wipes
    # NAP-audit actions between monthly audit runs.
    return "nap:" + hashlib.sha1(f"{action_type}|{target}|{dedupe}".encode()).hexdigest()[:16]


def upsert_actions(c: dict, mismatches: list[dict]) -> int:
    """One ai_citation_fix action per NEW mismatch (skip action_keys already in
    the plan — matches authority_targets.py's idempotent insert pattern)."""
    cid = c.get("company_id")
    if not cid or not mismatches:
        return 0
    existing_rows = _sb("GET", "/rest/v1/marketing_action_plan?company_id=eq."
                        + urllib.parse.quote(cid) + "&select=action_key")
    if existing_rows is None:
        print("    [warn] Supabase unavailable — mismatch actions not written.", file=sys.stderr)
        return 0
    existing = {r["action_key"] for r in existing_rows if r.get("action_key")}
    now = datetime.now(timezone.utc).isoformat()
    inserts = []
    for m in mismatches:
        key = action_key("ai_citation_fix", m["target"], m["dedupe"])
        if key in existing:
            continue
        inserts.append({
            "company_id": cid, "rank_ai_slug": c["slug"], "action_type": "ai_citation_fix",
            "assigned_system": "manual", "title": m["title"], "rationale": m["rationale"],
            "target": m["target"], "impact": "high", "effort": "low", "status": "planned",
            "pinned": False, "priority": m.get("priority", 1),
            "action_key": key, "source_run_at": now,
        })
    if inserts:
        _sb("POST", "/rest/v1/marketing_action_plan", inserts)
    return len(inserts)


# ---------------------------------------------------------------- per-client run
def audit_client(slug: str, dry_run: bool = False) -> int:
    c = load_client(slug)
    cit_p = ROOT / "clients" / slug / "citations.json"
    listings = []
    if cit_p.exists():
        listings = json.loads(cit_p.read_text()).get("listings", [])

    # Merge client-entered listing URLs from the app (Marketing -> Connect ->
    # Business Listings card writes user_integrations provider='citations',
    # connection_metadata.citation_urls keyed yelp/bing_places/apple_maps/bbb/
    # angi/homeadvisor/thumbtack/facebook). App-entered URLs are additive;
    # citations.json stays the operator-curated base.
    try:
        cid = c.get("company_id")
        if cid:
            rows = _sb("GET", "/rest/v1/user_integrations?provider=eq.citations"
                       f"&client_id=eq.{urllib.parse.quote(str(cid))}"
                       "&select=connection_metadata") or []
            urls_seen = {e["url"] for e in listings}
            for r in rows:
                cu = ((r.get("connection_metadata") or {}).get("citation_urls") or {})
                for platform, url in cu.items():
                    if url and url not in urls_seen:
                        listings.append({"platform": platform, "url": url,
                                         "source": "app"})
                        urls_seen.add(url)
    except Exception as e:
        print(f"  [warn] app citation_urls fetch failed: {str(e)[:100]}")
    print(f"\n=== NAP audit: {slug} ===")
    print(f"canonical: {c['name']} | {c['phone']} | {c['street_address']}, "
          f"{c['city']}, {c['state']} {c['postal_code']} | {c['domain']}")
    if not cit_p.exists():
        print(f"  [warn] {cit_p} missing — only Google Maps + GBP snapshot checked.")

    results: list[dict] = []
    results.append(check_google_maps(c))
    gbp = check_gbp_profile(c)
    if gbp:
        results.append(gbp)
    for entry in listings:
        results.append(check_citation(c, entry))

    # Duplicate platforms in citations.json
    by_platform: dict[str, list[str]] = {}
    for entry in listings:
        by_platform.setdefault(platform_of(entry), []).append(entry["url"])
    duplicates = [{"platform": p, "urls": urls}
                  for p, urls in by_platform.items() if len(urls) > 1]

    # Collapse to the mismatch list that drives the coverage gate + action plan.
    mismatches: list[dict] = []
    for r in results:
        target = r.get("url") or r["platform"]
        if r.get("phone_match") is False:
            found = r.get("found_phone") or ", ".join(r.get("phones_found", [])[:3]) or "?"
            mismatches.append({
                "kind": "phone", "platform": r["platform"], "target": target, "dedupe": "nap-phone",
                "title": f"Fix wrong phone number on {r['platform']}",
                "rationale": f"NAP audit: {r['platform']} listing shows {found} but the canonical "
                             f"business phone is {c['phone']}. Wrong numbers split call volume and "
                             f"erode local-ranking NAP consistency — update the listing. {target}",
                "priority": 1,
            })
        if r.get("address_match") is False:
            found_addr = r.get("found_address") or "partial/other address fragments"
            mismatches.append({
                "kind": "address", "platform": r["platform"], "target": target, "dedupe": "nap-address",
                "title": f"Fix address on {r['platform']}",
                "rationale": f"NAP audit: {r['platform']} shows an address that doesn't match the "
                             f"canonical '{c['street_address']}, {c['city']}, {c['state']} "
                             f"{c['postal_code']}' (found: {found_addr}). {target}",
                "priority": 2,
            })
        if r.get("name_match") is False:
            mismatches.append({
                "kind": "name", "platform": r["platform"], "target": target, "dedupe": "nap-name",
                "title": f"Fix business name on {r['platform']}",
                "rationale": f"NAP audit: {r['platform']} shows '{r.get('found_name')}' but the "
                             f"canonical name is '{c['name']}'. {target}",
                "priority": 2,
            })
    for d in duplicates:
        mismatches.append({
            "kind": "duplicate", "platform": d["platform"], "target": d["urls"][-1], "dedupe": "nap-dup",
            "title": f"Remove/merge duplicate {d['platform']} listing",
            "rationale": "NAP audit: multiple live listings on the same platform split reviews and "
                         "confuse Google's entity matching. Claim and merge/close the duplicate: "
                         + " vs ".join(d["urls"]),
            "priority": 1,
        })

    # ---- table
    hdr = f"  {'PLATFORM':<14} {'PHONE FOUND':<28} {'PHONE':<7} {'ADDRESS':<9} NOTES"
    print("\n" + hdr + "\n  " + "-" * 100)
    def _flag(v):
        return {True: "OK", False: "MISS", None: "?"}[v]
    for r in results:
        phone = r.get("found_phone") or ", ".join(r.get("phones_found", [])[:2]) or "—"
        note = r.get("notes") or ""
        if r.get("status") not in ("ok", None):
            note = f"[{r['status']}] {note}"
        print(f"  {r['platform']:<14} {phone:<28} {_flag(r.get('phone_match')):<7} "
              f"{_flag(r.get('address_match')):<9} {note[:80]}")
    for d in duplicates:
        print(f"  {d['platform']:<14} {'—':<28} {'—':<7} {'—':<9} "
              f"DUPLICATE listing x{len(d['urls'])}")
    print(f"\n  {len(mismatches)} unresolved mismatch(es), {len(duplicates)} duplicate platform(s).")

    out = {
        "slug": slug, "checked_at": datetime.now(timezone.utc).isoformat(),
        "canonical": {k: c[k] for k in ("name", "phone", "street_address", "city",
                                        "state", "postal_code", "domain")},
        "results": results, "duplicates": duplicates,
        "mismatches": [{k: m[k] for k in ("kind", "platform", "target", "title")}
                       for m in mismatches],
    }
    if dry_run:
        print("  (dry-run — nap-audit.json not written, no actions upserted)")
        return 0
    out_p = ROOT / "clients" / slug / "nap-audit.json"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    added = upsert_actions(c, mismatches)
    out["actions_upserted"] = added
    out_p.write_text(json.dumps(out, indent=2) + "\n")
    print(f"  wrote {out_p.relative_to(ROOT)}; {added} new action(s) added to the plan.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="NAP consistency audit across listings")
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--slug", help="one client")
    grp.add_argument("--all", action="store_true", help="every active client")
    ap.add_argument("--dry-run", action="store_true", help="print only; no writes")
    args = ap.parse_args()

    if args.slug:
        return audit_client(args.slug, args.dry_run)
    rc = 0
    for p in sorted((ROOT / "clients").glob("*.json")):
        if p.name == "company_map.json":
            continue
        rec = json.loads(p.read_text())
        if rec.get("status") != "active":
            continue
        try:
            rc |= audit_client(rec["slug"], args.dry_run)
        except Exception as e:  # one client must never abort a scheduled --all run
            rc = 1
            print(f"  {rec.get('slug')}: ERROR ({type(e).__name__}: {str(e)[:200]}) — skipped",
                  file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
