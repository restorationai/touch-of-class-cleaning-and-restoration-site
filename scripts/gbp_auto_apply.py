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
    # Change-log row (2026-09-29, every client action logs): the Reports tab
    # and monthly summary read marketing_gbp_changes. log_change is fail-soft.
    names = [_svc_display(d) for d in dropped]
    gbp.log_change(cid, "service_remove",
                   f"Cleaned {len(names)} junk service entr{'y' if len(names) == 1 else 'ies'} "
                   f"off your Google listing: {', '.join(names[:8])}"
                   + (" and more" if len(names) > 8 else "") + ".",
                   actor="optimizer", meta={"removed": names})
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
    if r.status_code == 200:
        gbp.log_change(cid, "description",
                       "Business description on your Google listing rewritten to "
                       "highlight your services and service area.",
                       actor="optimizer", meta={"description": text[:750]})
    return "updated" if r.status_code == 200 else f"failed {r.status_code}: {r.text[:100]}"


BLOCKED_KV = "gbp-auto-apply-blocked"


def _access_block(msg: str) -> str | None:
    """A skip that no amount of re-running can clear: we hold no Google
    write access to this listing (no OAuth token / place, or the listing is
    not in the connected account: suspended, unverified, never shared)."""
    m = (msg or "").lower()
    for needle, why in (("no token", "no Google connection (OAuth token / place_id)"),
                        ("no gbp location", "listing not found in the connected Google account"),
                        ("no location", "listing not found in the connected Google account"),
                        ("plan-input.json", "no plan-input.json (client not planned yet)")):
        if needle in m:
            return why
    return None


def run_client(slug: str, cid: str, terms: list[str], apply: bool) -> str | None:
    """Returns an access-block reason when the client's auto-safe items can
    never apply until a human fixes Google access (else None)."""
    plan = stage(cid, slug, terms)
    n_auto = len(plan["add"]) + len(plan["remove"]) + (1 if plan["description"] else 0)
    if n_auto == 0 and not plan["protected"]:
        return None
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
        return None

    done = {"added": 0, "removed": 0, "description": False}
    if plan["add"]:
        msg = gbp.add_services(slug, [_svc_display(a) for a in plan["add"]])
        print(f"  add -> {msg}")
        m_add = re.search(r"added (\d+)/", msg)
        done["added"] = int(m_add.group(1)) if m_add else 0
        blocked = _access_block(msg)
        if blocked:
            # Nothing else below can succeed either (same token/listing).
            print(f"  BLOCKED: {blocked} — {n_auto} auto-safe item(s) wait for access")
            return blocked
        if "skip" not in msg and "failed" not in msg.lower():
            _mark(cid, "service", plan["add"], "applied")
    if plan["remove"]:
        msg = remove_services(slug, cid, plan["remove"])
        print(f"  remove -> {msg}")
        m_rm = re.match(r"removed (\d+)", msg)
        done["removed"] = int(m_rm.group(1)) if m_rm else 0
        if msg.startswith("removed") or "nothing matched" in msg:
            _mark(cid, "service", plan["remove"], "applied")
    if plan["protected"]:
        _mark(cid, "service", plan["protected"], "dismissed")
        print(f"  protected -> {len(plan['protected'])} REMOVE suggestion(s) dismissed (law)")
    if plan["description"]:
        msg = apply_description(slug, cid, plan["description"])
        print(f"  description -> {msg}")
        if msg == "updated":
            done["description"] = True
            rows = _sb("GET", f"/rest/v1/marketing_gbp_suggestions?company_id=eq.{cid}"
                       "&item_type=eq.description&status=eq.open&select=item") or []
            _mark(cid, "description", [r["item"] for r in rows], "applied")
    # Ops ledger line: what Google actually ACCEPTED this run, never the plan
    # (2026-09-29: this used to log the plan every night, e.g. "52 services
    # added" 58 nights running while add_services confirmed 0). The client
    # Reports lines are the per-change marketing_gbp_changes rows written by
    # add_services / remove_services / apply_description; monthly_summary
    # skips this summary as their twin.
    if done["added"] or done["removed"] or done["description"]:
        try:
            from work_log import work_log
            bits = []
            if done["added"]:
                bits.append(f"{done['added']} service{'s' if done['added'] != 1 else ''} added")
            if done["removed"]:
                bits.append(f"{done['removed']} junk entr{'y' if done['removed'] == 1 else 'ies'} cleaned")
            if done["description"]:
                bits.append("business description refreshed")
            work_log(cid, "gbp", "optimizer-auto-apply",
                     f"Google listing tuned automatically: {', '.join(bits)}.",
                     evidence={**plan, "applied": done}, source="gbp_auto_apply.py")
        except Exception:
            pass
    return None


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
    apply = a.apply and not a.dry_run
    blocked: dict[str, dict] = {}
    for slug in slugs:
        cid = inv.get(slug)
        if not cid or cid not in active:
            continue
        try:
            why = run_client(slug, cid, terms, apply=apply)
        except Exception as e:  # noqa: BLE001 — one client never stops the fleet
            print(f"{slug}: ERROR {str(e)[:150]}")
            why = _access_block(str(e))
        if why:
            blocked[cid] = {"slug": slug, "reason": why}
    # ACCESS-BLOCK LEDGER (2026-09-29, optimizer SLA triage): 340 auto-safe
    # items sat >7 days and the watchdog blamed "the nightly apply", but every
    # one belonged to a client whose Google listing we cannot write (no OAuth
    # connection, listing not in the account, GBP suspended). Record them so
    # the SLA can say "blocked on Google access" instead of "apply broken";
    # `since` survives across nights so the age of the block is visible.
    if apply and a.all:
        try:
            prev = ((_sb("GET", f"/rest/v1/ops_kv?k=eq.{BLOCKED_KV}&select=v")
                     or [{}])[0].get("v") or {})
            now = datetime.now(timezone.utc).isoformat()
            for cid, b in blocked.items():
                b["since"] = (prev.get(cid) or {}).get("since") or now
            _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
                {"k": BLOCKED_KV, "v": blocked, "updated_at": now},
                prefer="resolution=merge-duplicates,return=minimal")
            print(f"\naccess-blocked clients: {len(blocked)} -> ops_kv {BLOCKED_KV}")
        except Exception as e:  # noqa: BLE001
            print(f"  [blocked-ledger] warn: {str(e)[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
