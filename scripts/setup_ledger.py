#!/usr/bin/env python3
"""Setup ledger — the overseer (Santino 2026-07-28: "no client should ever get
left behind"). For every ACTIVE client on the Rank AI plan (other plans are
deliberately ignored), derive the setup state from the systems themselves —
never from someone having marked a box — and route every gap:

  us_owed      -> Santino's attention list (nightly ops email + app
                  SuperadminDashboard reads marketing_setup_ledger)
  client_owed  -> Monica already owns these via the checklist/ask passes;
                  the ledger just aggregates counts for the app + the
                  escalation ladder
  auto         -> the ledger FIXES it itself (GSC registration + IndexNow
                  for live sites)

Items:
  site-built      preview site exists in sites/{slug} (CRITICAL when the
                  kickoff call is within 3 days or already past)
  site-live       the client's real domain serves our site; if WE control
                  the zone and the site is built but not live, the detail
                  says LAUNCH NOW (own-domain policy, PuroClean 2026-07-28)
  domain-access   built + domain known + zone not ours + not live ->
                  client-owed registrar-access ask
  gsc-indexnow    live site registered in Search Console + IndexNow-pinged
                  (auto-heals: runs gsc_register + indexnow once, marks done)
  google-connected  reflects user_integrations state (ask pass owns nudges)
  client-asks     open client_input count + no-reply streak (ladder input)

Run:  python3 scripts/setup_ledger.py [--dry-run]
Wired into client_ops_sync's nightly pass via ensure_ledger().
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = ROOT / "clients"
SITES_DIR = ROOT / "sites"
sys.path.insert(0, str(ROOT / "scripts"))

from client_ops_sync import _sb, slug_map  # noqa: E402


def _norm_domain(d: str | None) -> str:
    d = (d or "").strip().lower()
    d = re.sub(r"^https?://", "", d).strip("/ ")
    return d[4:] if d.startswith("www.") else d


def _client_record(slug: str) -> dict:
    p = CLIENTS_DIR / f"{slug}.json"
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except json.JSONDecodeError:
        return {}


def _our_zones() -> dict[str, str]:
    """{domain: zone_status} for zones on our Cloudflare account. status
    'active' = NS actually point at us (launchable); 'pending' = zone created
    but the registrar cutover hasn't happened (crew3r 2026-07-28)."""
    tok = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not tok:
        return {}
    out: dict[str, str] = {}
    page = 1
    try:
        while True:
            r = requests.get("https://api.cloudflare.com/client/v4/zones",
                             headers={"Authorization": f"Bearer {tok}"},
                             params={"per_page": 50, "page": page}, timeout=30)
            body = r.json()
            for z in body.get("result") or []:
                out[z["name"].lower()] = z.get("status") or "?"
            if page >= (body.get("result_info") or {}).get("total_pages", 1):
                break
            page += 1
    except Exception:
        pass
    return out


def _site_serves_us(domain: str, brand_name: str) -> bool:
    """True only when the domain serves OUR build. Brand-name matching is
    useless here — the client's OLD site obviously contains their name
    (crew3r.com false-positived) — so require our own markers."""
    del brand_name
    try:
        r = requests.get(f"https://{domain}/", timeout=20,
                         headers={"User-Agent": "Mozilla/5.0 (rank-ai ledger)"})
        if r.status_code != 200:
            return False
        # every Astro build links /_astro/ asset bundles; old WP sites never do
        return "/_astro/" in r.text or "/images/logo" in r.text
    except Exception:
        return False


