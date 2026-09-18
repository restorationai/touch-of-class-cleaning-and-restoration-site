#!/usr/bin/env python3
"""GBP listing-NAME-change suggestion cards -- SUGGESTION ONLY, never applied.

Renaming a Google Business Profile is the single riskiest GBP edit we can
recommend: keyword-added names are the top suspension trigger, and Google
policy requires the listing name to match real-world branding (signage, DBA,
website). So this script NEVER touches the GBP. It only researches and seeds
ONE human-actionable card per client into marketing_action_plan:

  1. Reads the client's CURRENT listing title from the Business Information
     API (read-only; local auth helper, deliberately not importing gbp.py).
  2. Researches candidate keyword terms for the client's vertical via the
     DataForSEO google_ads search_volume API, scoped to the client's metro
     (companies.city/state -> "City,State,United States"; falls back to US
     national volumes when DFS has no city-level location).
  3. Picks the highest-volume term. If the listing name already contains it,
     the client is SKIPPED (their name is already keyworded with the best
     term). Otherwise one claude-sonnet-5 call composes a natural keyworded
     name ("{Current Name} {Term}", adjusted to read like a real brand).
  4. Seeds ONE pinned suggestion card (action_type gbp_fix, assigned_system
     manual -- nothing automated consumes gbp_fix rows) via
     client_ops_sync.insert_plan_row. The action_key seed is stable per
     client, so reruns never duplicate; a changed suggestion retitles the
     open row in place.

The card's rationale carries the research numbers AND a BEST PRACTICES block
(DBA first, branding must match, revert on verification) so whoever acts on
it knows exactly what the safe path is.

Usage:
    python3 scripts/gbp_name_suggest.py [--dry-run] [--slug SLUG]
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = ROOT / "clients"
sys.path.insert(0, str(ROOT / "scripts"))

from client_ops_sync import (  # noqa: E402
    _sb, action_key, insert_plan_row, load_env, slug_map)

load_env()

import os  # noqa: E402  (after load_env so .env values are visible)

INFO_API = "https://mybusinessbusinessinformation.googleapis.com/v1"
ACCT_API = "https://mybusinessaccountmanagement.googleapis.com/v1"
DFS_VOLUME = "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live"
ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-5"

# Candidate keyword terms per vertical. Only verticals listed here get a
# suggestion; anything else (e.g. construction) is skipped rather than
# guessed -- a wrong-vertical keyword in a listing name is worse than none.
VERTICAL_TERMS = {
    "restoration": ["water damage restoration", "water cleanup",
                    "water damage repair", "restoration company"],
    "plumbing": ["plumber", "plumbing services", "emergency plumber",
                 "plumbing company"],
    # construction/GC (2026-09-18, TDI refresh exposed the missing set):
    # remodel intent carries the volume; "general contractor" is the
    # identity phrase Google's category corroborates.
    "construction": ["general contractor", "home remodeling",
                     "kitchen remodeling", "bathroom remodeling",
                     "custom home builder", "construction company"],
}

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut",
    "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota",
    "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}
_STATE_BY_NAME = {v.lower(): v for v in US_STATES.values()}

# The exact guidance every card carries. No em dashes anywhere (house LAW).
BEST_PRACTICES = (
    "BEST PRACTICES (read before acting; this is a SUGGESTION card, nothing "
    "on our side will ever change the listing name automatically):\n"
    "1. Google policy requires the listing name to match the business's "
    "real-world branding, exactly as it appears on signage, the website and "
    "legal documents. A keyword added only on Google violates policy.\n"
    "2. File a matching DBA (doing business as) BEFORE renaming the listing, "
    "so the keyworded name IS the real-world name.\n"
    "3. Update signage, website branding, logo text and social profiles to "
    "match the new name before or alongside the GBP change.\n"
    "4. Keyword-stuffed names are the single biggest suspension trigger on "
    "Google Business Profiles. Add at most this one term; never stack "
    "cities, extra services or superlatives into the name.\n"
    "5. If Google requests re-verification, flags the listing, or the "
    "profile gets suspended after the change, REVERT to the original name "
    "immediately and appeal from the original name.")


# --------------------------------------------------------------------------- #
# GBP read (local helper -- read-only; gbp.py deliberately not imported)
# --------------------------------------------------------------------------- #
def _place_id_from_connection(company_id: str) -> str | None:
    """place_id from the company's OWN google connection. Never another row's."""
    rows = _sb("GET", "/rest/v1/user_integrations?provider=eq.google"
               f"&select=connection_metadata&client_id=eq.{company_id}",
               prefer="return=representation") or []
    for row in rows:
        md = row.get("connection_metadata") or {}
        if md.get("place_id"):
            return md["place_id"]
    return None


def _get_access_token(company_id: str) -> str | None:
    """Refresh a business.manage access token; agency-row fallback (the agency
    account manages every client location, same pattern the fleet uses)."""
    rows = _sb("GET", "/rest/v1/user_integrations?provider=eq.google"
               "&select=client_id,refresh_token,connection_metadata"
               f"&client_id=eq.{company_id}",
               prefer="return=representation") or []
    if not rows:
        rows = _sb("GET", "/rest/v1/user_integrations?provider=eq.google"
                   "&select=client_id,refresh_token,connection_metadata&limit=5",
                   prefer="return=representation") or []
    for row in rows:
        rt = row.get("refresh_token") or (row.get("connection_metadata") or {}).get("refresh_token")
        if not rt:
            continue
        resp = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
            "client_secret": os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            "refresh_token": rt, "grant_type": "refresh_token"}, timeout=30)
        if resp.ok:
            return resp.json()["access_token"]
    return None


def _g(url: str, token: str) -> dict:
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=60)
    r.raise_for_status()
    return r.json()


def read_listing_title(company_id: str) -> str | None:
    """Current listing title, matched by the client's own place_id.

    A falsy place_id must NEVER be matched: the agency token manages every
    client location, and None == None would hand back a STRANGER's listing
    (the aaa-water-damage / ProBrite Gen incident, 2026-08-05)."""
    place_id = _place_id_from_connection(company_id)
    if not place_id:
        return None
    token = _get_access_token(company_id)
    if not token:
        return None
    for acct in _g(f"{ACCT_API}/accounts", token).get("accounts", []):
        url = (f"{INFO_API}/{acct['name']}/locations"
               "?readMask=name,title,categories,metadata&pageSize=100")
        for loc in _g(url, token).get("locations", []):
            if (loc.get("metadata") or {}).get("placeId") == place_id:
                return loc.get("title")
    return None


# --------------------------------------------------------------------------- #
# DataForSEO keyword research
# --------------------------------------------------------------------------- #
def load_dfs_creds() -> tuple[str, str]:
    """Env vars first; local fallback to the dataforseo MCP creds in
    ~/.claude.json (same pattern as geogrid_scan.py)."""
    u, p = os.environ.get("DATAFORSEO_USERNAME"), os.environ.get("DATAFORSEO_PASSWORD")
    if u and p:
        return u, p
    cfg_path = Path.home() / ".claude.json"
    if cfg_path.exists():
        found: dict = {}

        def walk(o):
            if isinstance(o, dict):
                if "DATAFORSEO_USERNAME" in o and "DATAFORSEO_PASSWORD" in o:
                    found["u"], found["p"] = o["DATAFORSEO_USERNAME"], o["DATAFORSEO_PASSWORD"]
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(json.loads(cfg_path.read_text()))
        if "u" in found:
            return found["u"], found["p"]
    sys.exit("ERROR: no DataForSEO credentials (env or ~/.claude.json).")


def metro_location(city: str | None, state: str | None) -> str | None:
    """DFS location_name for the client's metro, or None when unbuildable."""
    city = (city or "").strip()
    state = (state or "").strip()
    if not city or not state:
        return None
    full = US_STATES.get(state.upper()) or _STATE_BY_NAME.get(state.lower())
    if not full:
        return None
    return f"{city},{full},United States"


