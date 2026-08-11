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

# ---- domain access: THE registrar truth (Santino 2026-08-04) ---------------
# LIVE failure, Jerrott Gray / Reign Restoration first-day thread: Monica told
# him "We'll reach out through GoDaddy to get the switch made." There is no
# such path. No registrar — GoDaddy least of all — offers an API, a support
# route or any mechanism by which we can REQUEST access to somebody else's
# domain. Access only ever moves one way: the owner grants it from inside
# their own account. These strings are the single source of truth; the app's
# Site-tab card, the setup ledger and Monica's texts all render THEM, so the
# client hears exactly one story wherever they look.
#
# Address split (do not drift): registrar / delegate invites go to
# setup@restorationai.io (the Concierge's own intake alias, see
# scripts/email_intake.py). contact@restorationai.io is the GOOGLE-side
# identity — Business Profile manager grants, Search Console users — and must
# never be given out for a registrar invite.
DOMAIN_ACCESS_INVITE_EMAIL = "setup@restorationai.io"
DOMAIN_ACCESS_GOOGLE_EMAIL = "contact@restorationai.io"

DOMAIN_ACCESS_TRUTH = (
    "WE CANNOT GET DOMAIN ACCESS OURSELVES. No registrar lets an agency "
    "request access to a customer's domain, and there is no API for it. The "
    "owner has to hand it over: either they send a delegate-access invite, "
    "or they give us the login. NEVER say or imply that we will reach out "
    "to, contact, go through, work with or request anything from GoDaddy "
    "(or any registrar) to get access, and never imply the switch can "
    "happen without the client doing this one thing first.")

DOMAIN_ACCESS_ASK_GODADDY = (
    "Sign in at account.godaddy.com/access, tap Invite to Access, and send "
    f"the invite to {DOMAIN_ACCESS_INVITE_EMAIL} with the Domains "
    "permission. Takes about two minutes, on a phone or a computer.")

DOMAIN_ACCESS_ASK_GENERIC = (
    "Nearly every domain company has an 'invite someone' or 'delegate "
    f"access' option in the account settings: send that invite to "
    f"{DOMAIN_ACCESS_INVITE_EMAIL}. If theirs has no invite option, the "
    "alternative is a quick 15-minute call where they sign in and we drive.")

# What Monica is handed verbatim (compose context) and what the app card /
# ledger renders. One text, three surfaces.
DOMAIN_ACCESS_HOWTO = (
    DOMAIN_ACCESS_TRUTH + "\n"
    "HOW THE CLIENT GRANTS IT (GoDaddy, the common case): "
    + DOMAIN_ACCESS_ASK_GODADDY + "\n"
    "ANY OTHER DOMAIN COMPANY: " + DOMAIN_ACCESS_ASK_GENERIC + "\n"
    f"Delegate invites go to {DOMAIN_ACCESS_INVITE_EMAIL}. "
    f"({DOMAIN_ACCESS_GOOGLE_EMAIL} is the Google-side address for Business "
    "Profile and Search Console access only — never for a domain invite.)")


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
    """Find-or-create by action_key; pinned so strategist's weekly wipe skips it.

    Find-or-create used to mean a row seeded months ago kept its ORIGINAL
    wording forever, so rewriting an ask here changed nothing for any client
    that already had it (Santino 2026-08-05: "get the crew photo link in use"
    survived every rewrite because Crew's row predated them). An OPEN row now
    has its title refreshed in place whenever the seeder's wording changes —
    the action_key, and therefore the row's identity and history, is
    untouched.
    """
    key = action_key(company_id, key_seed)
    existing = _sb("GET", "/rest/v1/marketing_action_plan"
                   f"?company_id=eq.{company_id}&action_key=eq.{key}"
                   "&select=id,title,status", prefer="return=representation") or []
    if existing:
        stale = [r for r in existing if r.get("status") == "planned"
                 and (r.get("title") or "") != title]
        if stale and not dry_run:
            for r in stale:
                _sb("PATCH",
                    f"/rest/v1/marketing_action_plan?id=eq.{r['id']}",
                    {"title": title})
        elif stale:
            print(f"    [dry-run] would retitle plan row {stale[0]['id'][:8]}: "
                  f"{stale[0].get('title')!r} -> {title!r}")
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
    # A marketing_sites ROW IS NOT PROOF THE CLIENT IS BOOTSTRAPPED.
    #
    # This pass creates that row itself, but the REPO half (clients/{slug}.json,
    # plan-input, the company_map entry) is written by bootstrap_client.py. So
    # the first run created the row, every run afterwards saw the row and
    # skipped, and the repo half was never written by the one job that has
    # commit rights. RT Olson signed up 2026-08-08 and was still missing from
    # company_map a day later — invisible to every ensure_* pass, because they
    # all key off that map. Dry County is in the same state right now.
    #
    # Completion is now judged on the REPO artefact, which is the thing that
    # was actually missing (Santino 2026-08-09: "we don't want a manual human
    # to have to approve anything").
    def _repo_bootstrapped(cid: str) -> bool:
        slug = (cid_to_slug or {}).get(cid)
        return bool(slug and (ROOT / "clients" / f"{slug}.json").exists())

    for co in cos:
        if "test" in (co.get("name") or "").lower():
            continue
        if co["id"] in have and _repo_bootstrapped(co["id"]):
            continue
        pipeline_slug = ((cid_to_slug or {}).get(co["id"])
                         # A slug this company ALREADY OWNS on its
                         # marketing_sites row is its identity too. Without
                         # this, a client whose DB row exists but whose repo
                         # files do not sees its own slug in `taken` and mints
                         # a duplicate: Burley would have become
                         # burley-industries-of-hartland-2, splitting one
                         # client across two identities in a job that commits
                         # to main unattended.
                         or next((r.get("rank_ai_slug") for r in sites
                                  if r.get("company_id") == co["id"]
                                  and r.get("rank_ai_slug")), None))
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


