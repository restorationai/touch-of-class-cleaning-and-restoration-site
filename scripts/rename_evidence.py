#!/usr/bin/env python3
"""rename_evidence.py — the DBA filing IS the rename consent. Find it.

Santino 2026-09-30: "If they went and filed a DBA, they're obviously
consenting ... that should trump all else. Stop searching so hard for
consent; search hard for the DBA filing, because without the upload we can't
move forward with citations anyway." So there is ONE requirement and ONE
proof: the filing document, on file, for the chosen name. (The earlier
call/message consent search is gone.)

The texted/emailed/hub-tile lanes in client_concierge already verify filings
the moment they arrive. This sweep is the safety net for what they miss: a
filing saved under a generic name ("Image.jpeg", "scan.pdf"), an emailed
attachment kept by email-intake, anything uploaded before a name was chosen.
For every client with a CHOSEN name and no filing on record it vision-reads
each not-yet-checked PDF/image in
  branding/{cid}/docs/**   (hub uploads, saved attachments)
  email-intake/{cid}/**    (emailed attachments)
with the same DBA_EXTRACT_SYSTEM reader the live lanes use. Exact match to
the chosen name -> rename_intent.dba_filed + dba_doc_url + dba_verified
'vision_sweep' + approval {via: 'dba_filing'}: the citations gate clears.
A filing for a DIFFERENT name -> one escalation with both strings (this
sweep never texts clients). Each file is read once (ops_kv
dba-scan-seen:{cid}).

Runs in call-intel.yml (every 30 min) after rename_pipeline.py.
Usage: python3 scripts/rename_evidence.py [--slug X] [--dry-run]
"""
from __future__ import annotations

import argparse
import base64
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import requests  # noqa: E402
import client_concierge as cc  # noqa: E402
from client_ops_sync import slug_map  # noqa: E402

EXTS = (".pdf", ".jpg", ".jpeg", ".png", ".webp")
MIN_BYTES = 15_000          # signature icons / tracking pixels are not filings
MAX_BYTES = 12_000_000
MAX_READS = 15              # vision reads per client per pass
SKIP = re.compile(r"outlook-|signature|logo|banner|icon|image00\d", re.I)


def _sbh():
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return os.environ["SUPABASE_URL"].rstrip("/"), {"apikey": key, "Authorization": f"Bearer {key}"}


def _list(bucket: str, prefix: str, depth: int = 0) -> list[dict]:
    url, h = _sbh()
    r = requests.post(f"{url}/storage/v1/object/list/{bucket}", headers=h, timeout=60,
                      json={"prefix": prefix, "limit": 1000})
    out = []
    for o in (r.json() if r.ok else []):
        full = f"{prefix}/{o['name']}".strip("/")
        if o.get("id") is None:
            if depth < 4:
                out += _list(bucket, full, depth + 1)
        else:
            out.append({"bucket": bucket, "path": full,
                        "size": (o.get("metadata") or {}).get("size") or 0})
    return out


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower().replace("&", " and ")).strip()


def _media(path: str) -> str:
    p = path.lower()
    return ("application/pdf" if p.endswith(".pdf") else "image/png" if p.endswith(".png")
            else "image/webp" if p.endswith(".webp") else "image/jpeg")


def sweep(cid: str, slug: str, dry: bool) -> str | None:
    co = cc.fetch_companies([cid]).get(cid) or {}
    if not co or cc.company_inactive(co):
        return None
    ints = co.get("integration_settings") or {}
    ri = dict(ints.get("rename_intent") or {})
    if ri.get("decision") == "keep":
        return None
    chosen = cc._sb("GET", f"/rest/v1/marketing_gbp_suggestions?company_id=eq.{cid}"
                    "&item_type=eq.name&status=eq.chosen&select=item") or []
    if not chosen:
        return None
    name = chosen[0]["item"]
    now = datetime.now(timezone.utc).isoformat()
    if ri.get("dba_doc_url") and ri.get("dba_name") and _norm(ri["dba_name"]) == _norm(name):
        if (ri.get("approval") or {}).get("via") != "dba_filing":
            cc._merge_rename_intent(cid, {"approval": {
                "status": "found", "via": "dba_filing", "name": name,
                "url": ri["dba_doc_url"], "at": ri.get("dba_filed_at"),
                "checked_at": now, "found_by": "rename_evidence"}}, dry)
        return "on_file"
    seen_key = f"dba-scan-seen:{cid}"
    seen = set(cc.kv_get(seen_key) or [])
    files = [f for f in _list("branding", f"{cid}/docs") + _list("email-intake", cid)
             if f["path"].lower().endswith(EXTS) and MIN_BYTES <= f["size"] <= MAX_BYTES
             and not SKIP.search(f["path"].rsplit("/", 1)[-1])
             and f"{f['bucket']}/{f['path']}" not in seen]
    url, h = _sbh()
    reads, result = 0, "none"
    for f in files:
        if reads >= MAX_READS:
            break
        key = f"{f['bucket']}/{f['path']}"
        r = requests.get(f"{url}/storage/v1/object/{key}", headers=h, timeout=60)
        seen.add(key)
        if not r.ok:
            continue
        reads += 1
        data, media = r.content, _media(f["path"])
        if media != "application/pdf" and len(data) > 3_500_000:
            # the vision API rejects images over ~5MB (base64): shrink first
            try:
                import io
                from PIL import Image
                im = Image.open(io.BytesIO(data)).convert("RGB")
                im.thumbnail((2400, 2400))
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=85)
                data, media = buf.getvalue(), "image/jpeg"
            except Exception:  # noqa: BLE001
                continue
        doc = cc._dba_extract(co, [{"media_type": media,
                                    "data": base64.b64encode(data).decode()}])
        if not (doc and doc.get("is_dba_document") and doc.get("registered_name")):
            continue
        reg = str(doc["registered_name"]).strip()
        doc_url = f"{url}/storage/v1/object/public/{key}" if f["bucket"] == "branding" else key
        if _norm(reg) == _norm(name):
            print(f"{slug}: DBA FOUND in {key}: {reg!r}")
            cc._merge_rename_intent(cid, {
                "dba_filed": True, "dba_name": reg, "dba_filed_at": doc.get("filed_on"),
                "dba_doc_url": doc_url, "dba_verified": "vision_sweep", "dba_verified_at": now,
                "approval": {"status": "found", "via": "dba_filing", "name": name,
                             "url": doc_url, "at": doc.get("filed_on"), "checked_at": now,
                             "found_by": "rename_evidence"}}, dry)
            cc.append_escalation(co, None, f"DBA FOUND by the file sweep in {key}: {reg!r} "
                                 "matches the chosen name. Citations gate is CLEAR.", dry)
            result = "found"
            break
        print(f"{slug}: DBA for a DIFFERENT name in {key}: {reg!r} vs chosen {name!r}")
        cc.append_escalation(co, None, f"DBA MISMATCH found by the file sweep in {key}: "
                             f"document reads {reg!r}, chosen name is {name!r}. Check by eye "
                             "before anything runs.", dry, ping=True)
        result = "mismatch"
    if not dry:
        cc.kv_set(seen_key, sorted(seen)[-500:])
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cc.load_env()
    for cid, slug in slug_map().items():
        if a.slug and slug != a.slug:
            continue
        try:
            out = sweep(cid, slug, a.dry_run)
            if out:
                print(f"{slug}: {out}")
        except Exception as e:  # noqa: BLE001
            print(f"{slug}: ERROR {str(e)[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
