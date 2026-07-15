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
    def esc(s: str) -> str:
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


# ---------------------------------------------------------------- main
def run(since_override: str | None, dry_run: bool, do_send: bool) -> int:
    run_start = datetime.now(timezone.utc)
    cursor_out = run_start.strftime("%Y-%m-%dT%H:%M:%SZ")
    state = load_state()
    since = since_override or state.get("cursor") or (
        run_start - timedelta(days=DEFAULT_LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cid_to_slug = slug_map()
    print(f"client-ops sync since {since}"
          f"{' [DRY RUN]' if dry_run else ''}")

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
    ap.add_argument("--dry-run", action="store_true",
                    help="classify + print everything; write nothing anywhere")
    ap.add_argument("--since", help="ISO timestamp cursor override (e.g. 2026-07-01)")
    ap.add_argument("--send", action="store_true",
                    help="actually deliver the digest email (default: print it)")
    args = ap.parse_args()

    load_env()
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")):
        print("ERROR: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required.", file=sys.stderr)
        return 1
    return run(args.since, args.dry_run, args.send)


if __name__ == "__main__":
    sys.exit(main())
