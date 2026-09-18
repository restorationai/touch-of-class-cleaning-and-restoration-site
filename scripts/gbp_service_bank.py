#!/usr/bin/env python3
"""gbp_service_bank.py — A5: the WEEKLY long-tail service generator
(Santino 2026-09-17: "the more services the better, as long as each maps
to a distinct long-tail search... make sure A5 is active and alive").

Reads the volume-validated bank (templates/restoration/service-bank.json)
and, per client, stages every variant whose BASE capability the client
actually has (plan-input services or the base already on their GBP) and
which is not already on the listing. Staged = an auto_safe ADD suggestion;
the A2 nightly batch applies them in ONE Google call per client.

WHY WEEKLY + IDEMPOTENT: one-shot generators rot. This re-runs every week,
so a client missed once is caught the next pass, and every NEW bank entry
(e.g. the surface-damage family added 09-17) applies RETROACTIVELY to the
whole fleet automatically. Each run stamps ops_kv 'heartbeat:service-bank'
for the pipeline watchdog — a dead generator announces itself.

Truth gates: variants only fan out from capabilities the client has;
license_gate families (plumbing) require the license fact on the client
record; dedupe is normalized (distinct modifiers survive, true duplicates
don't).

CLI: python3 scripts/gbp_service_bank.py [--slug X] [--dry-run] [--cap 40]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from client_ops_sync import _sb, slug_map  # noqa: E402
from gbp_auto_apply import _norm  # noqa: E402

BANK = ROOT / "templates" / "restoration" / "service-bank.json"


def load_bank() -> dict:
    return json.loads(BANK.read_text())["families"]


def client_capabilities(slug: str, cid: str) -> tuple[set, set, bool]:
    """(capability slugs, normalized names already on GBP, plumbing_ok)."""
    caps: set = set()
    pi_p = ROOT / "clients" / slug / "plan-input.json"
    rec_p = ROOT / "clients" / f"{slug}.json"
    plumbing_ok = False
    if pi_p.exists():
        pi = json.loads(pi_p.read_text())
        caps |= set(pi.get("services") or [])
        lic = " ".join(str(x) for x in (pi.get("brand") or {}).get(
            "license_numbers", []) or [])
    if rec_p.exists():
        rec = json.loads(rec_p.read_text())
        lt = json.dumps(rec.get("licenses") or rec.get("brand", {})).lower()
        plumbing_ok = "plumb" in lt
    prof = (_sb("GET", f"/rest/v1/marketing_gbp_profiles?company_id=eq.{cid}"
                "&select=services") or [{}])[0]
    on_gbp = {_norm(str(s)) for s in (prof.get("services") or [])}
    # GBP services also witness capabilities (base name present -> capable)
    return caps, on_gbp, plumbing_ok


def stage_client(slug: str, cid: str, bank: dict, cap: int,
                 dry: bool) -> int:
    caps, on_gbp, plumbing_ok = client_capabilities(slug, cid)
    sugg = _sb("GET", f"/rest/v1/marketing_gbp_suggestions?company_id=eq.{cid}"
               "&item_type=eq.service&select=item,status") or []
    known = {_norm(s["item"]) for s in sugg}
    staged = []
    for base, fam in bank.items():
        gated = isinstance(fam, dict)
        variants = fam["variants"] if gated else fam
        if gated and fam.get("license_gate") == "plumbing" and not plumbing_ok:
            continue
        base_capable = (base in caps
                        or _norm(base.replace("-", " ")) in on_gbp
                        or any(_norm(base.replace("-", " ")) in g for g in on_gbp))
        if not base_capable:
            continue
        for v in variants:
            n = _norm(v["name"])
            if n in on_gbp or n in known or (v.get("vol") or 0) <= 0:
                continue
            staged.append(v["name"])
            known.add(n)
            if len(staged) >= cap:
                break
        if len(staged) >= cap:
            break
    if not staged:
        return 0
    print(f"  {slug}: +{len(staged)} long-tail service(s): "
          + ", ".join(staged[:8]) + (" ..." if len(staged) > 8 else ""))
    if dry:
        return len(staged)
    for name in staged:
        _sb("POST", "/rest/v1/marketing_gbp_suggestions",
            {"company_id": cid, "item": name, "item_type": "service",
             "status": "open", "verdict": "ADD", "auto_safe": True,
             "source": "service-bank", "confidence": 0.9,
             "reason": "volume-validated long-tail variant (A5 weekly bank)"},
            prefer="return=minimal")
    return len(staged)




def _active_cids() -> set:
    """Companies the engines may touch. Cancelled/departed clients (Mold
    Solutionz class, dead 09-09) must never be staged, applied, or written
    to — 70 of its suggestions were sitting open because nothing filtered."""
    return {c["id"] for c in _sb(
        "GET", "/rest/v1/companies?status=eq.Active&select=id") or []}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cap", type=int, default=40,
                    help="max new variants staged per client per run")
    a = ap.parse_args()
    bank = load_bank()
    inv = {s: c for c, s in slug_map().items()}
    slugs = [a.slug] if a.slug else sorted(inv)
    total = 0
    active = _active_cids()
    for slug in slugs:
        cid = inv.get(slug)
        if not cid or cid not in active:
            continue
        try:
            total += stage_client(slug, cid, bank, a.cap, a.dry_run)
        except Exception as e:  # noqa: BLE001
            print(f"  {slug}: ERROR {str(e)[:120]}")
    print(f"service-bank: {total} variant(s) staged"
          f"{' [dry-run]' if a.dry_run else ''}")
    if not a.dry_run and not a.slug:
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": "heartbeat:service-bank",
             "v": {"at": datetime.now(timezone.utc).isoformat(),
                   "staged": total}},
            prefer="resolution=merge-duplicates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
