#!/usr/bin/env python3
"""Client-ops feedback loop (phase 1) — watch app-side changes, flow them back
into pipeline work without Santino relaying anything.

What it watches (Supabase, service role):
  - `client_intake_items`   — questions we seeded in the app that the client
    (or Santino) answered: status flips off 'pending', answer jsonb filled,
    answered_at stamped.
  - `marketing_action_plan` — rows an operator moved off 'planned'
    (done / dismissed / approved / resolved).

What it does with them — mechanical handlers first, everything else digest-only:
  1. LICENSE:  an answer carrying a CSLB/HIC-style license number (or a
     yes_no 'yes' confirming a license number quoted in the question) for a
     client with a pipeline record → append the number to
     clients/{slug}/plan-input.json  brand.license_numbers (the claims-lint
     brand-truth source), journal it, and OPEN a marketing_action_plan row
     "License on file — trust badges pending re-render" (assigned_system
     manual, pinned). We never auto-rerender — rendering costs money; a human
     or the next maintenance run applies it.
  2. GATING yes_no (tagline consent, domain/DBA confirmation, disclosure
     approval, anything with `blocks` set) → append to
     clients/{slug}/ops-journal.md with timestamp + insert a pinned
     action-plan row describing the unblocked work.
  3. CUSTOMER LIST checklist completed (blocks=review_campaign or the
     question reads like a past-customer export) → action-plan row
     "Customer list received — stage for review campaign".
  4. Everything else (free-text answers, done/dismissed/approved plan rows)
     → digest only.

Digest: if anything was processed, ONE email via SendGrid to
contact@restorationai.io — "Client Ops Digest — {date}" — grouped by client:
what was answered, what was auto-applied, what needs Santino/Claude action.
The same content lands in clients/_ops/digest-{date}.md (committed by the
workflow). No email on empty runs.

State: clients/_ops/last-sync.json — timestamp cursor + processed item ids —
committed by the workflow so runs are idempotent across CI machines.

Inserted plan rows are pinned=true so the weekly strategist refresh (which
wipes unpinned 'planned' rows) never deletes open client-ops work.

Usage:
    python3 scripts/client_ops_sync.py --dry-run            # print, write nothing
    python3 scripts/client_ops_sync.py --since 2026-07-01   # override cursor
    python3 scripts/client_ops_sync.py --send               # real run + real email
    python3 scripts/client_ops_sync.py                      # real run, email printed

Env (rank-ai/.env or CI secrets): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
SENDGRID_API_KEY (email; optional SENDGRID_FROM). Runs daily from
.github/workflows/client-ops-sync.yml (14:00 UTC + workflow_dispatch).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = ROOT / "clients"
OPS_DIR = CLIENTS_DIR / "_ops"
STATE_PATH = OPS_DIR / "last-sync.json"

NOTIFY_EMAIL = "contact@restorationai.io"
FROM_EMAIL = os.environ.get("SENDGRID_FROM", NOTIFY_EMAIL)
SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"
UA = "rank-ai-client-ops-sync/1.0"
DEFAULT_LOOKBACK_DAYS = 14
PLAN_WATCH_STATUSES = ("done", "dismissed", "approved", "resolved")

# license number in free text: optional 1-3 letter class prefix + 5-8 digits,
# anchored to a license context word nearby (CSLB / HIC / license / lic / #).
LICENSE_CONTEXT_RE = re.compile(r"\b(?:CSLB|HIC|licen[cs]e|lic\.?)\b", re.I)
LICENSE_NUM_RE = re.compile(r"\b([A-Z]{0,3}[-.]?\d{5,8})\b")
GATING_RE = re.compile(
    r"tagline|domain|DBA|disclos|consent|OK to|sister compan|registered as|confirm", re.I)
CUSTOMER_LIST_RE = re.compile(r"customer list|past[- ]customer|export.*customer", re.I)


def load_env() -> None:
    """Fail-soft .env loader (matches master_scheduler.py) — never overrides CI env."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ---------------------------------------------------------------- supabase REST
def _sb(method: str, path: str, body=None, prefer: str = "return=minimal"):
    url = os.environ["SUPABASE_URL"].rstrip("/") + path
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    resp = requests.request(method, url, json=body, timeout=30, headers={
        "apikey": key, "Authorization": f"Bearer {key}",
        "Content-Type": "application/json", "Prefer": prefer, "User-Agent": UA,
    })
    resp.raise_for_status()
    return resp.json() if resp.content else None


# ---------------------------------------------------------------- identity map
def slug_map() -> dict[str, str]:
    """company_id -> rank_ai_slug, from company_map.json + clients/*.json records."""
    out: dict[str, str] = {}
    for f in sorted(CLIENTS_DIR.glob("*.json")):
        if f.name == "company_map.json":
            continue
        try:
            cid = json.loads(f.read_text()).get("company_id")
        except (json.JSONDecodeError, OSError):
            continue
        if cid:
            out[cid] = f.stem
    cmap_path = CLIENTS_DIR / "company_map.json"
    if cmap_path.exists():
        for slug, cid in json.loads(cmap_path.read_text()).items():
            out[cid] = slug  # company_map wins
    return out


# ---------------------------------------------------------------- state
def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"cursor": None, "processed_intake_ids": [], "processed_plan_events": []}


def save_state(state: dict, dry_run: bool) -> None:
    if dry_run:
        return
    state["processed_intake_ids"] = state["processed_intake_ids"][-1000:]
    state["processed_plan_events"] = state["processed_plan_events"][-1000:]
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")


# ---------------------------------------------------------------- pull
def fetch_answered_intake(since: str) -> list[dict]:
    # answered_at can be null on legacy rows — include those, dedupe via state.
    since = urllib.parse.quote(since)  # '+00:00' offsets break raw query strings
    q = ("/rest/v1/client_intake_items?status=neq.pending"
         f"&or=(answered_at.gte.{since},answered_at.is.null)"
         "&select=id,company_id,question,field_type,answer,status,blocks,answered_at"
         "&order=answered_at.asc.nullsfirst")
    return _sb("GET", q, prefer="return=representation") or []


def fetch_plan_changes(since: str) -> list[dict]:
    since = urllib.parse.quote(since)
    q = ("/rest/v1/marketing_action_plan"
         f"?status=in.({','.join(PLAN_WATCH_STATUSES)})&updated_at=gte.{since}"
         "&select=id,company_id,rank_ai_slug,title,action_type,status,updated_at"
         "&order=updated_at.asc")
    return _sb("GET", q, prefer="return=representation") or []


# ---------------------------------------------------------------- classify
def answer_text(item: dict) -> str:
    ans = item.get("answer")
    if isinstance(ans, dict):
        ans = ans.get("value", ans)
    if isinstance(ans, (list, dict)):
        return json.dumps(ans)
    return str(ans) if ans is not None else ""


