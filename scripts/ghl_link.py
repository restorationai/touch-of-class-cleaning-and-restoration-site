#!/usr/bin/env python3
"""GHL <-> app durable contact linkage for Rank AI clients.

The Client Concierge (scripts/client_concierge.py) used to *guess* which
GoHighLevel contact belongs to an app company via full-text search. This
script makes the linkage durable: it finds the right GHL contact for every
company in the app (Supabase `companies`), and stores the confirmed contact id
in `companies.integration_settings.ghl_contact_id` (jsonb MERGE — existing
keys like slack/goals/franchise are preserved, never clobbered).

Subcommands
    match                Report-only. For every app company, search GHL by
                         (a) stored ghl_contact_id, (b) admin/owner profile
                         emails, (c) company email, (d) company phone,
                         (e) full-text company name / owner last name.
                         Scores each candidate and prints a table:
                         matched / ambiguous / missing.
    link [--dry-run]     Write linkage: hardcoded verified seeds first
                         (SEED_LINKS below, verified by hand 2026-07-10),
                         then every auto-match with score >= 80 (exact email
                         or exact phone). Merges into integration_settings.
    enroll-pipeline      Ensure every LINKED client has an opportunity in the
        [--execute]      "Restoration AI Secured Clients" pipeline.
                         DRY-RUN BY DEFAULT — prints what it would create.
                         --execute performs the POST /opportunities/ calls.
                         (Kept dry-run until Santino approves.)

Scoring (match)
    100  stored integration_settings.ghl_contact_id resolves in GHL
     90  exact email match (company email or an app profile email)
     80  exact phone match (last 10 digits)
     40  name-query hit (top result only)         } report-only, never
     30  owner-last-name query hit                } auto-linked

Test/internal companies (TEST_EXCLUDE) are never linked or enrolled.

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GHL_API_KEY, GHL_LOCATION_ID
(from rank-ai/.env).

Usage
    python3 scripts/ghl_link.py match
    python3 scripts/ghl_link.py link --dry-run
    python3 scripts/ghl_link.py link
    python3 scripts/ghl_link.py enroll-pipeline            # dry-run
    python3 scripts/ghl_link.py enroll-pipeline --execute  # after approval
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
GHL_BASE = "https://services.leadconnectorhq.com"
GHL_VERSION = "2021-07-28"
UA = "rank-ai-ghl-link/1.0"

SECURED_PIPELINE_NAME = "Restoration AI Secured Clients"

# Verified by hand 2026-07-10 (full-text query search + phone/email check).
# company_id -> (ghl_contact_id, note)
SEED_LINKS: dict[str, tuple[str, str]] = {
    # Jack Bispo runs BOTH All Pro Plumbing and ProRestoration
    "CO-1783380243102": ("KxKV79O4z0eLJq6PfmBQ", "Jack Bispo — All Pro Plumbing"),
    "CO-1779551010975": ("KxKV79O4z0eLJq6PfmBQ", "Jack Bispo — ProRestoration"),
    "CO-1783376797396": ("TOTNFqyoRYIC03KX23YN", "Jeff Sibley — MCC Restoration"),
    "CO-1783443032282": ("utHNNSRjzjVWbSgsSE2M", "Robert Randig — FireDEX"),
    # Flood Fixers' app account is shared with PuroClean folks (member
    # profiles), so auto-match is ambiguous — Gabriel Herrera is the client.
    "CO-1775605259504": ("Z92RAztfo9LmK6fzQ2ay", "Gabriel Herrera — Flood Fixers"),
}

# Internal / test / deleted companies: never link, never enroll.
TEST_EXCLUDE: set[str] = {
    "CO-1782880883337",       # Test (Rank AI)
    "CO-1780604438034",       # Test Account
    "CO-1774183293943",       # SIPTest
    "CO-TEST-1782170767924",  # Test RLS Company
    "CO-1766552577794",       # XYZ Restoration (internal)
    "CO-1771891084135",       # [DELETED] Solid Restoration
}

AUTO_LINK_MIN_SCORE = 80


# ---------------------------------------------------------------- env / REST
def load_env() -> None:
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
        "Content-Type": "application/json", "Prefer": prefer, "User-Agent": UA,
    })
    resp.raise_for_status()
    return resp.json() if resp.content else None


def _ghl(method: str, path: str, *, params=None, body=None):
    resp = requests.request(
        method, GHL_BASE + path, params=params, json=body, timeout=30,
        headers={"Authorization": f"Bearer {os.environ['GHL_API_KEY']}",
                 "Version": GHL_VERSION, "Accept": "application/json",
                 "User-Agent": UA})
    if resp.status_code >= 400:
        raise RuntimeError(f"GHL {method} {path} -> {resp.status_code}: {resp.text[:300]}")
    return resp.json() if resp.content else None


def _loc() -> str:
    return os.environ["GHL_LOCATION_ID"]


def _norm_phone(p: str | None) -> str:
    return re.sub(r"\D", "", p or "")[-10:]


def _norm_email(e: str | None) -> str:
    return (e or "").strip().lower()


# ---------------------------------------------------------------- data pulls
def fetch_companies() -> list[dict]:
    return _sb("GET", "/rest/v1/companies?select=id,name,phone,email,"
               "account_owner_name,status,integration_settings"
               "&order=name.asc") or []


def fetch_profiles_by_company() -> dict[str, list[dict]]:
    rows = _sb("GET", "/rest/v1/profiles?select=company_id,full_name,role,email"
               "&order=company_id") or []
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["company_id"], []).append(r)
    # admins/owners first — they are the people we actually text
    rank = {"owner": 0, "admin": 1, "superadmin": 2, "member": 3}
    for lst in out.values():
        lst.sort(key=lambda p: rank.get((p.get("role") or "member"), 3))
    return out


def ghl_search(query: str, limit: int = 5) -> list[dict]:
    if not query or not str(query).strip():
        return []
    data = _ghl("GET", "/contacts/", params={
        "locationId": _loc(), "query": str(query).strip(), "limit": limit})
    return data.get("contacts") or []


def ghl_get_contact(contact_id: str) -> dict | None:
    try:
        data = _ghl("GET", f"/contacts/{contact_id}")
        c = (data or {}).get("contact") or data
        return c if c and c.get("id") else None
    except RuntimeError:
        return None


# ---------------------------------------------------------------- matching
def match_company(company: dict, profiles: list[dict]) -> list[dict]:
    """Return scored candidates [{contact_id, name, phone, email, score, via}]."""
    candidates: dict[str, dict] = {}

    def add(contact: dict, score: int, via: str):
        cid = contact["id"]
        cur = candidates.get(cid)
        if cur is None or score > cur["score"]:
            candidates[cid] = {
                "contact_id": cid,
                "name": contact.get("contactName") or contact.get("name") or "?",
                "phone": contact.get("phone"), "email": contact.get("email"),
                "score": score, "via": via}

    # (a) stored linkage
    stored = (company.get("integration_settings") or {}).get("ghl_contact_id")
    if stored:
        c = ghl_get_contact(stored)
        if c:
            add(c, 100, "stored ghl_contact_id")

    # (b) profile emails — admins/owners outrank members (shared app accounts
    #     often carry stray member profiles) — and (c) company email.
    role_score = {"owner": 90, "admin": 90, "superadmin": 88, "member": 85}
    emails = [(p.get("email"), role_score.get((p.get("role") or "member"), 85),
               p.get("role") or "member") for p in profiles]
    emails.append((company.get("email"), 90, "company email"))
    seen: set[str] = set()
    for em, score, role in emails:
        em = _norm_email(em)
        if not em or em in seen:
            continue
        seen.add(em)
        for c in ghl_search(em):
            if _norm_email(c.get("email")) == em:
                add(c, score, f"email {em} ({role})")

    # (d) company phone
    ph = _norm_phone(company.get("phone"))
    if len(ph) == 10:
        for c in ghl_search(ph):
            if _norm_phone(c.get("phone")) == ph:
                add(c, 80, f"phone …{ph[-4:]}")

    # (e) full-text: company name, then owner last name (report-only scores)
    for c in ghl_search(company.get("name") or "", limit=3):
        add(c, 40, "name query")
    owner = (company.get("account_owner_name") or "").strip()
    if not owner and profiles:
        owner = (profiles[0].get("full_name") or "").strip()
    last = owner.split()[-1] if owner and len(owner.split()) > 1 else ""
    if len(last) >= 3:
        for c in ghl_search(last, limit=3):
            add(c, 30, f"owner last name {last!r}")

    return sorted(candidates.values(), key=lambda x: -x["score"])


def classify(cands: list[dict]) -> str:
    if not cands:
        return "missing"
    top = cands[0]["score"]
    if top < AUTO_LINK_MIN_SCORE:
        return "weak"
    if len([c for c in cands if c["score"] == top]) > 1:
        return "ambiguous"
    return "matched"


def eligible_companies() -> list[dict]:
    out = []
    for co in fetch_companies():
        name = (co.get("name") or "").lower()
        if co["id"] in TEST_EXCLUDE or "[deleted]" in name or "test" in name.split():
            continue
        out.append(co)
    return out


def cmd_match(_args) -> int:
    companies = eligible_companies()
    profiles = fetch_profiles_by_company()
    print(f"Matching {len(companies)} companies against GHL "
          f"(test/internal excluded)…\n")
    hdr = (f"{'company':<20} {'name':<32} {'verdict':<10} {'score':>5} "
           f"{'contact':<22} {'contact name':<24} via")
    print(hdr)
    print("-" * len(hdr))
    tally = {"matched": 0, "ambiguous": 0, "missing": 0, "weak": 0}
    for co in companies:
        cands = match_company(co, profiles.get(co["id"], []))
        verdict = classify(cands)
        tally[verdict] += 1
        top = cands[0] if cands else None
        seeded = " [SEED]" if co["id"] in SEED_LINKS else ""
        print(f"{co['id']:<20} {co['name'][:32]:<32} {verdict + seeded:<10} "
              f"{(top['score'] if top else 0):>5} "
              f"{(top['contact_id'] if top else '-'):<22} "
              f"{(top['name'][:24] if top else '-'):<24} "
              f"{top['via'] if top else '-'}")
        if verdict == "ambiguous":
            for c in cands[1:4]:
                print(f"{'':<20} {'':<32} {'':>10} {c['score']:>5} "
                      f"{c['contact_id']:<22} {c['name'][:24]:<24} {c['via']}")
    print(f"\nmatched={tally['matched']} ambiguous={tally['ambiguous']} "
          f"weak={tally['weak']} missing={tally['missing']}")
    return 0


# ---------------------------------------------------------------- link
def merge_link(company: dict, contact_id: str, method: str, dry_run: bool) -> None:
    settings = dict(company.get("integration_settings") or {})
    if settings.get("ghl_contact_id") == contact_id:
        print(f"  {company['id']} already linked to {contact_id} — no-op")
        return
    settings.update({
        "ghl_contact_id": contact_id,
        "ghl_link_method": method,
        "ghl_linked_at": datetime.now(timezone.utc).isoformat(),
    })
    if dry_run:
        print(f"  [dry-run] would PATCH {company['id']} "
              f"integration_settings.ghl_contact_id={contact_id} ({method})")
        return
    _sb("PATCH",
        f"/rest/v1/companies?id=eq.{urllib.parse.quote(company['id'])}",
        {"integration_settings": settings}, prefer="return=minimal")
    print(f"  LINKED {company['id']} ({company['name']}) -> {contact_id} ({method})")


def cmd_link(args) -> int:
    companies = eligible_companies()
    profiles = fetch_profiles_by_company()
    by_id = {c["id"]: c for c in companies}
    linked, skipped = [], []

    # 1. hardcoded verified seeds
    for cid, (contact_id, note) in SEED_LINKS.items():
        co = by_id.get(cid)
        if not co:
            print(f"  WARNING: seed company {cid} not found in app", file=sys.stderr)
            continue
        c = ghl_get_contact(contact_id)
        if not c:
            print(f"  WARNING: seed contact {contact_id} ({note}) not found in "
                  f"GHL — skipping", file=sys.stderr)
            continue
        merge_link(co, contact_id, f"seed: {note}", args.dry_run)
        linked.append((cid, co["name"], contact_id, c.get("contactName"), f"seed: {note}"))

    # 2. confident auto-matches for everyone else
    for co in companies:
        if co["id"] in SEED_LINKS:
            continue
        cands = match_company(co, profiles.get(co["id"], []))
        verdict = classify(cands)
        if verdict == "matched":
            top = cands[0]
            merge_link(co, top["contact_id"], top["via"], args.dry_run)
            linked.append((co["id"], co["name"], top["contact_id"], top["name"], top["via"]))
        else:
            skipped.append((co["id"], co["name"], verdict))

    print(f"\n=== final mapping ({len(linked)} linked"
          f"{' — DRY RUN, nothing written' if args.dry_run else ''}) ===")
    for cid, name, contact_id, cname, via in linked:
        print(f"  {cid:<20} {name[:34]:<34} -> {contact_id}  {cname or '?':<24} [{via}]")
    if skipped:
        print(f"\n=== not linked ({len(skipped)}) ===")
        for cid, name, verdict in skipped:
            print(f"  {cid:<20} {name[:34]:<34} {verdict}")
    return 0


# ---------------------------------------------------------------- enroll
def find_pipeline(name: str) -> dict:
    data = _ghl("GET", "/opportunities/pipelines", params={"locationId": _loc()})
    for p in data.get("pipelines", []):
        if p.get("name") == name:
            return p
    raise RuntimeError(f"pipeline {name!r} not found")


def pipeline_opportunities(pipeline_id: str) -> list[dict]:
    """All opportunities in a pipeline (paginates /opportunities/search)."""
    out: list[dict] = []
    params = {"location_id": _loc(), "pipeline_id": pipeline_id, "limit": 100}
    url = "/opportunities/search"
    while True:
        data = _ghl("GET", url, params=params)
        out.extend(data.get("opportunities") or [])
        nxt = (data.get("meta") or {}).get("nextPageUrl")
        if not nxt or not (data.get("opportunities") or []):
            break
        parsed = urllib.parse.urlparse(nxt)
        url = parsed.path
        params = dict(urllib.parse.parse_qsl(parsed.query))
    return out


def cmd_enroll(args) -> int:
    pipeline = find_pipeline(SECURED_PIPELINE_NAME)
    stage = pipeline["stages"][0]  # entry stage
    print(f"pipeline: {pipeline['name']} ({pipeline['id']}) — entry stage "
          f"{stage['name']!r} ({stage['id']})")
    opps = pipeline_opportunities(pipeline["id"])
    have = {}
    for o in opps:
        if o.get("contactId"):
            have.setdefault(o["contactId"], []).append(o)
    print(f"existing opportunities in pipeline: {len(opps)} "
          f"({len(have)} distinct contacts)")

    companies = eligible_companies()
    to_create, ok = [], []
    for co in companies:
        contact_id = (co.get("integration_settings") or {}).get("ghl_contact_id")
        if not contact_id:
            continue
        if contact_id in have:
            o = have[contact_id][0]
            ok.append((co, o))
        else:
            to_create.append((co, contact_id))

    print(f"\n=== already enrolled ({len(ok)}) ===")
    for co, o in ok:
        print(f"  {co['id']:<20} {co['name'][:32]:<32} opp {o['id']} "
              f"({o.get('name') or 'unnamed'}, status={o.get('status')})")

    print(f"\n=== would create ({len(to_create)}) "
          f"{'' if args.execute else '[DRY RUN — pass --execute after approval]'} ===")
    for co, contact_id in to_create:
        payload = {"pipelineId": pipeline["id"], "locationId": _loc(),
                   "contactId": contact_id, "name": co["name"].strip(),
                   "pipelineStageId": stage["id"], "status": "open"}
        print(f"  {co['id']:<20} {co['name'][:32]:<32} "
              f"POST /opportunities/ {json.dumps(payload)}")
        if args.execute:
            result = _ghl("POST", "/opportunities/", body=payload)
            oid = ((result or {}).get("opportunity") or {}).get("id") or "?"
            print(f"    CREATED opportunity {oid}")
    return 0


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("match", help="report-only match table")
    pl = sub.add_parser("link", help="write seeds + confident auto-matches")
    pl.add_argument("--dry-run", action="store_true")
    pe = sub.add_parser("enroll-pipeline",
                        help="ensure Secured Clients opportunities (dry-run default)")
    pe.add_argument("--execute", action="store_true",
                    help="actually create opportunities (needs Santino's go)")
    args = ap.parse_args()
    load_env()
    missing = [k for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY",
                           "GHL_API_KEY", "GHL_LOCATION_ID")
               if not os.environ.get(k)]
    if missing:
        print(f"ERROR: missing env: {', '.join(missing)}", file=sys.stderr)
        return 1
    return {"match": cmd_match, "link": cmd_link,
            "enroll-pipeline": cmd_enroll}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
