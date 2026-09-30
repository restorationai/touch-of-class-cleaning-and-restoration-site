#!/usr/bin/env python3
"""site_structure.py — the site-structure policy, in one place (Santino 2026-09-30).

WHY: the GBP parity engine and the restoration core floor kept adding service
pages, and three things went wrong: GBP phrasings ("Emergency Water Removal",
"Board Up Services") became their own pages, near-duplicate pages shipped
side by side (Dry1 Out: /services/emergency-board-up/ AND
/services/emergency-board-ups/), and parity-added services took over the
homepage strip (ProRestoration showed Roofing and Commercial Restoration on
the homepage of a restoration-first company). The rules:

  1. GBP SERVICE MAP. Every GBP service maps to an EXISTING site service page
     when it is a synonym or long-tail of it. The map lives per client in
     clients/{slug}/gbp-service-map.json (built by scripts/gbp_service_map.py:
     deterministic name/cluster match first, then one Claude classification
     call + DataForSEO volumes). A mapped GBP service NEVER creates a page.
     The GBP can carry 100-200 long-tail services; the site stays lean.
  2. NEW PAGE BAR. A new dedicated page only for a genuinely distinct service
     the client really offers (GBP / truth table / plan-input) whose head term
     clears the volume bar: >= NEW_PAGE_METRO_MIN searches/mo in the client's
     city (DataForSEO Google Ads search_volume), or, when the city only shows
     DataForSEO's floor bucket (<= 10), >= NEW_PAGE_NATIONAL_MIN nationally
     for the head term plus its "near me" form. At most
     MAX_NEW_PAGES_PER_NIGHT new service pages per client per night; the
     rest wait in the queue.
  3. HOMEPAGE = CURATED CORE. The homepage services strip renders
     plan-input "homepage_services" (pinned, ordered), mirrored into
     sites/{slug}/src/data/homepage-services.json. Parity and core-floor
     pages still get /services/ and internal links, never the homepage.
  4. NO DUPLICATE PAGES. Pages in the same SERVICE_CLUSTERS group are one
     service in different words. A "variant" member (plural, 24/7, emergency,
     combined name) always merges (301) into the canonical page. A
     non-variant member (a different query for the same work) stays only
     when its head term plus "near me" reaches DUP_KEEP_NATIONAL_MIN
     searches/mo nationally; the kept pair and its volumes are recorded in
     the client's gbp-service-map.json. Merges run through
     scripts/service_merge.py (static 301s, link rewrite, plan-input
     merged_services so the nightly never rebuilds them). ON HOLD since
     09-30 pending Santino's review of the first 75; run only on his call.
  5. WATER REMOVAL (Santino 09-30): "get the water out now" (emergency
     water removal, water extraction, water removal, water cleanup) is ONE
     dedicated page, /services/emergency-water-removal/ ("Emergency Water
     Removal & Cleanup in {City}"), separate from water damage restoration.
     water-cleanup was renamed into it (scripts/water_removal_rollout.py).

City-level DataForSEO volumes floor at 10/mo for almost every restoration
term (Bakersfield: "water damage restoration" 30, everything else 10), so
they cannot separate a real query from a dead one; that is why the duplicate
bar is national.

scripts/site_structure_audit.py reports all four per site.
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITES = ROOT / "sites"
CLIENTS = ROOT / "clients"

DEAD_CLIENTS = {"mcc-restoration", "mold-solutionz"}

# ---- thresholds (mirrored in docs/ROADMAP-STATUS.md standing rules) ----
NEW_PAGE_METRO_MIN = 20          # searches/mo in the client's city
NEW_PAGE_NATIONAL_MIN = 5000     # head + "near me", when the city shows only the floor bucket
DUP_KEEP_NATIONAL_MIN = 10000    # head + "near me": a non-variant twin page keeps its own URL
MAX_NEW_PAGES_PER_NIGHT = 2      # new service pages per client per night
HOMEPAGE_MAX = 6
METRO_FLOOR = 10                 # DataForSEO's smallest city bucket = no usable signal

# ---- same-service clusters. Members are (slug, head_term, variant).
# Canonical = the first member present on the site that is rendered (falls
# back to the first present). Only phrasing variants of ONE service belong
# here; related-but-different services (flood vs water damage, commercial vs
# industrial) are NOT clusters.
SERVICE_CLUSTERS: list[dict] = [
    # Santino 09-30: "get the water out now" is its own page, separate from
    # water damage restoration; water-cleanup was renamed into it.
    {"name": "water damage", "members": [
        ("water-damage-restoration", "water damage restoration", False),
        ("24-7-emergency-water-damage-restoration", "24 hour water damage restoration", True),
    ]},
    {"name": "water removal", "members": [
        ("emergency-water-removal", "emergency water removal", False),
        ("water-cleanup", "water cleanup", True),
        ("24-7-emergency-water-cleanup", "emergency water cleanup", True),
    ]},
    {"name": "air duct cleaning", "members": [
        ("air-duct-cleaning", "air duct cleaning", False),
        ("air-duct-hvac-cleaning", "air duct and hvac cleaning", True),
        ("air-duct-cleaning-service", "air duct cleaning service", True),
    ]},
    {"name": "carpet cleaning", "members": [
        ("carpet-cleaning", "carpet cleaning", False),
        ("carpet-upholstery-cleaning", "carpet and upholstery cleaning", True),
    ]},
    {"name": "basement flooding", "members": [
        ("basement-flooding-cleanup", "basement flooding cleanup", False),
        ("basement-flood-cleanup", "basement flood cleanup", True),
        ("basement-water-cleanup", "basement water cleanup", True),
    ]},
    {"name": "sewage cleanup", "members": [
        ("sewage-cleanup", "sewage cleanup", False),
        ("basement-sewage-cleanup", "basement sewage cleanup", True),
        ("emergency-sewage-cleanup", "emergency sewage cleanup", True),
        ("category-3-water-cleanup", "category 3 water cleanup", True),
    ]},
    {"name": "burst pipes", "members": [
        ("burst-pipe-repair", "burst pipe repair", False),
        ("burst-pipe-water-damage-cleanup", "burst pipe water damage", True),
        ("burst-frozen-pipes", "burst frozen pipes", True),
    ]},
    {"name": "contents restoration", "members": [
        ("contents-restoration", "contents restoration", False),
        ("contents-restoration-storage", "contents restoration", True),
        ("contents-restoration-pack-out", "contents pack out", True),
        ("content-recovery", "content recovery", True),
    ]},
    {"name": "board-up", "members": [
        ("emergency-board-up-tarping", "emergency board up", False),
        ("emergency-board-up", "emergency board up", True),
        ("emergency-board-ups", "emergency board ups", True),
        ("emergency-tarping", "emergency tarping", False),
    ]},
    {"name": "general contracting", "members": [
        ("general-contracting", "general contracting", False),
        ("general-contractor", "general contractor", True),
        ("job-type-id-construction", "construction company", True),
    ]},
    {"name": "remodeling", "members": [
        ("home-remodeling", "home remodeling", False),
        ("remodeler", "remodeler", True),
    ]},
    {"name": "bathroom remodeling", "members": [
        ("bathroom-remodeling", "bathroom remodeling", False),
        ("bathroom-remodeler", "bathroom remodeler", True),
        ("job-type-id-bathroom-remodeling", "bathroom remodeling", True),
    ]},
    {"name": "basement remodeling", "members": [
        ("basement-remodeling", "basement remodeling", False),
        ("job-type-id-basement-remodeling", "basement remodeling", True),
    ]},
    {"name": "mold inspection", "members": [
        ("mold-inspection-testing", "mold inspection", False),
        ("mold-inspection-assessment", "mold assessment", True),
    ]},
    {"name": "post-construction cleaning", "members": [
        ("post-construction-cleaning", "post construction cleaning", False),
        ("post-construction-specialty-cleaning", "post construction cleaning", True),
    ]},
    {"name": "vandalism", "members": [
        ("vandalism-cleanup", "vandalism cleanup", False),
        ("vandalism-graffiti-removal", "graffiti removal", False),
        ("vandalism-damage-cleanup-and-repair", "vandalism repair", True),
    ]},
    {"name": "leak detection", "members": [
        ("water-leak-detection", "water leak detection", False),
        ("leak-detection", "leak detection", True),
    ]},
    {"name": "slab leak", "members": [
        ("slab-leak-repair", "slab leak repair", False),
        ("slab-leak-and-pipe-repair", "slab leak and pipe repair", True),
    ]},
    {"name": "smoke damage", "members": [
        ("smoke-damage-restoration", "smoke damage restoration", False),
        ("smoke-damage-cleaning", "smoke damage cleaning", True),
        ("soot-removal", "soot removal", False),
    ]},
    {"name": "storm damage", "members": [
        ("storm-damage-restoration", "storm damage restoration", False),
        ("hurricane-damage-restoration", "hurricane damage restoration", False),
    ]},
    {"name": "odor removal", "members": [
        ("odor-removal", "odor removal", False),
        ("odor-control", "odor control", True),
        ("odor-control-deodorization", "odor control", True),
    ]},
    {"name": "appliance leaks", "members": [
        ("appliance-leak-cleanup", "appliance leak cleanup", False),
        ("water-heater-flood-cleanup", "water heater flood cleanup", False),
    ]},
    {"name": "sewer camera", "members": [
        ("sewer-camera-inspection", "sewer camera inspection", False),
        ("camera-inspections-of-drain-and-sewer-line", "drain camera inspection", True),
    ]},
    {"name": "emergency plumbing", "members": [
        ("emergency-plumbing", "emergency plumber", False),
        ("common-plumbing-emergencies", "plumbing emergencies", True),
    ]},
    {"name": "indoor air quality", "members": [
        ("indoor-air-quality-testing", "indoor air quality testing", False),
        ("indoor-air-quality", "indoor air quality", True),
    ]},
    {"name": "decks", "members": [
        ("decks-pergolas-fences", "deck builder", False),
        ("deck-construction", "deck construction", True),
    ]},
    {"name": "windows", "members": [
        ("windows-doors", "windows and doors", False),
        ("windows", "window installation", True),
    ]},
]

PLACEHOLDER_MARK = "Page body not yet generated"

# House mappings for common GBP phrasings (Santino's examples, 2026-09-30):
# checked before any fuzzy/Claude step. First candidate page present wins.
GBP_ALIASES: list[tuple[str, list[str]]] = [
    # 09-30: water cleanup / removal / extraction -> the emergency water
    # removal page (falls back to water damage restoration where absent)
    (r"^(24 7 )?(emergency )?water (removal|extraction|clean ?up)$|^standing water removal$",
     ["emergency-water-removal", "water-damage-restoration"]),
    (r"^water mitigation$", ["water-damage-restoration"]),
    (r"\bboard[- ]?ups?\b|\btarping\b",
     ["emergency-board-up-tarping", "emergency-board-up"]),
    # review fixes 09-30: wet carpet is water damage, not carpet cleaning;
    # mold removal anywhere (crawl space, attic, "mold and odor") is remediation
    (r"\bwet carpet\b|\bcarpet water damage\b",
     ["water-damage-restoration"]),
    (r"\bmold (removal|remediation|cleanup|cleaning|mitigation)\b|\bmold and odor\b",
     ["mold-remediation"]),
]


def alias_page(label: str, pages: dict) -> str | None:
    n = norm(label)
    for pat, cands in GBP_ALIASES:
        if re.search(pat, n):
            for c in cands:
                if c in pages:
                    return c
    return None


# --------------------------------------------------------------------------- #
# site + plan readers
# --------------------------------------------------------------------------- #
def live_slugs() -> list[str]:
    return sorted(p.name for p in SITES.iterdir()
                  if (p / "src").is_dir() and p.name not in DEAD_CLIENTS)


def plan_input_path(slug: str) -> Path:
    return CLIENTS / slug / "plan-input.json"


def load_plan_input(slug: str) -> dict:
    p = plan_input_path(slug)
    return json.loads(p.read_text()) if p.exists() else {}


def save_plan_input(slug: str, pi: dict) -> None:
    """Keep the file's existing escaping style (literal UTF-8 vs \\u escapes)
    so a one-key change is a one-key diff."""
    p = plan_input_path(slug)
    old = p.read_text() if p.exists() else ""
    literal = any(ord(ch) > 127 for ch in old)
    p.write_text(json.dumps(pi, indent=2, ensure_ascii=not literal) + "\n")


def _frontmatter(text: str) -> dict:
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    out: dict = {}
    if not m:
        return out
    for line in m.group(1).splitlines():
        mm = re.match(r"^(\w+):\s*(.*)$", line)
        if mm:
            out[mm.group(1)] = mm.group(2).strip().strip('"')
    return out


def service_pages(slug: str) -> dict[str, dict]:
    """{service_slug: {title, h1, display, priority, rendered, path}} for
    every /services/{x}/ page (content collection = routing)."""
    out: dict[str, dict] = {}
    d = SITES / slug / "src" / "content" / "services"
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.md")):
        text = f.read_text(errors="replace")
        fm = _frontmatter(text)
        try:
            pr = float(fm.get("priority") or 0)
        except ValueError:
            pr = 0.0
        disp = fm.get("service_display") or ""
        if not disp or disp == f.stem:
            disp = re.sub(r"\s+in\s+.*$", "", fm.get("h1", "")) or f.stem.replace("-", " ").title()
        out[f.stem] = {"title": fm.get("title", ""), "h1": fm.get("h1", ""),
                       "display": disp, "priority": pr,
                       "rendered": PLACEHOLDER_MARK not in text, "path": f}
    return out


def metro_of(slug: str) -> tuple[str | None, str | None]:
    pi = load_plan_input(slug)
    prim = next((a for a in pi.get("service_areas") or [] if a.get("primary")), None)
    if prim:
        return prim.get("city"), prim.get("state")
    b = pi.get("brand") or {}
    return b.get("city"), b.get("state")


# --------------------------------------------------------------------------- #
# per-client service map (GBP map + duplicate decisions), one file per client
# --------------------------------------------------------------------------- #
def map_path(slug: str) -> Path:
    return CLIENTS / slug / "gbp-service-map.json"


def load_map(slug: str) -> dict:
    p = map_path(slug)
    d: dict = {}
    if p.exists():
        try:
            d = json.loads(p.read_text())
        except json.JSONDecodeError:
            d = {}
    d.setdefault("slug", slug)
    d.setdefault("policy", "scripts/site_structure.py (Santino 2026-09-30)")
    d.setdefault("gbp_services", {})  # GBP label -> {verdict, page, volume, reason}
    d.setdefault("merged", {})        # merged page slug -> {into, reason, volumes, at}
    d.setdefault("kept_pairs", [])    # [{a, b, volumes, reason}]
    return d


def save_map(slug: str, d: dict) -> None:
    p = map_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    d["gbp_services"] = dict(sorted(d.get("gbp_services", {}).items(), key=lambda kv: kv[0].lower()))
    p.write_text(json.dumps(d, indent=2) + "\n")


def norm(s: str) -> str:
    s = (s or "").lower().replace("&", " and ")
    s = re.sub(r"^job_type_id:", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def map_lookup(m: dict, gbp_label: str) -> dict | None:
    n = norm(gbp_label)
    for k, v in m.get("gbp_services", {}).items():
        if norm(k) == n:
            return v
    return None


def cluster_of(service_slug: str) -> dict | None:
    for c in SERVICE_CLUSTERS:
        if any(s == service_slug for s, _, _ in c["members"]):
            return c
    return None


def cluster_home(slug: str, service_slug: str) -> str | None:
    """If service_slug is a same-service twin of a page this site already
    has, the existing page's slug (so it maps instead of building)."""
    c = cluster_of(service_slug)
    if not c:
        return None
    pages = service_pages(slug)
    m = load_map(slug)
    for s, _, _ in c["members"]:
        if s != service_slug and s in pages and s not in m["merged"]:
            return s
    return None