def extract_license_numbers(item: dict) -> list[str]:
    """License numbers from the answer; for a yes_no 'yes', a number quoted in
    the question counts (client just confirmed it applies)."""
    ans = answer_text(item)
    sources = []
    if LICENSE_CONTEXT_RE.search(item.get("question", "") + " " + ans):
        sources.append(ans)
        if item.get("field_type") == "yes_no" and ans.strip().lower() in ("yes", "true", "y"):
            sources.append(item.get("question", ""))
    nums: list[str] = []
    for src in sources:
        for m in LICENSE_NUM_RE.findall(src):
            if m not in nums:
                nums.append(m)
    return nums


def classify_intake(item: dict) -> str:
    """'license' | 'gating_yes_no' | 'customer_list' | 'digest'"""
    if extract_license_numbers(item):
        return "license"
    if item.get("field_type") == "yes_no" and (
            item.get("blocks") or GATING_RE.search(item.get("question", ""))):
        return "gating_yes_no"
    if item.get("field_type") == "checklist" and (
            item.get("blocks") == "review_campaign"
            or CUSTOMER_LIST_RE.search(item.get("question", ""))):
        return "customer_list"
    return "digest"


# ---------------------------------------------------------------- act
def action_key(company_id: str, seed: str) -> str:
    return hashlib.sha256(f"ops:{company_id}:{seed}".encode()).hexdigest()[:16]


def insert_plan_row(company_id: str, slug: str | None, key_seed: str, *,
                    title: str, rationale: str, action_type: str,
                    target: str | None, impact: str, effort: str,
                    dry_run: bool) -> bool:
    """Find-or-create by action_key; pinned so strategist's weekly wipe skips it."""
    key = action_key(company_id, key_seed)
    existing = _sb("GET", "/rest/v1/marketing_action_plan"
                   f"?company_id=eq.{company_id}&action_key=eq.{key}&select=id",
                   prefer="return=representation") or []
    if existing:
        return False
    row = {
        "company_id": company_id, "rank_ai_slug": slug, "priority": 1,
        "action_type": action_type, "title": title, "rationale": rationale,
        "target": target, "assigned_system": "manual", "impact": impact,
        "effort": effort, "status": "planned", "pinned": True,
        "action_key": key, "source_run_at": datetime.now(timezone.utc).isoformat(),
    }
    if dry_run:
        print(f"    [dry-run] would insert plan row: {title!r} (key {key})")
        return True
    _sb("POST", "/rest/v1/marketing_action_plan", [row])
    return True