def _upcoming_kickoff(ints: dict) -> str | None:
    """ISO start time of a future kickoff appointment, else None."""
    gcid = ints.get("ghl_contact_id")
    key = os.environ.get("GHL_API_KEY")
    if not (gcid and key):
        return None
    try:
        r = requests.get(
            f"https://services.leadconnectorhq.com/contacts/{gcid}/appointments",
            headers={"Authorization": f"Bearer {key}", "Version": "2021-07-28",
                     "User-Agent": "Mozilla/5.0 (rank-ai ops)"}, timeout=20)
        for ev in r.json().get("events") or []:
            if "kickoff" not in (ev.get("title") or "").lower():
                continue
            try:
                t = datetime.strptime(ev.get("startTime", "")[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            if t > datetime.now() - timedelta(hours=12):
                return ev.get("startTime")
    except Exception:
        pass
    return None


def _upsert(rows: list[dict], dry_run: bool) -> None:
    if not rows or dry_run:
        return
    for r in rows:
        r["updated_at"] = datetime.now(timezone.utc).isoformat()
    _sb("POST", "/rest/v1/marketing_setup_ledger?on_conflict=company_id,item_key",
        rows, prefer="resolution=merge-duplicates")


def _gsc_heal(domain: str, slug: str) -> str:
    """Idempotent GSC registration + IndexNow for a live domain."""
    msgs = []
    try:
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "gsc_register.py"),
                            "--domain", domain], capture_output=True, text=True, timeout=300)
        msgs.append("gsc:" + ("ok" if "VERIFIED" in (r.stdout + r.stderr) or "already" in
                              (r.stdout + r.stderr).lower() else "check"))
    except Exception as e:
        msgs.append(f"gsc:err {str(e)[:40]}")
    try:
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_site.py"),
                            "indexnow", "--slug", slug], capture_output=True, text=True, timeout=180)
        msgs.append("indexnow:" + ("ok" if "202" in r.stdout or "200" in r.stdout else "check"))
    except Exception as e:
        msgs.append(f"indexnow:err {str(e)[:40]}")
    return " ".join(msgs)


