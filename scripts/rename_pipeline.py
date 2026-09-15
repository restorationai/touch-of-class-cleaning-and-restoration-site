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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--slug")
    a = ap.parse_args()
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