def search_volumes(auth: str, terms: list[str], location: str | None) -> tuple[dict, str]:
    """{term: monthly volume} plus the location label actually used. Tries the
    metro first; an unknown location_name (or a DFS task error) falls back to
    US national so one bad city string never kills the client's card."""
    def _post(body_loc: dict) -> list | None:
        r = requests.post(DFS_VOLUME,
                          headers={"Authorization": "Basic " + auth,
                                   "Content-Type": "application/json"},
                          json=[{"keywords": terms, "language_code": "en", **body_loc}],
                          timeout=60)
        task = (r.json().get("tasks") or [{}])[0]
        if int(task.get("status_code") or 0) >= 40000:
            return None
        return task.get("result") or []

    label, items = "United States (national)", None
    if location:
        items = _post({"location_name": location})
        if items:
            label = location.replace(",United States", "").replace(",", ", ")
    if items is None or not items:
        items = _post({"location_code": 2840}) or []
    vols = {i.get("keyword", "").lower(): int(i.get("search_volume") or 0)
            for i in items if isinstance(i, dict)}
    return {t: vols.get(t.lower(), 0) for t in terms}, label


# --------------------------------------------------------------------------- #
# Compose (one claude-sonnet-5 call per client; gbp.py's retry pattern, local)
# --------------------------------------------------------------------------- #
def _anthropic_json(system: str, user: str) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY in rank-ai/.env")
    last = ""
    messages = [{"role": "user", "content": user + "\n\nReply with ONLY the JSON object. "
                 "The very first character of your reply must be '{'. No preamble."}]
    for _attempt in (1, 2, 3):
        r = requests.post(ANTHROPIC_API, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"},
            data=json.dumps({"model": ANTHROPIC_MODEL, "max_tokens": 1024,
                             "system": system, "messages": messages}), timeout=120)
        if r.status_code in (429, 500, 503, 529):
            last = f"HTTP {r.status_code}"
            continue
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json().get("content", []))
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        if not text:
            last = "empty response"
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
            last = f"non-JSON: {text[:120]!r}"
            messages = messages[:1] + [
                {"role": "assistant", "content": text[:2000]},
                {"role": "user", "content": "That was not valid JSON. Send the complete "
                 "JSON object now, nothing else. First character must be '{'."}]
    raise RuntimeError(f"Anthropic did not return valid JSON after 3 tries ({last})")


