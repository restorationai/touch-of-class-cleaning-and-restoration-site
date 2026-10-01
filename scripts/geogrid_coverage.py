#!/usr/bin/env python3
"""
Rank AI — geo-grid COVERAGE: the one definition of what a client's map
rankings should contain, and how far reality is from it.

Santino 2026-10-01 ("feels like the system is broken"): radii never showed,
configured keywords/cities were silently missing, and "latest" maps were
two months old, all with nothing alerting. Every consumer now asks this
module the same question instead of re-deriving it:

  - geogrid_cron --list   which clients have due work (the matrix roster)
  - geogrid_cron --slug   which combos to scan for one client
  - pipeline_watchdog     coverage / staleness / image-health cards
  - the app               via the published config JSON (publish_config)

A COMBO is (keyword, city label, miles). The config files in
clients/{slug}/ stay the single source of truth:
    geogrid-keywords.txt   one keyword per line
    geogrid-cities.json    [{"label","lat","lng","miles_list"?}, ...]
The FIRST city is the home city and always scans 6.5 / 9.5 / 15 (plus any
extra radii it lists); every other city scans its miles_list or 9.5.

CLI:
    python3 scripts/geogrid_coverage.py                 # audit table, 35d window
    python3 scripts/geogrid_coverage.py --heads         # + HEAD every latest image
    python3 scripts/geogrid_coverage.py --json out.json # machine-readable
    python3 scripts/geogrid_coverage.py --publish-config  # app config JSONs
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# Dead / on-hold clients never get scanned or audited (MCC + Mold Solutionz
# dead, TDI on hold, Santino 10-01).
SKIP_SLUGS = {"mcc-restoration", "mold-solutionz-24-7-llc", "tdi-builders"}
INACTIVE = {"paused", "cancelled", "canceled", "churned", "inactive",
            "archived", "suspended"}
HOME_MILES = (6.5, 9.5, 15.0)
SECONDARY_MILES = (9.5,)
STALE_DAYS = 35            # coverage window: monthly cadence + slack
RESCAN_GAP_DAYS = 7        # never rescan a combo scanned in the last week
MAX_FAILS_PER_MONTH = 3    # a combo that failed this often waits for a human


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(d: datetime) -> str:
    # 'Z' form: '+00:00' in a query string decodes to a space and 400s
    return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def month_start(d: datetime | None = None) -> datetime:
    d = d or now()
    return d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def norm_label(s) -> str:
    return " ".join(str(s or "").split())


def combo_key(keyword: str, label: str, miles) -> tuple:
    return (" ".join(str(keyword or "").lower().split()),
            norm_label(label).lower(), round(float(miles or 0), 2))


def company_map() -> dict:
    try:
        return json.loads((ROOT / "clients" / "company_map.json").read_text())
    except Exception:  # noqa: BLE001
        return {}


def load_config(slug: str) -> tuple[list[str], list[dict]]:
    kw_f = ROOT / "clients" / slug / "geogrid-keywords.txt"
    ct_f = ROOT / "clients" / slug / "geogrid-cities.json"
    kws = [" ".join(ln.split()) for ln in kw_f.read_text().splitlines()
           if ln.strip()] if kw_f.exists() else []
    kws = list(dict.fromkeys(kws))
    cities = json.loads(ct_f.read_text()) if ct_f.exists() else []
    out = []
    for c in cities:
        c = dict(c)
        c["label"] = norm_label(c.get("label"))
        out.append(c)
    return kws, out


def radii_for(index: int, city: dict) -> list[float]:
    listed = [float(m) for m in (city.get("miles_list") or [])]
    if index == 0:
        return sorted(set(HOME_MILES) | set(listed))
    return sorted(set(listed or SECONDARY_MILES))


def expected_combos(slug: str) -> list[dict]:
    kws, cities = load_config(slug)
    return [{"keyword": kw, "city": c, "label": c["label"], "miles": m,
             "key": combo_key(kw, c["label"], m)}
            for kw in kws for i, c in enumerate(cities) for m in radii_for(i, c)]


# ---------------------------------------------------------------------------
# Supabase reads (REST, service role)
# ---------------------------------------------------------------------------

def _sb_get(path: str) -> list:
    import requests
    u = os.environ["SUPABASE_URL"].rstrip("/")
    k = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    out, off = [], 0
    while True:
        r = requests.get(f"{u}{path}", timeout=60, headers={
            "apikey": k, "Authorization": f"Bearer {k}",
            "Range-Unit": "items", "Range": f"{off}-{off + 999}"})
        r.raise_for_status()
        rows = r.json() or []
        out += rows
        if len(rows) < 1000:
            return out
        off += 1000


def statuses(ids: list[str]) -> dict:
    if not ids:
        return {}
    rows = _sb_get("/rest/v1/companies?select=id,status,name&id=in.("
                   + ",".join(ids) + ")")
    return {r["id"]: r for r in rows}


def active_roster(include_unconfigured: bool = False) -> list[str]:
    """Slugs that should have map rankings: mapped, not skipped, company row
    present and not paused/cancelled, and (unless asked) configured."""
    cmap = company_map()
    st = statuses(list(cmap.values()))
    out = []
    for slug, cid in cmap.items():
        if slug in SKIP_SLUGS or cid not in st:
            continue
        if str(st[cid].get("status") or "").strip().lower() in INACTIVE:
            continue
        kws, cities = load_config(slug)
        if (kws and cities) or include_unconfigured:
            out.append(slug)
    return out


def fetch_scans(company_id: str, since: datetime | None = None) -> list[dict]:
    q = (f"/rest/v1/marketing_geogrid_scans?company_id=eq.{company_id}"
         "&select=id,keyword,city_label,miles,scanned_at,image_url,"
         "found_points,total_points,cost_usd&order=scanned_at.desc")
    if since:
        q += f"&scanned_at=gte.{iso(since)}"
    return _sb_get(q)


def failures(slug: str) -> dict:
    """{combo_key_str: count} of failed attempts this month (ops_kv)."""
    k = f"geogrid-failures:{slug}:{now().strftime('%Y-%m')}"
    try:
        rows = _sb_get(f"/rest/v1/ops_kv?k=eq.{k}&select=v")
        return (rows[0].get("v") or {}) if rows else {}
    except Exception:  # noqa: BLE001
        return {}


def record_failure(slug: str, key: tuple, err: str) -> None:
    import requests
    k = f"geogrid-failures:{slug}:{now().strftime('%Y-%m')}"
    v = failures(slug)
    ks = "|".join(str(x) for x in key)
    cur = v.get(ks) or {}
    v[ks] = {"count": int(cur.get("count") or 0) + 1, "last": iso(now()),
             "error": str(err)[:200]}
    try:
        u = os.environ["SUPABASE_URL"].rstrip("/")
        sk = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        requests.post(f"{u}/rest/v1/ops_kv?on_conflict=k", json={"k": k, "v": v},
                      timeout=30, headers={
                          "apikey": sk, "Authorization": f"Bearer {sk}",
                          "Content-Type": "application/json",
                          "Prefer": "resolution=merge-duplicates"})
    except Exception:  # noqa: BLE001 — bookkeeping never kills a scan
        pass


# ---------------------------------------------------------------------------
# Coverage + due work
# ---------------------------------------------------------------------------

def coverage(slug: str, scans: list[dict] | None = None,
             window_days: int = STALE_DAYS) -> dict:
    cid = company_map().get(slug)
    combos = expected_combos(slug)
    if scans is None:
        scans = fetch_scans(cid) if cid else []
    latest: dict[tuple, dict] = {}
    for s in scans:                       # newest first
        latest.setdefault(combo_key(s["keyword"], s["city_label"], s["miles"]), s)
    cutoff = now() - timedelta(days=window_days)
    present, missing, stale, zero, no_image = [], [], [], [], []
    for c in combos:
        s = latest.get(c["key"])
        if not s:
            missing.append(c)
            continue
        when = datetime.fromisoformat(str(s["scanned_at"]).replace("Z", "+00:00"))
        if when < cutoff:
            stale.append({**c, "last": str(s["scanned_at"])[:10]})
            continue
        present.append({**c, "scan": s})
        if not s.get("found_points"):
            zero.append({**c, "scan": s})
        if not s.get("image_url"):
            no_image.append({**c, "scan": s})
    return {"slug": slug, "company_id": cid, "expected": len(combos),
            "present": present, "missing": missing, "stale": stale,
            "zero": zero, "no_image": no_image, "latest": latest}


def due_combos(slug: str, scans: list[dict] | None = None) -> list[dict]:
    """Combos with no scan this calendar month AND none in the last
    RESCAN_GAP_DAYS, minus combos that already failed MAX_FAILS_PER_MONTH
    times this month. On the 1st that is everything (the monthly fleet
    run); on any later day it is only what the month has not covered yet,
    so a killed or partial run finishes itself on the next daily pass."""
    cid = company_map().get(slug)
    if scans is None:
        scans = fetch_scans(cid) if cid else []
    done_month, done_gap = set(), set()
    for s in scans:
        when = datetime.fromisoformat(str(s["scanned_at"]).replace("Z", "+00:00"))
        k = combo_key(s["keyword"], s["city_label"], s["miles"])
        if when >= month_start():
            done_month.add(k)
        if when >= now() - timedelta(days=RESCAN_GAP_DAYS):
            done_gap.add(k)
    fails = failures(slug)
    out = []
    for c in expected_combos(slug):
        if c["key"] in done_month or c["key"] in done_gap:
            continue
        ks = "|".join(str(x) for x in c["key"])
        if int((fails.get(ks) or {}).get("count") or 0) >= MAX_FAILS_PER_MONTH:
            continue
        out.append(c)
    return out


# ---------------------------------------------------------------------------
# Image health
# ---------------------------------------------------------------------------

def head_ok(url: str | None) -> bool:
    import requests
    if not url:
        return False
    try:
        r = requests.head(url, timeout=20, allow_redirects=True)
        return r.status_code == 200 and "image" in r.headers.get("content-type", "")
    except Exception:  # noqa: BLE001
        return False


def broken_images(scans: list[dict]) -> list[dict]:
    with cf.ThreadPoolExecutor(16) as ex:
        oks = list(ex.map(lambda s: head_ok(s.get("image_url")), scans))
    return [s for s, ok in zip(scans, oks) if not ok]


# ---------------------------------------------------------------------------
# App config mirror (display copy; the repo files stay canonical)
# ---------------------------------------------------------------------------

def config_doc(slug: str) -> dict:
    kws, cities = load_config(slug)
    return {
        "company_id": company_map().get(slug), "slug": slug,
        "updated_at": iso(now()), "stale_days": STALE_DAYS,
        "keywords": kws,
        "cities": [{"label": c["label"], "home": i == 0,
                    "miles_list": radii_for(i, c)} for i, c in enumerate(cities)],
        "cadence": "monthly (rescans run on the 1st; missed combos retry daily)",
    }


def publish_config(slug: str) -> bool:
    from geogrid_store import FALLBACK_BUCKET, r2_put
    doc = config_doc(slug)
    if not doc["company_id"]:
        return False
    return r2_put(FALLBACK_BUCKET, f"config/{doc['company_id']}.json",
                  json.dumps(doc, indent=1).encode(), "application/json")


def dispatch_scan(slug: str, mode: str = "due") -> bool:
    """Queue one client's geogrid job (geogrid-scan.yml) instead of scanning
    inline: the job runs in the client's own concurrency lane with its own
    timeout. mode=due never re-buys a combo already scanned this month."""
    import requests
    tok = (os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or os.environ.get("GH_PAT")
           or os.environ.get("GITHUB_TOKEN") or "")
    if not tok:
        return False
    try:
        r = requests.post(
            "https://api.github.com/repos/restorationai/Rank-AI-Pipeline/actions/"
            "workflows/geogrid-scan.yml/dispatches",
            json={"ref": "main", "inputs": {"slug": slug, "mode": mode}},
            headers={"Authorization": f"token {tok}",
                     "Accept": "application/vnd.github+json"}, timeout=30)
        return r.status_code == 204
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# CLI audit
# ---------------------------------------------------------------------------

def main() -> int:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser(description="Geo-grid coverage audit")
    ap.add_argument("--slug")
    ap.add_argument("--heads", action="store_true", help="HEAD every latest image")
    ap.add_argument("--json", help="write the audit to this path")
    ap.add_argument("--publish-config", action="store_true")
    a = ap.parse_args()
    slugs = [a.slug] if a.slug else active_roster(include_unconfigured=True)
    report = []
    tot_e = tot_p = 0
    for slug in slugs:
        if a.publish_config:
            print(f"  config {slug}: {'ok' if publish_config(slug) else 'FAILED'}")
            continue
        cov = coverage(slug)
        bad = broken_images([c["scan"] for c in cov["present"]]) if a.heads else []
        due = due_combos(slug)
        tot_e += cov["expected"]
        tot_p += len(cov["present"])
        row = {"slug": slug, "expected": cov["expected"],
               "present": len(cov["present"]), "missing": len(cov["missing"]),
               "stale": len(cov["stale"]), "zero_found": len(cov["zero"]),
               "no_image": len(cov["no_image"]), "broken_images": len(bad),
               "due_now": len(due),
               "missing_list": [f"{c['keyword']} @ {c['label']} {c['miles']}mi"
                                for c in cov["missing"] + cov["stale"]]}
        report.append(row)
        print(f"{slug:48} {row['present']:3}/{row['expected']:<3} "
              f"missing={row['missing']:3} stale={row['stale']:3} "
              f"zero={row['zero_found']:3} noimg={row['no_image']} "
              f"broken={row['broken_images']} due={row['due_now']}")
    if not a.publish_config:
        print(f"\nTOTAL {tot_p}/{tot_e} combos current (<= {STALE_DAYS}d)")
    if a.json:
        Path(a.json).write_text(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