def ensure_gbp_manager_access(dry_run: bool, cid_to_slug: dict) -> list[str]:
    """Agency MANAGER access on every client GBP — invited AND accepted daily.

    Santino 2026-08-04, on finding scripts/gbp_admin_invite.py had run exactly
    once by hand on 08-01: 'build sustainability, not one-off fixes'. Reign
    connected Google on 08-03, nothing invited the agency account, so Reign
    could never appear in Bing's GBP import — and every future client would
    have failed the same way, silently. This is that script on a schedule.

    Bing Places imports only the listings contact@restorationai.io directly
    manages, so this pass is the upstream dependency of the whole Bing/
    citations lane. Idempotent (state re-derived from Google; confirmed
    managers re-verified weekly), and it accepts its own invitations through
    the account-management API — no Gmail step, no browser profile."""
    try:
        from gbp_admin_invite import ensure_agency_manager
    except Exception as e:  # noqa: BLE001
        return [f"gbp-manager-access: unavailable ({str(e)[:80]})"]
    try:
        results, attention = ensure_agency_manager(dry_run, cid_to_slug)
    except Exception as e:  # noqa: BLE001 — never take the sweep down
        return [f"gbp-manager-access: pass failed ({str(e)[:100]})"]
    out: list[str] = []
    for slug, v in sorted(results.items()):
        # Quiet on steady state — only transitions and real blockers speak.
        if v.get("changed") and v["state"] == "manager":
            out.append(f"{slug}: agency is now a MANAGER on their Google "
                       "listing (unblocks the Bing import)")
        elif v["state"] == "pending":
            out.append(f"{slug}: GBP manager invite sent, not yet accepted")
    out += [a if ":" in a.split(" ")[0] else f"(gbp-access) {a}"
            for a in attention]
    return out


# Asks we have WITHDRAWN. Deleting an entry from `checks` is not enough and is
# the trap worth naming: rows are only ever closed by the gap_open==False
# branch at the bottom of ensure_setup_checklist, so a check that no longer
# exists can never close the rows it already seeded. They stay `planned` — on
# the board, in the ask ranking, and speakable by Monica — forever. Seeds
# listed here get their open rows closed on the next pass and cost one no-op
# query per client after that.
#
# {slug} is substituted per client.
RETIRED_ASK_SEEDS = (
    # Santino 2026-08-07: a human vets the service list now. Two failures, not
    # one. (1) The ask itself was unreasonable — Rudy got "confirm all 13
    # services on your Google profile". (2) Monica spoke the INTERNAL HEADLINE
    # instead of the MONICA: script in the rationale, which said max 3 and
    # conversational and "the client does nothing in Google". The headline is
    # written for the ops board, never for a client.
    "checklist-svc-confirm-{slug}",
    # Santino 2026-08-08: every client goes to Open 24 hours regardless of
    # industry, because the AI receptionist answers and books after hours.
    # Setting it is our job; asking the owner only invited a narrower answer
    # than the truth.
    "checklist-hours-{slug}",
)


MIN_GBP_PHOTOS = 15   # Santino 2026-08-08: only ask for photos below this.


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _branding_files(cid: str, prefix: str, limit: int = 400) -> list[dict]:
    """List objects under branding/{cid}/{prefix}. [] on any failure — a
    storage hiccup must never make us ask for something we hold."""
    try:
        sb_url = os.environ["SUPABASE_URL"].rstrip("/")
        sb_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        r = requests.post(f"{sb_url}/storage/v1/object/list/branding",
                          headers={"apikey": sb_key,
                                   "Authorization": f"Bearer {sb_key}",
                                   "Content-Type": "application/json"},
                          json={"prefix": f"{cid}/{prefix}", "limit": limit},
                          timeout=30)
        return [f for f in (r.json() or []) if isinstance(f, dict) and f.get("id")]
    except Exception:
        return []


