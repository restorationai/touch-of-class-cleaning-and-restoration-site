#!/usr/bin/env python3
"""city_page_gate.py: CITY PAGES MUST MAKE SENSE (Santino 2026-10-01).

"I don't think it's a bad idea to do city pages for all the services, but
each page needs to make sense."

WHY: the 09-24 restoration core floor gives every water-restoration plan all
20 core-tier services, and the 09-30 nightly re-plan crossed them with every
service-area city: ~13,450 unrendered city x service placeholders (industrial
restoration in beach towns, basement flooding cleanup in Florida and Las
Vegas). Rendering them all would cost weeks and ~$500 for pages nobody
searches.

THE GATE. plan_site.py plans /service-areas/{city}/{service}/ only when ALL
of these hold:

  (i)   OFFERED. The client actually offers the service: the truth table
        (companies.services), the pre-core-floor plan-input services (intake
        + parity, git history before 2026-09-24), a non-core service listed
        explicitly in plan-input, or a GBP service in the client's OWN words
        (not one we pushed: applied ADD suggestions and labels identical to a
        catalog page name are excluded; job_type_id entries are excluded).
        A core-floor DEFAULT the client never confirmed keeps its single
        /services/{x}/ page and gets NO city pages. Stored in "offered"
        below; a client confirmation adds {slug: ["client_request ..."]}.
  (ii)  IN AREA. The city is one of the client's service areas (plan-input
        service_areas, the home city excluded as always).
  (iii) DEMAND OR LOCAL ANGLE, and PLAUSIBLE. Not judged implausible for
        that city by the per-site Claude pass (basement flooding cleanup
        where homes rarely have basements: Florida, Las Vegas, Southern
        California; industrial restoration in a small residential suburb),
        AND at least one of:
          - "{head} {city}" >= COMBO_MIN searches/mo (DataForSEO Google Ads,
            US; 10 is the smallest bucket Google reports, i.e. measurable
            local demand),
          - the head term (+ "near me") >= HEAD_METRO_MIN/mo in the
            client's metro (DataForSEO city-level location of the primary
            city),
          - a genuine local angle named by the Claude pass (industrial
            district, coastal flood zone, old housing with basements...).
        ANCHOR services pass in every service-area city with no checks:
        water damage restoration for restoration (Santino's example), the
        trade's core emergency service for plumbing.

PERSISTENCE: clients/{slug}/city-page-gate.json holds the per-combo
decisions, so the nightly re-plan never recreates a failed combo and never
pays twice. New combos (a new city or service) are decided on the fly by
plan_site (one DataForSEO batch + one Claude call per site); with no
credentials/network they are HELD (not planned, not persisted) until a run
that can decide them. src "manual" decisions are never re-decided.
RENDERED pages are never dropped by the plan: a rendered combo that fails is
kept and reported (clearly failing = implausible or not offered).

CLI:
  python3 scripts/city_page_gate.py report [--slug X]          # counts only
  python3 scripts/city_page_gate.py refresh --all               # nightly: offered + new combos
  python3 scripts/city_page_gate.py prune  --slug X [--apply]  # delete failing placeholders
  python3 scripts/city_page_gate.py prune  --all   [--apply]
prune = decide + re-plan + delete failing PLACEHOLDER location pages + strip
their links from every content file. Deploy is separate (sync-deploy).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENTS = ROOT / "clients"
SITES = ROOT / "sites"
sys.path.insert(0, str(ROOT / "scripts"))

POLICY = "scripts/city_page_gate.py (Santino 2026-10-01)"
COMBO_MIN = 10            # "{head} {city}" searches/mo
HEAD_METRO_MIN = 1000     # head + "near me" searches/mo in the client's metro
CORE_FLOOR_DATE = "2026-09-24"
SKIP = {"tdi-builders", "mcc-restoration", "mold-solutionz"}
ANCHORS = {"restoration": {"water-damage-restoration"},
           "plumbing": {"emergency-plumbing"}}
PLACEHOLDER_MARK = "Page body not yet generated"
MODEL = os.environ.get("CITY_GATE_MODEL", "claude-sonnet-5")

# search phrasing for catalog names that read badly as a query
HEAD_OVERRIDES = {
    "large-loss-response": "large loss restoration",
    "emergency-board-up-tarping": "emergency board up",
    "general-contracting": "general contractor",
    "contents-restoration-storage": "contents restoration",
    "contents-restoration": "contents restoration",
    "reconstruction": "restoration reconstruction",
    "sewage-cleanup": "sewage cleanup",
    "burst-pipe-repair": "burst pipe repair",
    "mold-inspection-testing": "mold inspection",
    "odor-removal": "odor removal",
    "emergency-water-removal": "emergency water removal",
    "water-heater-flood-cleanup": "water heater flood cleanup",
    "ceiling-water-damage-repair": "ceiling water damage repair",
}


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


# --------------------------------------------------------------------------- #
# store
# --------------------------------------------------------------------------- #
def gate_path(slug: str) -> Path:
    return CLIENTS / slug / "city-page-gate.json"


def load_gate(slug: str) -> dict:
    d: dict = {}
    try:
        d = json.loads(gate_path(slug).read_text())
    except (OSError, json.JSONDecodeError):
        d = {}
    d.setdefault("policy", POLICY)
    d.setdefault("thresholds", {"combo_min": COMBO_MIN, "head_metro_min": HEAD_METRO_MIN})
    d.setdefault("decisions", {})
    return d


def save_gate(slug: str, d: dict) -> None:
    d["decisions"] = dict(sorted(d.get("decisions", {}).items()))
    if "offered" in d:
        d["offered"] = dict(sorted(d["offered"].items()))
    p = gate_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")


def _vertical(slug: str) -> str:
    try:
        return str(json.loads((CLIENTS / f"{slug}.json").read_text()).get("vertical")
                   or "restoration")
    except (OSError, json.JSONDecodeError):
        return "restoration"


def _catalog(slug: str) -> dict:
    import verticals
    cat = json.loads(Path(verticals.resolve_template(slug, "services.json")).read_text())
    return {s["slug"]: s for s in cat["services"]}


def head_term(service: dict) -> str:
    sl = service.get("slug", "")
    if sl in HEAD_OVERRIDES:
        return HEAD_OVERRIDES[sl]
    try:
        import site_structure as ss
        c = ss.cluster_of(sl)
        if c:
            return next(h for s, h, _ in c["members"] if s == sl)
    except Exception:  # noqa: BLE001
        pass
    name = str(service.get("display_name") or sl.replace("-", " ")).lower()
    name = re.sub(r"[^a-z0-9 ]+", " ", name)
    return " ".join(name.split())


# --------------------------------------------------------------------------- #
# (i) offered services
# --------------------------------------------------------------------------- #
def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout


def pre_floor_services(slug: str) -> list[str]:
    """plan-input services before the core floor existed (or the first
    committed version for a client created after it)."""
    path = f"clients/{slug}/plan-input.json"
    rev = _git("rev-list", "-1", f"--before={CORE_FLOOR_DATE}", "HEAD", "--", path).strip()
    if not rev:
        revs = _git("rev-list", "--reverse", "HEAD", "--", path).split()
        rev = revs[0] if revs else ""
    if not rev:
        return []
    try:
        return list(json.loads(_git("show", f"{rev}:{path}")).get("services") or [])
    except json.JSONDecodeError:
        return []


def compute_offered(slug: str, plan_input: dict) -> dict[str, list[str]]:
    """{service_slug: [evidence, ...]} from every confirmation source.
    Needs Supabase for the truth table + GBP sources (skipped when absent)."""
    cat = _catalog(slug)
    out: dict[str, list[str]] = {}

    def add(s: str, why: str) -> None:
        if s in cat:
            out.setdefault(s, [])
            if why not in out[s]:
                out[s].append(why)

    for s in pre_floor_services(slug):
        add(s, f"plan-input before core floor ({CORE_FLOOR_DATE})")
    for s in plan_input.get("services") or []:
        if (cat.get(s) or {}).get("tier") != "core":
            add(s, "explicit non-core plan-input service")
    for s, why in (load_gate(slug).get("offered") or {}).items():
        for w in why:
            if str(w).startswith(("client_request", "manual")):
                add(s, w)
    try:
        from client_ops_sync import _sb
        from work_log import company_id_for_slug
        cid = company_id_for_slug(slug)
        if cid:
            co = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}&select=services") or [{}])[0]
            truth = co.get("services") or []
            if isinstance(truth, str):
                truth = [t.strip() for t in truth.split(",")]
            if truth:
                from service_ripple import map_services
                for s in map_services(slug, truth)[0]:
                    add(s, "truth table (companies.services)")
            prof = (_sb("GET", f"/rest/v1/marketing_gbp_profiles?company_id=eq.{cid}"
                        "&select=services") or [{}])[0].get("services") or []
            ours = {r["item"].strip().lower() for r in (_sb(
                "GET", f"/rest/v1/marketing_gbp_suggestions?company_id=eq.{cid}"
                "&item_type=eq.service&status=eq.applied&select=item&limit=5000") or [])}
            import site_structure as ss
            names = {ss.norm(v.get("display_name", "")) for v in cat.values()} | \
                {ss.norm(k.replace("-", " ")) for k in cat} | _bank_names()
            m = ss.load_map(slug)
            for raw in prof:
                raw = str(raw or "").strip()
                if not raw or raw.lower().startswith("job_type_id:") or raw.lower() in ours:
                    continue
                if ss.norm(raw) in names:
                    continue   # a catalog page name / service-bank name: our own push
                e = ss.map_lookup(m, raw) or {}
                # deterministic matches only: a Claude "long-tail of" mapping
                # ("Painting" -> general contracting) is not proof of the service
                if (e.get("verdict") == "mapped" and e.get("page")
                        and e.get("source") in ("exact", "alias", "catalog", "cluster",
                                                "containment", "merged")):
                    add(e["page"], f"GBP service in the client's words: {raw!r}")
    except Exception as e:  # noqa: BLE001 -- partial evidence beats none
        print(f"  {slug}: offered sources partial ({str(e)[:100]})")
    # Emergency water removal is Santino's 09-30 default for every water
    # damage client (same work, its own high-volume query), not a floor guess.
    if "water-damage-restoration" in out and "emergency-water-removal" in cat:
        add("emergency-water-removal", "default with water damage restoration (Santino 09-30)")
    return dict(sorted(out.items()))


def _bank_names() -> set[str]:
    import site_structure as ss
    out: set[str] = set()
    for p in (ROOT / "templates").glob("*/service-bank.json"):
        try:
            fams = json.loads(p.read_text()).get("families") or {}
        except (OSError, json.JSONDecodeError):
            continue
        for fam in fams.values():
            for v in (fam.get("variants") if isinstance(fam, dict) else fam) or []:
                out.add(ss.norm(v.get("name", "")))
    return out


def offered_services(slug: str, inputs: dict, floor_added: set) -> set[str]:
    """Offline view for plan_site: the stored confirmations + any explicit
    non-core service. No stored set yet (new client): explicit plan-input
    services minus what the core floor added in memory."""
    g = load_gate(slug)
    explicit = set(inputs.get("_explicit_services") or [])
    planned = {s["slug"] for s in inputs["services"]}
    if "offered" in g:
        cat_tier = {s["slug"]: s.get("tier") for s in inputs["services"]}
        return (set(g["offered"]) | {s for s in explicit if cat_tier.get(s) != "core"}) & planned
    return (explicit - set(floor_added)) & planned


# --------------------------------------------------------------------------- #
# (iii) demand + plausibility
# --------------------------------------------------------------------------- #
def _dfs(terms: list[str], location_name: str | None) -> dict[str, int]:
    """Google Ads search volume. Raises on any task failure (never reports a
    failed call as zero demand)."""
    import requests
    import gbp
    from gbp_name_suggest import DFS_VOLUME
    creds = gbp._dfs_auth()
    if not creds:
        raise RuntimeError("no DataForSEO credentials")
    auth = base64.b64encode(f"{creds[0]}:{creds[1]}".encode()).decode()
    out: dict[str, int] = {}
    terms = sorted({t for t in terms if t and len(t) <= 80})
    for i in range(0, len(terms), 900):
        chunk = terms[i:i + 900]
        body = {"keywords": chunk, "language_code": "en"}
        body.update({"location_name": location_name} if location_name else {"location_code": 2840})
        r = requests.post(DFS_VOLUME, json=[body], timeout=120,
                          headers={"Authorization": "Basic " + auth})
        r.raise_for_status()
        task = (r.json().get("tasks") or [{}])[0]
        if int(task.get("status_code") or 0) != 20000:
            raise RuntimeError(f"DataForSEO {task.get('status_code')}: {task.get('status_message')}")
        for it in task.get("result") or []:
            if isinstance(it, dict):
                out[str(it.get("keyword", "")).lower()] = int(it.get("search_volume") or 0)
    return {t: out.get(t.lower(), 0) for t in terms}


JUDGE_SYSTEM = """You decide whether a local landing page "{service} in {city}"
makes sense on a property-damage restoration (or trade) company's website.
Judge each service against each listed service-area city of THIS company.

