#!/usr/bin/env python3
"""rename_site_sync.py — the moment a client's DBA filing is VERIFIED, put
the new name on their website's legal surfaces (Santino 2026-09-16, A2 of
the rename build: "footer legal line + schema legalName/alternateName...
runs at DBA-verification").

Why this exists: BrightLocal's pre-submission checks and Google's GBP
rename review both compare the proposed name against the client's website
(the Dry Bros campaign 999576 hold was exactly this). A site that carries
"[legal name], doing business as [DBA]" in the footer and declares the DBA
as the schema.org business name corroborates the rename BEFORE citations
land and BEFORE the GBP edit — turning the site from the thing that trips
verification into the thing that passes it.

Trigger is the DBA *verification*, never the name choice: the footer line
is a legal assertion ("doing business as") that only becomes true when the
state approves the filing. Monica's vision-verify stamps
rename_intent.dba_verified — this script sweeps behind that stamp.

Per eligible client (Active, rename_intent.dba_name + dba_verified, site
in sites/{slug}, not yet stamped site_synced_at):
  1. Resolve the display-cased DBA (the chosen marketing_gbp_suggestions
     card when it matches the filing case-insensitively — filings come
     back ALL CAPS, the chosen card carries the case we actually publish;
     else the filed string verbatim).
  2. Surgically set dbaName + legalName in sites/{slug}/src/lib/brand.ts
     (same pattern as citations_sync.py; scaffold-token files are skipped).
  3. Sites already pushed to main get commit + sync-deploy main so the
     legal surfaces go LIVE; preview-only sites get the source edit and
     the next deploy carries it.
  4. Stamp integration_settings.rename_intent.site_synced_at (idempotence)
     and write the app work ledger.

Rides client-ops-sync.yml right after citations_sync. CLI:
    python3 scripts/rename_site_sync.py [--slug X] [--dry-run] [--no-deploy]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from client_ops_sync import _sb, slug_map  # noqa: E402

_DBA_RE = re.compile(r'(\bdbaName:\s*")([^"]*)(")')
_LEGAL_RE = re.compile(r'(\blegalName:\s*")([^"]*)(")')


def _display_case(cid: str, filed: str) -> str:
    """Filings come back ALL CAPS; the chosen suggestion card holds the
    case we publish everywhere (GBP, citations). Use it when it is the
    same name; otherwise trust the filed string verbatim."""
    rows = _sb("GET", f"/rest/v1/marketing_gbp_suggestions?company_id=eq.{cid}"
               "&item_type=eq.name&status=eq.chosen&select=item"
               "&order=created_at.desc&limit=1") or []
    chosen = (str(rows[0].get("item")) or "").strip() if rows else ""
    if chosen and chosen.strip().lower() == filed.strip().lower():
        return chosen
    return filed


def _git(args: list) -> None:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[:200]}")


def sync_one(slug: str, cid: str, co: dict, dry_run: bool,
             no_deploy: bool) -> str | None:
    ints = co.get("integration_settings") or {}
    ri = ints.get("rename_intent") or {}
    filed = (ri.get("dba_name") or "").strip()
    verified = bool(ri.get("dba_verified") or ri.get("dba_verified_at"))
    if not (filed and verified):
        return None
    if ri.get("site_synced_at"):
        return None  # already carried to the site

    brand_path = ROOT / "sites" / slug / "src" / "lib" / "brand.ts"
    if not brand_path.exists():
        return f"{slug}: DBA verified but no site yet — will sync at scaffold"
    src = brand_path.read_text()
    if "{{BRAND_" in src:
        return f"{slug}: SKIP (unsubstituted scaffold tokens)"
    if "dbaName" not in src:
        return (f"{slug}: SKIP — brand.ts predates the dbaName field; "
                "re-port the template legal surfaces to this site")

    dba = _display_case(cid, filed)
    legal = (co.get("legal_business_name") or "").strip() \
        or (co.get("name") or "").strip()
    if dba.strip().lower() == legal.strip().lower():
        # Filed string IS the legal name (no separate trade name) — the
        # footer's existing legalName line already covers it.
        return f"{slug}: DBA equals legal name — nothing to add"

    changes = []
    if _DBA_RE.search(src).group(2) != dba:
        changes.append(f'dbaName -> "{dba[:60]}..."' if len(dba) > 60
                       else f'dbaName -> "{dba}"')
    if _LEGAL_RE.search(src).group(2) != legal:
        changes.append(f'legalName -> "{legal}"')
    if not changes:
        return f"{slug}: brand.ts already carries the DBA"
    verdict = f"{slug}: {'; '.join(changes)}"
    if dry_run:
        return verdict + "  [dry-run]"

    src = _DBA_RE.sub(lambda m: m.group(1) + dba + m.group(3), src, count=1)
    src = _LEGAL_RE.sub(lambda m: m.group(1) + legal + m.group(3), src,
                        count=1)
    brand_path.write_text(src)

    rec_path = ROOT / "clients" / f"{slug}.json"
    on_main = False
    if rec_path.exists():
        try:
            on_main = bool((json.loads(rec_path.read_text()).get("build")
                            or {}).get("last_pushed_main_at"))
        except (json.JSONDecodeError, OSError):
            pass

    deployed = False
    if on_main and not no_deploy:
        rel = f"sites/{slug}/src/lib/brand.ts"
        _git(["add", rel])
        _git(["commit", "-m",
              f"{slug}: DBA on legal surfaces (footer + schema) [automated]",
              "--", rel])
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_site.py"),
             "sync-deploy", "--slug", slug, "--branch", "main",
             "--allow-dirty"],
            capture_output=True, text=True, timeout=900, cwd=ROOT)
        deployed = r.returncode == 0
        if deployed:
            verdict += "  [deployed to main]"
        else:
            tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:]
            verdict += f"\n    DEPLOY FAILED: {tail[0][:150] if tail else '?'}"
            return verdict  # no stamp — retry next sweep
    else:
        verdict += "  [source edit only — next deploy carries it]"

    ri["site_synced_at"] = datetime.now(timezone.utc).isoformat()
    ints["rename_intent"] = ri
    _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
        {"integration_settings": ints})

    try:
        from work_log import work_log
        work_log(cid, "citations", "dba-site-sync",
                 f"Website now carries the registered DBA: footer legal "
                 f"line and schema.org business name updated to \"{dba}\".",
                 evidence={"slug": slug, "dba": dba, "legal": legal,
                           "deployed": deployed},
                 source="rename_site_sync.py")
    except Exception:
        pass
    return verdict


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-deploy", action="store_true")
    a = ap.parse_args()

    inv = {s: c for c, s in slug_map().items()}
    comps = {c["id"]: c for c in
             _sb("GET", "/rest/v1/companies?status=eq.Active&select="
                 "id,name,legal_business_name,integration_settings") or []}
    slugs = [a.slug] if a.slug else sorted(inv)
    acted = 0
    for slug in slugs:
        cid = inv.get(slug)
        if not cid or cid not in comps:
            continue
        try:
            line = sync_one(slug, cid, comps[cid], a.dry_run, a.no_deploy)
        except Exception as e:  # noqa: BLE001 — one client never stops the fleet
            line = f"{slug}: ERROR {str(e)[:150]}"
        if line:
            print(line)
            acted += 1
    if not acted:
        print("rename-site-sync: no verified DBAs awaiting site sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