def close_satisfied_intake_items(cid: str, slug: str, dry_run: bool) -> list[str]:
    """Close wizard intake items whose artefact we ALREADY HOLD.

    The standing rule is "never ask a client for something we already have",
    and it was being broken constantly because the guards only ever protected
    the setup-checklist PLAN rows. The wizard's `client_intake_items` are a
    separate table fed by a separate system, and nothing ever closed them: a
    hub upload lands in storage and pins an ops row, but the item that asked
    for it stays `pending` forever.

    Two live examples on 2026-08-08. Rudy (Life Savers) uploaded his customer
    list on 08-06 and the item was still open two days later. Curt (Home Pride)
    was asked for his logo while we held FIVE logo files and his live site was
    already serving one.

    Each rule below must be able to point at the artefact. When we cannot prove
    we hold it, the item stays open — this closes items, it never invents an
    answer.
    """
    out: list[str] = []
    items = _sb("GET", "/rest/v1/client_intake_items"
                f"?company_id=eq.{cid}&status=eq.pending"
                "&select=id,question", prefer="return=representation") or []
    if not items:
        return out

    photos = _branding_files(cid, "job-photos") + _branding_files(cid, "job-photos/posted")
    gbp_photos = len([f for f in photos if re.sub(r"^r\d+_", "", f["name"]).startswith("gbp-")])
    logos = [f for f in _branding_files(cid, "brand") if "logo" in f["name"].lower()]
    docs = _branding_files(cid, "docs/other") + _branding_files(cid, "docs")
    cust = [f for f in docs if re.search(r"customer|client.?list", f["name"], re.I)]

    for it in items:
        q = (it.get("question") or "").lower()
        why = None
        if "logo" in q and logos:
            why = f"we already hold {len(logos)} logo file(s) in storage"
        elif "job photos" in q and gbp_photos >= MIN_GBP_PHOTOS:
            why = (f"their Google profile already has {gbp_photos} photos "
                   f"(threshold {MIN_GBP_PHOTOS})")
        elif "team photo" in q:
            # Santino 2026-08-08: a team photo is ONLY for the review-request
            # campaign. Asking every client for one as general onboarding is
            # friction with no consumer.
            why = "team photos are only asked for the review-request campaign"
        elif "equipment supplier" in q or "distributors do you buy" in q:
            why = "withdrawn 2026-08-08 — we research the supplier ourselves"
        elif "customer list" in q and cust:
            why = f"already uploaded: {cust[0]['name']}"
        if not why:
            continue
        if not dry_run:
            _sb("PATCH", "/rest/v1/client_intake_items"
                f"?id=eq.{it['id']}",
                {"status": "answered",
                 "answer": f"Closed automatically {_utcnow()[:10]}: {why}.",
                 "answered_at": _utcnow()})
        out.append(f"{slug}: closed intake — {it['question'][:52]} ({why})")
    return out


