#!/usr/bin/env python3
"""
Rank AI — System 4 monthly refresh cron (Layer 1, deterministic).

Loops every LIVE client (status active + apex cut over), runs the Layer-1
refresh scorer (sitemap + page-date extraction + optional GSC index flags),
and emits one aggregated summary so content decay gets caught without anyone
remembering to run the skill.

This is the unattended backstop. The Layer-2 `rank-ai-refresh-recommender`
skill still does the deeper, per-client reasoning on demand — this cron just
surfaces WHICH clients have stale / aging / not-indexed pages each month.

Report channel (v1): SendGrid email to the agency. Railway containers are
ephemeral, so the per-client refresh-candidates.json this writes does not
persist there — the email is the durable output. When the dashboard table
lands (developer spec, Step 3), this can also upsert into Supabase.

Usage:
  python3 scripts/refresh_cron.py                 # all live clients, email if key present
  python3 scripts/refresh_cron.py --dry-run       # score + print, never email
  python3 scripts/refresh_cron.py --max-urls 150  # cap URLs inspected per client

Env (set on the Railway cron service):
  SENDGRID_API_KEY        — to send the summary email (omit -> stdout only)
  REFRESH_REPORT_EMAIL    — recipient (default contact@restorationai.io)
  SENDGRID_FROM           — verified sender (default contact@restorationai.io)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# Reuse the exact Layer-1 scorer — no logic duplicated.
import refresh_scorer as rs  # noqa: E402

DEFAULT_TO = "contact@restorationai.io"
FLAG_LABELS = [("stale_12mo", "Stale (>12mo)"), ("aging", "Aging"), ("not_indexed", "Not indexed")]


def live_clients() -> list[str]:
    """Slugs of clients that are active AND cut over to apex (real live sitemap)."""
    out: list[str] = []
    for f in sorted((ROOT / "clients").glob("*.json")):
        try:
            rec = json.loads(f.read_text())
        except Exception:
            continue
        if rec.get("status") != "active":
            continue
        apex_live = bool(rec.get("cut_over_at") or rec.get("apex_cutover", {}).get("completed_at"))
        if apex_live:
            out.append(f.stem)
    return out


def score_one(slug: str, max_urls: int) -> dict:
    """Run the Layer-1 scorer for one client. Never raises — returns a result row."""
    try:
        c = rs.load_client(slug)
        origin, source = rs.determine_origin(c, None)
        state = rs.score(c, origin=origin, origin_source=source,
                         max_urls=max_urls, include_pattern=None)
        # Persist locally too (harmless; useful when run from a dev box).
        rs.write_atomic(ROOT / "clients" / slug / "refresh-candidates.json", state)
        fc = state.get("flag_counts", {})
        return {
            "slug": slug,
            "ok": True,
            "inspected": state.get("inspected_count", 0),
            "gsc_enabled": state.get("gsc_enabled", False),
            "stale_12mo": fc.get("stale_12mo", 0),
            "aging": fc.get("aging", 0),
            "not_indexed": fc.get("not_indexed", 0),
            "error": None,
        }
    except SystemExit as e:  # scorer uses sys.exit on no-sitemap / bad client
        return {"slug": slug, "ok": False, "error": f"scorer exit: {e.code}",
                "inspected": 0, "stale_12mo": 0, "aging": 0, "not_indexed": 0, "gsc_enabled": False}
    except Exception as e:
        return {"slug": slug, "ok": False, "error": str(e)[:200],
                "inspected": 0, "stale_12mo": 0, "aging": 0, "not_indexed": 0, "gsc_enabled": False}


def render_text(rows: list[dict], when: str) -> str:
    lines = [f"Rank AI — monthly refresh audit ({when})", ""]
    lines.append(f"{'client':28} {'urls':>5} {'stale':>6} {'aging':>6} {'noidx':>6}  gsc")
    lines.append("-" * 64)
    tot = {"inspected": 0, "stale_12mo": 0, "aging": 0, "not_indexed": 0}
    for r in rows:
        if not r["ok"]:
            lines.append(f"{r['slug']:28} ERROR: {r['error']}")
            continue
        lines.append(f"{r['slug']:28} {r['inspected']:>5} {r['stale_12mo']:>6} "
                     f"{r['aging']:>6} {r['not_indexed']:>6}  {'yes' if r['gsc_enabled'] else 'no'}")
        for k in tot:
            tot[k] += r[k]
    lines.append("-" * 64)
    lines.append(f"{'TOTAL':28} {tot['inspected']:>5} {tot['stale_12mo']:>6} "
                 f"{tot['aging']:>6} {tot['not_indexed']:>6}")
    flagged = [r["slug"] for r in rows if r["ok"] and (r["stale_12mo"] or r["not_indexed"])]
    lines += ["", "Action: run `rank-ai-refresh-recommender` for clients with stale / not-indexed pages:"]
    lines.append("  " + (", ".join(flagged) if flagged else "(none — everything fresh)"))
    return "\n".join(lines)


def send_email(subject: str, body: str, dry_run: bool) -> None:
    api_key = os.environ.get("SENDGRID_API_KEY")
    if dry_run or not api_key:
        reason = "dry-run" if dry_run else "no SENDGRID_API_KEY"
        print(f"\n[email skipped: {reason}] — summary above is the report.")
        return
    to_addr = os.environ.get("REFRESH_REPORT_EMAIL", DEFAULT_TO)
    from_addr = os.environ.get("SENDGRID_FROM", DEFAULT_TO)
    payload = {
        "personalizations": [{"to": [{"email": to_addr}]}],
        "from": {"email": from_addr, "name": "Rank AI Refresh Cron"},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
    }
    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"\n[email sent -> {to_addr}] status {resp.status}")
    except Exception as e:
        # Non-fatal: the run succeeded; only delivery failed.
        print(f"\n[email FAILED -> {to_addr}]: {e}  (summary still printed above)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Rank AI System 4 — monthly refresh cron")
    ap.add_argument("--max-urls", type=int, default=200, help="Cap on URLs inspected per client")
    ap.add_argument("--dry-run", action="store_true", help="Score + print, never email")
    args = ap.parse_args()

    when = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    slugs = live_clients()
    print(f"==> Refresh cron: {len(slugs)} live client(s): {', '.join(slugs) or '(none)'}\n")

    rows = [score_one(s, args.max_urls) for s in slugs]
    summary = render_text(rows, when)
    print("\n" + summary)

    flagged = sum(1 for r in rows if r["ok"] and (r["stale_12mo"] or r["not_indexed"]))
    subject = f"Rank AI refresh audit — {len(slugs)} clients, {flagged} need attention ({when})"
    send_email(subject, summary, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