def append_journal(slug: str, lines: list[str], dry_run: bool) -> None:
    path = CLIENTS_DIR / slug / "ops-journal.md"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    block = f"\n## {stamp} — client ops sync\n" + "\n".join(f"- {l}" for l in lines) + "\n"
    if dry_run:
        print(f"    [dry-run] would append to {path.relative_to(ROOT)}:{block}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(f"# Ops Journal — {slug}\n")
    with path.open("a") as f:
        f.write(block)


def apply_license(slug: str, numbers: list[str], dry_run: bool) -> list[str]:
    """Add license numbers to plan-input brand truth. Returns numbers newly added."""
    path = CLIENTS_DIR / slug / "plan-input.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    brand = data.setdefault("brand", {})
    lic = brand.setdefault("license_numbers", [])
    added = [n for n in numbers if n not in lic]
    if not added:
        return []
    if dry_run:
        print(f"    [dry-run] would add license(s) {added} to {path.relative_to(ROOT)}")
        return added
    lic.extend(added)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return added


# ---------------------------------------------------------------- digest
def send_email(subject: str, html: str, do_send: bool) -> None:
    if not do_send:
        print(f"\n[email suppressed — pass --send to deliver] Subject: {subject}")
        return
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        print(f"  email skipped (no SENDGRID_API_KEY): {subject}", file=sys.stderr)
        return
    payload = {"personalizations": [{"to": [{"email": NOTIFY_EMAIL}]}],
               "from": {"email": FROM_EMAIL, "name": "Rank AI Bot"},
               "subject": subject,
               "content": [{"type": "text/html", "value": html}]}
    resp = requests.post(SENDGRID_URL, json=payload, timeout=30, headers={
        "Authorization": f"Bearer {api_key}", "User-Agent": UA})
    if 200 <= resp.status_code < 300:
        print(f"  digest emailed to {NOTIFY_EMAIL}")
    else:
        print(f"  SendGrid error {resp.status_code}: {resp.text[:200]}", file=sys.stderr)


def digest_markdown(date_str: str, per_client: dict[str, dict]) -> str:
    lines = [f"# Client Ops Digest — {date_str}", ""]
    for client in sorted(per_client):
        d = per_client[client]
        lines.append(f"## {client}")
        for section, header in (("answered", "Answered"),
                                ("auto", "Auto-applied"),
                                ("plan_changes", "Action-plan changes"),
                                ("attention", "Needs Santino/Claude")):
            if d.get(section):
                lines.append(f"### {header}")
                lines.extend(f"- {e}" for e in d[section])
        lines.append("")
    return "\n".join(lines) + "\n"


def digest_html(date_str: str, per_client: dict[str, dict]) -> str:
    def esc(s) -> str:
        # A non-string entry (a dict slipped into a section list) crashed the
        # WHOLE ops run on 2026-08-01 — the digest must never be fatal, so
        # stringify anything and let the odd entry render as JSON.
        if not isinstance(s, str):
            s = json.dumps(s, default=str)
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    parts = ['<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;'
             'max-width:640px;margin:0 auto;color:#0f172a">',
             f'<h2 style="letter-spacing:-.01em">Client Ops Digest — {esc(date_str)}</h2>']
    for client in sorted(per_client):
        d = per_client[client]
        parts.append(f'<h3 style="color:#7c3aed;margin-bottom:2px">{esc(client)}</h3>')
        for section, header in (("answered", "Answered"),
                                ("auto", "Auto-applied"),
                                ("plan_changes", "Action-plan changes"),
                                ("attention", "Needs Santino/Claude")):
            if d.get(section):
                parts.append(f'<p style="margin:8px 0 2px;font-weight:600">{header}</p><ul style="margin:2px 0">')
                parts.extend(f"<li>{esc(e)}</li>" for e in d[section])
                parts.append("</ul>")
    parts.append('<p style="font-size:12px;color:#94a3b8">Rank AI client-ops sync '
                 '&middot; scripts/client_ops_sync.py</p></div>')
    return "".join(parts)


# ------------------------------------------------------- bootstrap backstop
def ensure_bootstrapped(dry_run: bool, do_send: bool,
                        cid_to_slug: dict[str, str] | None = None,
                        full: bool = False) -> list[str]:
    """Auto-provision the DB/KV half of the sales-to-ops handoff for Active
    companies with no marketing_sites row (the Gregory Arianoff gap): slug +
    marketing_sites row + public upload-link KV entry. Repo files + GBP sync
    still need scripts/bootstrap_client.py locally (the worker cannot commit),
    so an alert email lists exactly what to run."""
    import re as _re
    # Rank AI marketing clients only: plan is the source of truth (Santino,
    # 2026-07-21 — Leakproof/Rapid Response are receptionist plans; wizard
    # artifacts alone misfire because receptionist clients sometimes click
    # through the marketing wizard). Test companies excluded by name.
    cos = _sb("GET", "/rest/v1/companies?status=eq.Active&plan=eq.Rank%20AI"
              "&select=id,name",
              prefer="return=representation") or []
    cos = [c for c in cos
           if not _re.search(r"test|trachawk|xyz restoration", (c.get("name") or "").lower())]
    sites = _sb("GET", "/rest/v1/marketing_sites?select=company_id,rank_ai_slug",
                prefer="return=representation") or []
    have = {r["company_id"] for r in sites}
    taken = {r.get("rank_ai_slug") for r in sites if r.get("rank_ai_slug")}
    lines: list[str] = []
    for co in cos:
        if co["id"] in have or "test" in (co.get("name") or "").lower():
            continue
        pipeline_slug = (cid_to_slug or {}).get(co["id"])
        if pipeline_slug:
            slug = pipeline_slug        # existing pipeline identity wins
        else:
            base = _re.sub(r"-{2,}", "-",
                           _re.sub(r"[^a-z0-9]+", "-", (co.get("name") or "").lower())).strip("-")
            slug, n = (base or "client"), 2
            while slug in taken:
                slug, n = f"{base}-{n}", n + 1
        taken.add(slug)
        if dry_run:
            lines.append(f"WOULD bootstrap {co['name']} ({co['id']}) as {slug}")
            continue
        if full:
            import subprocess as _sp
            r = _sp.run([sys.executable, str(Path(__file__).parent / "bootstrap_client.py"),
                         "--company-id", co["id"], "--slug", slug],
                        capture_output=True, text=True, timeout=900)
            ok = r.returncode == 0
            lines.append(f"{'FULL-bootstrapped' if ok else 'FULL bootstrap FAILED'} "
                         f"{co['name']} ({co['id']}) as {slug}"
                         + ("" if ok else f": {(r.stdout + r.stderr)[-200:]}"))
            continue
        try:
            _sb("POST", "/rest/v1/marketing_sites", body={
                "company_id": co["id"], "rank_ai_slug": slug,
                "domain": slug + ".invalid",   # reserved TLD = obviously-pending
                "tier": "standard", "plan_template": "restoration"})
            try:
                import upload_links_sync as uls
                ns = uls.kv_namespace_id()
                uls.cf("PUT", f"/storage/kv/namespaces/{ns}/bulk", [{
                    "key": slug,
                    "value": json.dumps({"cid": co["id"], "name": co["name"],
                                          "hub": uls.hub_token(slug)}),
                }])
                kv_note = "upload link LIVE"
                try:
                    hub = f"https://restorationai.io/hub/{slug}/{uls.hub_token(slug)}"
                    row = _sb("GET", f"/rest/v1/companies?id=eq.{co['id']}"
                              "&select=integration_settings",
                              prefer="return=representation")
                    ints = (row or [{}])[0].get("integration_settings") or {}
                    if not isinstance(ints, dict):
                        ints = {}
                    ints["hub_url"] = hub
                    _sb("PATCH", f"/rest/v1/companies?id=eq.{co['id']}",
                        body={"integration_settings": ints})
                except Exception:
                    pass
            except Exception as e:  # KV needs CF env on this host
                kv_note = f"KV pending ({str(e)[:60]})"
            lines.append(f"auto-bootstrapped {co['name']} ({co['id']}) as {slug} — {kv_note}")
        except Exception as e:
            lines.append(f"FAILED bootstrap {co['name']} ({co['id']}): {str(e)[:120]}")
    if lines:
        send_email("New-client bootstrap backstop",
                   "<br>".join(lines) + "<br><br>Finish repo files + GBP sync with: "
                   "<code>python3 scripts/bootstrap_client.py --company-id CO-... --slug ...</code>",
                   do_send)
        for ln in lines:
            print("  [bootstrap] " + ln)
    return lines


# ---------------------------------------------------------------- main


def ensure_ads_first_sync(dry_run: bool, cid_to_slug: dict) -> list[str]:
    """Any client with a selected Ads account but zero synced campaigns gets
    ads_sync run immediately (the sync loops every connected account, so one
    invocation covers all stragglers in the pass)."""
    import subprocess
    rows = _sb("GET", "/rest/v1/user_integrations?provider=in.(google,google_ads)"
               "&select=client_id,connection_metadata",
               prefer="return=representation") or []
    stragglers = []
    for r in rows:
        cid = r.get("client_id")
        if not cid or not (r.get("connection_metadata") or {}).get("selected_ads_customer_id"):
            continue
        camps = _sb("GET", f"/rest/v1/marketing_ads_campaigns?company_id=eq.{cid}"
                    "&select=id&limit=1", prefer="return=representation") or []
        if not camps:
            stragglers.append(cid_to_slug.get(cid, cid))
    if not stragglers:
        return []
    if dry_run:
        return [f"ads first-sync: WOULD run for {', '.join(stragglers)}"]
    try:
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "ads_sync.py")],
                           capture_output=True, text=True, timeout=1800)
        ok = r.returncode == 0
        return [f"ads first-sync ({', '.join(stragglers)}): {'ok' if ok else 'FAILED'}"]
    except Exception as e:
        return [f"ads first-sync failed ({str(e)[:100]})"]


