#!/usr/bin/env python3
"""rename_pipeline.py — one derived stage per client for the Profile Rename
program (Santino 2026-09-15: "now it is a big part of our system").

The rename journey was invisible: conversation state lived in ops_kv,
DBA facts in integration_settings.rename_intent, citation progress in
BrightLocal metadata, and the GBP execution nowhere at all. This derives
ONE canonical stage per client — from verifiable signals only, per the
Build Stages board law — and mirrors the whole map to ops_kv
`rename-pipeline`, which the build-stages edge function serves to the
board's RENAME tab.

STAGES (the client's journey, in order):
  not_started        no name candidates exist yet
  researched         candidates seeded, conversation not opened
  outreach           pitch sent / options out — client is choosing
  name_locked        name chosen/confirmed — waiting on their DBA filing
  citations_building DBA verified — listings being built under the name
  ready_for_rename   citations live — the one-time GBP change can happen
                     (NEVER auto-executed: Amin law, human clicks)
  renamed_verifying  GBP renamed — watching Google verification
  live_verified      verification cleared — journey complete
  keep_name          client decided to keep their name (parking lane)

Signals: marketing_gbp_suggestions (item_type=name statuses), ops_kv
rename-convo:{cid} (stage/chosen/at), integration_settings.rename_intent
(decision, dba_verified, dba_doc_url, gbp_renamed_at,
gbp_verification), user_integrations provider=citations
(bl_ordered statuses). New execution fields (gbp_renamed_at,
gbp_verification) live in rename_intent — set by whoever performs the
rename, read here.

`since` is sticky: a client whose stage is unchanged keeps the original
entry timestamp, so days-in-stage means what it says.

Rides call-intel.yml (~30 min freshness). CLI:
    python3 scripts/rename_pipeline.py [--dry-run] [--slug SLUG]
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

KV_KEY = "rename-pipeline"
MIN_LIVE_FOR_READY = 8   # enough live listings to safely execute the rename


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def derive(co: dict, sugs: list[dict], convo: dict | None,
           bl_ordered: list[dict]) -> dict:
    ri = (co.get("integration_settings") or {}).get("rename_intent") or {}
    stage = "not_started"
    detail: dict = {}
    chosen = next((s["item"] for s in sugs if s.get("status") == "chosen"),
                  None) or (convo or {}).get("chosen") or ri.get("dba_name")
    live = [o for o in bl_ordered
            if str(o.get("status", "")).lower() in ("live", "updated",
                                                    "existing")]
    if bl_ordered:
        detail["citations"] = {"live": len(live), "ordered": len(bl_ordered)}
    if chosen:
        detail["chosen"] = chosen
    if ri.get("dba_doc_url"):
        detail["dba_doc_url"] = ri["dba_doc_url"]
    if (convo or {}).get("at"):
        detail["last_convo_at"] = convo["at"]

    open_sugs = [s for s in sugs if s.get("status") == "open"]
    kv_stage = str((convo or {}).get("stage") or "")

    if ri.get("decision") == "keep" or (kv_stage == "closed"
                                        and not chosen and not open_sugs
                                        and sugs):
        stage = "keep_name"
    elif ri.get("gbp_verification") == "verified":
        stage = "live_verified"
    elif ri.get("gbp_renamed_at"):
        stage = "renamed_verifying"
        detail["renamed_at"] = ri["gbp_renamed_at"]
    elif ri.get("dba_verified") and len(live) >= min(
            MIN_LIVE_FOR_READY, max(len(bl_ordered), 1)):
        stage = "ready_for_rename"
    elif ri.get("dba_verified"):
        stage = "citations_building"
    elif chosen or kv_stage in ("confirmed", "awaiting_dba"):
        stage = "name_locked"
    elif kv_stage in ("pitched", "options"):
        stage = "outreach"
    elif open_sugs:
        stage = "researched"
    return {"stage": stage, **detail}


def _mark(slug: str, field: str, value) -> int:
    """Phase 3b: stamp GBP-execution facts into rename_intent (the human
    just performed the rename, or verification cleared)."""
    inv = slug_map()
    cid = next((c for c, s in inv.items() if s == slug), None)
    if not cid:
        sys.exit(f"unknown slug {slug}")
    rows = _sb("GET", f"/rest/v1/companies?id=eq.{cid}"
               "&select=integration_settings") or []
    ints = (rows[0].get("integration_settings") if rows else {}) or {}
    ri = dict(ints.get("rename_intent") or {})
    ri[field] = value
    ints["rename_intent"] = ri
    _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
        {"integration_settings": ints})
    print(f"{slug}: rename_intent.{field} = {value}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="sync",
                    choices=("sync", "mark-renamed", "mark-verified"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--slug")
    a = ap.parse_args()
    if a.cmd == "mark-renamed":
        if not a.slug:
            sys.exit("mark-renamed needs --slug")
        return _mark(a.slug, "gbp_renamed_at", _now())
    if a.cmd == "mark-verified":
        if not a.slug:
            sys.exit("mark-verified needs --slug")
        return _mark(a.slug, "gbp_verification", "verified")
    inv = {c: s for s, c in {s: c for c, s in slug_map().items()}.items()}
    comps = _sb("GET", "/rest/v1/companies?status=eq.Active"
                "&select=id,name,integration_settings") or []
    sug_rows = _sb("GET", "/rest/v1/marketing_gbp_suggestions"
                   "?item_type=eq.name&select=company_id,item,status") or []
    sugs_by: dict[str, list] = {}
    for s in sug_rows:
        sugs_by.setdefault(s["company_id"], []).append(s)
    kv_rows = _sb("GET", "/rest/v1/ops_kv?k=like.rename-convo:*"
                  "&select=k,v") or []
    convo_by = {r["k"].split(":", 1)[1]: r["v"] for r in kv_rows
                if isinstance(r.get("v"), dict)}
    cit_rows = _sb("GET", "/rest/v1/user_integrations?provider=eq.citations"
                   "&select=client_id,bl_ordered:connection_metadata->bl_ordered") or []
    bl_by = {r["client_id"]: (r.get("bl_ordered") or []) for r in cit_rows}

    # RECONCILE (Santino 2026-09-18, Kenny/Veterans): whatever lane a DBA
    # arrives through (text, email forward, hub upload, an operator at
    # 11pm), the next sweep trues up the two links that used to be manual:
    #   1. a verified DBA with no dba_doc_url picks up the newest document
    #      sitting in branding/{cid}/docs/dba
    #   2. a recorded dba_name marks its matching candidate row "chosen"
    #      and dismisses the siblings — a decided name never displays as an
    #      open question.
    if not a.dry_run:
        import os as _os
        import requests as _rq2
        _sb_url = _os.environ["SUPABASE_URL"].rstrip("/")
        _sb_key = _os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        _H = {"apikey": _sb_key, "Authorization": f"Bearer {_sb_key}",
              "Content-Type": "application/json"}

        def _norm_nm(t: str) -> str:
            import re as _re
            t = _re.sub(r"[‐-―−]", "-", str(t or ""))
            t = _re.sub(r"\s*&\s*", " and ", t)
            return _re.sub(r"\s+", " ", t).strip().lower()

        for co in comps:
            cid, ints = co["id"], co.get("integration_settings") or {}
            ri = dict(ints.get("rename_intent") or {})
            # 1. doc link heal
            if (ri.get("dba_filed") or ri.get("dba_verified"))                     and not ri.get("dba_doc_url"):
                try:
                    lr = _rq2.post(f"{_sb_url}/storage/v1/object/list/branding",
                                   headers=_H,
                                   json={"prefix": f"{cid}/docs/dba",
                                         "limit": 20}, timeout=30)
                    objs = [o for o in (lr.json() if lr.ok else [])
                            if isinstance(o, dict) and o.get("name")]
                    objs.sort(key=lambda o: (not str(o["name"]).lower()
                                             .endswith(".pdf"),
                                             str(o.get("created_at") or "")))
                    if objs:
                        ri["dba_doc_url"] = (f"{_sb_url}/storage/v1/object/"
                                             f"public/branding/{cid}/docs/dba/"
                                             f"{objs[0]['name']}")
                        ints["rename_intent"] = ri
                        co["integration_settings"] = ints
                        _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
                            {"integration_settings": ints})
                        print(f"  >> heal: {co.get('name')} dba_doc_url <- "
                              f"{objs[0]['name']}")
                except Exception as e:  # noqa: BLE001 — heal never breaks sync
                    print(f"  doc-link heal failed for {co.get('name')}: "
                          f"{str(e)[:80]}")
            # 2. chosen-candidate heal
            dba = ri.get("dba_name")
            rows = sugs_by.get(cid) or []
            if dba and rows and not any(x.get("status") == "chosen"
                                        for x in rows):
                target = next((x for x in rows
                               if _norm_nm(x["item"]) == _norm_nm(dba)), None)
                if target:
                    from urllib.parse import quote as _q
                    for x in rows:
                        if x.get("status") == "dismissed":
                            continue
                        st = ("chosen" if x is target else "dismissed")
                        _sb("PATCH", "/rest/v1/marketing_gbp_suggestions"
                            f"?company_id=eq.{cid}&item_type=eq.name"
                            f"&item=eq.{_q(x['item'])}",
                            {"status": st,
                             "reason": ("DBA on record matches — healed by "
                                        "the sweep" if st == "chosen" else
                                        "name decision final (DBA on record)")})
                        x["status"] = st
                    print(f"  >> heal: {co.get('name')} slate finalized "
                          f"-> {target['item'][:50]}")

    # PHASE 3c (2026-09-16, A4): verification poll. For every client whose
    # GBP rename was executed (gbp_renamed_at) but not yet confirmed, read
    # the LIVE GBP title and compare against the chosen name. Match ->
    # stamp gbp_verification=verified right here, so the board flips to
    # live_verified in this same sweep and nobody has to remember
    # mark-verified. No match -> print the watch line (a rename Google
    # rejects silently reverts the title; the elapsed days make that
    # visible). Poll is read-only against Google — the rename itself stays
    # a human act (Amin law).
    if not a.dry_run:
        gbp_rows = _sb("GET", "/rest/v1/marketing_gbp_profiles"
                       "?select=company_id,location_name") or []
        loc_by = {g["company_id"]: g.get("location_name") for g in gbp_rows}
        for co in comps:
            cid, ints = co["id"], co.get("integration_settings") or {}
            ri = dict(ints.get("rename_intent") or {})
            if not ri.get("gbp_renamed_at") or \
                    ri.get("gbp_verification") == "verified":
                continue
            chosen = next((x["item"] for x in sugs_by.get(cid, [])
                           if x.get("status") == "chosen"), None) \
                or ri.get("dba_name") or ""
            loc = loc_by.get(cid)
            if not (chosen and loc):
                continue
            try:
                import requests as _rq
                from gbp import get_access_token
                tok = get_access_token(cid)
                if not tok:
                    continue
                r = _rq.get("https://mybusinessbusinessinformation."
                            f"googleapis.com/v1/{loc}?readMask=title",
                            headers={"Authorization": f"Bearer {tok}"},
                            timeout=30)
                live_title = (r.json().get("title") or "").strip()
            except Exception as e:  # noqa: BLE001 — poll never breaks sync
                print(f"  3c poll failed for {co.get('name')}: "
                      f"{str(e)[:80]}")
                continue
            norm = lambda t: " ".join(t.lower().split())  # noqa: E731
            if norm(live_title) == norm(chosen):
                ri["gbp_verification"] = "verified"
                ri["gbp_verified_at"] = _now()
                ints["rename_intent"] = ri
                co["integration_settings"] = ints  # derive sees it this run
                _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
                    {"integration_settings": ints})
                print(f"  >> 3c VERIFIED: {co.get('name')} GBP now shows "
                      f"'{live_title}'")
                try:
                    from work_log import work_log
                    work_log(cid, "citations", "gbp-rename-verified",
                             "Google Business Profile rename is live and "
                             f"verified: \"{live_title}\".",
                             evidence={"title": live_title},
                             source="rename_pipeline.py")
                except Exception:
                    pass
            else:
                print(f"  3c watching {co.get('name')}: GBP still "
                      f"'{live_title[:50]}' (renamed "
                      f"{ri['gbp_renamed_at'][:10]})")

    prev_rows = _sb("GET", f"/rest/v1/ops_kv?k=eq.{KV_KEY}&select=v") or []
    prev = (prev_rows[0]["v"] if prev_rows else {}) or {}
    prev_clients = prev.get("clients") or {}

    out: dict = {}
    for co in comps:
        cid = co["id"]
        slug = inv.get(cid)
        if a.slug and slug != a.slug:
            continue
        d = derive(co, sugs_by.get(cid, []), convo_by.get(cid),
                   bl_by.get(cid, []))
        if d["stage"] == "not_started" and cid not in prev_clients:
            continue  # keep the map tight: only clients in the program
        old = prev_clients.get(cid) or {}
        d["since"] = (old.get("since") if old.get("stage") == d["stage"]
                      else _now())
        d["name"] = (co.get("name") or "").strip()
        d["slug"] = slug
        out[cid] = d
        print(f"  {d['stage']:18} {(d['name'] or cid)[:34]:36} "
              f"{('-> ' + (d.get('chosen') or ''))[:52]}")

    # PHASE 3a (2026-09-15): stage-transition prompts. Entering
    # ready_for_rename files ONE pinned [TODO-SANTINO] note — the GBP name
    # change is always a deliberate human act (Amin law), so the system's
    # job is to make sure nobody misses the moment citations go live.
    if not a.dry_run:
        for cid, d in out.items():
            old_stage = (prev_clients.get(cid) or {}).get("stage")
            if d["stage"] == "ready_for_rename" and old_stage != "ready_for_rename":
                cites = d.get("citations") or {}
                _sb("POST", "/rest/v1/marketing_ops_notes",
                    {"company_id": cid, "status": "open",
                     "author": "rename_pipeline",
                     "body": (f"[TODO-SANTINO] READY FOR GBP RENAME: "
                              f"{d.get('name')} — citations are live "
                              f"({cites.get('live', '?')} of "
                              f"{cites.get('ordered', '?')}) under the new "
                              f"name:\n{d.get('chosen')}\n"
                              "TIER-1 EVIDENCE CHECKLIST before executing "
                              "(Santino 2026-09-16):\n"
                              "  [ ] aggregator submissions under new name "
                              "(AUTO with every citation order since "
                              "2026-09-16: Data Axle + Neustar + YP Network; "
                              "pre-A3 campaigns need the BL-support "
                              "retrofit)\n"
                              "  [ ] BBB free business profile under new name\n"
                              "  [ ] IICRC Certified Firm listing updated "
                              "(DBA doc is the evidence; techs-only clients "
                              "get the firm-registration offer)\n"
                              "  [ ] Apple Maps + Bing Places updated\n"
                              "  [ ] rename PRESS RELEASE (AUTO-DRAFTED "
                              "to the app's Press Releases panel when this "
                              "note filed — approve + publish the same "
                              "week as the change)\n"
                              "  [ ] associations where credentialed "
                              "(RIA/NADCA/IAQA) + chamber OFFERED "
                              "(client-paid, primary city only)\n"
                              "Then execute the one-time Google Business "
                              "Profile name change and run:\n"
                              f"  python3 scripts/rename_pipeline.py "
                              f"mark-renamed --slug {d.get('slug')}\n"
                              "The pipeline then watches re-verification. "
                              "NEVER auto-executed by design.")},
                    prefer="return=minimal")
                print(f"  >> ready_for_rename prompt filed for {d.get('name')}")
                # A5: the rename announcement drafts itself at this exact
                # transition, so the release is sitting in the app before
                # anyone reads the checklist. Fail-open — a drafting error
                # never blocks the prompt.
                try:
                    import subprocess as _sp
                    r = _sp.run([sys.executable,
                                 str(ROOT / "scripts" / "press_release.py"),
                                 "draft", "--slug", d.get("slug") or "",
                                 "--kind", "rename"],
                                capture_output=True, text=True, timeout=600)
                    tail = (r.stdout or r.stderr).strip().splitlines()[-1:]
                    print(f"  >> rename PR draft: {tail[0][:120] if tail else r.returncode}")
                except Exception as e:  # noqa: BLE001
                    print(f"  >> rename PR draft failed: {str(e)[:100]}")

    counts: dict[str, int] = {}
    for d in out.values():
        counts[d["stage"]] = counts.get(d["stage"], 0) + 1
    print(f"rename pipeline: {len(out)} client(s) in program — "
          + ", ".join(f"{k}:{v}" for k, v in sorted(counts.items())))
    if not a.dry_run and not a.slug:
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": KV_KEY, "v": {"clients": out, "derived_at": _now()}},
            prefer="resolution=merge-duplicates")
        print("mirrored to ops_kv rename-pipeline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
