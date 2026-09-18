#!/usr/bin/env python3
"""gbp_auto_apply.py — the GBP Optimizer's AUTO half (A1-A3, Santino
2026-09-17, RestorationXpress postmortem).

The optimizer has always RESEARCHED well and shipped nothing: 16 clients,
~700 open suggestions, because applying was one click per item — and each
click is a full Google location update, which slams Google's per-minute
edit quota (the Dry County 429). This script applies the safe classes in
BULK: any number of service changes coalesce into ONE location PATCH via
the existing capped gbp.add_services machinery.

WHAT IT TOUCHES (auto-safe classes only):
  services ADD      -> one batched serviceItems PATCH
  services REMOVE   -> same PATCH, but ONLY removals that survive the
                       REMOVAL LAW (below); junk/duplicate phrases only
  description ADD   -> profile.description PATCH (the researched text)
Categories, names, pages, MERGE and NEEDS-REVIEW are NEVER auto-applied —
those change identity or need judgment, and stay human clicks in the app.

REMOVAL LAW (Santino 2026-09-17, the Dry County biohazard case): a service
is only removable when it is blatantly NOT a real service — junk umbrella
phrases ("Residential Services"), garbled fragments, exact duplicates.
Anything matching the restoration catalog or the PROTECTED terms below is
NEVER removed, whatever the verdict says: most restoration companies do or
would take that work. Protected REMOVE suggestions get dismissed with a
'protected' note so they stop cluttering the panel.

Modes:
    --slug X --dry-run     stage one client (prints every change, writes nothing)
    --slug X --apply       apply one client
    --all --apply          fleet (rides client-ops-sync nightly)
    --purge-protected      one-time fleet dismissal of REMOVE suggestions
                           that violate the law (no GBP writes at all)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import requests  # noqa: E402
import gbp  # noqa: E402  (tokens, find_location, add_services, _sb, INFO_API)
from client_ops_sync import _sb, slug_map  # noqa: E402

# Real-service protection: the whole restoration catalog + terms the law
# explicitly shields. Normalized-substring match in either direction.
PROTECTED_EXTRA = [
    "biohazard", "trauma", "crime scene", "unattended death", "odor",
    "deodoriz", "contents", "board up", "board-up", "tarping",
    "reconstruction", "remodel", "carpet clean", "carpet removal",
    "upholstery", "duct", "sewage", "sewer", "crawl space", "asbestos",
    "lead", "hoarding", "pack out", "pack-out", "storage", "plumbing",
    "leak detection", "roof", "debris", "sanitiz", "disinfect",
    "insurance billing", "insurance claim", "emergency service",
    "hepa", "air scrub", "dehumidif", "moisture", "drying",
]


def _catalog_terms() -> list[str]:
    terms = list(PROTECTED_EXTRA)
    try:
        cat = json.loads((ROOT / "templates/restoration/services.json").read_text())
        items = cat if isinstance(cat, list) else cat.get("services", [])
        for s in items:
            if isinstance(s, dict):
                terms.append(s.get("display_name") or "")
                terms.append((s.get("slug") or "").replace("-", " "))
                terms += s.get("secondary_keywords") or []
    except Exception:
        pass
    return [t for t in terms if t]


def _norm(t: str) -> str:
    t = re.sub(r"^job_type_id:", "", (t or "").strip())
    return re.sub(r"[^a-z0-9 ]+", " ", t.replace("_", " ").lower()).strip()


def is_protected(service: str, terms: list[str]) -> bool:
    n = _norm(service)
    if not n:
        return False
    for t in terms:
        tn = _norm(t)
        if tn and (tn in n or n in tn):
            return True
    return False


def _svc_display(item: str) -> str:
    return re.sub(r"^job_type_id:", "", item).replace("_", " ").strip()


def stage(cid: str, slug: str, terms: list[str]) -> dict:
    """Classify every open suggestion into the auto plan + human leftovers."""
    rows = _sb("GET", f"/rest/v1/marketing_gbp_suggestions?company_id=eq.{cid}"
               "&status=eq.open&select=item,item_type,verdict,reason") or []
    plan = {"add": [], "remove": [], "protected": [], "description": None,
            "human": {"category": 0, "name": 0, "page": 0,
                      "needs_review": 0, "merge": 0}}
    for r in rows:
        t, v = r["item_type"], (r.get("verdict") or "").upper()
        if t == "service":
            if v == "ADD":
                plan["add"].append(r["item"])
            elif v == "REMOVE":
                if is_protected(r["item"], terms):
                    plan["protected"].append(r["item"])
                else:
                    plan["remove"].append(r["item"])
            elif v == "MERGE":
                plan["human"]["merge"] += 1
            elif v == "NEEDS-REVIEW":
                plan["human"]["needs_review"] += 1
        elif t == "description" and v == "ADD":
            plan["description"] = (r.get("reason") or "").strip()[:750]
        elif t in ("category", "name", "page"):
            plan["human"][t] = plan["human"].get(t, 0) + 1
    return plan


def _mark(cid: str, item_type: str, items: list[str], status: str,
          note: str | None = None) -> None:
    for it in items:
        import urllib.parse
        enc = urllib.parse.quote(it, safe="")
        body = {"status": status}
        _sb("PATCH", f"/rest/v1/marketing_gbp_suggestions?company_id=eq.{cid}"
            f"&item_type=eq.{item_type}&item=eq.{enc}&status=eq.open", body)


def remove_services(slug: str, cid: str, removals: list[str]) -> str:
    """One serviceItems PATCH that drops the junk entries. Mirrors
    add_services' read-modify-write; never touches anything else."""
    brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
    token = gbp.get_access_token(cid)
    place = brand.get("place_id") or gbp._place_id_from_connection(cid)
    if not (token and place):
        return "skip (no token/place)"
    loc = gbp.find_location(token, place)
    if not loc:
        return "skip (no location)"
    drop = {_norm(x) for x in removals}
    keep, dropped = [], []
    for s in loc.get("serviceItems", []):
        if "freeFormServiceItem" in s:
            nm = ((s["freeFormServiceItem"].get("label") or {}).get("displayName") or "")
        else:
            nm = (s.get("structuredServiceItem") or {}).get("serviceTypeId") or ""
        if _norm(nm) in drop:
            dropped.append(nm)
        else:
            keep.append(s)
    if not dropped:
        return "nothing matched on the live listing"
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.patch(f"{gbp.INFO_API}/{loc['name']}?updateMask=serviceItems",
                       headers=hdrs, data=json.dumps({"serviceItems": keep}),
                       timeout=60)
    if r.status_code != 200:
        return f"PATCH failed {r.status_code}: {r.text[:120]}"
    return f"removed {len(dropped)}: {', '.join(_svc_display(d) for d in dropped[:6])}" \
           + (" ..." if len(dropped) > 6 else "")