def compose_name(title: str, term: str, metro: str) -> str:
    """Keyworded name with the researched term VERBATIM inside it.

    First fleet pass (2026-08-09): the old 'blend rather than repeat' rule let
    the model mutate the term (Life Savers got 'Water Damage Cleanup' when the
    researched term was 'water damage restoration'; narestco got a truncated
    'Water Damage'). A suggestion whose keyword differs from the term the
    volume numbers were pulled for makes the card's rationale wrong, so the
    term is now non-negotiable: validated here, one corrective retry, then a
    deterministic 'Brand - Term' fallback."""
    system = (
        "You compose Google Business Profile listing names for local service "
        "businesses. Given the CURRENT listing name and ONE keyword term, "
        "produce the keyworded name a human could adopt as real branding.\n"
        "Rules:\n"
        "- Keep the existing brand name recognizable and first; the term "
        "follows naturally (e.g. 'Flood Fixers Water Damage Restoration').\n"
        "- The keyword term must appear in the name VERBATIM, word for word "
        "and in order (title case is fine). Never shorten, reorder or swap "
        "any word of the term.\n"
        "- If keeping the term verbatim would repeat a word already in the "
        "brand name, separate brand and term with ' - ' instead of mutating "
        "either (e.g. 'Life Savers Restoration - Water Damage Restoration').\n"
        "- Use ONLY the given term; never add cities, extra services, "
        "superlatives or slogans.\n"
        "- Aim for 60 characters or fewer where sensible; never exceed 80.\n"
        "- Plain characters only: letters, digits, spaces, & and hyphens. "
        "NEVER use an em dash.\n"
        "Return JSON: {\"suggested_name\": \"...\"}")
    user = json.dumps({"current_listing_name": title, "keyword_term": term,
                       "metro": metro}, ensure_ascii=False)
    for attempt in (1, 2):
        out = _anthropic_json(system, user)
        name = str(out.get("suggested_name") or "").strip()
        # Belt-and-braces: no em dashes ever leave this script.
        name = name.replace("—", "-").replace("–", "-")
        name = re.sub(r"\s+", " ", name).strip()
        if name and _norm(term) in _norm(name) and len(name) <= 80:
            return name
        user += ("\n\nYour previous attempt broke the rules. The term "
                 f"\"{term}\" must appear verbatim and the name must stay "
                 "at or under 80 characters.")
    return f"{title} - {term.title()}"  # deterministic, always rule-clean


# --------------------------------------------------------------------------- #
# Card seeding
# --------------------------------------------------------------------------- #
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())).strip()


def build_rationale(title: str, term: str, vols: dict, label: str,
                    suggested: str) -> str:
    lines = ", ".join(f'"{t}": {v}/mo' for t, v in
                      sorted(vols.items(), key=lambda kv: -kv[1]))
    return (
        f"Keyword research (Google Ads monthly search volume, {label}): "
        f"{lines}. Highest-volume term not already in the listing name: "
        f"\"{term}\" ({vols[term]} searches/mo). Current listing name: "
        f"\"{title}\". Suggested keyworded name: \"{suggested}\".\n\n"
        + BEST_PRACTICES)