def retire_withdrawn_asks(cid: str, slug: str, dry_run: bool) -> list[str]:
    """Close any still-open row seeded by an ask we have since withdrawn.

    Deliberately gate-free: called for every active client, not only the ones
    that currently qualify for checklist nags.
    """
    out: list[str] = []
    for tmpl in RETIRED_ASK_SEEDS:
        seed = tmpl.format(slug=slug)
        key = action_key(cid, seed)
        stale = _sb("GET", "/rest/v1/marketing_action_plan"
                    f"?company_id=eq.{cid}&action_key=eq.{key}"
                    "&status=eq.planned&select=id",
                    prefer="return=representation") or []
        if stale:
            if not dry_run:
                _sb("PATCH", "/rest/v1/marketing_action_plan"
                    f"?company_id=eq.{cid}&action_key=eq.{key}",
                    {"status": "done"})
            out.append(f"{slug}: retired ask — {seed}")
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
      hours        GBP claimed but no business hours set
      crew-photos  zero crew-uploaded job photos ever (gbp- imports and
                   posted/ recycles don't count)

    RETIRED: svc-confirm (see RETIRED_ASK_SEEDS).
    """
    from upload_links_sync import hub_token

    out: list[str] = []
    # ein + integration_settings ride along for the verification-evidence check
    # below; without them every client reads as "missing everything".
    active = _sb("GET", "/rest/v1/companies?status=ilike.active"
                 "&select=id,name,ein,integration_settings",
                 prefer="return=representation") or []

    # Withdrawals run FIRST and UNCONDITIONALLY, over EVERY mapped client —
    # not `active`, and ahead of the gates below (no slug; no GBP profile and
    # no LSA blocker). None of those conditions have anything to do with
    # whether an ask we have withdrawn should still be open on someone's
    # board. Both exclusions were real: mold-solutionz is status=paused, so
    # the active-only query never saw it, and the sweep originally sat at the
    # bottom of the loop behind two continues. A paused client is the worst
    # case to skip, because the stale ask simply reanimates on unpause.
    for _cid, _slug in cid_to_slug.items():
        out += retire_withdrawn_asks(_cid, _slug, dry_run)
        out += close_satisfied_intake_items(_cid, _slug, dry_run)

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
            "ASK CLIENT: send the contractor license + insurance certificate "
            "Google needs for Local Services Ads",
            ("Google rejected or is missing verification documents on this client's "
             "Local Services Ads, so their LSA cannot serve. Blocker: {}\n\n"
             "MONICA: ask the owner for the required documents (state contractor "
             "license, current certificate of insurance). Give the HUB LINK and "
             "nothing else: {} (pick the License / Insurance category). NEVER offer "
             "email and never say 'reply with a photo' (Santino 2026-08-09, after "
             "Josiah was told to email his customer list to setup@) — an emailed "
             "attachment only lands in an ops row needing a human to file it, while "
             "a hub upload goes straight to storage and pins its own task. Do not "
             "assume a device: it works from a phone or a computer. We resubmit to "
             "Google for them, they should NOT have to log into anything.").format(
                (lsa[0]["title"] if lsa else ""), hub)))

        # svc-confirm REMOVED 2026-08-07 (Santino). A human vets the service
        # list now. It went out to Rudy as "confirm all 13 services on your
        # Google profile" — thirteen is not a question, it is homework, and it
        # is our job. The seed is retired below, not merely deleted; see
        # RETIRED_ASK_SEEDS for why that distinction matters.

        # VERIFICATION EVIDENCE (Santino 2026-08-06). Directories do not just
        # want a name and address; the ones worth having make you PROVE the
        # business is real before the listing counts. Nextdoor accepts an EIN
        # letter or a government business licence in place of a phone code,
        # and that document route is what lets us verify a page without a code
        # landing on an owner's phone mid-job. HomeGuide and others ask for
        # year founded outright.
        #
        # The wizard has collected licence/certifications/founded year into
        # integration_settings.licensing since 2026-07-26, but almost nobody
        # filled them: across 23 active clients it was 4, 6 and 6 respectively,
        # and EIN was 1. Invisible fields do not get filled, so this asks.
        #
        # ONE ask covering the set, not three: MAX_ITEMS_PER_MESSAGE is 1 and
        # three separate checklist rows would queue three separate texts about
        # paperwork.
        _lic = ((co.get("integration_settings") or {}).get("licensing") or {})
        # NEVER ASK FOR WHAT WE ALREADY HOLD. The wizard's licensing block is
        # not the only place a licence lives: TRG's NJ HIC 13VH05488600 was
        # confirmed on a call and written into clients/{slug}.json, and asking
        # him for it again is the same mistake we made asking ProRestoration
        # for photos we already had 231 of. Treat a licence recorded anywhere
        # in the client record as present.
        _lic_known = bool(str(_lic.get("license_number") or "").strip())
        if not _lic_known:
            try:
                _rec = (CLIENTS_DIR / f"{slug}.json")
                if _rec.exists():
                    _blob = json.loads(_rec.read_text())
                    _nums = ((_blob.get("nap") or {}).get("license_numbers")
                             or (_blob.get("brand") or {}).get("license_numbers")
                             or _blob.get("license_numbers") or [])
                    _lic_known = bool([x for x in _nums if str(x).strip()])
            except Exception:
                pass
        _missing_docs = [lbl for lbl, val in (
            ("your license number", "known" if _lic_known else ""),
            ("the year you started", _lic.get("founded_year")),
            ("your EIN", co.get("ein")),
        ) if not str(val or "").strip()]
        # RELEASED 2026-08-06. The hold was "lets make sure its in the app
        # first" (Santino) — asking for an EIN before the app could store it
        # would land the reply on the board and nowhere durable. That shipped:
        # wizard step 4 writes companies.ein, and Marketing > Connect has the
        # Business Verification card beside Business Information. Verified live
        # in the deployed bundle at app.restorationai.io, not just merged.
        _ASK_FOR_VERIFICATION_DOCS = True
        checks.append((
            f"checklist-verification-docs-{slug}",
            _ASK_FOR_VERIFICATION_DOCS and len(_missing_docs) >= 2,
            "ASK CLIENT: license number, year founded, EIN — needed to verify "
            "their directory listings",
            ("Missing: {}. These are what directories accept as PROOF the "
             "business is real — Nextdoor takes an EIN letter or a state "
             "license instead of texting a verification code to the owner, and "
             "an unverified page cannot post. MONICA: ask plainly and in one "
             "message, e.g. 'to get your listings verified I need a couple of "
             "things off your paperwork: your {} — whenever you get a minute.' "
             "Say what it is FOR. An owner asked for a tax ID with no reason "
             "given will assume the worst, and they would be right to."
             ).format(", ".join(_missing_docs), " and your ".join(_missing_docs))))

        # HOURS ARE NO LONGER A QUESTION (Santino 2026-08-08): every client is
        # set to Open 24 hours regardless of industry, because the AI
        # receptionist answers and books after hours, so the listing is
        # genuinely reachable around the clock. Asking the owner what hours to
        # show invited a narrower answer than the truth and suppressed the
        # listing for "open now" searches in the meantime. This is now our job,
        # not theirs — the ask is retired (see RETIRED_ASK_SEEDS) and the 24/7
        # write belongs to the GBP maintenance pass.

        crew = 0
        have_already = 0     # photos we ALREADY hold from any source (GBP, website)
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
                    if base.startswith("gbp-"):
                        have_already += 1
                    else:
                        crew += 1
                        newest_upload = max(newest_upload, f.get("created_at") or "")
        except Exception:
            crew = 1  # storage hiccup: assume fine, never nag on bad data
        # Anything we harvested off their own Google profile or website counts too.
        try:
            _mf = ROOT / "clients" / slug / "photo-manifest.json"
            if _mf.exists():
                _a = json.loads(_mf.read_text()).get("assets")
                have_already += len(_a) if isinstance(_a, (list, dict)) else 0
        except Exception:
            pass
        # NEVER ASK FOR WHAT WE ALREADY HAVE (Santino 2026-08-05). This fired on
        # crew == 0 alone, which counts ONLY uploads through the hub link and
        # skips every gbp- file by name. ProRestoration was being asked to "send
        # job photos, not one has ever come in" while we sat on 231 of theirs,
        # 200 pulled straight off their own Google profile. The ask is for
        # clients we genuinely have nothing usable for, not for clients who
        # simply have not used the upload link.
        checks.append((
            f"checklist-crew-photos-{slug}", crew == 0 and have_already < 6,
            "ASK CLIENT: send job photos from the crew — we have none from any source",
            ("We hold no usable job photos for this client from ANY source: nothing "
             "uploaded through the hub, nothing on their Google profile, nothing "
             "harvested from their site. MONICA: re-share their CLIENT HUB link ({}) "
             "— photos upload right there, no login, from a phone OR a computer. "
             "Texting it to the crew group chat is one good option, not the only "
             "one; even 3-4 pics from recent jobs is plenty. "
             "(hub only — the raw /gbpphotos/ link is deprecated, 2026-08-01)").format(hub)))

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
            "ASK CLIENT: send a few new job photos — nothing new in 30+ days",
            ("It's been over a month since any new photo landed on their Google "
             "profile or came in from the crew — fresh photos are a real local-ranking "
             "signal and keep the listing alive. MONICA: friendly nudge, re-share the "
             "crew upload link ({}) and suggest 3-4 phone pics from whatever job "
             "they're on this week.").format(photos_link)))

        # YouTube channel readiness (Santino 2026-07-28): connected YouTube with
        # NO channel on the Google account means we cannot upload videos for
        # them. Verified live against the YouTube API (channel_id missing in
        # metadata can just mean the backfill never ran) before flagging.
        # 2026-08-04: the verification itself now lives in video_maker
        # (youtube_channel_state) so the ask, the ledger card and the video
        # cron's skip all read the SAME answer. has_channel is None when the
        # Google side could not be read — never nag on that.
        yt_gap = False
        try:
            import video_maker as _vm
            yt_gap = _vm.youtube_channel_state(slug)["has_channel"] is False
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
            "ASK CLIENT: do they want Local Services Ads, the Google Guaranteed "
            "listings at the top of search?",
            "No Local Services Ads account exists for this client and we've never "
            "asked if they want one. MONICA: ask conversationally, e.g. 'quick "
            "question - Local Services Ads (the Google Guaranteed listings with the "
            "green checkmark at the very top) - is that something you'd want us to "
            "set up? They're pay-per-lead and work great for emergency calls.' "
            "Relay their answer to the team; if yes we handle the whole setup."))

        checks.append((
            f"checklist-youtube-channel-{slug}", yt_gap,
            "ASK CLIENT: create a YouTube channel on their Google account — we "
            "cannot publish their videos without one",
            "Their YouTube is connected but the Google account has no YouTube channel "
            "yet, so nothing we produce can be published — video production is paused "
            "for them until it exists. MONICA: keep it light and make it feel like "
            "nothing, e.g. 'your YouTube account is linked up on our end, but there's "
            "no actual channel on it yet — creating one takes about 30 seconds: go to "
            "youtube.com signed into that same Google account, click your picture "
            "top-right, hit Create a channel, and name it after the business. Or if "
            "it's easier, say the word and we'll hop on a quick call and do it "
            "together.' Once it exists we handle every upload from there."))

        for seed, gap_open, title, rationale in checks:
            key = action_key(cid, seed)
            existing = _sb("GET", "/rest/v1/marketing_action_plan"
                           f"?company_id=eq.{cid}&action_key=eq.{key}"
                           "&select=id,status", prefer="return=representation") or []
            # Always go through insert_plan_row while the gap is open: it
            # creates the row when absent AND refreshes the wording of one
            # that already exists (2026-08-05 — the old `not existing`
            # short-circuit is why every rewrite of these asks was invisible
            # to the clients who already had them).
            if gap_open:
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


def ensure_ads_mcc_access(dry_run: bool, cid_to_slug: dict) -> list[str]:
    """Invite ourselves onto every client Ads/LSA account we know about.

    GBP has had this since 2026-08-04 (ensure_gbp_manager_access invites AND
    self-accepts, daily). Ads never did: the MCC invite was only ever created
    by a human clicking the app's lsa-request-access button, which is why five
    clients had no invite at all on 2026-08-08. Santino: make it automatic on
    connect, for both.

    This is the CREATE half. The accept half already exists and is proven —
    ads_link_accept.accept_pending_links() clears a PENDING link using the
    client's own grant, no client action. Together they close the loop.

    Only fires where we actually know the Ads customer id. An account we have
    never discovered cannot be linked, and guessing is not an option, so those
    are reported for lsa_detect to find rather than silently skipped.
    """
    out: list[str] = []
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from lsa_detect import build_mcc_client
    except Exception as e:  # noqa: BLE001
        return [f"ads-mcc-access: unavailable ({str(e)[:80]})"]
    cl, mcc = build_mcc_client()
    if not cl:
        return ["ads-mcc-access: no MCC credentials on this host — skipped"]

    # Everything the manager account is already linked to, whatever the state.
    linked: dict[str, str] = {}
    try:
        from ads_manager import gaql
        for r in gaql(cl, mcc, "SELECT customer_client_link.client_customer, "
                               "customer_client_link.status FROM customer_client_link"):
            linked[r.customer_client_link.client_customer.split("/")[-1]] = \
                r.customer_client_link.status.name
    except Exception as e:  # noqa: BLE001
        return [f"ads-mcc-access: could not read manager links ({str(e)[:90]})"]

    for cid, slug in sorted(cid_to_slug.items(), key=lambda kv: kv[1]):
        co = _sb("GET", f"/rest/v1/companies?id=eq.{cid}&select=integration_settings",
                 prefer="return=representation") or []
        ints = (co[0].get("integration_settings") or {}) if co else {}
        if isinstance(ints, str):
            try:
                ints = json.loads(ints)
            except json.JSONDecodeError:
                ints = {}
        acct = str(((ints.get("lsa") or {}).get("customer_id") or "")).replace("-", "")
        if not acct:
            continue                      # nothing discovered yet — lsa_detect's job
        state = linked.get(acct)
        if state in ("ACTIVE", "PENDING"):
            continue                      # already invited or already ours
        if dry_run:
            out.append(f"{slug}: [dry-run] would invite MCC onto Ads account {acct}")
            continue
        try:
            svc = cl.get_service("CustomerClientLinkService")
            op = cl.get_type("CustomerClientLinkOperation")
            link = op.create
            link.client_customer = f"customers/{acct}"
            link.status = cl.enums.ManagerLinkStatusEnum.PENDING
            svc.mutate_customer_client_link(customer_id=mcc, operation=op)
            out.append(f"{slug}: MCC invite created on Ads account {acct} "
                       "(ads_link_accept clears it on the nightly sweep)")
        except Exception as e:  # noqa: BLE001 — one bad account never stops the pass
            out.append(f"{slug}: MCC invite FAILED on {acct} — {str(e)[:110]}")
    return out


def ensure_internal_launch_tasks(dry_run: bool, cid_to_slug: dict) -> list[str]:
    """Seed the work that is OURS: a built site we can launch but haven't.

    Every other check in this file asks a CLIENT for something, which is
    exactly why Go Green sat dark from 2026-07-24. We registered
    gogreenrestorationofnc.com ourselves, pointed the nameservers at a
    Cloudflare zone, and never populated it. The client owed us nothing, so no
    ask existed, so no board anywhere showed the domain resolving to nothing
    for two weeks. "Waiting on us" had no representation in the system.

    Fires when a site is BUILT, is NOT live, and we can already act:
      - the domain's nameservers point at Cloudflare (we control DNS), or
      - domain access is granted / credentials provided.

    Deliberately action_type "site_launch", NOT client_input: this must land on
    the ops board and must never become a message to the client. There is
    nothing to ask them for.
    """
    import subprocess
    out: list[str] = []
    BUILT = {"preview_ready", "preview_live", "pushed_staging", "pushed_main"}
    READY_ACCESS = {"granted", "creds_provided", "ns_live", "delegate_granted"}

    rows = _sb("GET", "/rest/v1/marketing_sites"
               "?select=rank_ai_slug,company_id,domain,build_status,apex_live,"
               "domain_access_status", prefer="return=representation") or []
    for r in rows:
        slug = r.get("rank_ai_slug")
        cid = r.get("company_id")
        dom = (r.get("domain") or "").strip()
        if not (slug and cid and dom) or dom.endswith(".invalid"):
            continue
        if r.get("apex_live") is True or r.get("build_status") not in BUILT:
            continue

        # apex_live IS NOT TRUSTWORTHY. PuroClean reads False while
        # purocleaneastlasvegas.com has been serving our site for days, so the
        # flag alone would raise a launch task for a site that is already live.
        # Probe the real thing (the same lesson as the Crew go-live check: the
        # DNS/flag state and what a visitor actually gets are different facts).
        # The marker is /llms.txt, not a phrase on the homepage. "Call Us Now"
        # matched homelyft.net, which is still the CLIENT'S OWN old site — a
        # string match would have flipped apex_live to true on a site we have
        # never launched. Every site we build ships llms.txt; theirs do not.
        # ...and a 200 is not enough either. prorestorationca.com serves a SOFT
        # 404: every path returns 200 with their homepage HTML, which mentions
        # their own domain 151 times, so both the status check and a substring
        # check pass on a site we have never launched. Require the body to be
        # our actual llms.txt: plain text starting with a markdown heading.
        try:
            resp = requests.get(f"https://{dom}/llms.txt", timeout=12,
                                allow_redirects=True)
            body = (resp.text or "").lstrip()
            if (resp.ok and body.startswith("#") and not body.startswith("<")
                    and f"https://{dom}/" in body):
                out.append(f"{slug}: already live at {dom} — apex_live flag is "
                           "stale, not seeding a launch task")
                if not dry_run:
                    _sb("PATCH", "/rest/v1/marketing_sites"
                        f"?rank_ai_slug=eq.{slug}", {"apex_live": True})
                continue
        except Exception:
            pass   # unreachable: fall through, a launch task is the right call

        # THE CLIENT HAS TO HAVE SIGNED OFF. Quality Contracting is
        # creds_provided and built, but Fran sent 17 pages of change requests
        # on 2026-08-05 — "we can launch it" is not "we should". Only seed once
        # the preview ask is actually resolved.
        preview = _sb("GET", "/rest/v1/marketing_action_plan"
                      f"?company_id=eq.{cid}&action_type=eq.client_input"
                      "&title=ilike.*preview*&select=status",
                      prefer="return=representation") or []
        if preview and not any((p.get("status") or "") in ("resolved", "done")
                               for p in preview):
            continue

        why = None
        if str(r.get("domain_access_status") or "") in READY_ACCESS:
            why = f"domain access is {r['domain_access_status']}"
        else:
            # We may already control DNS without any access ever being
            # "granted" — the Go Green case, where we bought the domain.
            try:
                ns = subprocess.run(["dig", "+short", "NS", dom],
                                    capture_output=True, text=True,
                                    timeout=15).stdout.lower()
                if "ns.cloudflare.com" in ns:
                    why = "nameservers already point at our Cloudflare zone"
            except Exception:
                pass
        if not why:
            continue   # genuinely waiting on the client — rank 12 covers it

        if insert_plan_row(
                cid, slug, f"internal-push-live-{slug}",
                title=f"PUSH THE SITE LIVE: {dom} is built and we can launch it",
                rationale=(
                    f"{dom} is built ({r['build_status']}) and NOT live, and we "
                    f"can already act: {why}. This is OURS, not the client's — "
                    "there is nothing to ask them for, so nothing was ever "
                    "surfacing it. INTERNAL: do not message the client about "
                    "this item. Launch checklist: mirror any existing DNS into "
                    "the zone FIRST (an empty zone plus delegated nameservers "
                    "takes their email down), attach the Pages custom domain, "
                    "point apex + www, verify apex AND www return 200 with a "
                    "valid certificate, then confirm MX still resolves."),
                action_type="site_launch", target=f"https://{dom}",
                impact="high", effort="low", dry_run=dry_run):
            out.append(f"{slug}: seeded INTERNAL launch task — {dom} ({why})")
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
            CONNECT_TITLE = ("ASK CLIENT: connect their Google account so we "
                             "can manage the Business Profile, reviews and "
                             "rankings")
            existing = _sb("GET",
                "/rest/v1/marketing_action_plan?company_id=eq.{}"
                "&action_key=eq.google-connect-{}&select=id,title,status"
                .format(cid, slug))
            if existing:
                # keep the wording current on rows seeded before a rewrite
                for r_ in existing:
                    if r_.get("status") == "planned" \
                            and (r_.get("title") or "") != CONNECT_TITLE \
                            and not dry_run:
                        _sb("PATCH", "/rest/v1/marketing_action_plan"
                            f"?id=eq.{r_['id']}", {"title": CONNECT_TITLE})
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
                   "title": CONNECT_TITLE,
                   "target": link,
                   # GBP-connect link rule (Santino 2026-08-03): the ask's
                   # instruction text ALWAYS carries the link — the concierge
                   # compose also hard-enforces it (a connect ask without the
                   # link never passes; MCC got "here's a link" with no link
                   # attached 2026-07-25).
                   "rationale": ("Their listing exists but the account isn't "
                                 "connected. ALWAYS include this exact link in "
                                 "the message and tell them to sign in with "
                                 "the Google account that manages their "
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
    sweep_lines: list[str] = []   # "{slug}: what happened" from every pass
    for fn in (ensure_google_connect_asks, ensure_gbp_first_sync,
               ensure_gbp_manager_access, ensure_ads_mcc_access,
               ensure_baseline_scans, ensure_ads_first_sync,
               ensure_internal_launch_tasks,
               ensure_setup_checklist):
        for ln in fn(dry_run, cid_to_slug):
            print("  " + ln)
            sweep_lines.append(ln)
    # Setup ledger — the overseer: derives per-client setup state, auto-heals
    # GSC/IndexNow on live sites, and returns the us-owed attention list
    # (fed into the digest's "Needs Santino/Claude" sections below).
    # INDEPENDENT try/excepts, not one shared block (DISS 2026-08-04 audit):
    # a single wrapper meant any ensure_ledger raise silently took the
    # auto-build down with it — the site build would just never happen and the
    # only trace was one "(ledger) errored" line. Site builds never wait on the
    # ledger's health.
    ledger_lines: list[str] = []
    try:
        from setup_ledger import ensure_ledger
        ledger_lines += ensure_ledger(dry_run, cid_to_slug)
    except Exception as e:
        ledger_lines.append(f"(ledger) errored: {str(e)[:120]}")
    try:
        from setup_ledger import ensure_auto_site_build
        ledger_lines += ensure_auto_site_build(dry_run, cid_to_slug)
    except Exception as e:
        ledger_lines.append(f"(auto-site-build) errored: {str(e)[:120]}")
    for ln in ledger_lines:
        print("  LEDGER: " + ln)
    sweep_lines += ledger_lines

    # Inbound client email -> Monica's notes (email-blindness fix 2026-08-09:
    # Fran's site feedback sat unread 3 days, Jeff's screenshot got a blind
    # ack, Kenny's customer list got a promise with no retrieval). Same
    # independent try/except as the ledger — a Gmail hiccup must never take
    # the sweep down. Read-only on the mailbox; state in ops_kv.
    try:
        from email_inbox_sync import sync_inbox
        for ln in sync_inbox(dry_run, cid_to_slug):
            print("  EMAIL: " + ln)
            sweep_lines.append(ln)
    except Exception as e:  # noqa: BLE001
        print(f"  EMAIL: inbox sync errored: {str(e)[:120]}")

    # Stage-dwell checker (Santino 2026-08-10): derive every client's website
    # stage EXACTLY like the app's Build Stages board, track dwell time in
    # ops_kv 'stage-history', and route each unmet exit item to the system
    # that already owns it (auto-build asks, ledger domain ask, launch seeder,
    # [DEV] inbox for the imagery pass). Same independent try/except as the
    # ledger and email passes — a checker raise must never take the sweep down.
    try:
        from stage_checker import check_stages
        for ln in check_stages(dry_run, cid_to_slug):
            print("  STAGE: " + ln)
            sweep_lines.append(ln)
    except Exception as e:  # noqa: BLE001
        print(f"  STAGE: stage checker errored: {str(e)[:120]}")

    # Work ledger (fail-open): one 'routine' line item per ACTIVE client per
    # sweep — the nightly checks are documented work even on quiet nights
    # (Santino 2026-08-01: every movement recorded as a line item).
    if not dry_run:
        try:
            from work_log import work_log
            by_slug: dict[str, list[str]] = {}
            for ln in sweep_lines:
                label, _, rest = ln.partition(": ")
                if rest:
                    by_slug.setdefault(label.strip(), []).append(rest.strip())
            for cid, slug in sorted(cid_to_slug.items()):
                try:
                    rec = json.loads((ROOT / "clients" / f"{slug}.json").read_text())
                except Exception:
                    rec = {}
                if rec.get("status") != "active":
                    continue
                healed = by_slug.get(slug, [])
                detail = ("Nightly account review: checked Google connection, "
                          "business-listing sync, rank tracking, ads data, and "
                          "the setup checklist.")
                if healed:
                    detail += (f" {len(healed)} item(s) automatically "
                               "actioned or flagged.")
                else:
                    detail += " Everything current — no fixes needed."
                work_log(cid, "routine", "nightly-sweep", detail,
                         evidence={"slug": slug, "actions": healed[:12]},
                         source="client_ops_sync.py")
        except Exception as e:  # noqa: BLE001 — ledger never blocks the sweep
            print(f"  [work-log] warn: {str(e)[:100]}")

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
        #
        # ensure_auto_site_build joins it too (DISS Restoration 2026-08-04):
        # the auto-build lived ONLY in the once-daily 14:00 UTC ops sync, so a
        # client who signed up at 18:36 got the full bootstrap (client files,
        # geo-grid, tracking number, ledger rows) within 13 minutes and then
        # sat at build_status=pending for ~19 hours with no site — a silent
        # gap nobody was paged about. This job already runs every 2 hours and
        # is the thing that mints the client, so the build belongs here.
        # cap=1: bounds the 2-hourly job to a single render (the daily sync
        # keeps its cap of 4 for backlog catch-up).
        from setup_ledger import ensure_auto_site_build as _autobuild
        from setup_ledger import ensure_ledger as _ledger

        def _autobuild_capped(dry, mapping):
            return _autobuild(dry, mapping, cap=1)
        _autobuild_capped.__name__ = "ensure_auto_site_build"

        for fn in (ensure_gbp_first_sync, ensure_baseline_scans,
                   ensure_ads_first_sync, _ledger, _autobuild_capped):
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
