"""Playbook: registrar nameserver cutover -> our Cloudflare zone.

Reality per Santino (2026-08-01): GoDaddy delegate access is granted to our
EMAIL via their UI and confers NO API access, so GoDaddy runs through the
browser under our own logged-in session (profile). Other registrars
(Bluehost/QCI etc.) come as client-provided credentials in
~/.rankai/portal-creds.json under "{registrar}:{slug}".

Flow:
  1. Resolve the target NS pair from OUR Cloudflare zone for the domain
     (zone must already exist; refuses otherwise — creating zones is
     build_site/launch territory).
  2. Registrar route:
       godaddy  -> godaddy.com under agency session -> delegate account
                   switcher -> domain -> Nameservers
       bluehost -> login with client creds (challenge_detected on any 2FA)
  3. guard_live() -> replace NS with the Cloudflare pair. Audit shots
     before/after. NEVER touch other DNS records, contacts, or locks.
  4. Verify: poll `dig NS` until the new pair shows (or ledger 'propagating').
  5. Ledger + [TODO-SANTINO] note with the before/after shots for oversight.

Supervised until three clean cutovers. EMAIL-SAFE RULE: if the domain has MX
records at the registrar's DNS (not ours), STOP and flag — a blind NS move
kills their email (the TRG/All Pro cutovers were engineered around this).
"""
from __future__ import annotations

import os
import subprocess

import requests

from ..chassis import Session, ledger, portal_creds


def cloudflare_ns_for(domain: str) -> list[str]:
    tok = os.environ.get("CLOUDFLARE_API_TOKEN")
    r = requests.get("https://api.cloudflare.com/client/v4/zones",
                     headers={"Authorization": f"Bearer {tok}"},
                     params={"name": domain}, timeout=30)
    zones = (r.json() or {}).get("result") or []
    return zones[0].get("name_servers") or [] if zones else []


def current_ns(domain: str) -> list[str]:
    try:
        out = subprocess.run(["dig", "+short", "NS", domain],
                             capture_output=True, text=True, timeout=20).stdout
        return sorted(x.strip(". ") for x in out.splitlines() if x.strip())
    except Exception:
        return []


def run(session: Session, domain: str | None = None, registrar: str | None = None) -> int:
    if not domain:
        print("domain_connect needs --domain")
        return 1
    target = cloudflare_ns_for(domain)
    if not target:
        print(f"REFUSED: no Cloudflare zone for {domain} — create the zone via "
              "the launch flow first (this playbook only flips NS).")
        ledger(session.company_id, session.playbook, f"ns-cutover:{domain}",
               "refused_no_zone")
        return 1
    print(f"target NS: {target}")
    print(f"current NS: {current_ns(domain)}")

    reg = (registrar or "godaddy").lower()
    if reg != "godaddy":
        creds = portal_creds(f"{reg}:{session.slug}")
        if not creds:
            print(f"REFUSED: no {reg} credentials for {session.slug} in "
                  "~/.rankai/portal-creds.json — add them first (never the repo).")
            return 1

    # Supervised: registrar UIs are pinned during first runs, same discipline
    # as bing_places. Email-safe check is MANDATORY before any live flip.
    print("\nSupervised checklist:")
    print(" 1. EMAIL-SAFE: inspect current DNS for MX at the registrar; if the")
    print("    Cloudflare zone lacks matching MX records, STOP and flag.")
    print(f" 2. {reg}: open domain management for {domain}")
    print(f" 3. Replace nameservers with: {', '.join(target)}")
    print(" 4. Save behind guard_live(); audit shots before/after")
    print(" 5. dig NS until propagation confirms; ledger the result")
    if session.guard_live(f"NS cutover {domain} -> {','.join(target[:2])}"):
        print("LIVE armed — selectors not pinned yet; supervised run required.")
        ledger(session.company_id, session.playbook, f"ns-cutover:{domain}",
               "needs_supervised_run", live=True)
        return 2
    return 0
