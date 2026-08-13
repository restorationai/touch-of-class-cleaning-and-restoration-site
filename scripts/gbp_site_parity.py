#!/usr/bin/env python3
"""gbp_site_parity.py -- the GBP <-> site PARITY CHECKER.

Santino's thesis (valid): a Google Business Profile service backed by a
matching website page ranks; a bare label on the listing doesn't. This script
closes that loop fleet-wide, both directions:

  (a) GBP services with NO matching site service page -> classify each one
      with ONE claude-sonnet-5 call per client, volumes attached via ONE
      DataForSEO google_ads search_volume call scoped to the client's metro:
        worth_a_page       real distinct service people search for
                           (volume >= 10/mo in-metro, or nationally
                           meaningful) -> queue a page build
        fold_into_existing phrasing variant of an existing page's intent
                           -> no action, reported with its target page
        trim_candidate     junk/duplicate nobody searches -> NEVER removed;
                           one consolidated SUGGESTION card per client
  (b) site service pages with no GBP service entry -> report only (these
      should be rare post-enrichment; gbp_face_audit.fix_services adds them).

--apply actions (dry-run is the default):
  * worth_a_page  -> marketing_page_requests row (status 'queued'), matching
    the existing queue shape exactly, deduped against queued/building/built
    rows so reruns never double-queue. Cap 10 pages/client/run, highest
    search volume first. The gbp-maintenance create-pages --build drain
    turns the queue into plan-input -> render -> deploy.
  * trim_candidate -> ONE pinned marketing_action_plan card per client via
    client_ops_sync.insert_plan_row (idempotent seed key gbp-parity-trim);
    the list + volumes live in the rationale. Services are never removed.
  * one marketing_work_log row per client run summarizing the check.

Usage:
    python3 scripts/gbp_site_parity.py --all               # dry-run report
    python3 scripts/gbp_site_parity.py --all --apply
    python3 scripts/gbp_site_parity.py --slug narestco --apply
    python3 scripts/gbp_site_parity.py --all --apply \
        --skip-queue crew-restoration-construction         # classify+report only

Paused/cancelled clients are skipped (same companies.status gate as the
other gbp.py --all passes). Env: rank-ai/.env (Supabase, Google OAuth,
ANTHROPIC_API_KEY, DataForSEO).
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import gbp  # noqa: E402 -- reconcile, _norm, site_services, _anthropic_json, SB REST (import only, never edited)
from client_ops_sync import _sb as ops_sb  # noqa: E402
from client_ops_sync import action_key, insert_plan_row  # noqa: E402
from gbp_name_suggest import metro_location, search_volumes  # noqa: E402
from work_log import work_log  # noqa: E402

PARITY_MODEL = "claude-sonnet-5"
QUEUE_CAP = 10          # pages per client per run
MIN_METRO_VOLUME = 10   # searches/mo gate for worth_a_page (unless nationally meaningful)


# --------------------------------------------------------------------------- #
# roster + client metadata
# --------------------------------------------------------------------------- #
def roster(args) -> list[str]:
    """Same account-status gate as every other gbp --all pass (paused/cancelled
    clients are skipped). Reuses gbp._clients so the gate can never drift."""
    return gbp._clients(SimpleNamespace(all=args.all, slug=args.slug))


def companies_meta(slugs: list[str]) -> dict:
    """{slug: {name, city, state}} in one companies read."""
    cids = {s: gbp.company_id_for(s) for s in slugs}
    ids = ",".join(f'"{c}"' for c in cids.values() if c)
    rows = gbp._sb(f"companies?id=in.({ids})&select=id,name,city,state") if ids else []
    by_id = {r["id"]: r for r in rows}
    return {s: by_id.get(c, {}) for s, c in cids.items()}


def _dfs_auth_b64() -> str | None:
    """base64 basic-auth for DataForSEO; None (never exit) when unconfigured."""
    creds = gbp._dfs_auth()
    if not creds:
        return None
    return base64.b64encode(f"{creds[0]}:{creds[1]}".encode()).decode()


# --------------------------------------------------------------------------- #
# site pages (plan-input display names + rendered service .md files on disk)
# --------------------------------------------------------------------------- #
def site_pages(slug: str) -> list[str]:
    """Display names for every dedicated service page the client's site has.
    plan-input.json is canonical; the on-disk services/*.md stems are added so
    a rendered page that plan-input lost track of still counts as coverage."""
    pages = list(gbp.site_services(slug))
    seen = {gbp._norm(p) for p in pages}
    svc_dir = ROOT / "sites" / slug / "src" / "content" / "services"
    if svc_dir.is_dir():
        for f in sorted(svc_dir.glob("*.md")):
            disp = f.stem.replace("-", " ").title()
            if gbp._norm(disp) not in seen:
                seen.add(gbp._norm(disp))
                pages.append(disp)
    return pages


def unbacked_services(rec: dict, pages: list[str]) -> list[str]:
    """Direction (a), SERVICES ONLY: gbp.reconcile's gbp_without_page mixes the
    listing's categories in with its services; a category ('Water damage
    restoration service') is not a page candidate, so recompute over
    rec['gbp']['services'] with reconcile's own fuzzy containment match."""
    page_norms = {gbp._norm(p) for p in pages if gbp._norm(p)}
    out, seen = [], set()
    for raw in rec.get("gbp", {}).get("services", []):
        svc = gbp._svc_label(raw)  # 'job_type_id:mold_removal' -> 'Mold Removal'
        n = gbp._norm(svc)
        if not n or n in seen:
            continue
        seen.add(n)
        if not any(n in pn or pn in n for pn in page_norms):
            out.append(svc)
    return out


# --------------------------------------------------------------------------- #
# search volumes (one DataForSEO call per client, metro-scoped)
# --------------------------------------------------------------------------- #
def _kw(service: str) -> str:
    """A GBP service label as a Google-Ads-safe keyword (bad symbols kill the
    whole DFS task): lowercase, & -> and, ascii words only, <=10 words, <=80 chars."""
    t = (service or "").lower().replace("&", " and ")
    t = re.sub(r"[^a-z0-9' -]+", " ", t)
    t = " ".join(t.split()[:10])
    return t[:80].strip()


def volumes_for(services: list[str], city: str | None, state: str | None) -> tuple[dict, str]:
    """{original service label: monthly searches} + the location label used.
    One live google_ads search_volume call (metro first, US national fallback
    inside search_volumes). No creds / all-bad keywords -> zeros, never fatal."""
    auth = _dfs_auth_b64()
    kws = {}
    for s in services:
        k = _kw(s)
        if k:
            kws.setdefault(k, s)
    if not (auth and kws):
        return {s: 0 for s in services}, "unavailable"
    loc = metro_location(city, state)
    try:
        vols, label = search_volumes(auth, list(kws)[:1000], loc)
    except Exception as e:  # noqa: BLE001 -- volumes are an input, not a gate
        print(f"     [dfs] volume lookup failed ({str(e)[:80]}) -- volumes set to 0")
        return {s: 0 for s in services}, "unavailable"
    out = {s: 0 for s in services}
    for k, orig in kws.items():
        out[orig] = int(vols.get(k, 0) or 0)
    return out, label


# --------------------------------------------------------------------------- #
# classification (one claude-sonnet-5 call per client)
# --------------------------------------------------------------------------- #
CLASSIFY_SYSTEM = """You are a local-SEO strategist for a home-services company.
The company's Google Business Profile lists services; each service either has a
dedicated page on the company website or it does not. You are given ONLY the
services with no matching page, plus the list of pages the site already has and
Google Ads monthly search volumes for the company's metro.

Classify EVERY input service into exactly one verdict:
- "worth_a_page": a real, distinct service a customer would type into Google,
  deserving its own landing page, and not already covered by an existing page.
- "fold_into_existing": a phrasing variant or narrow sub-case of an EXISTING
  page's search intent. Set "fold_target" to the exact existing page name it
  belongs to (copy it verbatim from existing_pages).
- "trim_candidate": junk, a duplicate of another listed service, a vague
  marketing phrase, or something nobody searches for.

Also set "nationally_meaningful": true when the service is a recognized service
category that people genuinely search for across the US, even if this metro's
volume shows low or zero (small metros under-report). Keep "reason" under 12
words. Return every service exactly once, name copied verbatim.

Output JSON only:
{"classifications": [{"service": "...", "verdict": "worth_a_page|fold_into_existing|trim_candidate",
  "fold_target": null, "nationally_meaningful": false, "reason": "..."}]}"""


def classify(slug: str, meta: dict, pages: list[str], services: list[str],
             vols: dict, vol_label: str) -> dict:
    """{service: {verdict, fold_target, nationally_meaningful, reason}} via one
    claude-sonnet-5 call. Post-processing enforces the volume gate: worth_a_page
    stays only when metro volume >= 10/mo or the model marked it nationally
    meaningful; otherwise it demotes to trim_candidate."""
    vertical = None
    rec_path = ROOT / "clients" / f"{slug}.json"
    if rec_path.exists():
        try:
            vertical = json.loads(rec_path.read_text()).get("vertical")
        except json.JSONDecodeError:
            pass
    payload = {
        "company": meta.get("name") or slug,
        "vertical": vertical or "restoration",
        "metro": ", ".join(x for x in (meta.get("city"), meta.get("state")) if x) or "unknown",
        "volume_scope": vol_label,
        "existing_pages": pages,
        "services": [{"name": s, "monthly_searches": vols.get(s, 0)} for s in services],
    }
    out = gbp._anthropic_json(CLASSIFY_SYSTEM,
                              "Classify these services.\n\nDATA:\n" + json.dumps(payload),
                              model=PARITY_MODEL)
    by_service: dict = {}
    page_norms = {gbp._norm(p): p for p in pages}
    for row in out.get("classifications", []):
        name = str(row.get("service", "")).strip()
        verdict = row.get("verdict")
        if name not in services or verdict not in (
                "worth_a_page", "fold_into_existing", "trim_candidate"):
            continue
        fold = row.get("fold_target")
        if verdict == "fold_into_existing":
            # the target must be a real existing page; otherwise it isn't a fold
            fold = page_norms.get(gbp._norm(str(fold or "")))
            if not fold:
                verdict, fold = "trim_candidate", None
                row["reason"] = "fold target did not match an existing page"
        if verdict == "worth_a_page" and vols.get(name, 0) < MIN_METRO_VOLUME \
                and not row.get("nationally_meaningful"):
            verdict = "trim_candidate"
            row["reason"] = f"low search volume ({vols.get(name, 0)}/mo, not nationally meaningful)"
        by_service[name] = {"verdict": verdict, "fold_target": fold,
                            "reason": str(row.get("reason") or "")[:120]}
    for s in services:  # anything the model dropped: report-only, no action
        by_service.setdefault(s, {"verdict": "unclassified", "fold_target": None,
                                  "reason": "model returned no verdict"})
    return by_service


# --------------------------------------------------------------------------- #
# --apply actions
# --------------------------------------------------------------------------- #
def existing_queue_norms(cid: str) -> set:
    """Normalized service names already queued/building/built for this company,
    so reruns never double-queue. 'dismissed' counts too: a human said no to
    that page once, and the weekly parity pass must never resurrect it."""
    rows = gbp._sb(f"marketing_page_requests?company_id=eq.{cid}&select=service,status")
    return {gbp._norm(str(r.get("service", ""))) for r in rows
            if r.get("status") in ("queued", "building", "built", "dismissed")}


def queue_pages(cid: str, worth: list[tuple[str, int]], apply: bool) -> list[str]:
    """Queue up to QUEUE_CAP page requests, highest volume first, deduped.
    Matches the existing marketing_page_requests queue shape exactly."""
    have = existing_queue_norms(cid)
    queued = []
    for svc, vol in sorted(worth, key=lambda x: -x[1]):
        if len(queued) >= QUEUE_CAP:
            break
        n = gbp._norm(svc)
        if not n or n in have:
            continue
        if apply:
            requests.post(
                f"{gbp.SB_URL}/rest/v1/marketing_page_requests",
                headers={"apikey": gbp.SB_KEY,
                         "Authorization": f"Bearer {gbp.SB_KEY}",
                         "Content-Type": "application/json",
                         "Prefer": "return=minimal"},
                data=json.dumps({"company_id": cid, "service": svc,
                                 "status": "queued"}),
                timeout=30).raise_for_status()
        have.add(n)
        queued.append(svc)
    return queued


def seed_trim_card(cid: str, slug: str, trims: list[tuple[str, int, str]],
                   vol_label: str, apply: bool) -> bool:
    """ONE consolidated suggestion card per client (idempotent seed key
    gbp-parity-trim). Services are NEVER removed by automation; the card is a
    human decision. An open card gets its title and rationale refreshed in
    place when the numbers change (insert_plan_row retitles; rationale is
    patched here, same pattern as gbp_name_suggest.seed_card)."""
    lines = "\n".join(f'- "{s}" ({v}/mo{", " + r if r else ""})'
                      for s, v, r in sorted(trims, key=lambda x: x[1]))
    rationale = (
        f"GBP-site parity check: these {len(trims)} services on the Google "
        f"listing have no matching website page AND no meaningful search "
        f"demand (Google Ads monthly volume, {vol_label}), so they add "
        f"clutter without ranking power:\n{lines}\n\n"
        "NOTHING is removed automatically. Review the list in the GBP "
        "dashboard (Edit profile > Services); delete the ones the business "
        "truly does not offer or that duplicate another service, and tell us "
        "about any that ARE real so we can build a page instead. A shorter, "
        "page-backed services list beats a long list of bare labels.")
    title = f"SUGGESTION: {len(trims)} Google services look like dead weight"
    created = insert_plan_row(
        cid, slug, "gbp-parity-trim",
        title=title, rationale=rationale,
        action_type="gbp_fix",           # manual card; nothing automated consumes gbp_fix
        target=f"gbp:{slug}", impact="medium", effort="low",
        dry_run=not apply)
    if not created and apply:
        ops_sb("PATCH", "/rest/v1/marketing_action_plan"
               f"?company_id=eq.{cid}"
               f"&action_key=eq.{action_key(cid, 'gbp-parity-trim')}"
               "&status=eq.planned", {"rationale": rationale})
    return created


# --------------------------------------------------------------------------- #
# per-client run
# --------------------------------------------------------------------------- #
def check_client(slug: str, meta: dict, apply: bool, skip_queue: bool) -> dict:
    out = {"slug": slug, "skip": None, "gbp_services": 0, "unbacked": 0,
           "site_without_gbp": 0, "queued": [], "would_queue": [],
           "fold": [], "trim": [], "unclassified": [], "vol_label": ""}
    rec = gbp.reconcile(slug)
    if rec.get("error"):
        out["skip"] = rec["error"]
        return out
    cid = rec.get("company_id")
    pages = site_pages(slug)
    out["gbp_services"] = len(rec.get("gbp", {}).get("services", []))
    out["site_without_gbp"] = len(rec.get("site_without_gbp") or [])
    out["site_without_gbp_list"] = rec.get("site_without_gbp") or []
    unbacked = unbacked_services(rec, pages)
    out["unbacked"] = len(unbacked)
    if not unbacked:
        if apply and cid:
            work_log(cid, "gbp", "parity-check",
                     "Checked your Google services against your website: all "
                     f"{out['gbp_services']} services are backed by a matching page.",
                     evidence={"gbp_services": out["gbp_services"],
                               "site_without_gbp": out["site_without_gbp_list"]},
                     actor="automation", source="gbp_site_parity.py")
        return out

    vols, vol_label = volumes_for(unbacked, meta.get("city"), meta.get("state"))
    out["vol_label"] = vol_label
    verdicts = classify(slug, meta, pages, unbacked, vols, vol_label)

    worth = [(s, vols.get(s, 0)) for s, v in verdicts.items() if v["verdict"] == "worth_a_page"]
    out["fold"] = [(s, v["fold_target"]) for s, v in verdicts.items()
                   if v["verdict"] == "fold_into_existing"]
    out["trim"] = [(s, vols.get(s, 0), verdicts[s]["reason"]) for s, v in verdicts.items()
                   if v["verdict"] == "trim_candidate"]
    out["unclassified"] = [s for s, v in verdicts.items() if v["verdict"] == "unclassified"]

    if skip_queue:
        out["would_queue"] = [s for s, _ in sorted(worth, key=lambda x: -x[1])[:QUEUE_CAP]]
    else:
        out["queued"] = queue_pages(cid, worth, apply)
    out["worth"] = sorted(worth, key=lambda x: -x[1])

    if out["trim"] and cid:
        seed_trim_card(cid, slug, out["trim"], vol_label, apply)

    if apply and cid:
        if skip_queue and worth:
            detail = (f"Checked your Google services against your website: "
                      f"{len(worth)} look worth new pages (page building deferred), "
                      f"{len(out['trim'])} flagged for review.")
        else:
            detail = (f"Checked your Google services against your website: "
                      f"{len(out['queued'])} services getting new pages, "
                      f"{len(out['trim'])} flagged for review.")
        work_log(cid, "gbp", "parity-check", detail,
                 evidence={"unbacked": len(unbacked),
                           "queued": out["queued"] or out["would_queue"],
                           "trim": [s for s, _, _ in out["trim"]],
                           "fold": {s: t for s, t in out["fold"]},
                           "volumes_scope": vol_label,
                           "site_without_gbp": out["site_without_gbp_list"]},
                 actor="automation", source="gbp_site_parity.py")
    return out


# --------------------------------------------------------------------------- #
# CLI + fleet report
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true",
                    help="queue pages + seed cards + work_log (default: dry-run report)")
    ap.add_argument("--skip-queue", action="append", default=[], metavar="SLUG",
                    help="classify + report this client but do NOT queue pages (repeatable)")
    args = ap.parse_args()

    slugs = roster(args)
    meta = companies_meta(slugs)
    results, failures = [], 0
    for slug in slugs:
        print(f"\n## {slug}")
        try:
            r = check_client(slug, meta.get(slug) or {}, args.apply,
                             skip_queue=slug in args.skip_queue)
        except Exception as e:  # noqa: BLE001 -- one client must never abort the fleet
            failures += 1
            print(f"   ERROR ({type(e).__name__}: {str(e)[:200]}) -- skipped")
            continue
        results.append(r)
        if r["skip"]:
            print(f"   SKIP -- {r['skip']}")
            continue
        print(f"   GBP services: {r['gbp_services']} | unbacked: {r['unbacked']} | "
              f"site pages missing on GBP: {r['site_without_gbp']}")
        if r["unbacked"]:
            print(f"   volumes: {r['vol_label']}")
            verb = "queued" if args.apply else "would queue"
            if r["queued"] or not r["would_queue"]:
                shown = r["queued"]
            else:
                verb = "would queue (QUEUE SKIPPED this run)"
                shown = r["would_queue"]
            vols = dict(r.get("worth", []))
            for s in shown:
                print(f"   + {verb}: {s} ({vols.get(s, 0)}/mo)")
            extra = [s for s, _ in r.get("worth", []) if s not in shown]
            if extra:
                print(f"   . worth_a_page beyond cap/dedupe: {extra}")
            for s, target in r["fold"]:
                print(f"   = fold into existing page: {s} -> {target}")
            for s, v, reason in r["trim"]:
                print(f"   - trim candidate: {s} ({v}/mo) {reason}")
            for s in r["unclassified"]:
                print(f"   ? unclassified (no action): {s}")
        if r["site_without_gbp"]:
            print(f"   site-only services (report only): {r['site_without_gbp_list']}")

    # fleet table
    print(f"\n{'=' * 78}")
    print(f"FLEET PARITY {'APPLIED' if args.apply else 'DRY-RUN'}")
    print(f"{'client':<38}{'gbp':>5}{'unbk':>6}{'queue':>7}{'trim':>6}{'fold':>6}{'site>':>6}")
    tot = [0] * 6
    for r in results:
        if r["skip"]:
            print(f"{r['slug']:<38} skip: {r['skip'][:38]}")
            continue
        q = len(r["queued"] or r["would_queue"])
        row = [r["gbp_services"], r["unbacked"], q, len(r["trim"]),
               len(r["fold"]), r["site_without_gbp"]]
        tot = [a + b for a, b in zip(tot, row)]
        mark = "*" if r["would_queue"] else ""
        print(f"{r['slug']:<38}{row[0]:>5}{row[1]:>6}{str(row[2]) + mark:>7}"
              f"{row[3]:>6}{row[4]:>6}{row[5]:>6}")
    print(f"{'TOTAL':<38}{tot[0]:>5}{tot[1]:>6}{tot[2]:>7}{tot[3]:>6}{tot[4]:>6}{tot[5]:>6}")
    if any(r.get("would_queue") for r in results):
        print("   * = classification only, page-queueing skipped this run (--skip-queue)")
    if failures:
        print(f"   ({failures} client(s) errored and were skipped -- see above)")
    return 0  # non-fatal: a client error must never fail the scheduled run


if __name__ == "__main__":
    sys.exit(main())