# --------------------------------------------------------------------------- #
# homepage core services
# --------------------------------------------------------------------------- #
def homepage_services(slug: str) -> list[str]:
    return list(load_plan_input(slug).get("homepage_services") or [])


def seed_homepage_services(slug: str) -> list[str]:
    """First build of a new client: freeze its homepage core NOW (top 6 by
    priority of the pages the initial build ships, minus synonym twins), so
    later parity/core-floor pages can never displace it. No-op when the
    client already has a pinned list."""
    pi = load_plan_input(slug)
    if pi.get("homepage_services") or not pi:
        return list(pi.get("homepage_services") or [])
    pages = service_pages(slug)
    twins = {"water-cleanup"}
    for c in SERVICE_CLUSTERS:
        twins |= {s for s, _, _ in c["members"][1:]}
    ranked = sorted((s for s in pages if s not in twins), key=lambda s: -pages[s]["priority"])
    pi["homepage_services"] = ranked[:HOMEPAGE_MAX]
    if pi["homepage_services"]:
        save_plan_input(slug, pi)
    return pi["homepage_services"]


def write_homepage_services(slug: str) -> Path | None:
    """Mirror plan-input homepage_services into the site's data file (a
    derived copy; plan-input is canonical). Only slugs with a page ship."""
    site = SITES / slug
    if not (site / "src" / "pages" / "index.astro").exists():
        return None  # content-only stub subtree, no homepage to feed
    pages = service_pages(slug)
    pinned = [s for s in homepage_services(slug) if s in pages][:HOMEPAGE_MAX]
    out = site / "src" / "data" / "homepage-services.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(pinned, indent=2) + "\n"
    if not out.exists() or out.read_text() != body:
        out.write_text(body)
    return out