Return two kinds of exceptions per service; every city you do not list is
"plausible but nothing special" (it then needs measurable search demand):

- "implausible": the page would not make sense in that city because the
  service barely exists there. Examples: basement flooding cleanup where
  homes rarely have basements (Florida, Gulf Coast, most of Texas, Las
  Vegas, Phoenix, Southern California); industrial restoration in a small
  residential suburb, beach town or rural village with no industrial base;
  commercial restoration or large-loss response in a tiny residential town;
  frozen-pipe services where it never freezes hard; hurricane services far
  inland. NEVER implausible on climate alone for burst pipes, leaks, water
  heaters, ceilings, sewage, mold, fire or smoke: those happen everywhere
  (pipes burst from age, pressure and corrosion, not only frost).
- "angle": a SPECIFIC, concrete local reason the service is unusually
  relevant in that city: an industrial or port district (industrial
  restoration), a large commercial or office base (commercial restoration,
  large loss), older housing stock with basements (basement flooding),
  a river, coastal or mapped flood zone (flood damage), hurricane exposure
  (storm damage), a hot humid climate (mold), hard freezes (burst pipes).
  Being an ordinary residential town is NOT an angle. Do not list a city
  as both.

Reasons: at most 8 words. Use the exact service and city slugs given.
Output JSON only:
{"services": {"<service_slug>": {"implausible": {"<city_slug>": "reason"},
                                  "angle": {"<city_slug>": "reason"}}}}"""


def _judge(slug: str, services: list[dict], areas: list[dict]) -> dict:
    """{service_slug: {"implausible": {...}, "angle": {...}}}; one Claude call
    per site (chunked by service when the grid is large)."""
    import gbp
    out: dict = {}
    per = max(1, 700 // max(1, len(areas)))
    for i in range(0, len(services), per):
        chunk = services[i:i + per]
        payload = {"company": slug, "vertical": _vertical(slug),
                   "services": [{"slug": s["slug"], "name": s.get("display_name")} for s in chunk],
                   "cities": [{"slug": a["slug"], "city": a["city"], "state": a["state"]}
                              for a in areas]}
        res = gbp._anthropic_json(JUDGE_SYSTEM, "Judge these.\n\nDATA:\n" + json.dumps(payload),
                                  model=MODEL)
        for k, v in (res.get("services") or {}).items():
            if isinstance(v, dict):
                out[k] = {"implausible": dict(v.get("implausible") or {}),
                          "angle": dict(v.get("angle") or {})}
    return out


def decide(slug: str, combos: list[tuple[dict, dict]], *, write: bool = True) -> dict:
    """Decide (iii) for (area, service) combos and persist. Returns the
    decisions written. Raises when DataForSEO or Claude is unavailable, so a
    failed call can never persist as 'no demand'."""
    g = load_gate(slug)
    anchors = ANCHORS.get(_vertical(slug), set())
    todo = [(a, s) for a, s in combos if s["slug"] not in anchors]
    new: dict = {}
    for a, s in combos:
        if s["slug"] in anchors:
            new[f"{a['slug']}__{s['slug']}"] = {"pass": True, "why": "anchor service (every service-area city)",
                                               "src": "auto", "at": _today()}
    if todo:
        services = list({s["slug"]: s for _, s in todo}.values())
        areas = list({a["slug"]: a for a, _ in todo}.values())
        heads = {s["slug"]: head_term(s) for s in services}
        combo_terms = {(a["slug"], s["slug"]): f"{heads[s['slug']]} {a['city'].lower()}"
                       for a, s in todo}
        # METRO = the service-area city people search the trade's anchor term
        # in most ("water damage restoration {city}"), so a client whose
        # office sits in a small town (DryCor: Thonotosassa) is measured
        # against its real metro (Tampa). Ties/no data -> the primary city.
        pi = json.loads((CLIENTS / slug / "plan-input.json").read_text())
        all_areas = pi.get("service_areas") or []
        anchor_head = {"plumbing": "plumber"}.get(_vertical(slug), "water damage restoration")
        anchor_terms = {f"{anchor_head} {x.get('city', '').lower()}": x for x in all_areas
                        if x.get("city")}
        vol = _dfs(list(combo_terms.values()) + list(anchor_terms), None)
        prim = next((x for x in all_areas if x.get("primary")), (all_areas or [{}])[0])
        best = max(anchor_terms, key=lambda t: vol.get(t, 0), default=None)
        if best and vol.get(best, 0) > vol.get(f"{anchor_head} {str(prim.get('city', '')).lower()}", 0):
            prim = anchor_terms[best]
        metro_vol: dict = {}
        try:
            from gbp_name_suggest import metro_location
            loc = metro_location(prim.get("city"), prim.get("state"))
            if loc:
                hv = _dfs([t for h in heads.values() for t in (h, f"{h} near me")], loc)
                metro_vol = {sl: hv.get(h, 0) + hv.get(f"{h} near me", 0) for sl, h in heads.items()}
                g["metro"] = loc
        except Exception as e:  # noqa: BLE001 -- the head route is optional
            print(f"  {slug}: metro volumes unavailable ({str(e)[:80]})")
        judged = _judge(slug, services, areas)
        g["heads"] = {**(g.get("heads") or {}),
                      **{sl: {"term": h, "metro": metro_vol.get(sl)} for sl, h in heads.items()}}
        for a, s in todo:
            key = f"{a['slug']}__{s['slug']}"
            j = judged.get(s["slug"]) or {}
            v = vol.get(combo_terms[(a["slug"], s["slug"])], 0)
            imp = (j.get("implausible") or {}).get(a["slug"])
            ang = (j.get("angle") or {}).get(a["slug"])
            hm = metro_vol.get(s["slug"]) or 0
            if imp:
                ok, why = False, f"implausible here: {imp}"
            elif v >= COMBO_MIN:
                ok, why = True, f"local demand: '{combo_terms[(a['slug'], s['slug'])]}' {v}/mo"
            elif hm >= HEAD_METRO_MIN:
                ok, why = True, f"metro demand: '{heads[s['slug']]}' {hm}/mo"
            elif ang:
                ok, why = True, f"local angle: {ang}"
            else:
                ok, why = False, (f"no local demand ('{combo_terms[(a['slug'], s['slug'])]}' "
                                  f"{v}/mo) and no local angle")
            new[key] = {"pass": ok, "why": why, "vol": v, "src": "auto", "at": _today(),
                        **({"implausible": True} if imp else {})}
    if write:
        g = {**load_gate(slug), **{k: v for k, v in g.items() if k in ("heads", "metro")}}
        for k, v in new.items():
            if (g["decisions"].get(k) or {}).get("src") == "manual":
                continue
            g["decisions"][k] = v
        g["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        save_gate(slug, g)
    return new


# --------------------------------------------------------------------------- #
# plan hook
# --------------------------------------------------------------------------- #
def _location_file(slug: str, area: str, service: str) -> Path:
    return SITES / slug / "src" / "content" / "locations" / f"{area}__{service}.md"


def is_rendered(path: Path) -> bool:
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return False
    fm = text.split("\n---", 1)[0] if text.startswith("---") else text[:4000]
    return bool(re.search(r"^rendered:\s*true\b", fm, re.M)) and PLACEHOLDER_MARK not in text


def plan_filter(slug: str, inputs: dict, floor_added: set, ring: list[dict],
                *, online: bool = True) -> set | None:
    """The set of (area_slug, service_slug) the plan may carry, or None to
    leave the cross-product untouched (skipped clients)."""
    if not slug or slug in SKIP:
        return None
    anchors = ANCHORS.get(_vertical(slug), set())
    offered = offered_services(slug, inputs, floor_added)
    g = load_gate(slug)
    if "offered" not in g:
        # first contact: persist the offline baseline so later floor additions
        # can never masquerade as confirmed services
        g["offered"] = {s: ["explicit plan-input service at gate creation"] for s in sorted(offered)}
        save_gate(slug, g)
    allowed: set = set()
    undecided = []
    for a in ring:
        for s in inputs["services"]:
            sl = s["slug"]
            key = f"{a['slug']}__{sl}"
            rendered = is_rendered(_location_file(slug, a["slug"], sl))
            if sl in anchors and sl in {x["slug"] for x in inputs["services"]}:
                allowed.add((a["slug"], sl))
                continue
            if sl not in offered:
                if rendered:
                    allowed.add((a["slug"], sl))   # grandfathered; reported by `report`
                continue
            d = g["decisions"].get(key)
            if d is None:
                undecided.append((a, s))
                if rendered:
                    allowed.add((a["slug"], sl))
                continue
            if d.get("pass") or rendered:
                allowed.add((a["slug"], sl))
    if undecided and online:
        try:
            got = decide(slug, undecided)
            for k, d in got.items():
                if d.get("pass"):
                    area, sl = k.split("__", 1)
                    allowed.add((area, sl))
            print(f"  city-gate: decided {len(got)} new combo(s), "
                  f"{sum(1 for d in got.values() if d.get('pass'))} pass")
        except Exception as e:  # noqa: BLE001 -- hold, never plan blind
            print(f"  city-gate: {len(undecided)} new combo(s) HELD, not planned "
                  f"(decision unavailable: {str(e)[:100]})")
    elif undecided:
        print(f"  city-gate: {len(undecided)} undecided combo(s) held (offline)")
    total = len(ring) * len(inputs["services"])
    print(f"  city-gate: {len(allowed)}/{total} city x service pages make sense "
          f"({len(offered)} offered service(s) of {len(inputs['services'])})")
    return allowed


# --------------------------------------------------------------------------- #
# prune existing placeholders
# --------------------------------------------------------------------------- #
LOC_URL_RE = re.compile(r"/service-areas/([a-z0-9-]+)/([a-z0-9-]+)/?(?=[\"')\s#?]|$)")
TEXT_EXT = {".md", ".mdx", ".astro", ".ts", ".tsx", ".js", ".mjs", ".json"}


def rewrite_dead_links(slug: str, dead: dict[str, str], apply: bool) -> int:
    """dead = {"/service-areas/{c}/{s}/": replacement URL}. Rewrites page
    links everywhere under src (frontmatter internal_links included), then
    dedupes internal_links + drops self-links."""
    import service_merge as sm
    site = SITES / slug
    touched = set()
    for p in (site / "src").rglob("*"):
        if not p.is_file() or p.suffix not in TEXT_EXT:
            continue
        try:
            text = p.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if "/service-areas/" not in text:
            continue

        def _sub(mm: re.Match) -> str:
            url = f"/service-areas/{mm.group(1)}/{mm.group(2)}/"
            return dead.get(url, mm.group(0))
        new = LOC_URL_RE.sub(_sub, text)
        if new != text:
            touched.add(p)
            if apply:
                p.write_text(new)
    if apply and touched:
        sm.dedupe_internal_links(site, apply=True, only=touched)
    return len(touched)


def replacement_for(slug: str, area: str, service: str, remaining: set[str]) -> str:
    """Where a link to a removed city page should point: the city's hub
    page, else the service page."""
    if f"/service-areas/{area}/" in remaining:
        return f"/service-areas/{area}/"
    return f"/services/{service}/" if f"/services/{service}/" in remaining else "/service-areas/"


def site_urls(slug: str) -> set[str]:
    base = SITES / slug / "src" / "content"
    out = set()
    for p in (base / "services").glob("*.md"):
        out.add(f"/services/{p.stem}/")
    for p in (base / "serviceAreas").glob("*.md"):
        out.add(f"/service-areas/{p.stem}/")
    for p in (base / "locations").glob("*.md"):
        if "__" in p.stem:
            a, s = p.stem.split("__", 1)
            out.add(f"/service-areas/{a}/{s}/")
    return out


def prune(slug: str, apply: bool, redecide: bool = False) -> dict:
    """Decide every existing + planned combo, re-plan, delete failing
    placeholders, strip their links. Rendered failures are reported only."""
    import render_sweep
    pi = json.loads((CLIENTS / slug / "plan-input.json").read_text())
    before = render_sweep.pending_pages(slug)
    g = load_gate(slug)
    g["offered"] = compute_offered(slug, pi)
    if apply:
        save_gate(slug, g)
    if redecide and apply:
        g = load_gate(slug)
        g["decisions"] = {k: v for k, v in g["decisions"].items() if v.get("src") == "manual"}
        save_gate(slug, g)
    # re-plan (plan_filter decides every new combo through decide()). No
    # scaffolding here: pruning never adds pages (the nightly add-pages does)
    if apply:
        rc = subprocess.run([sys.executable, str(ROOT / "scripts" / "plan_site.py"),
                             "generate", "--slug", slug], capture_output=True, text=True)
        tail = "\n".join(l for l in rc.stdout.splitlines() if "city-gate" in l or "plumb" in l)
        print(tail)
        if rc.returncode != 0:
            raise RuntimeError(f"plan_site failed: {rc.stderr[-300:]}")
    plan = json.loads((CLIENTS / slug / "plan" / "url-plan.json").read_text())
    planned = {p["url_path"] for p in plan["pages"]}
    loc_dir = SITES / slug / "src" / "content" / "locations"
    delete, keep_rendered_fail, kept_ph = [], [], 0
    decisions = load_gate(slug)["decisions"]
    offered = set(load_gate(slug).get("offered") or {})
    for f in sorted(loc_dir.glob("*__*.md")) if loc_dir.is_dir() else []:
        a, s = f.stem.split("__", 1)
        url = f"/service-areas/{a}/{s}/"
        rendered = is_rendered(f)
        if url in planned:
            if not rendered:
                kept_ph += 1
            else:
                d = decisions.get(f.stem) or {}
                if d.get("implausible") or (s not in offered and s not in
                                            ANCHORS.get(_vertical(slug), set())):
                    keep_rendered_fail.append({"url": url, "why": d.get("why")
                                               or "service not confirmed as offered"})
            continue
        if rendered:
            keep_rendered_fail.append({"url": url, "why": "rendered page outside the plan"})
            continue
        delete.append(f)
    remaining = site_urls(slug) - {f"/service-areas/{f.stem.split('__')[0]}/{f.stem.split('__')[1]}/"
                                   for f in delete}
    dead = {}
    for f in delete:
        a, s = f.stem.split("__", 1)
        dead[f"/service-areas/{a}/{s}/"] = replacement_for(slug, a, s, remaining)
    relinked = 0
    if apply:
        for f in delete:
            f.unlink()
        relinked = rewrite_dead_links(slug, dead, apply=True)
    after = render_sweep.pending_pages(slug)
    return {"slug": slug, "pending_before": before, "placeholders_deleted": len(delete),
            "placeholders_kept": kept_ph, "pending_after": after if apply else before - len(delete),
            "rendered_failing_kept": keep_rendered_fail, "files_relinked": relinked}


def report(slug: str) -> dict:
    g = load_gate(slug)
    d = g.get("decisions") or {}
    return {"slug": slug, "offered": len(g.get("offered") or {}),
            "decided": len(d), "pass": sum(1 for v in d.values() if v.get("pass")),
            "fail": sum(1 for v in d.values() if not v.get("pass"))}


def fleet() -> list[str]:
    out = []
    for p in sorted(SITES.iterdir()):
        if not (p / "src").is_dir() or p.name in SKIP:
            continue
        if not (CLIENTS / p.name / "plan-input.json").exists():
            continue
        try:
            st = str(json.loads((CLIENTS / f"{p.name}.json").read_text()).get("status") or "").lower()
        except (OSError, json.JSONDecodeError):
            st = ""
        if st in ("paused", "suspended", "inactive", "cancelled", "dead"):
            continue
        out.append(p.name)
    return out


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["report", "refresh", "prune"])
    ap.add_argument("--slug")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--redecide", action="store_true")
    a = ap.parse_args()
    slugs = [a.slug] if a.slug else fleet()
    for slug in slugs:
        if a.cmd == "report":
            print(json.dumps(report(slug)))
        elif a.cmd == "prune":
            try:
                r = prune(slug, a.apply, a.redecide)
            except Exception as e:  # noqa: BLE001 -- one site never stops the fleet
                print(json.dumps({"slug": slug, "error": str(e)[:300]}))
                continue
            fails = r.pop("rendered_failing_kept")
            print(json.dumps({**r, "rendered_failing_kept": len(fails)}), flush=True)
            for x in fails[:40]:
                print(f"    RENDERED, fails gate (kept): {x['url']}  {x['why']}")
        elif a.cmd == "refresh":
            try:
                print(json.dumps(refresh(slug)), flush=True)
            except Exception as e:  # noqa: BLE001
                print(json.dumps({"slug": slug, "error": str(e)[:300]}), flush=True)
    return 0


def refresh(slug: str) -> dict:
    """Nightly (client-ops-sync): re-derive the offered set (truth table and
    GBP change) and decide every undecided offered combo, so plan runs in
    steps without DataForSEO/Claude credentials still plan from stored
    decisions. Never re-decides an existing decision."""
    from plan_site import normalize_service_area
    pi = json.loads((CLIENTS / slug / "plan-input.json").read_text())
    g = load_gate(slug)
    old = set(g.get("offered") or {})
    g["offered"] = compute_offered(slug, pi)
    save_gate(slug, g)
    cat = _catalog(slug)
    ring = [normalize_service_area(dict(x)) for x in pi.get("service_areas") or []]
    ring = [x for x in ring if not x.get("primary")] if any(x.get("primary") for x in ring) \
        else ring[1:]
    anchors = ANCHORS.get(_vertical(slug), set())
    todo = [(x, cat[sv]) for x in ring for sv in g["offered"]
            if sv in cat and sv not in anchors
            and f"{x['slug']}__{sv}" not in g["decisions"]]
    got = decide(slug, todo) if todo else {}
    return {"slug": slug, "offered": len(g["offered"]),
            "offered_added": sorted(set(g["offered"]) - old),
            "offered_removed": sorted(old - set(g["offered"])),
            "decided": len(got), "pass": sum(1 for d in got.values() if d.get("pass"))}


if __name__ == "__main__":
    sys.exit(main())