def ensure_baseline_scans(dry_run: bool, cid_to_slug: dict) -> list[str]:
    """Day-one data blitz backstop (Kyle 2026-07-26: follow-up call with an
    empty Map Rankings tab, empty AI Search tab, no AI suggestions — every
    surface waited on a weekly cron). For each active client the nightly run
    fills whatever baseline is missing:
      geo-grid   configs exist but zero scans -> geogrid_cron --slug
      AI search  zero scan rows              -> ai_search_scan --slug
      optimizer  connected + zero suggestions -> gbp.py optimize --slug
    The connect-triggered chain (/gbp-first-sync) does this instantly for
    fresh connects; this pass catches everyone it misses."""
    import subprocess

    def run_tool(args_, timeout):
        r = subprocess.run([sys.executable] + args_, capture_output=True,
                           text=True, timeout=timeout)
        tail = (r.stdout or r.stderr or "").strip().splitlines()
        return tail[-1][:110] if tail else "no output"

    out: list[str] = []
    active = _sb("GET", "/rest/v1/companies?status=ilike.active&select=id",
                 prefer="return=representation") or []
    conns = {c["client_id"] for c in (_sb(
        "GET", "/rest/v1/user_integrations?provider=eq.google&select=client_id",
        prefer="return=representation") or []) if c.get("client_id")}
    def _company_pass(cid, slug):
        kw_f = CLIENTS_DIR / slug / "geogrid-keywords.txt"
        ct_f = CLIENTS_DIR / slug / "geogrid-cities.json"
        if kw_f.exists() and ct_f.exists():
            scans = _sb("GET", f"/rest/v1/marketing_geogrid_scans?company_id=eq.{cid}"
                        "&select=id&limit=1", prefer="return=representation") or []
            if not scans:
                if dry_run:
                    out.append(f"{slug}: WOULD run geo-grid baseline")
                else:
                    try:
                        out.append(f"{slug}: geo-grid baseline -> "
                                   + run_tool([str(ROOT / 'scripts' / 'geogrid_cron.py'),
                                               '--slug', slug], 3600))
                    except Exception as e:
                        out.append(f"{slug}: geo-grid baseline failed ({str(e)[:80]})")
        ai = _sb("GET", f"/rest/v1/marketing_ai_search_scans?company_id=eq.{cid}"
                 "&select=id&limit=1", prefer="return=representation") or []
        if not ai and (CLIENTS_DIR / slug / "plan-input.json").exists():
            if dry_run:
                out.append(f"{slug}: WOULD run AI-search baseline")
            else:
                try:
                    out.append(f"{slug}: AI-search baseline -> "
                               + run_tool([str(ROOT / 'scripts' / 'ai_search_scan.py'),
                                           '--slug', slug, '--limit', '8',
                                           '--engines', 'chatgpt,gemini,perplexity,claude'], 1800))
                except Exception as e:
                    out.append(f"{slug}: AI-search baseline failed ({str(e)[:80]})")
        if cid in conns:
            # table has NO id column (PK = company_id,item_type,item); select=id
            # 400'd here and killed the WHOLE baseline pass for every client
            sug = _sb("GET", f"/rest/v1/marketing_gbp_suggestions?company_id=eq.{cid}"
                      "&select=company_id&limit=1", prefer="return=representation") or []
            if not sug:
                if dry_run:
                    out.append(f"{slug}: WOULD run optimizer baseline")
                else:
                    try:
                        out.append(f"{slug}: optimizer baseline -> "
                                   + run_tool([str(ROOT / 'scripts' / 'gbp.py'),
                                               'optimize', '--slug', slug], 1200))
                    except Exception as e:
                        out.append(f"{slug}: optimizer baseline failed ({str(e)[:80]})")

    # one company's bad query must never starve the rest (select=id on the
    # id-less suggestions table 400'd and zeroed EVERY client's baselines)
    for co in active:
        cid = co["id"]
        slug = cid_to_slug.get(cid)
        if not slug:
            continue
        try:
            _company_pass(cid, slug)
        except Exception as e:
            out.append(f"{slug}: baseline pass errored ({str(e)[:80]})")
    return out


def ensure_gbp_first_sync(dry_run: bool, cid_to_slug: dict) -> list[str]:
    """Connected-but-never-synced clients get their first GBP sync immediately
    (Kyle 2026-07-26: connected Friday on the sales call, Locations tab sat on
    'No Business Profile connected' because the sync only runs Mon+Thu). Runs
    gbp.py sync per such client — populates the profile row, pulls reviews via
    v4, imports their GBP photo library. Scheduled syncs stay the refresher."""
    import subprocess
    out: list[str] = []
    conns = _sb("GET", "/rest/v1/user_integrations?provider=eq.google"
                "&select=client_id", prefer="return=representation") or []
    connected = {c["client_id"] for c in conns if c.get("client_id")}
    for cid in sorted(connected):
        slug = cid_to_slug.get(cid)
        if not slug:
            continue
        prof = _sb("GET", f"/rest/v1/marketing_gbp_profiles?company_id=eq.{cid}"
                   "&select=company_id", prefer="return=representation") or []
        if prof:
            continue
        if dry_run:
            out.append(f"{slug}: WOULD run first GBP sync")
            continue
        try:
            r = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "gbp.py"),
                 "sync", "--slug", slug],
                capture_output=True, text=True, timeout=600)
            tail = (r.stdout or r.stderr or "").strip().splitlines()
            out.append(f"{slug}: first GBP sync -> {tail[-1][:120] if tail else 'no output'}")
        except Exception as e:
            out.append(f"{slug}: first GBP sync failed ({str(e)[:100]})")
    return out