# --------------------------------------------------------------------------- #
# duplicate clusters
# --------------------------------------------------------------------------- #
def duplicate_clusters(slug: str) -> list[dict]:
    """[{name, canonical, members:[(slug, head, variant)]}] for clusters with
    2+ live pages on this site. Canonical = first rendered member present."""
    pages = service_pages(slug)
    out = []
    for c in SERVICE_CLUSTERS:
        present = [m for m in c["members"] if m[0] in pages]
        if len(present) < 2:
            continue
        rendered = [m for m in present if pages[m[0]]["rendered"]]
        canon = (rendered or present)[0][0]
        out.append({"name": c["name"], "canonical": canon,
                    "members": present,
                    "secondaries": [m for m in present if m[0] != canon]})
    return out


def pending_duplicates(slug: str) -> list[dict]:
    """Clusters whose secondary pages are neither merged nor a recorded kept
    pair: what the audit flags."""
    m = load_map(slug)
    kept = {tuple(sorted((k["a"], k["b"]))) for k in m.get("kept_pairs", [])}
    out = []
    for c in duplicate_clusters(slug):
        open_ = [s for s, _, _ in c["secondaries"]
                 if tuple(sorted((c["canonical"], s))) not in kept]
        if open_:
            out.append({**c, "open": open_})
    return out