def apply_description(slug: str, cid: str, text: str) -> str:
    brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
    token = gbp.get_access_token(cid)
    place = brand.get("place_id") or gbp._place_id_from_connection(cid)
    if not (token and place):
        return "skip (no token/place)"
    loc = gbp.find_location(token, place)
    if not loc:
        return "skip (no location)"
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.patch(f"{gbp.INFO_API}/{loc['name']}?updateMask=profile.description",
                       headers=hdrs,
                       data=json.dumps({"profile": {"description": text[:750]}}),
                       timeout=60)
    return "updated" if r.status_code == 200 else f"failed {r.status_code}: {r.text[:100]}"


def run_client(slug: str, cid: str, terms: list[str], apply: bool) -> None:
    plan = stage(cid, slug, terms)
    n_auto = len(plan["add"]) + len(plan["remove"]) + (1 if plan["description"] else 0)
    if n_auto == 0 and not plan["protected"]:
        return
    print(f"\n== {slug}")
    if plan["add"]:
        print(f"  ADD ({len(plan['add'])}): " + ", ".join(_svc_display(a) for a in plan["add"]))
    if plan["remove"]:
        print(f"  REMOVE junk ({len(plan['remove'])}): " + ", ".join(_svc_display(x) for x in plan["remove"]))
    if plan["protected"]:
        print(f"  PROTECTED by removal law ({len(plan['protected'])} kept): "
              + ", ".join(_svc_display(x) for x in plan["protected"]))
    if plan["description"]:
        print(f"  DESCRIPTION: {plan['description'][:90]}...")
    hum = {k: v for k, v in plan["human"].items() if v}
    if hum:
        print(f"  left for humans: {hum}")
    if not apply:
        print("  [dry-run] nothing written")
        return

    if plan["add"]:
        msg = gbp.add_services(slug, [_svc_display(a) for a in plan["add"]])
        print(f"  add -> {msg}")
        if "skip" not in msg and "failed" not in msg.lower():
            _mark(cid, "service", plan["add"], "applied")
    if plan["remove"]:
        msg = remove_services(slug, cid, plan["remove"])
        print(f"  remove -> {msg}")
        if msg.startswith("removed") or "nothing matched" in msg:
            _mark(cid, "service", plan["remove"], "applied")
    if plan["protected"]:
        _mark(cid, "service", plan["protected"], "dismissed")
        print(f"  protected -> {len(plan['protected'])} REMOVE suggestion(s) dismissed (law)")
    if plan["description"]:
        msg = apply_description(slug, cid, plan["description"])
        print(f"  description -> {msg}")
        if msg == "updated":
            rows = _sb("GET", f"/rest/v1/marketing_gbp_suggestions?company_id=eq.{cid}"
                       "&item_type=eq.description&status=eq.open&select=item") or []
            _mark(cid, "description", [r["item"] for r in rows], "applied")
    try:
        from work_log import work_log
        work_log(cid, "gbp", "optimizer-auto-apply",
                 f"Google listing tuned automatically: {len(plan['add'])} services added"
                 + (f", {len(plan['remove'])} junk entries cleaned" if plan["remove"] else "")
                 + (", business description refreshed" if plan["description"] else "") + ".",
                 evidence=plan, source="gbp_auto_apply.py")
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--purge-protected", action="store_true",
                    help="fleet: dismiss law-violating REMOVE suggestions, no GBP writes")
    a = ap.parse_args()
    terms = _catalog_terms()
    inv = {s: c for c, s in slug_map().items()}

    if a.purge_protected:
        purged = 0
        for slug, cid in sorted(inv.items()):
            plan = stage(cid, slug, terms)
            if plan["protected"]:
                _mark(cid, "service", plan["protected"], "dismissed")
                print(f"{slug}: dismissed {len(plan['protected'])} protected REMOVE(s): "
                      + ", ".join(_svc_display(x) for x in plan["protected"][:5]))
                purged += len(plan["protected"])
        print(f"\npurge complete: {purged} law-violating REMOVE suggestion(s) dismissed")
        return 0

    slugs = [a.slug] if a.slug else (sorted(inv) if a.all else [])
    if not slugs:
        sys.exit("need --slug or --all")
    # Cancelled/departed clients never get writes (Mold Solutionz class).
    active = {c["id"] for c in _sb(
        "GET", "/rest/v1/companies?status=eq.Active&select=id") or []}
    for slug in slugs:
        cid = inv.get(slug)
        if not cid or cid not in active:
            continue
        try:
            run_client(slug, cid, terms, apply=a.apply and not a.dry_run)
        except Exception as e:  # noqa: BLE001 — one client never stops the fleet
            print(f"{slug}: ERROR {str(e)[:150]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
