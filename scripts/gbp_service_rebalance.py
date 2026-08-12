#!/usr/bin/env python3
"""
gbp_service_rebalance.py — un-jam a GBP services list that exceeds Google's
100-items-per-category cap (System: GBP).

Google validates EVERY full-list serviceItems PATCH against the cap, so a
listing that drifted over it (Crew 2026-08-12: 170 items under the primary
category at rest) rejects every write we try — descriptions, adds, everything
"silently" fails with the same 400. This tool restores writability by working
WITHIN the existing categories only:

  1. Read serviceItems + categories; count items per category (free-form items
     carry a category field; structured items belong to the category whose
     serviceTypes catalog lists their serviceTypeId).
  2. Drop exact/normalized duplicate names automatically (same name modulo
     case/punctuation/whitespace), keeping the one with a description. A
     structured item always survives its free-form twin (it is the
     Google-canonical shape); the twin's description is copied over first if
     the structured one is blank.
  3. Reassign free-form services to the existing category that fits them best
     semantically (ONE claude-sonnet-5 call, batched: name -> ranked category
     ids), packing every category to at most 100 - HEADROOM items. Structured
     items never move (their serviceTypeId is bound to its catalog category).
  4. If some services STILL cannot fit anywhere (every category full), nothing
     is written and nothing is silently removed: the overflow is reported and
     ONE marketing_action_plan card is seeded (idempotent by action_key) with
     the proposed keep/drop list for a human to decide.
  5. Apply (--apply) = validateOnly preflight, then the real PATCH
     (updateMask=serviceItems), then a re-read to verify counts. Descriptions
     travel with their items; original item order is preserved (minus dropped
     duplicates); categories are never added, removed, or changed — that edit
     stays a one-click human decision.

Every applied rebalance logs one plain-English row to marketing_gbp_changes.

Usage:
    python3 scripts/gbp_service_rebalance.py --slug crew-restoration-construction
    python3 scripts/gbp_service_rebalance.py --slug crew-restoration-construction --apply
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gbp  # noqa: E402 — token/location/AI/log helpers live there

ROOT = Path(__file__).resolve().parent.parent

CAP = 100            # Google's hard limit on service items per category
HEADROOM = 5         # pack to CAP - HEADROOM so routine adds keep working
MODEL = "claude-sonnet-5"
OVERFLOW_SEED = "gbp-service-overflow"  # action_key seed for the decision card


def _norm_name(name: str) -> str:
    """Duplicate key: same name modulo case/punctuation/whitespace."""
    return re.sub(r"[^a-z0-9]+", " ", str(name or "").lower()).strip()


def _load_location(slug: str) -> tuple[str | None, str | None, str | None, dict | None, str | None]:
    """(cid, token, place, location, error)."""
    cid = gbp.company_id_for(slug)
    pi = ROOT / "clients" / slug / "plan-input.json"
    brand = json.loads(pi.read_text()).get("brand", {}) if pi.exists() else {}
    token = gbp.get_access_token(cid) if cid else None
    place = brand.get("place_id") or gbp._place_id_from_connection(cid)
    if not (token and place):
        return cid, None, None, None, "no token / place_id"
    loc = gbp.find_location(token, place)
    if not loc:
        return cid, token, place, None, "no GBP location"
    return cid, token, place, loc, None


def _categories(loc: dict) -> tuple[list[dict], dict[str, str], dict[str, str]]:
    """(existing categories [{id, label}], serviceTypeId -> category id,
    serviceTypeId -> display name). The location read carries each category's
    serviceTypes catalog (verified live 2026-08-12, crew read)."""
    cats_blk = loc.get("categories", {}) or {}
    cats = [c for c in [cats_blk.get("primaryCategory")] if c]
    cats += list(cats_blk.get("additionalCategories") or [])
    out, st_cat, st_name = [], {}, {}
    for c in cats:
        out.append({"id": c["name"], "label": c.get("displayName") or c["name"]})
        for st in c.get("serviceTypes") or []:
            st_cat.setdefault(st["serviceTypeId"], c["name"])
            st_name.setdefault(st["serviceTypeId"], st.get("displayName") or st["serviceTypeId"])
    return out, st_cat, st_name


def _item_category(item: dict, st_cat: dict[str, str], valid: set[str],
                   primary: str) -> str:
    if "structuredServiceItem" in item:
        return st_cat.get(item["structuredServiceItem"].get("serviceTypeId", ""), primary)
    # stale category tags (removed categories) count against the primary,
    # which is also where Google validates them (see add_services' heal)
    cat = (item.get("freeFormServiceItem") or {}).get("category")
    return cat if cat in valid else primary


def _item_display(item: dict, st_name: dict[str, str]) -> str:
    if "structuredServiceItem" in item:
        stid = item["structuredServiceItem"].get("serviceTypeId", "")
        return st_name.get(stid) or gbp._svc_label(stid)
    return (((item.get("freeFormServiceItem") or {}).get("label") or {})
            .get("displayName") or "")


def _counts(items: list[dict], cats: list[dict], st_cat: dict[str, str]) -> dict[str, int]:
    primary = cats[0]["id"]
    valid = {c["id"] for c in cats}
    out = {c["id"]: 0 for c in cats}
    for it in items:
        out[_item_category(it, st_cat, valid, primary)] += 1
    return out


def _dedupe(items: list[dict], st_name: dict[str, str]) -> tuple[list[dict], list[str]]:
    """Drop normalized-duplicate names; keep the best of each group.
    Winner: any structured item (canonical, immovable) else the free-form with
    the longest description, else the first seen. The longest description in
    the group is copied onto a winner that lacks one, so no copy is lost."""
    groups: dict[str, list[int]] = {}
    for i, it in enumerate(items):
        key = _norm_name(_item_display(it, st_name))
        if key:
            groups.setdefault(key, []).append(i)
    drop: set[int] = set()
    dropped_names: list[str] = []
    for key, idxs in groups.items():
        if len(idxs) < 2:
            continue
        structured = [i for i in idxs if "structuredServiceItem" in items[i]]
        if structured:
            winner = structured[0]
        else:
            winner = max(idxs, key=lambda i: (len(gbp._item_desc(items[i])), -i))
        best_desc = max((gbp._item_desc(items[i]) for i in idxs), key=len, default="")
        if best_desc and not gbp._item_desc(items[winner]):
            gbp._set_item_desc(items[winner], best_desc)
        for i in idxs:
            if i != winner:
                drop.add(i)
                dropped_names.append(_item_display(items[i], st_name))
    kept = [it for i, it in enumerate(items) if i not in drop]
    return kept, sorted(dropped_names)


def _rank_categories(free_items: list[tuple[int, dict]], cats: list[dict],
                     business: str, st_cat: dict[str, str], st_name: dict[str, str]) -> dict[int, list[str]]:
    """ONE model call: free-form service name -> ranked best-fit category ids.
    Returns {item index: [category id, ...]} (best first, ids validated)."""
    by_label = {c["label"].strip().lower(): c["id"] for c in cats}
    by_id = {c["id"]: c["id"] for c in cats}
    valid = {c["id"] for c in cats}
    primary = cats[0]["id"]
    sysmsg = (
        "You organize the services list on a local company's Google Business "
        "Profile. Given the listing's categories and its free-form service "
        "names, assign every service to the category that best fits it "
        "semantically (a roofing service belongs under a roofing category, a "
        "rebuild under construction, and so on). Rules:\n"
        "- Use ONLY the provided category ids, exactly as given.\n"
        "- Rank the 3 best-fitting categories per service, best first.\n"
        "- Every service key in the input must appear in the output.\n"
        'Return ONLY JSON: {"assignments": {"<key>": ["<best category id>", '
        '"<second>", "<third>"], ...}}')
    user = json.dumps({
        "business": business,
        "categories": [{"id": c["id"], "name": c["label"]} for c in cats],
        "services": [{"key": str(pos),
                      "name": _item_display(it, st_name),
                      "current_category": _item_category(it, st_cat, valid, primary)}
                     for pos, (_i, it) in enumerate(free_items)],
    }, indent=1)
    # keys above are positions within free_items, remap to item indexes below
    out = gbp._anthropic_json(sysmsg, "Assign the categories.\n\nDATA:\n" + user,
                              model=MODEL)
    raw = out.get("assignments") or {}
    ranked: dict[int, list[str]] = {}
    for pos, (idx, _it) in enumerate(free_items):
        ids = []
        for c in (raw.get(str(pos)) or []):
            cid = by_id.get(str(c)) or by_label.get(str(c).strip().lower())
            if cid and cid not in ids:
                ids.append(cid)
        ranked[idx] = ids
    return ranked


def rebalance(slug: str, apply: bool = False) -> str:
    cid, token, place, loc, err = _load_location(slug)
    if err:
        return f"{slug}: skip ({err})"
    cats, st_cat, st_name = _categories(loc)
    if not cats:
        return f"{slug}: skip (no categories on the listing)"
    primary = cats[0]["id"]
    label = {c["id"]: c["label"] for c in cats}
    items = json.loads(json.dumps(loc.get("serviceItems", [])))
    if not items:
        return f"{slug}: no service items on the listing"

    before = _counts(items, cats, st_cat)
    over = {c: n for c, n in before.items() if n > CAP}
    print(f"  [{slug}] {len(items)} service items across {len(cats)} categories (cap {CAP}/category)")
    for c in cats:
        flag = "  <-- OVER CAP" if before[c["id"]] > CAP else ""
        print(f"    before  {c['label']}: {before[c['id']]}{flag}")
    if not over:
        print("    listing is already within the cap in every category")

    # ---- 1. duplicates (automatic removals) --------------------------------
    items, dropped = _dedupe(items, st_name)
    if dropped:
        print(f"    duplicates dropped ({len(dropped)}): {dropped}")

    # ---- 2. semantic assignment for every free-form item ------------------
    free_items = [(i, it) for i, it in enumerate(items) if "freeFormServiceItem" in it]
    ranked = _rank_categories(free_items, cats,
                              loc.get("title") or slug, st_cat, st_name) if free_items else {}

    # structured items are the fixed load; free-form items pack greedily into
    # their ranked category with room (soft cap first, hard cap as fallback)
    valid = {c["id"] for c in cats}
    load = {c["id"]: 0 for c in cats}
    for i, it in enumerate(items):
        if "structuredServiceItem" in it:
            load[_item_category(it, st_cat, valid, primary)] += 1
    soft = CAP - HEADROOM
    room_order = [c["id"] for c in cats]
    moves: list[str] = []
    overflow: list[str] = []
    for i, it in free_items:
        cur = _item_category(it, st_cat, valid, primary)
        prefs = ranked.get(i) or []
        if cur not in prefs:
            prefs = prefs + [cur]
        prefs = prefs + sorted((c for c in room_order if c not in prefs),
                               key=lambda c: load[c])
        dest = next((c for c in prefs if load[c] < soft), None) \
            or next((c for c in prefs if load[c] < CAP), None)
        if dest is None:
            overflow.append(_item_display(it, st_name))
            load[cur] += 1  # it has to live somewhere; counts against current
            continue
        load[dest] += 1
        if dest != cur:
            moves.append(f"{_item_display(it, st_name)}: "
                         f"{label.get(cur, cur)} -> {label[dest]}")
        it["freeFormServiceItem"]["category"] = dest

    after = {c["id"]: load[c["id"]] for c in cats}
    print(f"    moves planned: {len(moves)}")
    for m in moves:
        print(f"      . {m}")
    for c in cats:
        print(f"    after   {c['label']}: {after[c['id']]}")

    # ---- 3. overflow: never silently remove distinct services -------------
    if overflow:
        print(f"    OVERFLOW — {len(overflow)} service(s) cannot fit under the cap "
              f"in any category: {overflow}")
        short = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()) \
            .get("brand", {}).get("short_name") or loc.get("title") or slug
        keep_n = len(items) - len(overflow)
        rationale = (
            f"Google allows at most {CAP} service items per category and this "
            f"listing's {len(cats)} categories are full: {len(items)} services "
            f"remain after removing duplicates, but only {keep_n} fit. Until "
            "the extra services are removed (or a human adds a category, which "
            "we never do automatically), Google rejects every services update "
            "for this client. Proposed: KEEP the "
            f"{keep_n} services that fit; DROP these {len(overflow)}: "
            + ", ".join(overflow) + ".")
        from client_ops_sync import insert_plan_row  # noqa: PLC0415 — heavy module, import on demand
        created = insert_plan_row(
            cid, slug, OVERFLOW_SEED,
            title=f"DECISION: {short} has more Google services than their categories can hold",
            rationale=rationale, action_type="gbp_fix", target=f"gbp:{slug}",
            impact="high", effort="low", dry_run=not apply)
        print(f"    decision card {'seeded' if created else 'already open'} "
              f"(key seed {OVERFLOW_SEED!r})")
        return (f"{slug}: BLOCKED — {len(overflow)} service(s) over capacity; "
                "no write attempted (a human decision card covers the keep/drop)")

    if not apply:
        return (f"{slug}: DRY RUN — {len(dropped)} duplicate(s) to drop, "
                f"{len(moves)} service(s) to re-home; every category lands at or "
                f"under {soft}. Re-run with --apply.")

    # ---- 4. validateOnly preflight, then the real PATCH --------------------
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = json.dumps({"serviceItems": items})
    r = requests.patch(f"{gbp.INFO_API}/{loc['name']}?updateMask=serviceItems&validateOnly=true",
                       headers=hdrs, data=body, timeout=60)
    if not r.ok:
        return f"{slug}: preflight failed {r.status_code}: {r.text[:300]}"
    print("    validateOnly preflight: OK")
    r = requests.patch(f"{gbp.INFO_API}/{loc['name']}?updateMask=serviceItems",
                       headers=hdrs, data=body, timeout=60)
    if not r.ok:
        return f"{slug}: PATCH failed {r.status_code}: {r.text[:300]}"

    # ---- 5. verify: re-read and recount ------------------------------------
    back = gbp.find_location(token, place) or {}
    back_items = back.get("serviceItems", [])
    verify = _counts(back_items, cats, st_cat)
    ok = len(back_items) == len(items) and all(n <= CAP for n in verify.values())
    for c in cats:
        print(f"    verify  {c['label']}: {verify[c['id']]}")
    if not ok:
        return (f"{slug}: PATCH accepted but verification mismatch — read back "
                f"{len(back_items)} items (expected {len(items)}), counts {verify}")

    summary = (f"Reorganized {len(moves)} services across your Google listing's "
               f"categories and removed {len(dropped)} duplicate entries so "
               "updates can flow again")
    gbp.log_change(cid, "service_rebalance", summary, actor="optimizer",
                   meta={"moved": len(moves), "duplicates_dropped": dropped,
                         "before": {label[c]: n for c, n in before.items()},
                         "after": {label[c]: n for c, n in verify.items()}})
    return (f"{slug}: APPLIED — {len(dropped)} duplicate(s) dropped, "
            f"{len(moves)} service(s) re-homed; listing now has {len(back_items)} "
            f"items, max {max(verify.values())} in any category (cap {CAP})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--apply", action="store_true",
                    help="write the rebalanced list to Google (default: dry run)")
    args = ap.parse_args()
    print("  " + rebalance(args.slug, apply=args.apply))
    return 0


if __name__ == "__main__":
    sys.exit(main())
