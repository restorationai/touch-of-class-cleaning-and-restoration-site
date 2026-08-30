#!/usr/bin/env python3
"""ask_staleness_audit.py — retire client asks whose answer we already hold
(Santino 2026-08-31, after three stale-ask incidents in one weekend: Michael
was asked for team mailboxes five weeks after his email-safe cutover, Rob was
asked for a logo that has served on his site header for a week, and Josiah
was asked whether he wants LSA while his LSA campaign was already running).

An ask is a PROMISE that we checked our own systems first. This audit makes
that promise mechanical: every pending intake item and planned client_input
ask is classified, and each auto-checkable class is verified against the
system that would hold the answer. Satisfied asks are retired with the
evidence written into them; unverifiable classes are only reported.

Auto-checkable classes:
  review-list    review_requests rows exist            -> list already loaded
  logo           repo logo.{png,webp} or bucket brand/logo* -> logo on file
  job-photos     >=3 files in branding job-photos      -> photos on file
  google-connect a working GBP token                    -> already connected
  nap            companies phone + (address|city+zip)   -> NAP on file
  lsa            lsa-status edge fn shows any campaign  -> LSA already running
  team-emails    cutover already completed              -> mailbox list moot

Runs daily from client-ops-sync BEFORE Monica's send slots, so a stale ask
dies before she can work it.

Usage:
  python3 scripts/ask_staleness_audit.py            # retire + report
  python3 scripts/ask_staleness_audit.py --dry-run  # report only
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
HDR = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
       "Content-Type": "application/json"}
STAMP = dt.date.today().isoformat()

CLASSES: list[tuple[str, re.Pattern]] = [
    ("review-list", re.compile(r"customer list for the review campaign|past.customer list", re.I)),
    ("logo", re.compile(r"company logo|send their logo|logo file", re.I)),
    ("job-photos", re.compile(r"job photos for the google business profile", re.I)),
    ("google-connect", re.compile(r"connect their google account", re.I)),
    ("nap", re.compile(r"phone number and address should (show|appear)", re.I)),
    ("lsa", re.compile(r"local services ads|google guaranteed", re.I)),
    ("team-emails", re.compile(r"email addresses does your team", re.I)),
]


def classify(text: str) -> str | None:
    for name, rx in CLASSES:
        if rx.search(text or ""):
            return name
    return None


def _get(path: str):
    r = requests.get(f"{SB_URL}/rest/v1/{path}", headers=HDR, timeout=30)
    return r.json() if r.ok else []


def _count(path: str) -> int:
    r = requests.get(f"{SB_URL}/rest/v1/{path}",
                     headers=HDR | {"Prefer": "count=exact", "Range": "0-0"},
                     timeout=20)
    cr = r.headers.get("content-range", "")
    return int(cr.split("/")[-1]) if r.ok and "/" in cr else 0


def _bucket_count(cid: str, prefix: str) -> int:
    r = requests.post(f"{SB_URL}/storage/v1/object/list/branding", headers=HDR,
                      json={"prefix": f"{cid}/{prefix}/", "limit": 100}, timeout=30)
    if not r.ok:
        return 0
    return sum(1 for o in r.json() if o.get("id"))


def _slug_for(cid: str) -> str | None:
    try:
        cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
        return next((s for s, c in cmap.items() if c == cid), None)
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------- class checks
# Each returns (satisfied: bool|None, evidence: str). None = cannot verify.
def check_review_list(cid: str, slug: str | None) -> tuple[bool | None, str]:
    n = _count(f"review_requests?company_id=eq.{cid}&select=id&limit=1")
    return (True, f"review campaign already holds {n:,} contacts") if n else (False, "no rows")


def check_logo(cid: str, slug: str | None) -> tuple[bool | None, str]:
    if slug:
        img = ROOT / "sites" / slug / "public" / "images"
        for name in ("logo.png", "logo.webp"):
            if (img / name).exists():
                return True, f"logo in site repo ({name})"
    r = requests.post(f"{SB_URL}/storage/v1/object/list/branding", headers=HDR,
                      json={"prefix": f"{cid}/brand/", "limit": 100}, timeout=30)
    if r.ok:
        for o in r.json():
            if o.get("id") and re.match(r"(?i)logo.*\.(png|webp|jpe?g|svg)$", o.get("name") or ""):
                return True, f"logo in brand uploads ({o['name']})"
    return False, "no logo found"


def check_job_photos(cid: str, slug: str | None) -> tuple[bool | None, str]:
    n = _bucket_count(cid, "job-photos") + _bucket_count(cid, "job-photos/posted")
    return (True, f"{n} job photos already in their gallery") if n >= 3 else (False, f"only {n} photos")


def check_google_connect(cid: str, slug: str | None) -> tuple[bool | None, str]:
    try:
        import gbp
        tok = gbp.get_access_token(cid)
        return (True, "Google connection live (token refresh works)") if tok else (False, "no token")
    except Exception as e:  # noqa: BLE001
        return None, f"check failed: {str(e)[:60]}"


def check_nap(cid: str, slug: str | None) -> tuple[bool | None, str]:
    co = _get(f"companies?id=eq.{cid}&select=phone,address,city,postal_code")
    if not co:
        return None, "no company row"
    c = co[0]
    phone_ok = bool((c.get("phone") or "").strip())
    addr_ok = bool((c.get("address") or "").strip()) or bool(
        (c.get("city") or "").strip() and (c.get("postal_code") or "").strip())
    if phone_ok and addr_ok:
        return True, "phone + address already on the Business Information card"
    return False, f"missing {'phone' if not phone_ok else ''}{' address' if not addr_ok else ''}".strip()


def check_lsa(cid: str, slug: str | None) -> tuple[bool | None, str]:
    """integration_settings.lsa is stamped by the daily lsa_detect.py pass
    (the Josiah case: his campaign was running and detectable; asking him
    'do you want LSA' should have been impossible)."""
    co = _get(f"companies?id=eq.{cid}&select=integration_settings")
    if not co:
        return None, "no company row"
    ints = co[0].get("integration_settings") or {}
    if isinstance(ints, str):
        try:
            ints = json.loads(ints)
        except Exception:  # noqa: BLE001
            ints = {}
    lsa = ints.get("lsa") or {}
    if lsa.get("setup_done") or lsa.get("customer_id") or lsa.get("campaign_id"):
        return True, f"LSA already detected on their account ({ {k: lsa[k] for k in ('customer_id','status') if lsa.get(k)} })"
    return False, "no LSA detected by the daily scan"


def check_team_emails(cid: str, slug: str | None) -> tuple[bool | None, str]:
    if not slug:
        return None, "no slug"
    try:
        cj = json.loads((ROOT / "clients" / f"{slug}.json").read_text())
        if cj.get("cut_over_at") or (cj.get("apex_cutover") or {}).get("completed_at"):
            return True, "cutover completed long ago with the full DNS mirror; list not needed"
    except Exception:  # noqa: BLE001
        pass
    return False, "not cut over yet (ask is legitimate pre-cutover)"


CHECKS = {"review-list": check_review_list, "logo": check_logo,
          "job-photos": check_job_photos, "google-connect": check_google_connect,
          "nap": check_nap, "lsa": check_lsa, "team-emails": check_team_emails}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    intake = _get("client_intake_items?status=eq.pending&select=id,company_id,question")
    plans = _get("marketing_action_plan?status=eq.planned&action_type=eq.client_input"
                 "&select=id,company_id,title,rationale")
    names = {c["id"]: c["name"] for c in _get("companies?select=id,name")}
    retired, kept, manual = [], [], []
    verdict_cache: dict[tuple[str, str], tuple[bool | None, str]] = {}

    def verdict(cls: str, cid: str):
        key = (cls, cid)
        if key not in verdict_cache:
            verdict_cache[key] = CHECKS[cls](cid, _slug_for(cid))
        return verdict_cache[key]

    for kind, rows, text_key in (("intake", intake, "question"),
                                 ("plan", plans, "title")):
        for r in rows:
            cid, text = r["company_id"], r.get(text_key) or ""
            label = f"{names.get(cid, cid)[:24]:24} | {text[:64]}"
            cls = classify(text)
            if not cls:
                manual.append(label)
                continue
            ok, why = verdict(cls, cid)
            if ok is True:
                retired.append(f"{label}  [{why}]")
                if not args.dry_run:
                    if kind == "intake":
                        requests.patch(
                            f"{SB_URL}/rest/v1/client_intake_items?id=eq.{r['id']}",
                            headers=HDR | {"Prefer": "return=minimal"},
                            json={"status": "answered",
                                  "answer": {"value": "(auto-resolved)",
                                             "source": f"ask_staleness_audit {STAMP}: {why}"}},
                            timeout=30)
                    else:
                        requests.patch(
                            f"{SB_URL}/rest/v1/marketing_action_plan?id=eq.{r['id']}",
                            headers=HDR | {"Prefer": "return=minimal"},
                            json={"status": "resolved",
                                  "rationale": (str(r.get("rationale") or "")[:800]
                                                + f"\n\nAUTO-RESOLVED {STAMP} (staleness audit): {why}.")},
                            timeout=30)
            else:
                kept.append(f"{label}  [{cls}: {why}]")

    print(f"== RETIRED ({len(retired)}){' [DRY RUN]' if args.dry_run else ''}:")
    for x in retired:
        print("  " + x)
    print(f"\n== KEPT, check says still needed ({len(kept)}):")
    for x in kept:
        print("  " + x)
    print(f"\n== NOT AUTO-CHECKABLE ({len(manual)}) — human list:")
    for x in manual:
        print("  " + x)
    return 0


if __name__ == "__main__":
    sys.exit(main())
