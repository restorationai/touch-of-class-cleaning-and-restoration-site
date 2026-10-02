#!/usr/bin/env python3
"""
Rank AI — geo-grid (local map rankings) scheduler. PER-CLIENT MATRIX.

Santino 2026-10-01 ("why did GitHub cancel it partway through?"): the old
fleet run scanned every client one grid after another (10-20 min per grid in
task mode), so a 1st-of-month run needed far more than its 330-minute job and
was killed partway, every month, and the daily cron ALSO ran a full fleet on
the 1st, colliding with it. The house law (09-19) is per-client fan-out, so:

  plan job    geogrid_cron.py --list --mode due     -> JSON roster of slugs
  scan jobs   geogrid_cron.py --slug X --mode due   -> one GitHub job per
              client, own timeout, own concurrency lane, max-parallel capped

WHAT IS DUE (geogrid_coverage.due_combos): every configured (keyword x city
x radius) with no scan this calendar month and none in the last 7 days. On
the 1st that is everything (the monthly run). Any later day it is only what
the month has not covered yet, so a killed or failed job finishes itself on
the next daily pass at no extra cost; there is no separate "resume" path.
A combo that fails 3 times in a month stops retrying (spend cap) and the
watchdog's coverage card names it.

Inside one client every grid is posted to DataForSEO at once and collected
together (geogrid_store.scan_many_and_store), so a 15-grid client takes about
as long as one grid.

Modes:
  due        the scheduled lane (monthly coverage + daily catch-up)
  ondemand   a single-slug dispatch (app Refresh, bootstrap): every combo not
             scanned in the last 20h, limited to one per client per month
             (GEOGRID_FORCE=1 overrides)

Usage:
  python3 scripts/geogrid_cron.py --list --mode due            # roster JSON
  python3 scripts/geogrid_cron.py --slug narestco --mode due   # one client
  python3 scripts/geogrid_cron.py --slug narestco --dry-run
  python3 scripts/geogrid_cron.py --mode due                   # local: all, sequential
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import geogrid_coverage as gc  # noqa: E402

COST_PER_SCAN = 0.102          # task mode, 13x13 (measured 09-06 / 10-01)
DEFAULT_DAILY_BUDGET = 40.0    # USD per scheduled pass; the rest rolls to tomorrow


def _log(msg: str) -> None:
    print(msg, flush=True)


def ondemand_combos(slug: str, scans: list[dict]) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=20)
    done = {gc.combo_key(s["keyword"], s["city_label"], s["miles"]) for s in scans
            if datetime.fromisoformat(str(s["scanned_at"]).replace("Z", "+00:00")) >= cutoff}
    return [c for c in gc.expected_combos(slug) if c["key"] not in done]


def ondemand_refused(slug: str, scans: list[dict]) -> str | None:
    """ON-DEMAND QUOTA (Santino 2026-09-06): one full rescan per client per
    calendar month on top of the scheduled pass. A client whose scans this
    month all come from ONE day (the scheduled pass or its first baseline)
    still has its rescan available."""
    if os.environ.get("GEOGRID_FORCE"):
        return None
    ms = gc.month_start()
    month = [s for s in scans
             if datetime.fromisoformat(str(s["scanned_at"]).replace("Z", "+00:00")) >= ms]
    days = {str(s["scanned_at"])[:10] for s in month}
    if len(month) > 5 and len(days) >= 2:
        return (f"monthly on-demand rescan already used ({len(month)} scans across "
                f"{len(days)} day(s) this month); GEOGRID_FORCE=1 overrides")
    return None


def plan(mode: str, slug: str | None, budget: float) -> list[str]:
    """The matrix roster: clients with work to do, cheapest-to-complete
    first under the per-pass budget (never-scanned clients always first)."""
    slugs = [slug] if slug else gc.active_roster()
    cmap = gc.company_map()
    rows = []
    for s in slugs:
        if s in gc.SKIP_SLUGS or s not in cmap:
            _log(f"  [{s}] skip (dead/on-hold or unmapped)")
            continue
        try:
            scans = gc.fetch_scans(cmap[s])
        except Exception as e:  # noqa: BLE001 — fail closed per client
            _log(f"  [{s}] skip this pass: scan history unreadable ({str(e)[:80]})")
            continue
        if mode == "ondemand":
            why = ondemand_refused(s, scans)
            if why:
                _log(f"  [{s}] REFUSED: {why}")
                continue
            n = len(ondemand_combos(s, scans))
        else:
            n = len(gc.due_combos(s, scans))
        if n:
            rows.append((0 if not scans else 1, n, s))
            _log(f"  [{s}] {n} scan(s) due")
    rows.sort()
    out, spend = [], 0.0
    for first, n, s in rows:
        cost = n * COST_PER_SCAN
        if out and not slug and spend + cost > budget:
            _log(f"  [{s}] deferred to the next pass (budget ${budget:.0f}, "
                 f"${spend:.2f} planned)")
            continue
        out.append(s)
        spend += cost
    _log(f"plan: {len(out)} client(s), ~${spend:.2f} estimated")
    return out


def run_client(slug: str, mode: str, dry_run: bool = False,
               max_scans: int | None = None) -> dict:
    cmap = gc.company_map()
    cid = cmap.get(slug)
    if not cid:
        _log(f"  [{slug}] SKIP: no company_id mapping")
        return {"slug": slug, "scans": 0, "fails": 0, "cost": 0.0}
    kws, cities = gc.load_config(slug)
    if not kws or not cities:
        _log(f"  [{slug}] SKIP: no geogrid-keywords.txt / geogrid-cities.json")
        return {"slug": slug, "scans": 0, "fails": 0, "cost": 0.0}
    if not dry_run:
        # the app reads configured coverage from this mirror ("not scanned
        # yet" instead of silently omitting a keyword)
        _log(f"  [{slug}] app config mirror: {'ok' if gc.publish_config(slug) else 'FAILED'}")
    scans = gc.fetch_scans(cid)
    if mode == "ondemand":
        why = ondemand_refused(slug, scans)
        if why:
            _log(f"  [{slug}] REFUSED: {why}")
            return {"slug": slug, "scans": 0, "fails": 0, "cost": 0.0}
        combos = ondemand_combos(slug, scans)
    else:
        combos = gc.due_combos(slug, scans)
    if max_scans is not None:
        combos = combos[:max_scans]
    _log(f"  [{slug}] {len(kws)} keyword(s) x {len(cities)} city(ies) = "
         f"{len(gc.expected_combos(slug))} configured; {len(combos)} to scan now "
         f"(~${len(combos) * COST_PER_SCAN:.2f})")
    if dry_run or not combos:
        for c in combos:
            _log(f"      WOULD scan: '{c['keyword']}' @ {c['label']} ({c['miles']}mi)")
        return {"slug": slug, "scans": 0, "fails": 0, "cost": 0.0}

    from geogrid_store import sb_client, scan_many_and_store
    sb = sb_client()
    tally = {"scans": 0, "fails": 0, "cost": 0.0, "systemic": 0}

    def _on(res):
        c = res["combo"]
        if res["row"]:
            r = res["row"]
            tally["scans"] += 1
            tally["cost"] += float(r.get("cost_usd") or 0.0)
            _log(f"      ok: '{c['keyword']}' @ {c['label']} {c['miles']}mi | "
                 f"avg={r.get('avg_rank')} top3={r.get('pct_in_top3')}% "
                 f"found={r.get('found_points')}/{r.get('total_points')} "
                 f"img={'yes' if r.get('image_url') else 'NO'}")
        else:
            tally["fails"] += 1
            if not str(res["error"]).startswith(("implausible", "listing not visible")):
                tally["systemic"] += 1      # DataForSEO/storage, not identity
            gc.record_failure(slug, c["key"], res["error"])
            _log(f"      FAIL: '{c['keyword']}' @ {c['label']} {c['miles']}mi: "
                 f"{str(res['error'])[:220]}")

    # VISIBILITY GATE (10-01: Heritage, Veterans, Dry Bros, Katofsky stored
    # 15/15/15/6 all-red maps). The home grids go first; if the listing is
    # found nowhere on its own home grid, every other grid would be red too,
    # so the rest is skipped and the app shows "profile not verified/visible
    # yet" instead. A client already judged invisible with no home grid due
    # (failure cap reached) is skipped outright.
    home = [c for c in combos if c.get("home")]
    rest = [c for c in combos if not c.get("home")]
    if not home and gc.visibility(slug).get("visible") is False:
        _log(f"  [{slug}] SKIP: listing judged not visible on its home grid "
             f"({gc.visibility(slug).get('reason', '')[:120]})")
        return {"slug": slug, **tally}

    def _home_verdict(results: list[dict]) -> None:
        if any(r["row"] for r in results):
            gc.set_visibility(slug, True)
            return
        errs = [str(r["error"] or "") for r in results]
        if errs and all(e.startswith(("listing not visible", "implausible")) for e in errs):
            gc.set_visibility(slug, False, errs[0])
            gc.publish_config(slug)
            raise _Invisible(errs[0])

    batches = ([home] if home else []) + [rest[i:i + 40] for i in range(0, len(rest), 40)]
    first_is_home = bool(home)
    chunk = int(os.environ.get("GEOGRID_CHUNK") or 40)
    flat = []
    for b in batches:   # keep the home batch whole; split anything oversized
        flat += [b[i:i + chunk] for i in range(0, len(b), chunk)] if b is not home else [b]
    for i, part in enumerate(flat):
        is_home = first_is_home and i == 0
        try:
            outcome = scan_many_and_store(sb, slug, part, on_result=_on)
        except Exception as e:  # noqa: BLE001 — e.g. no business identity
            for c in part:
                tally["fails"] += 1
                tally["systemic"] += 1
                gc.record_failure(slug, c["key"], str(e))
            _log(f"  [{slug}] batch FAILED before scanning: {str(e)[:220]}")
            continue
        if is_home:
            try:
                _home_verdict(outcome)
            except _Invisible as e:
                _log(f"  [{slug}] listing NOT VISIBLE on its home grid; skipping "
                     f"{len(combos) - len(part)} other grid(s): {str(e)[:160]}")
                break
    _log(f"  [{slug}] done: {tally['scans']} stored, {tally['fails']} failed "
         f"({tally['systemic']} systemic), ${tally['cost']:.2f}")
    return {"slug": slug, **tally}


class _Invisible(Exception):
    pass


def main() -> int:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser(description="Rank AI geo-grid scheduler (per-client)")
    ap.add_argument("--slug", help="One client")
    ap.add_argument("--mode", choices=["due", "ondemand"], default=None,
                    help="due = scheduled coverage lane; ondemand = single-slug "
                         "refresh (default: ondemand with --slug, else due)")
    ap.add_argument("--list", action="store_true",
                    help="Print the matrix roster (slugs=<json>) and exit")
    ap.add_argument("--budget", type=float,
                    default=float(os.environ.get("GEOGRID_DAILY_BUDGET") or DEFAULT_DAILY_BUDGET))
    ap.add_argument("--max-scans", type=int, help="Cap grids for this client run")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--baseline-only", action="store_true",
                    help="(legacy flag) same as --mode due")
    a = ap.parse_args()
    mode = a.mode or ("ondemand" if a.slug and not a.baseline_only else "due")

    if a.list:
        slugs = plan(mode, a.slug, a.budget)
        line = f"slugs={json.dumps(slugs)}"
        print(line)
        gh_out = os.environ.get("GITHUB_OUTPUT")
        if gh_out:
            with open(gh_out, "a") as f:
                f.write(line + "\n")
                f.write(f"mode={mode}\n")
        return 0

    if a.slug:
        r = run_client(a.slug, mode, a.dry_run, a.max_scans)
        # Per-combo failures are recorded in ops_kv and named on the
        # watchdog's coverage card. The job itself fails only when nothing
        # could be stored for a SYSTEMIC reason (DataForSEO/R2/Supabase), so
        # a red run means "the scanner is broken", never "one listing's
        # identity needs a human".
        return 1 if (r.get("systemic") and not r["scans"]) else 0

    # local convenience: the whole due roster, one client after another
    total = 0.0
    for s in plan(mode, None, a.budget):
        total += run_client(s, mode, a.dry_run)["cost"]
    _log(f"\nDone. DataForSEO spend: ${total:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