def ensure_setup_checklist(dry_run: bool, cid_to_slug: dict) -> list[str]:
    """Daily business-setup checklist (Santino 2026-07-25: 'this is why they
    pay US — we handle what we can'). Three buckets: auto-fix (ours, handled
    by the optimizer/responder/importer), one-click approvals (ours, in-app),
    and NEEDS-CLIENT — only that last bucket lands here, as pinned
    client_input asks Monica works over SMS/email (docs by hub upload link or
    email, never a call unless the client asks or goes quiet). Rows
    auto-resolve when the underlying gap clears; docs arriving via the hub
    already pin their own action-plan row, so ops gets notified to finish.

    v1 checks:
      lsa-docs     an open lsa_fix plan row -> ask for the real docs w/ links
      svc-confirm  NEEDS-REVIEW service/category suggestions -> batched
                   'do you actually offer these?' ask (top 3, humanized)
      hours        GBP claimed but no business hours set
      crew-photos  zero crew-uploaded job photos ever (gbp- imports and
                   posted/ recycles don't count)
    """
    from upload_links_sync import hub_token

    out: list[str] = []
    active = _sb("GET", "/rest/v1/companies?status=ilike.active&select=id,name",
                 prefer="return=representation") or []
    svc_label = (lambda s: s[len("job_type_id:"):].replace("_", " ").capitalize()
                 if str(s).startswith("job_type_id:") else str(s))

    for co in active:
        cid = co["id"]
        slug = cid_to_slug.get(cid)
        if not slug:
            continue
        hub = f"https://restorationai.io/hub/{slug}/{hub_token(slug)}"
        photos_link = f"https://restorationai.io/gbpphotos/{slug}"
        profs = _sb("GET", "/rest/v1/marketing_gbp_profiles"
                    f"?company_id=eq.{cid}&select=has_hours,claimed",
                    prefer="return=representation") or []
        prof = profs[0] if profs else {}
        lsa = _sb("GET", "/rest/v1/marketing_action_plan"
                  f"?company_id=eq.{cid}&action_type=eq.lsa_fix&status=eq.planned"
                  "&select=title,rationale", prefer="return=representation") or []
        # Only clients actually live on marketing ops (synced GBP) get
        # checklist nags — mid-onboarding clients aren't ready to be asked
        # for crew photos. An open LSA blocker qualifies on its own.
        if not profs and not lsa:
            continue

        checks: list[tuple[str, bool, str, str]] = []  # (seed, gap_open, title, rationale)
        checks.append((
            f"checklist-lsa-docs-{slug}", bool(lsa),
            "ASK CLIENT: documents needed to unblock Local Services Ads",
            ("Google rejected or is missing verification documents on this client's "
             "Local Services Ads, so their LSA cannot serve. Blocker: {}\n\n"
             "MONICA: ask the owner to send the required documents (state contractor "
             "license, current certificate of insurance). They can reply with a photo, "
             "email contact@restorationai.io, or use their private upload link: {} "
             "(pick the License / Insurance category). We resubmit to Google for them "
             "— they should NOT have to log into anything. Their upload pins a task "
             "for our team automatically.").format(
                (lsa[0]["title"] if lsa else ""), hub)))

        nr = _sb("GET", "/rest/v1/marketing_gbp_suggestions"
                 f"?company_id=eq.{cid}&status=eq.open&verdict=eq.NEEDS-REVIEW"
                 "&item_type=in.(service,category)&select=item,reason",
                 prefer="return=representation") or []
        top = ", ".join(svc_label(x["item"]) for x in nr[:3])
        checks.append((
            f"checklist-svc-confirm-{slug}", bool(nr),
            f"ASK CLIENT: confirm {len(nr)} service(s) on their Google listing",
            ("Our Google Business Profile audit flagged {} item(s) it cannot confirm "
             "the client actually offers (top: {}). MONICA: ask conversationally, max "
             "3 per message, e.g. 'quick sanity check, do you folks handle {}? Want to "
             "make sure your Google listing only shows what you actually do.' Relay "
             "answers back; our team applies the changes — the client does nothing in "
             "Google.").format(len(nr), top or "n/a", top or "these")))

        checks.append((
            f"checklist-hours-{slug}",
            bool(prof) and prof.get("claimed") is True and prof.get("has_hours") is False,
            "ASK CLIENT: business hours for the Google listing",
            "Their Google Business Profile has no hours set, which suppresses the "
            "listing for 'open now' searches. MONICA: ask what hours they want shown "
            "(24/7 emergency companies usually want Open 24 hours). We set it on "
            "Google for them."))

        crew = 0
        newest_upload = ""  # newest field-crew upload created_at (ISO)
        try:
            sb_url = os.environ["SUPABASE_URL"].rstrip("/")
            sb_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
            for sub in ("", "posted/"):
                r = requests.post(f"{sb_url}/storage/v1/object/list/branding",
                                  headers={"apikey": sb_key,
                                           "Authorization": f"Bearer {sb_key}",
                                           "Content-Type": "application/json"},
                                  json={"prefix": f"{cid}/job-photos/{sub}", "limit": 200},
                                  timeout=30)
                for f in r.json() or []:
                    if not isinstance(f, dict) or not f.get("id"):
                        continue
                    base = re.sub(r"^r\d+_", "", f["name"])
                    if not base.startswith("gbp-"):
                        crew += 1
                        newest_upload = max(newest_upload, f.get("created_at") or "")
        except Exception:
            crew = 1  # storage hiccup: assume fine, never nag on bad data
        checks.append((
            f"checklist-crew-photos-{slug}", crew == 0,
            "ASK CLIENT: get the crew photo link in use",
            ("No job photos have ever come in from the field crew — fresh photos feed "
             "both the Google profile and the website. MONICA: re-share their no-login "
             "crew upload link ({}) and suggest texting it to the crew group chat; "
             "even 3-4 phone pics from recent jobs is plenty.").format(photos_link)))

        # Photo freshness (Santino 2026-07-28): clients who HAVE uploaded before
        # but have gone 30+ days without a new photo anywhere (app upload OR
        # their Google profile) get a friendly reminder. Google side is checked
        # before nagging so a client whose GBP gets photos from elsewhere (e.g.
        # a daily posting tool, Home Pride) is never falsely nagged.
        photo_stale = False
        if crew > 0:
            from datetime import datetime as _dt, timedelta, timezone as _tz
            cutoff = _dt.now(_tz.utc) - timedelta(days=30)
            def _fresh(iso):
                try:
                    return _dt.fromisoformat(iso.replace("Z", "+00:00")) > cutoff
                except (ValueError, AttributeError):
                    return False
            fresh = _fresh(newest_upload)
            if not fresh:
                try:
                    import gbp as _gbp
                    tok = _gbp.get_access_token(cid)
                    place = _gbp._place_id_from_connection(cid)
                    if not place:
                        bfile = CLIENTS_DIR / slug / "plan-input.json"
                        if bfile.exists():
                            place = (json.loads(bfile.read_text()).get("brand") or {}).get("place_id")
                    loc = _gbp.find_location(tok, place) if (tok and place) else None
                    if loc:
                        acct = _gbp._g(f"{_gbp.ACCT_API}/accounts", tok)["accounts"][0]["name"]
                        media = _gbp._g("https://mybusiness.googleapis.com/v4/"
                                        f"{acct}/{loc['name']}/media", tok)
                        latest = max((m.get("createTime") or ""
                                      for m in media.get("mediaItems", [])), default="")
                        fresh = _fresh(latest)
                except Exception:
                    fresh = True  # can't verify the Google side — never nag on bad data
            photo_stale = not fresh
        checks.append((
            f"checklist-photo-fresh-{slug}", photo_stale,
            "ASK CLIENT: fresh job photos (none in 30+ days)",
            ("It's been over a month since any new photo landed on their Google "
             "profile or came in from the crew — fresh photos are a real local-ranking "
             "signal and keep the listing alive. MONICA: friendly nudge, re-share the "
             "crew upload link ({}) and suggest 3-4 phone pics from whatever job "
             "they're on this week.").format(photos_link)))

        # YouTube channel readiness (Santino 2026-07-28): connected YouTube with
        # NO channel on the Google account means we cannot upload videos for
        # them. Verified live against the YouTube API (channel_id missing in
        # metadata can just mean the backfill never ran) before flagging.
        yt_gap = False
        try:
            yt = _sb("GET", f"/rest/v1/user_integrations?client_id=eq.{cid}"
                     "&provider=eq.youtube&select=connection_metadata",
                     prefer="return=representation") or []
            md = (yt[0].get("connection_metadata") or {}) if yt else None
            if md is not None and not md.get("channel_id"):
                rt = md.get("refresh_token")
                if rt:
                    t = requests.post("https://oauth2.googleapis.com/token", data={
                        "client_id": os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
                        "client_secret": os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
                        "refresh_token": rt, "grant_type": "refresh_token"},
                        timeout=30).json().get("access_token")
                    if t:
                        ch = requests.get(
                            "https://www.googleapis.com/youtube/v3/channels"
                            "?part=id&mine=true",
                            headers={"Authorization": f"Bearer {t}"}, timeout=30).json()
                        yt_gap = not (ch.get("items") or [])
        except Exception:
            yt_gap = False  # verification failed — never nag on bad data
        # LSA intent (Santino 2026-07-28): a Google-connected client with no
        # LSA account resolved and no recorded intent gets ONE conversational
        # ask ("is LSA something you want to do?") instead of a form field.
        # Their answer is recorded by the escalation/backfill flow into
        # integration_settings.lsa_intent ("yes"/"no") which permanently
        # gates this check either way (yes -> lsa_fix pipeline takes over).
        lsa_gap = False
        try:
            co_row = _sb("GET", f"/rest/v1/companies?id=eq.{cid}"
                         "&select=integration_settings,plan",
                         prefer="return=representation") or []
            ints_ = (co_row[0].get("integration_settings") or {}) if co_row else {}
            if isinstance(ints_, str):
                ints_ = json.loads(ints_)
            # "later - revisit 2026-09-15" style answers re-open the ask once
            # the revisit date passes (Santino 2026-07-28: third state beyond
            # yes/no for clients who say "maybe later").
            from datetime import datetime as _ldt
            intent = str(ints_.get("lsa_intent") or "").strip().lower()
            intent_active = bool(intent)
            if intent.startswith("later"):
                m_ = re.search(r"(\d{4}-\d{2}-\d{2})", intent)
                if m_ and m_.group(1) <= _ldt.now().strftime("%Y-%m-%d"):
                    intent_active = False
            if (co_row and (co_row[0].get("plan") or "") == "Rank AI"
                    and not intent_active):
                gi_ = _sb("GET", f"/rest/v1/user_integrations?client_id=eq.{cid}"
                          "&provider=in.(google,google_ads)&select=connection_metadata",
                          prefer="return=representation") or []
                has_google = bool(gi_)
                has_lsa = any((g.get("connection_metadata") or {}).get("lsa_customer_id")
                              for g in gi_)
                lsa_gap = has_google and not has_lsa and not lsa
        except Exception:
            lsa_gap = False
        checks.append((
            f"checklist-lsa-intent-{slug}", lsa_gap,
            "ASK CLIENT: do they want Local Services Ads (Google Guaranteed)?",
            "No Local Services Ads account exists for this client and we've never "
            "asked if they want one. MONICA: ask conversationally, e.g. 'quick "
            "question - Local Services Ads (the Google Guaranteed listings with the "
            "green checkmark at the very top) - is that something you'd want us to "
            "set up? They're pay-per-lead and work great for emergency calls.' "
            "Relay their answer to the team; if yes we handle the whole setup."))

        checks.append((
            f"checklist-youtube-channel-{slug}", yt_gap,
            "ASK CLIENT: create their YouTube channel (account connected, no channel)",
            "Their YouTube is connected but the Google account has no YouTube channel "
            "yet, so we cannot post videos for them. MONICA: tell them it takes 2 "
            "minutes — open youtube.com while signed into that Google account, click "
            "their avatar, then 'Create a channel', use the business name. Once it "
            "exists we handle all the video posting."))

        for seed, gap_open, title, rationale in checks:
            key = action_key(cid, seed)
            existing = _sb("GET", "/rest/v1/marketing_action_plan"
                           f"?company_id=eq.{cid}&action_key=eq.{key}"
                           "&select=id,status", prefer="return=representation") or []
            if gap_open and not existing:
                if insert_plan_row(cid, slug, seed, title=title, rationale=rationale,
                                   action_type="client_input", target=None,
                                   impact="high", effort="low", dry_run=dry_run):
                    out.append(f"{slug}: seeded ask — {title}")
            elif not gap_open and existing and existing[0].get("status") == "planned":
                if not dry_run:
                    _sb("PATCH", "/rest/v1/marketing_action_plan"
                        f"?company_id=eq.{cid}&action_key=eq.{key}",
                        {"status": "done"})
                out.append(f"{slug}: gap cleared — resolved '{title}'")
    return out