# --------------------------------------------------------------------------- #
# volumes (DataForSEO Google Ads search_volume)
# --------------------------------------------------------------------------- #
_VOL_CACHE: dict = {}


def dfs_volumes(terms: list[str], city: str | None = None,
                state: str | None = None) -> tuple[dict, str]:
    """({term: monthly volume}, location label). city=None -> US national."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import gbp  # noqa: WPS433
    from gbp_name_suggest import metro_location, search_volumes
    terms = sorted({t for t in terms if t})
    loc = metro_location(city, state) if city else None
    key = (tuple(terms), loc)
    if key in _VOL_CACHE:
        return _VOL_CACHE[key]
    creds = gbp._dfs_auth()
    if not creds or not terms:
        return {t: 0 for t in terms}, "unavailable"
    auth = base64.b64encode(f"{creds[0]}:{creds[1]}".encode()).decode()
    vols: dict = {}
    label = "unavailable"
    for i in range(0, len(terms), 900):
        v, label = search_volumes(auth, terms[i:i + 900], loc)
        vols.update(v)
    _VOL_CACHE[key] = (vols, label)
    return vols, label


_NATIONAL: dict[str, int] = {}


def prefetch_national(heads: list[str]) -> None:
    """One batched national call for many heads (+ 'near me' forms). Many
    tiny calls trip DataForSEO's live-endpoint rate limit, which the helper
    reports as zeros; one batch does not."""
    want = sorted({t for h in heads for t in (h, f"{h} near me")} - set(_NATIONAL))
    if not want:
        return
    v, label = dfs_volumes(want)
    if label == "unavailable" or not any(v.values()):
        return  # never cache a failed call as "no demand"
    for t in want:
        _NATIONAL[t] = int(v.get(t, 0) or 0)


def cluster_heads() -> list[str]:
    return sorted({h for c in SERVICE_CLUSTERS for _, h, _ in c["members"]})


def national_demand(head: str) -> dict:
    """{'head': n, 'near_me': n, 'total': n} US national monthly searches."""
    if head not in _NATIONAL:
        prefetch_national([head])
    h, nm = _NATIONAL.get(head, 0), _NATIONAL.get(f"{head} near me", 0)
    return {"head": h, "near_me": nm, "total": h + nm}


def clears_new_page_bar(head: str, city: str | None, state: str | None) -> tuple[bool, dict]:
    """Rule 2. Returns (ok, evidence)."""
    metro = 0
    label = "unavailable"
    if city:
        v, label = dfs_volumes([head], city, state)
        metro = int(v.get(head, 0))
    ev = {"metro": metro, "metro_label": label}
    if metro >= NEW_PAGE_METRO_MIN:
        return True, ev
    nat = national_demand(head)
    ev["national"] = nat
    return (metro <= METRO_FLOOR and nat["total"] >= NEW_PAGE_NATIONAL_MIN), ev


# --------------------------------------------------------------------------- #
# Cloudflare Pages _redirects hygiene
# --------------------------------------------------------------------------- #
def _is_dynamic(src: str) -> bool:
    return "*" in src or bool(re.search(r"/:[A-Za-z]", src))


def normalize_redirects(path: Path, apply: bool = True) -> dict:
    """Cloudflare Pages counts every rule AFTER the first dynamic one
    (placeholder or splat) against the 100-dynamic cap and silently drops
    the rest (found 09-30: Air Care honored only rules 1-128 because a
    :city rule sat at #29). Static rules therefore go first, dynamic rules
    last, each block in its original order. Comments stay with the rule that
    follows them. Returns counts; refuses nothing, just reports caps."""
    text = path.read_text() if path.exists() else ""
    static, dynamic, pending = [], [], []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            pending.append(line)
            continue
        src = line.split()[0]
        (dynamic if _is_dynamic(src) else static).extend(pending + [line])
        pending = []
    out = static + dynamic + pending
    new = "\n".join(out).strip("\n") + "\n" if out else ""
    n_static = sum(1 for l in static if l.strip() and not l.lstrip().startswith("#"))
    n_dyn = sum(1 for l in dynamic if l.strip() and not l.lstrip().startswith("#"))
    if apply and new != text and text:
        path.write_text(new)
    return {"static": n_static, "dynamic": n_dyn, "changed": new != text,
            "over_cap": n_static > 2000 or n_dyn > 100}


# --------------------------------------------------------------------------- #
# git helper (seeding homepage_services from the pre-parity homepage)
# --------------------------------------------------------------------------- #
PRE_PARITY_DATE = "2026-09-17"   # gbp_parity.py P1-P3 went live 09-17


def pre_parity_service_slugs(slug: str) -> list[str] | None:
    """Service page slugs on main before the parity engine started, or None
    when the site had no service pages yet."""
    rev = subprocess.run(["git", "rev-list", "-1", f"--before={PRE_PARITY_DATE}", "HEAD"],
                         cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if not rev:
        return None
    ls = subprocess.run(["git", "ls-tree", "--name-only", rev,
                         f"sites/{slug}/src/content/services/"],
                        cwd=ROOT, capture_output=True, text=True).stdout.split()
    slugs = [Path(p).stem for p in ls if p.endswith(".md")]
    return slugs or None
