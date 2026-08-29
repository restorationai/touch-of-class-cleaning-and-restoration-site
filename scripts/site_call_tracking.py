#!/usr/bin/env python3
"""Wire sitewide call-tracking (Dynamic Number Insertion) into a client site.

Santino 2026-08-24: every website shows the client's TRACKING number to
humans while the HTML source, JSON-LD schema, and anything crawlers read
keep the canonical NAP number — so citations stay consistent. The GBP side
is already standard (gbp.py set-phone: tracking primary, real number in
additionalPhones).

What this does per slug:
  1. sites/{slug}/src/lib/brand.ts   — insert (or update) trackingPhone +
     trackingPhoneRaw after phoneRaw.
  2. sites/{slug}/src/layouts/BaseLayout.astro — insert the DNI swap
     script before </body> (idempotent; skips if already present). The
     script swaps visible text + tel: links after DOM parse and never
     touches <script>/<style> nodes, so JSON-LD schema keeps real NAP.
  3. npm build as a safety gate.

The tracking number comes from company_phone_setup.agent_phone_1 (the AI
dispatcher line — already answered + recorded, so site calls land in the
app's call log) unless --number overrides.

Usage:
  set -a && source .env && set +a
  python3 scripts/site_call_tracking.py --slug narestco            # one site
  python3 scripts/site_call_tracking.py --slug narestco --dry-run
  python3 scripts/site_call_tracking.py --all-activated            # fleet
  python3 scripts/site_call_tracking.py --slug X --number +1844...

Deploy is NOT part of this script — run build_site.py sync-deploy after,
so a human (or the calling agent) owns the production push.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SB_URL = "https://nyscciinkhlutvqkgyvq.supabase.co"

DNI_MARKER = "Dynamic Number Insertion"

DNI_BLOCK = """    {brand.trackingPhone && brand.trackingPhoneRaw && (
      /* Dynamic Number Insertion (2026-08-24): humans see + dial the
         tracking number; the HTML source, JSON-LD schema, and cached/
         crawled copies keep the canonical NAP number, so citations stay
         consistent. Runs after DOM parse; skips script/style nodes so the
         structured data is never rewritten. */
      <script is:inline define:vars={{
        tp: brand.trackingPhone, tpr: brand.trackingPhoneRaw,
        op: brand.phone, opr: brand.phoneRaw,
      }}>
        (function () {
          function swap() {
            document.querySelectorAll('a[href^="tel:"]').forEach(function (a) {
              var href = a.getAttribute("href") || "";
              if (href.indexOf(opr) !== -1 || href === "tel:" + op) {
                a.setAttribute("href", "tel:" + tpr);
              }
            });
            var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            var hits = [];
            while (walker.nextNode()) {
              var n = walker.currentNode;
              var tag = n.parentElement && n.parentElement.tagName;
              if (tag === "SCRIPT" || tag === "STYLE") continue;
              if (n.nodeValue && n.nodeValue.indexOf(op) !== -1) hits.push(n);
            }
            hits.forEach(function (n) {
              n.nodeValue = n.nodeValue.split(op).join(tp);
            });
          }
          if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", swap);
          } else swap();
        })();
      </script>
    )}
"""


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def fmt_display(raw: str) -> str:
    d = re.sub(r"\D", "", raw)
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    if len(d) != 10:
        die(f"cannot format phone {raw!r}")
    return f"({d[:3]}) {d[3:6]}-{d[6:]}"


def fmt_raw(raw: str) -> str:
    d = re.sub(r"\D", "", raw)
    if len(d) == 10:
        d = "1" + d
    return "+" + d


def sb_get(path: str) -> list:
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    r = requests.get(f"{SB_URL}/rest/v1/{path}", timeout=30, headers={
        "apikey": key, "Authorization": f"Bearer {key}"})
    r.raise_for_status()
    return r.json()


def company_for_slug(slug: str) -> tuple[str | None, str | None]:
    """(company_id, agent_phone_1) via the client's domain -> marketing_sites."""
    cj = ROOT / "clients" / f"{slug}.json"
    if not cj.exists():
        die(f"clients/{slug}.json not found")
    domain = json.loads(cj.read_text()).get("domain")
    if not domain:
        return None, None
    rows = sb_get(f"marketing_sites?domain=eq.{domain}&select=company_id")
    if not rows:
        return None, None
    cid = rows[0]["company_id"]
    setup = sb_get(f"company_phone_setup?id=eq.{cid}&select=agent_phone_1")
    return cid, (setup[0].get("agent_phone_1") if setup else None)


