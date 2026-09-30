#!/usr/bin/env python3
"""gbp_service_map.py — map every GBP service onto an existing site page.

WHY (Santino 2026-09-30): "The GBP will be trying to rank for all the
long-tail search terms, so there may be 100 to 200 different services on a
GBP. Obviously we wouldn't want 100 to 200 different services on the
website." Rule 1 + 2 of scripts/site_structure.py:

  * a GBP service that is a synonym / long-tail / modifier variant of an
    existing site service page MAPS to that page ("Emergency Water Removal"
    -> water-damage-restoration, "Board Up Services" -> emergency board-up).
    A mapped service never creates a page.
  * only a genuinely DISTINCT service whose head term clears the volume bar
    (NEW_PAGE_METRO_MIN in the client's city, else NEW_PAGE_NATIONAL_MIN
    nationally incl. "near me") is marked new_page; the create-pages drain
    builds at most MAX_NEW_PAGES_PER_NIGHT of those per client per night.

The map is stored per client at clients/{slug}/gbp-service-map.json (one
canonical store; the drain, gbp_parity.py and the audit all read it).
Matching order: exact name -> catalog slug -> same-service cluster ->
name containment -> ONE Claude call per client for the rest (+ DataForSEO
volumes for anything Claude calls distinct).

Usage:
    python3 scripts/gbp_service_map.py --slug prorestoration          # dry-run
    python3 scripts/gbp_service_map.py --all --apply                  # refresh every map
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dotenv import load_dotenv  # noqa: E402

import site_structure as ss  # noqa: E402

load_dotenv(ss.ROOT / ".env")

MODEL = "claude-sonnet-5"

SYSTEM = """You map a home-services company's Google Business Profile (GBP)
services onto the company's EXISTING website service pages. The GBP lists many
long-tail phrasings on purpose; the website must stay lean (one page per real
service). For every GBP service choose exactly one verdict:

- "map": the same service as an existing page, a synonym, a sub-case, a
  long-tail or modifier variant (emergency, 24/7, commercial, residential,
  "services", "company", "repair", "cleanup", a material or room), or a task
  normally performed as part of that page's service. Set "page" to the exact
  page slug from existing_pages. Prefer "map" whenever a customer searching
  that phrase would be well served by the existing page.
- "distinct": a genuinely different service with its own customer search
  intent that NO existing page covers AND that sits inside this company's
  own trade as its existing pages show it (a restoration company doing a
  restoration/cleaning service it has no page for). Never "distinct" for
  another trade.
- "junk": not a real customer-facing service for THIS company: marketing
  phrase, category label, equipment, nonsense, or a different trade that
  Google suggests on GBP listings (pest control, paving, concrete, gutters,
  pressure washing, insurance adjusting, plumbing or HVAC for a company
  with no plumbing/HVAC pages, and the like).

Also give "head_term": the 2-4 word Google search a customer would type for
that service (lowercase, no city, no "near me"). Keep "reason" under 12 words.
Return every input service exactly once, name copied verbatim.

