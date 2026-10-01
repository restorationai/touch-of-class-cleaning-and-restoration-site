#!/usr/bin/env python3
"""plumbing_gate.py: the EMERGENCY PLUMBING GATE (Santino 2026-10-01).

"If a company adds the '24/7 Emergency Plumbing' to their GBP, we should add
that as a service only once the name is confirmed or once the DBA filing has
been uploaded."

A restoration client's SITE carries emergency-plumbing (or any other
plumbing-claim service: slug or name contains "plumb") only when ONE of these
is true:

  (a) NAME CONFIRMED: the live GBP title (marketing_gbp_profiles.title)
      contains "plumbing", or rename_intent records the GBP rename as
      executed (gbp_renamed_at / gbp_verification) for a name with plumbing
      in it.
  (b) DBA ON FILE: rename_intent.dba_filed / dba_verified (the DBA upload,
      vision- or document-verified by scripts/rename_evidence.py, doc in
      branding/{cid}/docs) for a name that includes plumbing. The name is
      rename_intent.dba_name, else the CHOSEN name suggestion.
  (c) LICENSED PLUMBER: plumbing vertical (RT Olson, All Pro), a plumbing
      license type, or a license number shared with a plumbing-vertical
      client (emergency_naming.plumbing_licensed: ProRestoration runs on All
      Pro's CSLB license).

A chosen-but-unfiled name ("DRYCOR RESTORE TAMPA - 24/7 Emergency Plumbing
...", decision=rename, no DBA upload yet) does NOT pass: chosen is intent,
not confirmation.

Until the gate passes:
  * plan_site.py drops every plumbing service from the plan (the core floor
    no longer defaults it, an explicit plan-input entry is held, not built);
  * gbp_service_map.py maps a GBP "Emergency Plumbing" / "Plumbing" label
    onto water-damage-restoration (source "plumbing-gate"), so it never
    queues a page, and site_structure.page_services() keeps plumbing labels
    off the "Services We Handle" list (no word "plumbing" on the site);
  * gbp_service_bank.py does not stage the plumbing long-tail family.
The moment the gate passes (DBA uploaded, rename live), the next nightly
plan picks the service up again; the map re-decides "plumbing-gate" entries.

Canonical facts stay in Supabase (rename_intent, GBP profile, suggestions).
clients/{slug}/plumbing-gate.json is only the last decision + evidence, used
when Supabase is unreachable (CI without secrets, outage) so the plan does
not flap; with no cache and no network the gate is CLOSED.

CLI:
    python3 scripts/plumbing_gate.py                 # fleet report
    python3 scripts/plumbing_gate.py --slug drycor-restore
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENTS = ROOT / "clients"
sys.path.insert(0, str(ROOT / "scripts"))

PLUMB_RE = re.compile(r"plumb", re.I)
DEAD = {"mcc-restoration", "mold-solutionz"}


def is_plumbing_service(slug_or_label: str, display: str = "") -> bool:
    """A plumbing-CLAIM service: emergency-plumbing, "Plumbing", "24/7
    Emergency Plumbing". Water-damage phrasings that merely mention a
    plumbing leak/overflow are NOT claims (they are water damage work)."""
    s = f"{slug_or_label} {display}"
    if not PLUMB_RE.search(s):
        return False
    return not re.search(r"plumbing[- ](leak|overflow|malfunction|failure)|water[- ]damage",
                         s, re.I)


def _cache_path(slug: str) -> Path:
    return CLIENTS / slug / "plumbing-gate.json"


def _client(slug: str) -> dict:
    try:
        return json.loads((CLIENTS / f"{slug}.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _licensed(slug: str) -> str | None:
    if str(_client(slug).get("vertical") or "").lower() == "plumbing":
        return "plumbing vertical (licensed plumbing company)"
    try:
        from emergency_naming import plumbing_licensed
        if plumbing_licensed(slug):
            return "plumbing license on file (license type or shared plumbing license)"
    except Exception:  # noqa: BLE001
        pass
    return None


def _online_evidence(slug: str) -> dict:
    """Pull the rename facts from Supabase. Raises on any network/env gap."""
    import requests
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    cid = _client(slug).get("company_id")
    if not cid:
        from work_log import company_id_for_slug
        cid = company_id_for_slug(slug)
    if not cid:
        raise RuntimeError("no company_id")

    def get(path: str) -> list:
        r = requests.get(base + path, headers=h, timeout=15)
        r.raise_for_status()
        return r.json() or []

    co = (get(f"/rest/v1/companies?id=eq.{cid}&select=integration_settings") or [{}])[0]
    ints = co.get("integration_settings") or {}
    if isinstance(ints, str):
        ints = json.loads(ints)
    ri = ints.get("rename_intent") or {}
    prof = (get(f"/rest/v1/marketing_gbp_profiles?company_id=eq.{cid}&select=title") or [{}])[0]
    chosen = [s["item"] for s in get(
        f"/rest/v1/marketing_gbp_suggestions?company_id=eq.{cid}"
        "&item_type=eq.name&status=eq.chosen&select=item")]
    return {"company_id": cid, "gbp_title": prof.get("title") or "",
            "rename_intent": {k: ri.get(k) for k in (
                "decision", "dba_name", "dba_filed", "dba_filed_at", "dba_verified",
                "dba_doc_url", "gbp_renamed_at", "gbp_verification") if ri.get(k)},
            "chosen_names": chosen}


def decide(ev: dict) -> tuple[bool, str]:
    ri = ev.get("rename_intent") or {}
    if PLUMB_RE.search(ev.get("gbp_title") or ""):
        return True, f"(a) live GBP name has plumbing: {ev['gbp_title']!r}"
    name = ri.get("dba_name") or next(iter(ev.get("chosen_names") or []), "")
    if ri.get("decision") == "keep":
        return False, "client kept their current name (rename_intent decision=keep)"
    if (ri.get("gbp_renamed_at") or ri.get("gbp_verification")) and PLUMB_RE.search(name):
        return True, f"(a) GBP rename executed for {name!r}"
    if (ri.get("dba_filed") or ri.get("dba_verified")) and PLUMB_RE.search(name):
        return True, (f"(b) DBA on file ({ri.get('dba_verified') or 'filed'}"
                      f"{', ' + str(ri.get('dba_filed_at')) if ri.get('dba_filed_at') else ''}): {name!r}")
    # CHOSEN IS ENOUGH (Santino 2026-10-01: "if they even choose a plumbing
    # name, we can queue them to have the page built in an overnight sweep").
    if any(PLUMB_RE.search(n) for n in ev.get("chosen_names") or []) or (
            ri.get("decision") not in (None, "", "keep") and PLUMB_RE.search(ri.get("dba_name") or "")):
        picked = next((n for n in ev.get("chosen_names") or [] if PLUMB_RE.search(n)),
                      ri.get("dba_name"))
        return True, f"(a') client chose a plumbing name: {picked!r}"
    return False, "no plumbing name confirmed, no plumbing DBA, not a licensed plumber"


def evaluate(slug: str, *, online: bool = True, write: bool = True) -> dict:
    lic = _licensed(slug)
    if lic:
        return {"slug": slug, "allowed": True, "reason": f"(c) {lic}", "source": "local"}
    if online:
        try:
            ev = _online_evidence(slug)
            ok, why = decide(ev)
            out = {"slug": slug, "allowed": ok, "reason": why, "evidence": ev,
                   "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "source": "supabase"}
            if write and (ROOT / "sites" / slug / "src").is_dir():
                p = _cache_path(slug)
                old = {}
                try:
                    old = json.loads(p.read_text())
                except (OSError, json.JSONDecodeError):
                    pass
                # rewrite only on a decision/evidence change (no daily churn diffs)
                if {k: old.get(k) for k in ("allowed", "reason", "evidence")} != \
                        {k: out.get(k) for k in ("allowed", "reason", "evidence")}:
                    p.write_text(json.dumps(out, indent=2) + "\n")
            return out
        except Exception as e:  # noqa: BLE001 -- fall back to the last decision
            err = str(e)[:120]
        else:
            err = ""
    else:
        err = "offline"
    try:
        cached = json.loads(_cache_path(slug).read_text())
        return {**cached, "source": f"cache ({err})"}
    except (OSError, json.JSONDecodeError):
        return {"slug": slug, "allowed": False, "source": f"closed ({err})",
                "reason": "gate closed: no cached decision and Supabase unreachable"}


@lru_cache(maxsize=None)
def allowed(slug: str) -> bool:
    """Process-cached yes/no for plan_site / gbp_service_map / site_structure."""
    if not slug:
        return False
    return bool(evaluate(slug).get("allowed"))


# --------------------------------------------------------------------------- #
# removal (sites that do not meet the gate)
# --------------------------------------------------------------------------- #
FALLBACK = "water-damage-restoration"


def _is_placeholder(text: str) -> bool:
    fm = text.split("\n---", 1)[0]
    return ("Page body not yet generated" in text
            or not re.search(r"^rendered:\s*true\b", fm, re.M))


def remove(slug: str, apply: bool) -> dict:
    """Take every plumbing-claim service page (and its city pages) off a site
    that does not meet the gate. Placeholders are deleted; RENDERED pages get
    static 301s to the water damage restoration equivalent; every link is
    rewritten to that equivalent; plan-input / homepage / GBP map updated.
    Never touches a site that meets the gate."""
    import service_merge as sm
    import site_structure as ss
    if evaluate(slug).get("allowed"):
        return {"slug": slug, "skipped": "meets the plumbing gate"}
    site = ROOT / "sites" / slug
    content = site / "src" / "content"
    svc_files = [f for f in sorted((content / "services").glob("*.md"))
                 if is_plumbing_service(f.stem)]
    out = {"slug": slug, "services": [], "placeholders_deleted": 0,
           "rendered_redirected": [], "files_relinked": 0}
    if not svc_files:
        # stray city pages without a service page
        svcs = sorted({f.stem.split("__", 1)[1] for f in (content / "locations").glob("*__*.md")
                       if is_plumbing_service(f.stem.split("__", 1)[1])})
    else:
        svcs = [f.stem for f in svc_files]
    loc_dir = content / "locations"
    dst_cities = {f.stem.split("__", 1)[0] for f in loc_dir.glob(f"*__{FALLBACK}.md")}
    red_lines: list[str] = []
    for src in svcs:
        files = ([content / "services" / f"{src}.md"]
                 if (content / "services" / f"{src}.md").exists() else [])
        files += sorted(loc_dir.glob(f"*__{src}.md"))
        out["services"].append(src)
        for f in files:
            text = f.read_text(errors="replace")
            if f.parent.name == "services":
                url, dst = f"/services/{src}", f"/services/{FALLBACK}/"
            else:
                c = f.stem.split("__", 1)[0]
                url = f"/service-areas/{c}/{src}"
                dst = (f"/service-areas/{c}/{FALLBACK}/" if c in dst_cities
                       else f"/services/{FALLBACK}/")
            if _is_placeholder(text):
                out["placeholders_deleted"] += 1
            else:
                out["rendered_redirected"].append(f"{url}/ -> {dst}")
                red_lines += [f"{url} {dst} 301", f"{url}/ {dst} 301"]
            if apply:
                f.unlink()
        touched = sm.rewrite_links(site, src, FALLBACK, dst_cities, apply)
        if apply and touched:
            sm.dedupe_internal_links(site, apply=True, only=touched)
        out["files_relinked"] += len(touched)
        sm.filter_plan_artifacts(slug, src, apply)
    if apply and red_lines:
        red = site / "public" / "_redirects"
        existing = red.read_text() if red.exists() else ""
        new = [l for l in red_lines if l not in existing]
        if new:
            red.write_text(existing + ("" if existing.endswith("\n") or not existing else "\n")
                           + "# plumbing gate 2026-10-01: emergency plumbing held until the "
                             "plumbing name/DBA is confirmed (scripts/plumbing_gate.py)\n"
                           + "\n".join(new) + "\n")
            st = ss.normalize_redirects(red)
            if st.get("over_cap"):
                raise RuntimeError(f"{slug}: _redirects over the Cloudflare cap {st}")
    if apply and out["services"]:
        pi = ss.load_plan_input(slug)
        pi["services"] = [s for s in pi.get("services") or [] if s not in out["services"]]
        if pi.get("homepage_services"):
            pi["homepage_services"] = [s for s in pi["homepage_services"]
                                       if s not in out["services"]]
        ss.save_plan_input(slug, pi)
        m = ss.load_map(slug)
        for label, e in m.get("gbp_services", {}).items():
            if e.get("page") in out["services"] or (is_plumbing_service(label)
                                                    and e.get("verdict") != "declined"):
                m["gbp_services"][label] = {
                    "verdict": "mapped", "page": FALLBACK, "source": "plumbing-gate",
                    "reason": "plumbing gate not met: maps to water damage restoration",
                    "at": datetime.now(timezone.utc).date().isoformat()}
        ss.save_map(slug, m)
        ss.write_homepage_services(slug)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--remove", action="store_true",
                    help="take plumbing pages off sites that do not meet the gate (dry-run "
                         "unless --apply)")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:  # noqa: BLE001
        pass
    slugs = [a.slug] if a.slug else sorted(
        p.parent.name for p in CLIENTS.glob("*/plan-input.json")
        if p.parent.name not in DEAD and p.parent.name != "tdi-builders")
    for s in slugs:
        if a.remove:
            if not (ROOT / "sites" / s / "src").is_dir():
                continue
            print(json.dumps(remove(s, a.apply)))
            continue
        r = evaluate(s)
        print(f"{s:50s} {'KEEP plumbing' if r['allowed'] else 'gated       '}  {r['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
