#!/usr/bin/env python3
"""gbp_rename_research.py — headless SLATE researcher for the Profile
Rename program (Santino 2026-09-18: the app's Refresh Names button was
wired to gbp_name_suggest.py, which writes single action-plan cards, not
the marketing_gbp_suggestions slate the Profile Rename section displays —
TDI's refresh looked like it did nothing).

Produces 3-4 verbatim name candidates per client (QCI-slate style) and
writes them to marketing_gbp_suggestions (item_type=name), which is what
the app card and the pitch flow read.

House doctrine baked in:
  - Base identity + " - " + service phrase(s); "&" allowed, NO em dashes.
  - restoration: lead the aggressive 24/7 Emergency pattern; when the
    company can service plumbing panic jobs, the plumbing-forward option
    is the TOP recommendation regardless of license confirmation (law
    2026-09-18; the license question rides the pitch, not the slate).
  - construction/GC: remodel intent carries the volume (general
    contractor / home remodeling / kitchen & bathroom remodeling).
  - Max 3 service lanes per name; never stack cities or superlatives.
  - Volumes validated per-metro via DataForSEO (national fallback).

CLI: python3 scripts/gbp_rename_research.py --slug X [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import os  # noqa: E402
import requests  # noqa: E402
from client_ops_sync import _sb, slug_map  # noqa: E402
from gbp_name_suggest import (  # noqa: E402
    load_dfs_creds, metro_location, search_volumes, VERTICAL_TERMS)

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-5"

EXTRA_TERMS = {
    "restoration": ["emergency plumber", "mold remediation", "mold removal",
                    "fire damage restoration", "emergency plumbing"],
    "construction": ["remodeling contractor", "home builder",
                     "bathroom remodel", "kitchen remodel"],
    "plumbing": ["drain cleaning", "water heater repair"],
}

DOCTRINE = {
    "restoration": (
        "Lead aggressive: the 24/7 Emergency pattern ranks (house stance). "
        "If plumbing appears in the volume table, the plumbing-forward "
        "option MUST be first with the highest confidence (house law "
        "2026-09-18: recommend plumbing regardless of license status). "
        "Water damage restoration and mold remediation are core phrases."),
    "construction": (
        "Remodel intent carries the volume. Lead with the highest-volume "
        "remodel or general-contractor phrase. Never include restoration "
        "or mitigation phrases unless they appear in the services list."),
    "plumbing": (
        "Emergency plumber / plumbing phrases lead. 24/7 pattern ranks."),
}


def _base(cid: str, company_name: str) -> str:
    """The identity the candidates build on: an in-flight DBA name wins,
    then the live GBP title, then the company record name."""
    co = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}"
              "&select=integration_settings") or [{}])[0]
    ri = (co.get("integration_settings") or {}).get("rename_intent") or {}
    if ri.get("dba_name"):
        return str(ri["dba_name"])
    prof = (_sb("GET", f"/rest/v1/marketing_gbp_profiles?company_id=eq.{cid}"
                "&select=title") or [{}])[0]
    return str(prof.get("title") or company_name).strip()


def research(slug: str, dry: bool) -> int:
    inv = {s: c for c, s in slug_map().items()}
    cid = inv.get(slug)
    if not cid:
        print(f"ERROR: no company for slug {slug}")
        return 1
    co = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}"
              "&select=name,city,state,services") or [{}])[0]
    vertical = "restoration"
    rec_p = ROOT / "clients" / f"{slug}.json"
    if rec_p.exists():
        vertical = (json.loads(rec_p.read_text()).get("vertical")
                    or "restoration").strip().lower()
    if vertical not in VERTICAL_TERMS:
        print(f"ERROR: vertical {vertical!r} has no term set")
        return 1
    base = _base(cid, co.get("name") or slug)
    services: list[str] = []
    pi_p = ROOT / "clients" / slug / "plan-input.json"
    if pi_p.exists():
        services = list(json.loads(pi_p.read_text()).get("services") or [])
    terms = list(dict.fromkeys(
        VERTICAL_TERMS[vertical] + EXTRA_TERMS.get(vertical, [])))
    auth = load_dfs_creds()
    import base64
    if isinstance(auth, tuple):
        auth = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
    vols, label = search_volumes(auth, terms,
                                 metro_location(co.get("city"), co.get("state")))
    vol_table = "\n".join(f"  {t}: {v}/mo" for t, v in
                          sorted(vols.items(), key=lambda kv: -kv[1]))
    prompt = f"""You are naming a Google Business Profile for local search visibility.