def ensure_google_connect_asks(dry_run: bool, cid_to_slug: dict) -> list[str]:
    """Clients with a real Google Business Profile but NO Google connection in
    the app get a signed connect link seeded as a Monica ask (delivered to the
    PREFERRED contact — the office admin when one is set; Santino 2026-07-24,
    the All Pro case). Idempotent via action_key google-connect-{slug}."""
    import base64
    import hashlib
    import hmac as _hmac
    import time
    import uuid as _uuid

    secret = os.environ.get("CONNECT_LINK_SIGNING_SECRET", "")
    if not secret:
        return ["google-connect: CONNECT_LINK_SIGNING_SECRET unset — skipped"]

    def mint(cid):
        payload = {"cid": cid, "p": "google", "jti": str(_uuid.uuid4()),
                   "exp": int(time.time()) + 30 * 86400,
                   "o": "https://app.restorationai.io"}
        pb = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=").decode()
        sig = base64.urlsafe_b64encode(_hmac.new(
            secret.encode(), pb.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
        return ("https://nyscciinkhlutvqkgyvq.supabase.co/functions/v1/"
                "connect-link-start?t=" + pb + "." + sig)

    def shorten(slug, long_url):
        """restorationai.io/connect/{slug} — KV-backed 302 on gbpphotos-proxy.
        Raw Supabase links are unreadable and one got dropped from an SMS
        entirely (Jeff/MCC 2026-07-25). Falls back to the long URL if the KV
        write fails so an ask NEVER goes out linkless."""
        import requests as _rq
        acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        ctok = os.environ.get("CLOUDFLARE_R2_API_TOKEN")
        if not (acct and ctok):
            return long_url
        try:
            r = _rq.put(
                "https://api.cloudflare.com/client/v4/accounts/{}/storage/kv/"
                "namespaces/404d46bf0c72404495ab66d15157c499/values/connect%3A{}".format(acct, slug),
                headers={"Authorization": "Bearer " + ctok}, data=long_url, timeout=30)
            if r.ok:
                return "https://restorationai.io/connect/" + slug
        except Exception:
            pass
        return long_url

    def listing_exists(name, city, state):
        """One DFS maps lookup — only nudge when a listing actually exists."""
        try:
            import base64 as _b64

            import requests as _rq
            from geogrid_scan import load_dfs_creds
            u, pw = load_dfs_creds()
            r = _rq.post(
                "https://api.dataforseo.com/v3/serp/google/maps/live/advanced",
                headers={"Authorization": "Basic " + _b64.b64encode(
                    f"{u}:{pw}".encode()).decode(),
                    "Content-Type": "application/json"},
                json=[{"keyword": f"{name} {city} {state}",
                       "location_name": "United States", "language_code": "en",
                       "depth": 5}], timeout=90).json()
            items = ((r["tasks"][0].get("result") or [{}])[0] or {}).get("items") or []
            toks = {t for t in name.lower().split() if len(t) > 3}
            return any(toks & {t for t in (i.get("title") or "").lower().split()
                               if len(t) > 3} for i in items if i)
        except Exception:
            return False  # fail closed: no lookup, no nudge

    lines = []
    for cid, slug in cid_to_slug.items():
        try:
            gi = _sb("GET", "/rest/v1/user_integrations?client_id=eq.{}"
                     "&provider=eq.google&select=id".format(cid))
            if gi:
                # connected — auto-resolve any outstanding connect ask
                if not dry_run:
                    _sb("PATCH",
                        "/rest/v1/marketing_action_plan?company_id=eq.{}"
                        "&action_key=eq.google-connect-{}&status=eq.planned".format(cid, slug),
                        {"status": "resolved"})
                continue
            existing = _sb("GET",
                "/rest/v1/marketing_action_plan?company_id=eq.{}"
                "&action_key=eq.google-connect-{}&select=id".format(cid, slug))
            if existing:
                continue
            co = _sb("GET", "/rest/v1/companies?id=eq.{}"
                     "&select=name,city,state,plan,integration_settings".format(cid))
            if not co or (co[0].get("plan") or "") != "Rank AI":
                continue
            # kickoff-aware: a client with their kickoff call still ahead of
            # them gets set up ON the call — no automated connect nudges yet
            # (RestorationXpress case, Santino 2026-07-25)
            try:
                ints = co[0].get("integration_settings") or {}
                if isinstance(ints, str):
                    ints = json.loads(ints)
                gcid = ints.get("ghl_contact_id")
                if gcid and os.environ.get("GHL_API_KEY"):
                    import urllib.request as _ur
                    rq = _ur.Request(
                        "https://services.leadconnectorhq.com/contacts/{}/appointments".format(gcid),
                        headers={"Authorization": "Bearer " + os.environ["GHL_API_KEY"],
                                 "Version": "2021-07-28",
                                 "User-Agent": "Mozilla/5.0 (rank-ai ops)"})
                    evs = json.loads(_ur.urlopen(rq, timeout=20).read()).get("events") or []
                    from datetime import datetime as _dt
                    now_local = _dt.now()
                    def _future(ev):
                        try:
                            t = _dt.strptime(ev.get("startTime", ""), "%Y-%m-%d %H:%M:%S")
                            return t > now_local
                        except ValueError:
                            return False
                    upcoming_kickoff = any(
                        "kickoff" in (ev.get("title") or "").lower() and _future(ev)
                        and (ev.get("appointmentStatus") or "").lower() not in ("cancelled", "noshow")
                        for ev in evs)
                    if upcoming_kickoff:
                        lines.append(f"google-connect {slug}: kickoff call upcoming — deferring")
                        continue
            except Exception:
                pass  # gate is best-effort; a failed lookup never blocks the ask
            name = (co[0].get("name") or "").strip()
            if not listing_exists(name, co[0].get("city") or "",
                                  co[0].get("state") or ""):
                lines.append(f"google-connect {slug}: no listing found — manual review")
                continue
            link = shorten(slug, mint(cid))
            row = {"company_id": cid, "rank_ai_slug": slug,
                   "action_key": "google-connect-" + slug,
                   "action_type": "client_input", "status": "planned",
                   "priority": 1, "pinned": True, "impact": "high",
                   "effort": "low",
                   "title": "Connect your Google Business Profile",
                   "target": link,
                   "rationale": ("Their listing exists but the account isn't "
                                 "connected. Send this link and tell them to sign "
                                 "in with the Google account that manages their "
                                 "business listing: " + link)}
            if dry_run:
                lines.append(f"google-connect {slug}: WOULD seed ask")
            else:
                _sb("POST", "/rest/v1/marketing_action_plan", [row])
                lines.append(f"google-connect {slug}: ask seeded (Monica delivers)")
        except Exception as e:  # noqa: BLE001 — one client never kills the run
            lines.append(f"google-connect {slug}: ERROR {str(e)[:80]}")
    return lines


def run(since_override: str | None, dry_run: bool, do_send: bool) -> int:
    run_start = datetime.now(timezone.utc)
    cursor_out = run_start.strftime("%Y-%m-%dT%H:%M:%SZ")
    state = load_state()
    since = since_override or state.get("cursor") or (
        run_start - timedelta(days=DEFAULT_LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cid_to_slug = slug_map()
    print(f"client-ops sync since {since}"
          f"{' [DRY RUN]' if dry_run else ''}")

    ensure_bootstrapped(dry_run, do_send, cid_to_slug)
    for ln in ensure_google_connect_asks(dry_run, cid_to_slug):
        print("  " + ln)
    for ln in ensure_gbp_first_sync(dry_run, cid_to_slug):
        print("  " + ln)
    for ln in ensure_baseline_scans(dry_run, cid_to_slug):
        print("  " + ln)
    for ln in ensure_ads_first_sync(dry_run, cid_to_slug):
        print("  " + ln)
    for ln in ensure_setup_checklist(dry_run, cid_to_slug):
        print("  " + ln)
    # Setup ledger — the overseer: derives per-client setup state, auto-heals
    # GSC/IndexNow on live sites, and returns the us-owed attention list
    # (fed into the digest's "Needs Santino/Claude" sections below).
    try:
        from setup_ledger import ensure_auto_site_build, ensure_ledger
        ledger_lines = ensure_ledger(dry_run, cid_to_slug)
        ledger_lines += ensure_auto_site_build(dry_run, cid_to_slug)
    except Exception as e:
        ledger_lines = [f"(ledger) errored: {str(e)[:120]}"]
    for ln in ledger_lines:
        print("  LEDGER: " + ln)

    intake = [i for i in fetch_answered_intake(since)
              if i["id"] not in state["processed_intake_ids"]]
    plan = [p for p in fetch_plan_changes(since)
            if f"{p['id']}:{p['status']}" not in state["processed_plan_events"]]
    print(f"  {len(intake)} new intake answer(s), {len(plan)} action-plan change(s)")

    per_client: dict[str, dict] = {}

    def bucket(company_id: str, slug: str | None) -> dict:
        label = slug or company_id
        return per_client.setdefault(label, {"answered": [], "auto": [],
                                             "plan_changes": [], "attention": []})

    for ln in ledger_lines:
        label, _, rest = ln.partition(": ")
        if not rest:
            label, rest = "(ops)", ln
        bucket("", label)["attention"].append("LEDGER: " + rest)

    # Backstop: every mapped client with an app account should have intake
    # items — the day-one audit seeds them, but that's agent-executed and can
    # be missed (TRG had ZERO items for a week; the concierge had nothing to
    # collect). Flag it in the digest until someone seeds them.
    seeded = {r["company_id"] for r in
              (_sb("GET", "/rest/v1/client_intake_items?select=company_id",
                   prefer="return=representation") or [])}
    for cid, slug in cid_to_slug.items():
        if cid in seeded:
            continue
        # Live/active clients with nothing left to collect are fine — the gap
        # that bites is a client still in onboarding with zero items.
        try:
            status = json.loads((ROOT / "clients" / f"{slug}.json").read_text()).get("status")
        except Exception:
            status = None
        if status == "active":
            continue
        msg = ("NO client_intake_items seeded — day-one audit seeding was "
               "skipped; the concierge has nothing to collect for this client.")
        print(f"  WARNING: {slug} ({cid}) {msg}")
        bucket(cid, slug)["attention"].append({"question": msg, "answer": ""})

    for item in intake:
        cid = item["company_id"]
        slug = cid_to_slug.get(cid)
        b = bucket(cid, slug)
        ans = answer_text(item)
        q = item["question"]
        kind = classify_intake(item)
        b["answered"].append(f"[{item['field_type']}] {q} → {ans!r}")
        print(f"  intake {item['id'][:8]} ({slug or cid}) [{kind}]: {q[:70]!r} -> {ans[:60]!r}")

        if kind == "license" and slug:
            nums = extract_license_numbers(item)
            added = apply_license(slug, nums, dry_run)
            append_journal(slug, [f"License answer: {q} → {ans!r} "
                                  f"(numbers: {', '.join(nums)})"], dry_run)
            if added:
                b["auto"].append(f"License(s) {', '.join(added)} written to "
                                 f"plan-input.json brand truth")
            insert_plan_row(
                cid, slug, f"license:{item['id']}",
                title="License on file — trust badges pending re-render",
                rationale=(f"Client answered the intake question {q!r} with {ans!r}; "
                           f"license number(s) {', '.join(nums)} recorded in "
                           f"clients/{slug}/plan-input.json brand.license_numbers. "
                           "Site trust badges / license claims need a re-render to pick "
                           "this up — apply on the next build/maintenance pass (rendering "
                           "costs money, so it is not automatic)."),
                action_type="compliance", target=",".join(nums),
                impact="high", effort="low", dry_run=dry_run)
            b["auto"].append("Opened plan item: License on file — trust badges "
                             "pending re-render")
        elif kind == "gating_yes_no" and slug:
            append_journal(slug, [f"Gating answer: {q} → **{ans}**"
                                  + (f" (was blocking: {item['blocks']})"
                                     if item.get("blocks") else "")], dry_run)
            positive = ans.strip().lower() in ("yes", "true", "y")
            unblocked = (f"unblocks '{item['blocks']}'" if item.get("blocks")
                         else "the dependent work can proceed")
            insert_plan_row(
                cid, slug, f"gate:{item['id']}",
                title=(f"Client answered '{ans}': {q[:90]}"),
                rationale=(f"Gating intake question answered {ans!r} on "
                           f"{item.get('answered_at') or 'unknown date'} — "
                           f"{unblocked if positive else 'answer is negative — re-plan the dependent work'}. "
                           f"Logged in clients/{slug}/ops-journal.md."),
                action_type="client_input", target=item.get("blocks"),
                impact="medium", effort="low", dry_run=dry_run)
            b["auto"].append(f"Journaled gating answer + opened plan item "
                             f"({'unblocked' if positive else 'NEGATIVE answer'}: {q[:70]})")
        elif kind == "customer_list" and slug:
            append_journal(slug, [f"Customer-list checklist completed: {q}"], dry_run)
            insert_plan_row(
                cid, slug, f"custlist:{item['id']}",
                title="Customer list received — stage for review campaign",
                rationale=(f"Client completed the intake checklist {q!r}. Pull the list, "
                           "clean it, and stage contacts for the review reactivation "
                           "campaign (do NOT enroll before sender/number checks)."),
                action_type="review_campaign", target=None,
                impact="high", effort="medium", dry_run=dry_run)
            b["auto"].append("Opened plan item: Customer list received — stage for "
                             "review campaign")
        else:
            note = f"Review answer: [{item['field_type']}] {q} → {ans!r}"
            if kind != "digest" and not slug:
                note += " (no pipeline record for this company — handle manually)"
            b["attention"].append(note)
        state["processed_intake_ids"].append(item["id"])

    for row in plan:
        cid = row["company_id"]
        slug = row.get("rank_ai_slug") or cid_to_slug.get(cid)
        b = bucket(cid, slug)
        b["plan_changes"].append(
            f"{row['status'].upper()}: {row['title']} ({row['action_type']}, "
            f"{(row.get('updated_at') or '')[:10]})")
        if row["status"] == "dismissed":
            b["attention"].append(f"Dismissed by operator — drop from plans: {row['title']}")
        print(f"  plan {row['id'][:8]} ({slug or cid}): {row['status']} — {row['title'][:70]!r}")
        state["processed_plan_events"].append(f"{row['id']}:{row['status']}")

    if not per_client:
        print("Nothing new — no digest, no email.")
        state["cursor"] = cursor_out
        state["last_run_at"] = run_start.isoformat()
        save_state(state, dry_run)
        return 0

    date_str = run_start.strftime("%Y-%m-%d")
    md = digest_markdown(date_str, per_client)
    print("\n" + "=" * 60 + "\n" + md + "=" * 60)
    if not dry_run:
        OPS_DIR.mkdir(parents=True, exist_ok=True)
        (OPS_DIR / f"digest-{date_str}.md").write_text(md)
        print(f"  wrote clients/_ops/digest-{date_str}.md")
    send_email(f"Client Ops Digest — {date_str}",
               digest_html(date_str, per_client), do_send and not dry_run)

    state["cursor"] = cursor_out
    state["last_run_at"] = run_start.isoformat()
    save_state(state, dry_run)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bootstrap-only", action="store_true",
                    help="run only the new-client bootstrap backstop (full mode), then exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="classify + print everything; write nothing anywhere")
    ap.add_argument("--since", help="ISO timestamp cursor override (e.g. 2026-07-01)")
    ap.add_argument("--send", action="store_true",
                    help="actually deliver the digest email (default: print it)")
    args = ap.parse_args()
    if args.bootstrap_only:
        load_env()
        lines = ensure_bootstrapped(args.dry_run, getattr(args, "send", False),
                                    slug_map(), full=True)
        # Day-one blitz rides the same run (Santino 2026-07-26: every tab full
        # by first login, never 'come back tomorrow'). Fresh slug map — the
        # bootstrap above may have just minted new clients.
        m = slug_map()
        # ensure_ledger joins the day-one blitz (Santino 2026-07-28): a fresh
        # signup gets citations discovery, a tracking number, and ledger rows
        # in the SAME run the signup-alert webhook triggers — not 4h later.
        from setup_ledger import ensure_ledger as _ledger
        for fn in (ensure_gbp_first_sync, ensure_baseline_scans,
                   ensure_ads_first_sync, _ledger):
            try:
                extra = fn(args.dry_run, m)
            except Exception as e:  # noqa: BLE001 — blitz never blocks bootstrap
                extra = [f"{fn.__name__} failed: {str(e)[:100]}"]
            for ln in extra:
                print("  " + ln)
            lines += extra
        print("bootstrap-only: {} action(s)".format(len(lines)))
        raise SystemExit(0)

    load_env()
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")):
        print("ERROR: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required.", file=sys.stderr)
        return 1
    return run(args.since, args.dry_run, args.send)


if __name__ == "__main__":
    sys.exit(main())