Output JSON only:
{"services": [{"service": "...", "verdict": "map|distinct|junk", "page": null,
  "head_term": "...", "reason": "..."}]}"""


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _label(raw: str) -> str:
    s = str(raw or "").strip()
    if s.startswith("job_type_id:"):
        return s[len("job_type_id:"):].replace("_", " ").title()
    return s


def deterministic(slug: str, label: str, pages: dict, m: dict) -> dict | None:
    """Exact / catalog / cluster / containment match, or None."""
    import gbp
    n = ss.norm(label)
    if not n:
        return {"verdict": "declined", "page": None, "reason": "empty label", "source": "exact"}
    for s, p in pages.items():
        if n in (ss.norm(s), ss.norm(p["display"])):
            return {"verdict": "mapped", "page": s, "reason": "same name", "source": "exact"}
    alias = ss.alias_page(label, pages)
    if alias:
        return {"verdict": "mapped", "page": alias, "reason": "house alias", "source": "alias"}
    try:
        cslug = gbp.service_to_slug(label, slug)
    except (Exception, SystemExit):  # noqa: BLE001 -- verticals.die() on unknown clients
        cslug = None
    if cslug:
        if cslug in m.get("merged", {}):
            into = m["merged"][cslug]["into"]
            return {"verdict": "mapped", "page": into,
                    "reason": f"{cslug} was merged into {into}", "source": "merged"}
        if cslug in pages:
            return {"verdict": "mapped", "page": cslug, "reason": "catalog slug match",
                    "source": "catalog"}
        home = ss.cluster_home(slug, cslug)
        if home:
            return {"verdict": "mapped", "page": home,
                    "reason": f"same-service cluster as {home}", "source": "cluster"}
    # containment (reconcile's rule): "Mold Remediation Services" -> mold-remediation
    best = None
    for s, p in pages.items():
        for cand in {ss.norm(p["display"]), ss.norm(s)}:
            if cand and len(cand) >= 8 and (cand in n or n in cand):
                if not best or len(cand) > best[1]:
                    best = (s, len(cand))
    if best:
        return {"verdict": "mapped", "page": best[0], "reason": "name containment",
                "source": "containment"}
    return None


def classify(slug: str, labels: list[str], pages: dict) -> dict:
    """{label: {verdict, page, head_term, reason}} via ONE Claude call."""
    import gbp
    rec = ss.CLIENTS / f"{slug}.json"
    vertical = "restoration"
    if rec.exists():
        try:
            vertical = json.loads(rec.read_text()).get("vertical") or vertical
        except json.JSONDecodeError:
            pass
    payload = {"company_vertical": vertical,
               "existing_pages": [{"slug": s, "name": p["display"]} for s, p in pages.items()],
               "gbp_services": labels}
    out = gbp._anthropic_json(SYSTEM, "Map these services.\n\nDATA:\n" + json.dumps(payload),
                              model=MODEL)
    res = {}
    for row in out.get("services", []):
        name = str(row.get("service", "")).strip()
        if name not in labels:
            continue
        v = row.get("verdict")
        page = row.get("page")
        if v == "map" and page not in pages:
            # tolerate a display name instead of the slug; otherwise let the
            # volume bar judge it as a distinct service
            page = next((s for s, p in pages.items()
                         if ss.norm(str(page or "")) in (ss.norm(s), ss.norm(p["display"]))), None)
            if not page:
                v = "distinct"
        res[name] = {"verdict": v, "page": page if v == "map" else None,
                     "head_term": str(row.get("head_term") or ss.norm(name))[:60],
                     "reason": str(row.get("reason") or "")[:120]}
    return res


def resolve(slug: str, labels: list[str], apply: bool, *, force: bool = False,
            recheck: tuple = ()) -> dict:
    """Decide + persist a map entry for each label. Returns {label: entry}."""
    m = ss.load_map(slug)
    pages = ss.service_pages(slug)
    city, state = ss.metro_of(slug)
    out, pending = {}, []
    for raw in labels:
        label = _label(raw)
        prev = ss.map_lookup(m, label)
        if prev and recheck and prev.get("verdict") in recheck:
            prev = None
        if prev and not force and (prev.get("verdict") != "mapped" or prev.get("page") in pages):
            out[label] = prev
            continue
        d = deterministic(slug, label, pages, m)
        if d:
            out[label] = {**d, "at": _today()}
        else:
            pending.append(label)
    if pending:
        try:
            verdicts = classify(slug, pending, pages)
        except Exception as e:  # noqa: BLE001 -- unclassified = hold, never build blind
            print(f"   classify failed ({str(e)[:100]}): {len(pending)} held")
            verdicts = {}
        for label in pending:
            v = verdicts.get(label)
            if not v:
                out[label] = {"verdict": "held", "page": None,
                              "reason": "not classified yet", "at": _today()}
            elif v["verdict"] == "map":
                out[label] = {"verdict": "mapped", "page": v["page"], "source": "claude",
                              "reason": v["reason"], "at": _today()}
            elif v["verdict"] == "junk":
                out[label] = {"verdict": "declined", "page": None, "source": "claude",
                              "reason": "not a real service: " + v["reason"], "at": _today()}
            else:
                ok, ev = ss.clears_new_page_bar(v["head_term"], city, state)
                out[label] = {"verdict": "new_page" if ok else "declined", "page": None,
                              "source": "claude", "head_term": v["head_term"], "volume": ev,
                              "reason": (v["reason"] if ok else
                                         f"distinct but below the volume bar ({v['head_term']})"),
                              "at": _today()}
    if apply:
        for label, e in out.items():
            existing = next((k for k in m["gbp_services"] if ss.norm(k) == ss.norm(label)), label)
            m["gbp_services"][existing] = e
        ss.save_map(slug, m)
    return out


def gate(slug: str, service_label: str, *, client_request: bool = False) -> dict:
    """The create-pages drain's decision for ONE queued page request.
    Returns {action: build|map|decline|hold, page, reason}. A client/human
    request (client_request=True) skips the volume bar (no human gates on
    client requests) but still maps onto an existing page instead of
    building a duplicate."""
    e = resolve(slug, [service_label], apply=True)[_label(service_label)]
    v = e.get("verdict")
    if v == "mapped":
        return {"action": "map", "page": e.get("page"), "reason": e.get("reason")}
    if v == "new_page":
        return {"action": "build", "page": None, "reason": e.get("reason")}
    if client_request and v == "declined" and "below the volume bar" in str(e.get("reason")):
        return {"action": "build", "page": None, "reason": "client request (volume bar waived)"}
    if v == "held":
        return {"action": "hold", "page": None, "reason": e.get("reason")}
    return {"action": "decline", "page": None, "reason": e.get("reason")}


def gbp_services_for(slug: str) -> list[str] | None:
    import gbp
    rec = gbp.reconcile(slug)
    if rec.get("error"):
        print(f"   skip: {rec['error']}")
        return None
    return [_label(s) for s in rec.get("gbp", {}).get("services", [])]


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-decide existing entries")
    ap.add_argument("--recheck", default="", help="comma list of verdicts to re-decide, e.g. new_page,held")
    ap.add_argument("--from-map", action="store_true",
                    help="use the labels already in the map (no live GBP pull)")
    a = ap.parse_args()
    recheck = tuple(v for v in a.recheck.split(",") if v)
    slugs = [a.slug] if a.slug else ss.live_slugs()
    for slug in slugs:
        if not ss.plan_input_path(slug).exists():
            continue
        print(f"\n== {slug}")
        try:
            labels = (list(ss.load_map(slug)["gbp_services"]) if a.from_map
                      else gbp_services_for(slug))
        except Exception as e:  # noqa: BLE001
            print(f"   ERROR {str(e)[:140]}")
            continue
        if not labels:
            continue
        res = resolve(slug, labels, a.apply, force=a.force, recheck=recheck)
        counts: dict = {}
        for e in res.values():
            counts[e["verdict"]] = counts.get(e["verdict"], 0) + 1
        print(f"   {len(res)} GBP services -> {counts}")
        for label, e in res.items():
            if e["verdict"] != "mapped":
                print(f"   {e['verdict']:9} {label} ({e.get('reason', '')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
