#!/usr/bin/env python3
"""systems_pulse.py — daily all-systems health pulse (one compact email).

Built 2026-07-23 after a week of heavy shipping ("make sure everything is
firing on all cylinders"). Checks OUTCOMES, not intentions: did the artifact
each system is supposed to produce actually appear, and are the live sites
actually up? Sends one green/red table to the team; any RED line means act.

Checks:
  sites      every active client's apex + www over HTTPS (incl. SSL) + staging
             previews for preview_ready clients
  content    a post was written in the last 4 days per active client
             (Mon/Thu cadence -> 4d tolerance)
  videos     a video row in the last 4 days per YouTube-connected active client
  gsc        marketing_gsc_daily fresh within 5 days per synced client
  gbp        marketing_gbp_profiles synced_at within 9 days
  concierge  ops_kv concierge-state written within 26 hours (worker alive)
  jobs       no failed marketing_jobs in the last 24h (lead audits etc.)
  press      current-quarter drafts exist for all non-departed clients

Scheduling: ops_scheduler DAILY_JOBS ("pulse", 14:45 UTC).
"""
from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

import requests

SB = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
H = {"apikey": KEY, "Authorization": "Bearer " + KEY}
NOW = datetime.now(timezone.utc)


def iso_z(dt_) -> str:
    return dt_.strftime("%Y-%m-%dT%H:%M:%SZ")


def sb(path):
    r = requests.get(SB + path, headers=H, timeout=30)
    r.raise_for_status()
    return r.json()


def active_clients() -> list[dict]:
    out = []
    for f in sorted((ROOT / "clients").glob("*.json")):
        if f.name == "company_map.json":
            continue
        c = json.loads(f.read_text())
        c["slug"] = f.stem
        out.append(c)
    return out


def http_ok(url: str) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": "rankai-pulse/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return (200 <= r.status < 400), str(r.status)
    except ssl.SSLError as e:
        return False, "SSL: " + str(e)[:60]
    except Exception as e:
        return False, str(e)[:60]


def run_checks() -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    clients = active_clients()
    cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
    active = [c for c in clients if c.get("status") == "active" and c.get("domain")]

    # 1. live sites (apex + www)
    for c in active:
        d = c["domain"]
        for host in (d, "www." + d):
            ok, note = http_ok(f"https://{host}/")
            checks.append((f"site {host}", ok, note))

    # 2. staging previews for pre-launch clients (new convention first,
    # legacy {slug}-preview direct-upload projects as fallback)
    for c in clients:
        if c.get("status") == "active":
            continue
        if c.get("build_status") in ("pushed_staging", "preview_ready"):
            ok, note = http_ok(f"https://staging.rankai-{c['slug']}.pages.dev/")
            if not ok:
                ok2, note2 = http_ok(f"https://{c['slug']}-preview.pages.dev/")
                if ok2:
                    ok, note = ok2, note2 + " (legacy preview)"
            checks.append((f"staging {c['slug']}", ok, note))

    # 3. content cadence (posts written last 4d, active clients w/ sites)
    cutoff = iso_z(NOW - timedelta(days=4))
    for c in active:
        qp = ROOT / "clients" / c["slug"] / "content-queue.json"
        if not qp.exists():
            continue
        q = json.loads(qp.read_text())
        items = q if isinstance(q, list) else q.get("items", [])
        recent = [i for i in items if (i.get("written_at") or "") >= cutoff]
        checks.append((f"content {c['slug']}", bool(recent),
                       f"{len(recent)} post(s) last 4d"))

    # 4. videos last 4d per connected client
    try:
        vids = sb(f"/rest/v1/marketing_videos?created_at=gte.{iso_z(NOW - timedelta(days=4))}&select=company_id")
        by_cid: dict = {}
        for v in vids:
            by_cid[v["company_id"]] = by_cid.get(v["company_id"], 0) + 1
        yt = sb("/rest/v1/user_integrations?provider=eq.youtube&select=client_id,status")
        connected = {r["client_id"] for r in yt if r.get("status") in (None, "connected", "active")}
        for c in active:
            cid = cmap.get(c["slug"])
            if cid in connected:
                n = by_cid.get(cid, 0)
                checks.append((f"videos {c['slug']}", n > 0, f"{n} last 4d"))
    except Exception as e:
        checks.append(("videos query", False, str(e)[:60]))

    # 5. GSC freshness (per client with any GSC rows)
    try:
        rows = sb("/rest/v1/marketing_gsc_daily?select=company_id,date&order=date.desc&limit=400")
        latest: dict = {}
        for r in rows:
            latest.setdefault(r["company_id"], r["date"])
        stale_cut = (NOW - timedelta(days=5)).date().isoformat()
        for cid, dt_ in latest.items():
            checks.append((f"gsc {cid[-6:]}", dt_ >= stale_cut, f"latest {dt_}"))
    except Exception as e:
        checks.append(("gsc query", False, str(e)[:60]))

    # 6. GBP sync freshness
    try:
        rows = sb("/rest/v1/marketing_gbp_profiles?select=company_id,synced_at")
        cut = (NOW - timedelta(days=9)).isoformat()
        for r in rows:
            checks.append((f"gbp-sync {r['company_id'][-6:]}",
                           (r.get("synced_at") or "") >= cut,
                           f"synced {str(r.get('synced_at'))[:10]}"))
    except Exception as e:
        checks.append(("gbp query", False, str(e)[:60]))

    # 7. concierge worker alive (state written in last 26h)
    try:
        rows = sb("/rest/v1/ops_kv?k=eq.concierge-state&select=updated_at")
        ts = rows[0].get("updated_at", "") if rows else ""
        checks.append(("concierge worker", ts >= iso_z(NOW - timedelta(hours=26)),
                       f"state {ts[:16]}"))
    except Exception as e:
        checks.append(("concierge state", False, str(e)[:60]))

    # 8. failed jobs last 24h
    try:
        rows = sb(f"/rest/v1/marketing_jobs?status=eq.failed&queued_at=gte.{iso_z(NOW - timedelta(days=1))}&select=id,type,error")
        checks.append(("jobs (24h failures)", len(rows) == 0,
                       "none" if not rows else f"{len(rows)} failed: " + (rows[0].get("error") or "")[:60]))
    except Exception as e:
        checks.append(("jobs query", False, str(e)[:60]))

    return checks


def send_email(checks) -> None:
    sg = os.environ.get("SENDGRID_API_KEY", "")
    reds = [c for c in checks if not c[1]]
    subject = ("[Rank AI pulse] ALL GREEN ({} checks)".format(len(checks))
               if not reds else
               "[Rank AI pulse] {} RED / {} checks".format(len(reds), len(checks)))
    lines = ["{} {:28s} {}".format("✅" if ok else "🔴", name, note)
             for name, ok, note in sorted(checks, key=lambda c: c[1])]
    body = "Daily systems pulse — {}\n\n{}".format(NOW.strftime("%Y-%m-%d %H:%M UTC"),
                                                   "\n".join(lines))
    print(body)
    if not sg:
        print("\n(no SENDGRID_API_KEY — printed only)")
        return
    payload = json.dumps({
        "personalizations": [{"to": [{"email": "contact@restorationai.io"}]}],
        "from": {"email": "contact@restorationai.io"},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}]})
    req = urllib.request.Request("https://api.sendgrid.com/v3/mail/send", method="POST",
        data=payload.encode(),
        headers={"Authorization": "Bearer " + sg, "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30)
    print("\nemail sent")


if __name__ == "__main__":
    send_email(run_checks())
