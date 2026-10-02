#!/usr/bin/env python3
"""
Rank AI — geo-grid MONTH WATCH: did this month's map-rankings pass land?

Santino 2026-10-01 ("add a watcher to the map ranking for the next month"):
after the geogrid overhaul (per-client matrix, home city only, self-healing
centers, implausible-zero guard) the first full monthly pass is November.
This checks it from the outside and emails a plain report, per client:

  scanned    home-city combos (keyword x 6.5/9.5/15) scanned THIS month
  zero       scans this month that found the listing nowhere
  images     latest map images that are missing or do not serve
  visible    the listing-visibility verdict (ops_kv geogrid-visibility:*)

Verdict per client: OK, PARTIAL (some combos still due; the daily lane
finishes them), ZERO (every home grid found nothing: identity/center
problem), BROKEN-IMG, or NOT STARTED.

The pipeline_watchdog geogrid card covers the steady state (from the 4th
of every month); this is the one-month human-readable checkpoint. The
workflow (geogrid-month-watch.yml) runs it on Nov 2, 4 and 8.

CLI:
    python3 scripts/geogrid_month_watch.py            # print the report
    python3 scripts/geogrid_month_watch.py --email    # + email Santino
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import geogrid_coverage as gc  # noqa: E402


def _when(s: dict) -> datetime:
    return datetime.fromisoformat(str(s["scanned_at"]).replace("Z", "+00:00"))


def client_row(slug: str) -> dict:
    cid = gc.company_map().get(slug)
    scans = gc.fetch_scans(cid) if cid else []
    start = gc.month_start()
    month = [s for s in scans if _when(s) >= start]
    latest: dict[tuple, dict] = {}
    for s in month:                                   # newest first
        latest.setdefault(gc.combo_key(s["keyword"], s["city_label"], s["miles"]), s)
    combos = gc.expected_combos(slug)
    home = [c for c in combos if c["home"]]
    done = [latest[c["key"]] for c in home if c["key"] in latest]
    zero = [s for s in done if not s.get("found_points")]
    broken = gc.broken_images(done) if done else []
    vis = gc.visibility(slug)
    if not done and vis.get("visible") is False:
        verdict = "NOT TOP 20"     # scanner refuses to save an all-zero grid
    elif not done:
        verdict = "NOT STARTED"
    elif len(zero) == len(done):
        verdict = "ZERO"
    elif broken:
        verdict = "BROKEN-IMG"
    elif len(done) < len(home):
        verdict = "PARTIAL"
    else:
        verdict = "OK"
    return {"slug": slug, "expected": len(home), "done": len(done),
            "zero": len(zero), "broken": len(broken), "verdict": verdict,
            "visible": vis.get("visible"), "vis_reason": vis.get("reason") or "",
            "spent": round(sum(float(s.get("cost_usd") or 0) for s in month), 2)}


def report() -> tuple[str, str]:
    rows = []
    for slug in sorted(gc.active_roster()):
        try:
            rows.append(client_row(slug))
        except Exception as e:  # noqa: BLE001
            rows.append({"slug": slug, "expected": 0, "done": 0, "zero": 0,
                         "broken": 0, "verdict": f"ERROR {str(e)[:60]}",
                         "visible": None, "vis_reason": "", "spent": 0})
    ok = sum(1 for r in rows if r["verdict"] == "OK")
    bad = [r for r in rows if r["verdict"] not in ("OK", "PARTIAL", "NOT TOP 20")]
    month = gc.month_start().strftime("%B")
    subject = (f"[Rank AI] Map rankings, {month} pass: {ok}/{len(rows)} clients complete"
               + (f", {len(bad)} need a look" if bad else ""))
    lines = [f"{month} map-rankings pass, home city only (6.5 / 9.5 / 15 mi).",
             f"Checked {gc.iso(gc.now())[:16].replace('T', ' ')} UTC.", ""]
    if bad:
        lines.append("NEEDS A LOOK")
        for r in bad:
            lines.append(f"  {r['slug']}: {r['verdict']} ({r['done']}/{r['expected']} "
                         f"scanned, {r['zero']} zero, {r['broken']} broken images)")
        lines.append("")
    lines.append("ALL CLIENTS")
    for r in rows:
        vis = {True: "visible", False: "not in top 20", None: "unjudged"}[r["visible"]]
        lines.append(f"  {r['verdict']:<11} {r['slug']:<44} {r['done']:>2}/{r['expected']:<2} "
                     f"zero {r['zero']}  img-broken {r['broken']}  {vis}  ${r['spent']}")
    partial = [r["slug"] for r in rows if r["verdict"] == "PARTIAL"]
    if partial:
        lines += ["", "PARTIAL clients finish on the daily 10:25 UTC lane; no action "
                  "unless they are still partial on the 8th."]
    unseen = [r["slug"] for r in rows if r["verdict"] == "NOT TOP 20"]
    if unseen:
        lines += ["", "NOT TOP 20 = the listing is not in the top 20 anywhere on its home "
                  "grid, so no map is saved and the app shows the not-visible panel: "
                  + ", ".join(unseen)]
    lines += ["", "ZERO = every home grid found nothing (listing identity or grid center, "
              "not a real ranking). NOT STARTED after the 2nd = the lane did not run "
              "for that client; check the geogrid-scan workflow."]
    return subject, "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--email", action="store_true", help="email the report to Santino")
    a = ap.parse_args()
    subject, body = report()
    print(subject + "\n\n" + body)
    if a.email:
        import requests  # noqa: PLC0415
        run = os.environ.get("RUN_URL")
        r = requests.post("https://api.sendgrid.com/v3/mail/send", timeout=30, headers={
            "Authorization": f"Bearer {os.environ['SENDGRID_API_KEY']}"}, json={
            "personalizations": [{"to": [{"email": "contact@restorationai.io"}],
                                  "subject": subject}],
            "from": {"email": "no-reply@restorationai.io", "name": "Rank AI Bot"},
            "content": [{"type": "text/plain",
                         "value": body + (f"\n\nRun: {run}" if run else "")}]})
        print(f"email: HTTP {r.status_code}")
        r.raise_for_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