Business identity (the name candidates MUST start with this, verbatim): "{base}"
Vertical: {vertical}
City/State: {co.get('city')}, {co.get('state')}
Services they sell: {', '.join(services) or 'unknown'}

Search volumes for {label}:
{vol_table}

DOCTRINE: {DOCTRINE.get(vertical, '')}
Format: "{base} - <Service Phrase>" or "{base} - <Phrase 1>, <Phrase 2> & <Phrase 3>".
Rules: max 3 service lanes per name; ampersand allowed; NEVER an em dash;
no city names inside the name; no superlatives; every phrase must map to a
service they actually sell; keep the strongest exact search phrases intact
and early (display truncates around 35-40 characters).
HARD LIMIT: the full name must be 90 characters or fewer. Directory and
citation platforms reject or truncate longer names, and the name must
print IDENTICALLY on every surface (GBP, citations, site). Count before
you answer. House standard: the word "and", never "&" (DBA portals
normalize special characters unpredictably) — when a name runs long,
shorten or drop a service lane instead of reaching for "&".

Return STRICT JSON only:
{{"candidates": [{{"name": str, "confidence": float 0.5-0.95, "reason": str (one sentence naming the volumes/pattern that justify it)}}]}}
3 or 4 candidates, each a DIFFERENT strategic focus (volume leader, alternate lane mix, conservative short)."""
    r = requests.post(ANTHROPIC_API, timeout=120, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01", "content-type": "application/json"},
        # 4000 not 1200: sonnet-5 can spend ~1k tokens thinking before the
        # JSON, and a truncated slate parses as garbage (TDI first run).
        json={"model": MODEL, "max_tokens": 4000,
              "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    txt = "".join(b.get("text", "") for b in r.json().get("content", []))
    m = re.search(r"\{.*\}", txt, re.S)
    cands = []
    if m:
        try:
            cands = json.loads(m.group(0))["candidates"]
        except json.JSONDecodeError:
            # unescaped quotes inside reason strings — same failure class
            # as the video narration JSON; reuse that state-machine repair.
            from video_maker import parse_script_json
            cands = parse_script_json(m.group(0)).get("candidates") or []
    existing = {str(x.get("item", "")).lower() for x in
                _sb("GET", f"/rest/v1/marketing_gbp_suggestions?company_id=eq.{cid}"
                    "&item_type=eq.name&select=item,status") or []}
    wrote = 0
    for c in cands[:4]:
        name = re.sub(r"\s*[—–]\s*", " - ", str(c.get("name", ""))).strip()
        if not name.lower().startswith(base.lower()[:12]) or name.lower() in existing:
            continue
        if len(name) > 90:
            # HARD CAP (Santino 2026-09-19): >90 breaks BrightLocal + many
            # directories, and the name must print identically everywhere.
            # No "&" rescue — house standard is the word "and" (09-14);
            # an overlong name simply doesn't make the slate.
            print(f"  [len {len(name)}>90 — REJECTED] {name}")
            continue
        print(f"  [{c.get('confidence')}] {name}\n      {c.get('reason')}")
        if dry:
            wrote += 1
            continue
        _sb("POST", "/rest/v1/marketing_gbp_suggestions",
            {"company_id": cid, "item": name, "item_type": "name",
             "status": "open", "verdict": "ADD", "auto_safe": False,
             "confidence": float(c.get("confidence") or 0.6),
             "source": "rename-research",
             "reason": str(c.get("reason") or "")[:400]},
            prefer="return=minimal")
        wrote += 1
    print(f"{slug}: {wrote} candidate(s)" + (" [dry-run]" if dry else ""))
    return 0 if wrote else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    return research(a.slug, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