def ensure_ledger(dry_run: bool, cid_to_slug: dict | None = None) -> list[str]:
    """Evaluate the ledger for every Active Rank AI client. Returns attention
    lines (us-owed gaps) for the nightly ops email."""
    cid_to_slug = cid_to_slug or slug_map()
    zones = _our_zones()
    cos = _sb("GET", "/rest/v1/companies?status=ilike.active&plan=eq.Rank%20AI"
              "&select=id,name,website,services,integration_settings",
              prefer="return=representation") or []
    attention: list[str] = []

    for co in cos:
        cid = co["id"]
        slug = cid_to_slug.get(cid)
        if not slug:
            attention.append(f"(no slug) {co.get('name')}: not in slug map — bootstrap missing")
            continue
        ints = co.get("integration_settings") or {}
        if isinstance(ints, str):
            try:
                ints = json.loads(ints)
            except json.JSONDecodeError:
                ints = {}
        rows: list[dict] = []

        # ---- site-built --------------------------------------------------
        built = (SITES_DIR / slug / "src").exists()
        kickoff = None if built else _upcoming_kickoff(ints)
        detail = None
        if not built:
            detail = "No preview site exists."
            if kickoff:
                try:
                    days = (datetime.strptime(kickoff[:19], "%Y-%m-%d %H:%M:%S")
                            - datetime.now()).days
                    if days <= 3:
                        detail = (f"CRITICAL: kickoff {kickoff} is {max(days, 0)} day(s) away "
                                  "and NO preview site exists — build it before the call.")
                except ValueError:
                    pass
        rows.append({"company_id": cid, "item_key": "site-built", "kind": "us_owed",
                     "status": "done" if built else "open",
                     "title": "Preview site built",
                     "detail": detail,
                     "evidence": {"kickoff": kickoff, "site_dir": built}})
        if not built:
            attention.append(f"{slug}: SITE NOT BUILT" + (f" — {detail}" if detail and "CRITICAL" in detail else ""))

        # ---- site-live / domain-access ------------------------------------
        domain = _norm_domain(_client_record(slug).get("domain") or co.get("website"))
        live = False
        if domain and built:
            live = _site_serves_us(domain, co.get("name") or "")
        zstat = zones.get(domain, "") if domain else ""
        ours = zstat == "active"
        if not domain:
            rows.append({"company_id": cid, "item_key": "site-live", "kind": "us_owed",
                         "status": "blocked", "title": "Live on real domain",
                         "detail": "No domain on file — ask the client or buy one (own-domain = launch immediately).",
                         "evidence": {}})
            if built:
                attention.append(f"{slug}: site built, NO DOMAIN on file — decide buy vs client's registrar")
        else:
            d2 = None
            if not live and built:
                if ours:
                    d2 = "ZONE ACTIVE ON OUR CF — launch now (own-domain policy)."
                elif zstat == "pending":
                    d2 = ("Zone created on our CF but NS cutover pending — needs the "
                          "registrar step (client creds/delegate access).")
                else:
                    d2 = "Client-controlled domain; needs registrar/delegate access for cutover."
            rows.append({"company_id": cid, "item_key": "site-live", "kind": "us_owed",
                         "status": "done" if live else ("open" if built else "blocked"),
                         "title": "Live on real domain", "detail": d2,
                         "evidence": {"domain": domain, "zone_status": zstat or "none"}})
            if built and not live:
                attention.append(f"{slug}: built but NOT LIVE on {domain} — "
                                 + ("LAUNCH NOW (zone active)" if ours else
                                    ("NS cutover pending (zone ready)" if zstat == "pending"
                                     else "needs domain access")))
            rows.append({"company_id": cid, "item_key": "domain-access", "kind": "client_owed",
                         "status": "open" if (built and domain and not ours and not live) else "done",
                         "title": "Registrar / domain access",
                         "detail": None if live or ours else
                         "Monica: ask for registrar delegate access (or creds) so we can launch.",
                         "evidence": {"domain": domain, "zone_status": zstat or "none"}})

        # ---- gsc-indexnow (auto-heal once per live site) -------------------
        if live:
            existing = _sb("GET", "/rest/v1/marketing_setup_ledger"
                           f"?company_id=eq.{cid}&item_key=eq.gsc-indexnow&select=status",
                           prefer="return=representation") or []
            if not existing or existing[0].get("status") != "done":
                note = "dry-run" if dry_run else _gsc_heal(domain, slug)
                rows.append({"company_id": cid, "item_key": "gsc-indexnow", "kind": "auto",
                             "status": "done" if not dry_run else "open",
                             "title": "Search Console + IndexNow",
                             "detail": note, "evidence": {"domain": domain}})
                attention.append(f"{slug}: gsc/indexnow auto-heal -> {note}")

        # ---- google-connected (reflect only) -------------------------------
        gi = _sb("GET", f"/rest/v1/user_integrations?client_id=eq.{cid}"
                 "&provider=eq.google&select=id", prefer="return=representation") or []
        rows.append({"company_id": cid, "item_key": "google-connected", "kind": "client_owed",
                     "status": "done" if gi else "open",
                     "title": "Google connected",
                     "detail": None if gi else "Connect-ask pass owns the nudges "
                     f"(short link: https://restorationai.io/connect/{slug}).",
                     "evidence": {}})

        # ---- client-asks aggregate (ladder input) ---------------------------
        asks = _sb("GET", "/rest/v1/marketing_action_plan"
                   f"?company_id=eq.{cid}&action_type=eq.client_input&status=eq.planned"
                   "&select=action_key", prefer="return=representation") or []
        rows.append({"company_id": cid, "item_key": "client-asks", "kind": "client_owed",
                     "status": "open" if asks else "done",
                     "title": f"{len(asks)} open client ask(s)",
                     "detail": ("ESCALATION CANDIDATE: 4+ open asks — Monica should propose "
                                "a 15-minute setup call instead of more texts."
                                if len(asks) >= 4 else None),
                     "evidence": {"count": len(asks)}})
        if len(asks) >= 4:
            attention.append(f"{slug}: {len(asks)} open client asks — propose a setup call (ladder)")

        _upsert(rows, dry_run)

    return attention


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    print(f"==> Setup ledger ({'dry-run' if dry else 'live'})")
    for line in ensure_ledger(dry):
        print("  ATTENTION:", line)