def seed_card(cid: str, slug: str, title: str, term: str, vols: dict,
              label: str, suggested: str, dry_run: bool) -> bool:
    rationale = build_rationale(title, term, vols, label, suggested)
    created = insert_plan_row(
        cid, slug, "gbp-name-suggest",
        title=f"SUGGESTION: keyworded listing name - {suggested}",
        rationale=rationale,
        action_type="gbp_fix",           # renders as a manual GBP card; no
        target=f"gbp:{slug}",            # automation consumes gbp_fix rows
        impact="high", effort="medium", dry_run=dry_run)
    if not created and not dry_run:
        # insert_plan_row refreshes only the TITLE of an open row when the
        # seeder's wording changes; the research numbers live in the
        # rationale, so keep that in step too (still only for rows a human
        # has not acted on -- status planned).
        _sb("PATCH", "/rest/v1/marketing_action_plan"
            f"?company_id=eq.{cid}"
            f"&action_key=eq.{action_key(cid, 'gbp-name-suggest')}"
            "&status=eq.planned", {"rationale": rationale})
    return created


# --------------------------------------------------------------------------- #
# Fleet run
# --------------------------------------------------------------------------- #
def run(dry_run: bool, only_slug: str | None) -> None:
    cid_to_slug = slug_map()
    cos = _sb("GET", "/rest/v1/companies?status=ilike.active&plan=eq.Rank%20AI"
              "&select=id,name,city,state",
              prefer="return=representation") or []
    u, p = load_dfs_creds()
    dfs_auth = base64.b64encode(f"{u}:{p}".encode()).decode()

    seeded, skipped = [], []
    for co in cos:
        cid, name = co["id"], (co.get("name") or "").strip()
        slug = cid_to_slug.get(cid)
        if not slug:
            skipped.append((name, "no slug mapping"))
            continue
        if only_slug and slug != only_slug:
            continue
        rec_path = CLIENTS_DIR / f"{slug}.json"
        vertical = None
        if rec_path.exists():
            try:
                vertical = json.loads(rec_path.read_text()).get("vertical")
            except json.JSONDecodeError:
                pass
        terms = VERTICAL_TERMS.get(vertical or "")
        if not terms:
            skipped.append((slug, f"vertical {vertical!r} has no term set"))
            continue

        try:
            title = read_listing_title(cid)
        except Exception as e:  # noqa: BLE001 -- one bad client, not the fleet
            skipped.append((slug, f"GBP read failed: {str(e)[:80]}"))
            continue
        if not title:
            skipped.append((slug, "no GBP connection / no listing matched"))
            continue

        loc = metro_location(co.get("city"), co.get("state"))
        try:
            vols, label = search_volumes(dfs_auth, terms, loc)
        except Exception as e:  # noqa: BLE001
            skipped.append((slug, f"DFS research failed: {str(e)[:80]}"))
            continue

        ranked = sorted(terms, key=lambda t: -vols.get(t, 0))
        top = ranked[0]
        norm_title = _norm(title)
        if _norm(top) in norm_title:
            skipped.append((slug, f'name already contains top term "{top}"'))
            continue
        term = next((t for t in ranked if _norm(t) not in norm_title), None)
        if term is None:
            skipped.append((slug, "name already contains every candidate term"))
            continue

        try:
            suggested = compose_name(title, term, label)
        except Exception as e:  # noqa: BLE001
            skipped.append((slug, f"compose failed: {str(e)[:80]}"))
            continue

        created = seed_card(cid, slug, title, term, vols, label, suggested, dry_run)
        seeded.append((slug, title, term, vols[term], label, suggested, created))
        print(f"  {slug}: \"{title}\" + \"{term}\" ({vols[term]}/mo, {label}) "
              f"-> \"{suggested}\" [{'NEW card' if created else 'card exists'}]")

    print(f"\n{'[dry-run] ' if dry_run else ''}suggestions: {len(seeded)} "
          f"({sum(1 for s in seeded if s[6])} new cards), skipped: {len(skipped)}")
    for slug, why in skipped:
        print(f"  skip {slug}: {why}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--slug", help="run a single client")
    args = ap.parse_args()
    run(args.dry_run, args.slug)


if __name__ == "__main__":
    main()