def patch_site(slug: str, number: str, dry_run: bool) -> bool:
    site = ROOT / "sites" / slug
    brand_path = site / "src" / "lib" / "brand.ts"
    layout_path = site / "src" / "layouts" / "BaseLayout.astro"
    if not brand_path.exists() or not layout_path.exists():
        print(f"  !! {slug}: brand.ts or BaseLayout.astro missing — SKIP")
        return False

    disp, raw = fmt_display(number), fmt_raw(number)
    brand = brand_path.read_text()
    changed = []

    if "trackingPhone" in brand:
        new_brand = re.sub(r'trackingPhone: "[^"]*"', f'trackingPhone: "{disp}"', brand)
        new_brand = re.sub(r'trackingPhoneRaw: "[^"]*"', f'trackingPhoneRaw: "{raw}"', new_brand)
        if new_brand != brand:
            changed.append("brand.ts (updated values)")
        brand = new_brand
    else:
        m = re.search(r'( *)phoneRaw: "[^"]*",\n', brand)
        if not m:
            print(f"  !! {slug}: phoneRaw anchor not found in brand.ts — SKIP")
            return False
        indent = m.group(1)
        insert = (
            f"{indent}// Sitewide call-tracking display number (DNI — see BaseLayout).\n"
            f"{indent}// Schema/NAP keep the canonical number above.\n"
            f'{indent}trackingPhone: "{disp}",\n'
            f'{indent}trackingPhoneRaw: "{raw}",\n'
        )
        brand = brand[:m.end()] + insert + brand[m.end():]
        changed.append("brand.ts (fields added)")

    layout = layout_path.read_text()
    if DNI_MARKER not in layout:
        if "</body>" not in layout:
            print(f"  !! {slug}: </body> not found in BaseLayout — SKIP")
            return False
        layout = layout.replace("  </body>", DNI_BLOCK + "  </body>", 1)
        if DNI_MARKER not in layout:  # indentation variant
            layout = layout_path.read_text().replace("</body>", DNI_BLOCK + "</body>", 1)
        changed.append("BaseLayout.astro (DNI script)")

    print(f"  {slug}: tracking {disp} — " + (", ".join(changed) or "already wired"))
    if dry_run or not changed:
        return True
    brand_path.write_text(brand)
    layout_path.write_text(layout)

    r = subprocess.run(["npm", "run", "build"], cwd=site, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  !! {slug}: build FAILED after patch — reverting via git")
        subprocess.run(["git", "checkout", "--", str(brand_path), str(layout_path)], cwd=ROOT)
        print((r.stdout + r.stderr)[-400:])
        return False
    print(f"  {slug}: build OK")
    return True


def _refuse_agent_line(slug: str, number: str, allow_agent: bool) -> None:
    """The AI receptionist line must NEVER be the site's displayed number
    unless explicitly forced (Santino 2026-08-29: the original 08-24 batch
    defaulted --number to agent_phone_1 and 7 client sites rang the AI
    instead of the business; policy is site tracker / GBP tracker, and the
    AI number only when a client explicitly chooses it)."""
    import json as _json, os as _os, re as _re, urllib.request as _rq
    key = _os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    url = _os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not (key and url):
        return
    try:
        cmap = _json.loads(open("clients/company_map.json").read())
        cid = cmap.get(slug)
        if not cid:
            return
        req = _rq.Request(f"{url}/rest/v1/company_phone_setup?id=eq.{cid}&select=agent_phone_1",
                          headers={"apikey": key, "Authorization": f"Bearer {key}"})
        rows = _json.loads(_rq.urlopen(req, timeout=15).read())
        agent = _re.sub(r"[^\d+]", "", (rows[0].get("agent_phone_1") or "")) if rows else ""
        if agent and _re.sub(r"[^\d+]", "", number) == agent and not allow_agent:
            raise SystemExit(
                f"{slug}: REFUSED — {number} is the AI receptionist line "
                "(agent_phone_1). Use the site/GBP tracking number, or pass "
                "--allow-agent-line if the client explicitly chose AI-first.")
    except SystemExit:
        raise
    except Exception:
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all-activated", action="store_true",
                   help="every Active company with an agent number and a live apex site")
    ap.add_argument("--number", help="override tracking number (default: the "
                    "provisioned site/GBP marketing tracker — NEVER the AI agent line)")
    ap.add_argument("--allow-agent-line", action="store_true",
                    help="explicitly permit the AI receptionist number as the displayed number")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    def marketing_tracker(slug: str) -> str | None:
        """site tracker first, GBP tracker second — the 2/3-number model
        (Santino 2026-08-29): 1) site tracking number, 2) GBP tracking
        number, 3) AI receptionist ONLY when a client explicitly opts in."""
        cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
        cid = cmap.get(slug)
        if not cid:
            return None
        rows = sb_get(f"companies?id=eq.{cid}&select=integration_settings")
        ints = (rows[0].get("integration_settings") or {}) if rows else {}
        if isinstance(ints, str):
            try:
                ints = json.loads(ints)
            except ValueError:
                ints = {}
        ct = ints.get("call_tracking") or {}
        return ((ct.get("website") or {}).get("number")
                or (ct.get("site") or {}).get("number")
                or (ct.get("gbp") or {}).get("number"))

    targets: list[tuple[str, str]] = []
    if args.slug:
        if args.number:
            _refuse_agent_line(args.slug, args.number, args.allow_agent_line)
            targets.append((args.slug, args.number))
        else:
            number = marketing_tracker(args.slug)
            if not number:
                die(f"{args.slug}: no site/GBP tracking number provisioned — "
                    "run call_tracking.py first (the AI agent line is never "
                    "used as a default; --allow-agent-line to force)")
            targets.append((args.slug, number))
    else:
        rows = sb_get(
            "company_phone_setup?select=id,agent_phone_1&agent_phone_1=not.is.null")
        agents = {r["id"]: r["agent_phone_1"] for r in rows}
        live = sb_get("marketing_sites?apex_live=eq.true&select=company_id,domain")
        dom_by_cid = {r["company_id"]: r["domain"] for r in live}
        active = {r["id"] for r in sb_get("companies?status=eq.Active&select=id")}
        by_domain = {}
        for cj in (ROOT / "clients").glob("*.json"):
            try:
                d = json.loads(cj.read_text()).get("domain")
                if d:
                    by_domain[d] = cj.stem
            except Exception:
                continue
        for cid, agent in agents.items():
            if cid not in active or cid not in dom_by_cid:
                continue
            slug = by_domain.get(dom_by_cid[cid])
            if slug and (ROOT / "sites" / slug).exists():
                number = marketing_tracker(slug)
                if not number:
                    print(f"  {slug}: SKIP — no marketing tracker provisioned "
                          "(never defaulting to the AI agent line)")
                    continue
                targets.append((slug, number))

    print(f"call-tracking DNI targets: {len(targets)}")
    ok = 0
    for slug, number in targets:
        ok += patch_site(slug, number, args.dry_run)
    print(f"done: {ok}/{len(targets)} patched" + (" (dry run)" if args.dry_run else ""))
    print("Next: build_site.py sync-deploy --slug {slug} --branch main for each.")


if __name__ == "__main__":
    main()
