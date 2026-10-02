#!/usr/bin/env python3
"""area_remove.py — take a service area off a client's website for good.

Santino 2026-10-02 (Shana/Angie, All Pro + ProRestoration): "take East Niles
off" was done by hand once per site, only on one of the two sites, and an
automated job put it back. This is the one repeatable path:

  1. plan-input: drop the city from service_areas, record it in
     client_removed_areas (who/when/why)
  2. never-list in the DB: companies.integration_settings.service_area_excluded
     (the Marketing tab list; gbp_parity honors it on the Google profile too)
  3. delete the area page + every city x service page
  4. scrub internal links to the removed pages from all content frontmatter
     and llms.txt
  5. _redirects: drop rules that pointed INTO the removed area, add static
     301s (area -> /service-areas/, area/service -> /services/{service}/)
     at the TOP of the file (static rules must precede dynamic ones)
  6. re-plan, and add client pins so the nightly regression watch fails
     loudly if the city ever reappears

    python3 scripts/area_remove.py --slug prorestoration --city "East Niles" \
        --city Woody --city Tarina --by client --why "Bakersfield neighborhood"
    (add --dry-run to preview)

Commit + deploy are left to the caller.
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


def area_slug(city: str, state: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", f"{city} {state}".lower()).strip("-")


def _ckey(c: str) -> str:
    return re.sub(r"\s+", " ", c.strip().lower())


def remove(slug: str, cities: list[str], by: str, why: str, dry: bool) -> list[str]:
    log: list[str] = []
    pi_p = ROOT / "clients" / slug / "plan-input.json"
    pi = json.loads(pi_p.read_text())
    site = ROOT / "sites" / slug
    content = site / "src" / "content"
    state = next((a.get("state") for a in pi.get("service_areas") or [] if a.get("state")), "")
    now = datetime.now(timezone.utc).isoformat()
    targets = [(c, state, area_slug(c, state)) for c in cities]
    keys = {_ckey(c) for c in cities}

    # 1 plan-input
    before = len(pi.get("service_areas") or [])
    pi["service_areas"] = [a for a in pi.get("service_areas") or []
                           if _ckey(a.get("city", "")) not in keys]
    rem = pi.setdefault("client_removed_areas", [])
    have = {_ckey(r.get("city", "")) for r in rem}
    for c, st, a in targets:
        if _ckey(c) not in have:
            rem.append({"city": c, "state": st, "slug": a, "removed_at": now[:10],
                        "requested_by": by, "why": why})
    log.append(f"plan-input: {before} -> {len(pi['service_areas'])} areas")

    # 3 pages
    removed_pages: list[tuple[str, str]] = []   # (area_slug, service_slug or "")
    for c, st, a in targets:
        p = content / "serviceAreas" / f"{a}.md"
        if p.exists():
            removed_pages.append((a, ""))
            if not dry:
                p.unlink()
        for lp in sorted((content / "locations").glob(f"{a}__*.md")):
            removed_pages.append((a, lp.stem.split("__", 1)[1]))
            if not dry:
                lp.unlink()
    log.append(f"pages deleted: {len(removed_pages)}")

    # 4 internal links + llms.txt
    link_re = re.compile(r'"/service-areas/(%s)/[^"]*",?\s*' % "|".join(re.escape(a) for _, _, a in targets))
    scrubbed = 0
    for md in content.rglob("*.md"):
        raw = md.read_text()
        if raw.startswith("---"):
            end = raw.find("\n---", 3)
            fm, body = raw[:end], raw[end:]
            new = link_re.sub("", fm).replace(", ]", "]")
            if new != fm:
                scrubbed += 1
                if not dry:
                    md.write_text(new + body)
    llms = site / "public" / "llms.txt"
    if llms.exists():
        lines = llms.read_text().splitlines()
        keep = [ln for ln in lines if not any(f"/service-areas/{a}/" in ln for _, _, a in targets)]
        if len(keep) != len(lines) and not dry:
            llms.write_text("\n".join(keep) + "\n")
        log.append(f"llms.txt: {len(lines) - len(keep)} line(s) removed")
    log.append(f"internal links scrubbed in {scrubbed} file(s)")

    # 5 redirects
    rd = site / "public" / "_redirects"
    rules = rd.read_text().splitlines() if rd.exists() else []
    srcs = tuple(f"/service-areas/{a}" for _, _, a in targets)
    kept = [r for r in rules if not r.split(" ", 1)[0].startswith(srcs)]
    services_dir = content / "services"
    new_rules: list[str] = []
    for _, _, a in targets:
        for src in (f"/service-areas/{a}", f"/service-areas/{a}/"):
            new_rules.append(f"{src} /service-areas/ 301")
        for (aa, svc) in removed_pages:
            if aa != a or not svc:
                continue
            dest = f"/services/{svc}/" if (services_dir / f"{svc}.md").exists() else "/services/"
            for src in (f"/service-areas/{a}/{svc}", f"/service-areas/{a}/{svc}/"):
                new_rules.append(f"{src} {dest} 301")
    out = new_rules + kept
    if not dry:
        rd.write_text("\n".join(out) + "\n")
    log.append(f"_redirects: {len(rules) - len(kept)} stale rule(s) dropped, {len(new_rules)} static 301s added")

    # 2 DB never-list (merge, never clobber)
    try:
        from client_ops_sync import _sb
        cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
        cid = cmap.get(slug)
        if cid:
            row = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}&select=integration_settings") or [{}])[0]
            cur = list(((row.get("integration_settings") or {}).get("service_area_excluded")) or [])
            ck = {_ckey(r.get("city", "")) for r in cur}
            add = [{"city": c, "state": st, "at": now, "by": by, "why": why}
                   for c, st, _ in targets if _ckey(c) not in ck]
            if add and not dry:
                # re-read right before write to keep the window tiny
                row2 = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}&select=integration_settings") or [{}])[0]
                ints = row2.get("integration_settings") or {}
                ints["service_area_excluded"] = cur + add
                _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}", {"integration_settings": ints})
            log.append(f"DB never-list: +{len(add)}")
    except Exception as e:  # noqa: BLE001
        log.append(f"DB never-list skipped: {str(e)[:100]}")

    if not dry:
        pi_p.write_text(json.dumps(pi, indent=2) + "\n")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "plan_site.py"),
                        "generate", "--slug", slug], cwd=ROOT, capture_output=True)
        # 6 pins
        pins_p = ROOT / "clients" / slug / "client-pins.json"
        pins = json.loads(pins_p.read_text()) if pins_p.exists() else {"pins": []}
        ids = {p.get("id") for p in pins.get("pins", [])}
        for c, st, a in targets:
            pid = f"{a}-removed"
            if pid not in ids:
                pins["pins"].append({"id": pid, "request": f"{by} {now[:10]}: {c} removed ({why})",
                                     "url": "/service-areas/", "forbid": [c]})
            if f"{a}-redirect" not in ids:
                pins["pins"].append({"id": f"{a}-redirect", "request": f"{c} page forwards to the service areas page",
                                     "url": f"/service-areas/{a}/", "status": 301,
                                     "location": "/service-areas/"})
        pins_p.write_text(json.dumps(pins, indent=2) + "\n")
        log.append("plan regenerated, pins written")
    return log


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--city", action="append", required=True)
    ap.add_argument("--by", default="client")
    ap.add_argument("--why", default="client asked to remove it")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    for line in remove(a.slug, a.city, a.by, a.why, a.dry_run):
        print("  " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
