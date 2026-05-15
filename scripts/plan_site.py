#!/usr/bin/env python3
"""
Rank AI site planner.

Produces a deterministic URL plan + content map for a Rank AI client, driven by
an industry template (currently: restoration). Output artifacts are consumed by
Skill 3 (build-site) and Skill 4 (blog routine).

Subcommands:
  generate   Read plan-input.json, produce all plan artifacts.
  validate   Lint an existing plan: dead links, missing keywords, schema gaps.
  report     Regenerate plan-report.md from current artifacts (useful after
             manual CSV edits).

Inputs:
  rank-ai/clients/{slug}.json              (client record, from Skill 1)
  rank-ai/clients/{slug}/plan-input.json   (this run's inputs)
  rank-ai/templates/{template}/...         (industry template)

Outputs (under rank-ai/clients/{slug}/plan/):
  url-plan.json
  content-map.csv
  internal-links.json
  schema-stubs.json
  plan-report.md

Spec: rank-ai/docs/site-plan-skill-spec.md
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = REPO_ROOT / "clients"
TEMPLATES_DIR = REPO_ROOT / "templates"

# Archetype-level priority. Multiplied with per-instance priority to rank pages
# in the content-map for content-generation order.
ARCHETYPE_PRIORITY = {
    "home": 10,
    "services-hub": 8,
    "service-landing": 9,
    "service-areas-hub": 7,
    "service-area": 8,
    "service-area-service": 7,
    "blog-index": 6,
    "blog-post": 6,
    "about": 5,
    "contact": 5,
    "legal": 2,
}

# ----------------------------------------------------------------------------
# IO helpers
# ----------------------------------------------------------------------------


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def load_json(path: Path) -> dict:
    if not path.exists():
        die(f"Missing required file: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        die(f"Invalid JSON in {path}: {e}")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def client_record_path(slug: str) -> Path:
    return CLIENTS_DIR / f"{slug}.json"


def plan_dir(slug: str) -> Path:
    return CLIENTS_DIR / slug / "plan"


# ----------------------------------------------------------------------------
# Substitution engine
# ----------------------------------------------------------------------------

_VAR_RE = re.compile(r"\{([^{}]+)\}")


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


FILTERS = {
    "lower": str.lower,
    "upper": str.upper,
    "title": str.title,
    "slug": _slugify,
}


def _resolve_dot_path(ctx: dict, dotted: str) -> str:
    """Resolve `service.display_name` through nested dict access."""
    cur = ctx
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return ""
    if cur is None:
        return ""
    return str(cur)


def render(template: str, ctx: dict) -> str:
    """Substitute `{var}` and `{var|filter|filter}` placeholders."""
    def replace(match: re.Match) -> str:
        expr = match.group(1).strip()
        parts = expr.split("|")
        value = _resolve_dot_path(ctx, parts[0].strip())
        for filt in parts[1:]:
            filt = filt.strip()
            if filt not in FILTERS:
                continue
            value = FILTERS[filt](value)
        return value
    return _VAR_RE.sub(replace, template)


# ----------------------------------------------------------------------------
# Template loading
# ----------------------------------------------------------------------------


@dataclass
class Template:
    name: str
    version: str
    descriptor: dict
    services_by_slug: dict
    seed_topics: list
    archetypes: dict           # archetype name -> archetype json
    archetype_by_ref: dict     # fixed_ref/instance ref -> archetype json (for fixed/legal)
    linking_rules: dict        # archetype name -> list of rule dicts
    kind_definitions: dict
    schema_stubs_available: set


def load_template(name: str) -> Template:
    root = TEMPLATES_DIR / name
    if not root.exists():
        die(f"Template not found: {root}")

    descriptor = load_json(root / "template.json")
    services_doc = load_json(root / "services.json")
    services_by_slug = {s["slug"]: s for s in services_doc["services"]}

    seed_doc = load_json(root / "seed-blog-topics.json")
    seed_topics = seed_doc["topics"]

    archetype_dir = root / "archetypes"
    if not archetype_dir.exists():
        die(f"Missing archetypes dir: {archetype_dir}")
    archetypes = {}
    archetype_by_ref = {}
    for path in sorted(archetype_dir.glob("*.json")):
        arc = load_json(path)
        # archetype filename -> json, lower-cased
        slug = path.stem
        archetypes[slug] = arc
        if "fixed_ref" in arc:
            archetype_by_ref[arc["fixed_ref"]] = arc
        if "fixed_refs" in arc:
            for ref in arc["fixed_refs"]:
                archetype_by_ref[ref] = arc

    linking_doc = load_json(root / "linking-rules.json")
    linking_rules = {r["from"]: r["to"] for r in linking_doc["rules"]}
    kind_definitions = linking_doc.get("kind_definitions", {})

    schema_dir = root / "schema"
    schema_stubs_available = {p.stem for p in schema_dir.glob("*.json")} if schema_dir.exists() else set()

    return Template(
        name=descriptor["name"],
        version=descriptor["version"],
        descriptor=descriptor,
        services_by_slug=services_by_slug,
        seed_topics=seed_topics,
        archetypes=archetypes,
        archetype_by_ref=archetype_by_ref,
        linking_rules=linking_rules,
        kind_definitions=kind_definitions,
        schema_stubs_available=schema_stubs_available,
    )


# ----------------------------------------------------------------------------
# Input validation + normalization
# ----------------------------------------------------------------------------


def normalize_service_area(area: dict) -> dict:
    """Ensure each area has a slug and the required fields are present."""
    if "slug" not in area:
        seed = f"{area.get('city','')}-{area.get('state','')}"
        area["slug"] = _slugify(seed)
    for k in ("city", "state"):
        if not area.get(k):
            die(f"Service area missing required field {k!r}: {area}")
    return area


def expand_inputs(template: Template, plan_input: dict, client: dict) -> dict:
    """Merge plan-input.json with derived/default fields. Returns a frozen
    'inputs' dict the rest of the pipeline reads from."""
    inputs = dict(plan_input)

    # Brand: pull from client record if not duplicated in plan-input
    brand = dict(plan_input.get("brand", {}))
    brand.setdefault("display_name", client["display_name"])
    brand.setdefault("domain", client["domain"])
    brand.setdefault("canonical_url", f"https://{client['domain']}")
    inputs["brand"] = brand

    # Resolve services from slugs to full service objects
    selected_slugs = plan_input.get("services") or []
    services = []
    missing = []
    for slug in selected_slugs:
        if slug in template.services_by_slug:
            services.append(template.services_by_slug[slug])
        else:
            missing.append(slug)
    if missing:
        die(f"Unknown service slugs (not in {template.name} catalog): {missing}")
    inputs["services"] = services

    # Service areas
    areas = [normalize_service_area(dict(a)) for a in (plan_input.get("service_areas") or [])]
    if not areas:
        die("At least one service area is required.")
    # Mark the primary area if not flagged
    if not any(a.get("primary") for a in areas):
        areas[0]["primary"] = True
    inputs["service_areas"] = areas

    # Brand convenience fields derived from primary area
    primary_area = next(a for a in areas if a.get("primary"))
    brand.setdefault("primary_city", primary_area["city"])
    brand.setdefault("primary_state", primary_area["state"])

    # Defaults
    inputs.setdefault("cross_product", True)
    inputs.setdefault("keyword_strategy", template.descriptor.get("default_keyword_strategy", "conservative"))
    inputs.setdefault("blog_seed_count", template.descriptor.get("default_blog_seed_count", 12))

    return inputs


# ----------------------------------------------------------------------------
# Pass 1 — IA expansion
# ----------------------------------------------------------------------------


@dataclass
class Page:
    url_path: str
    archetype: str
    vars: dict = field(default_factory=dict)
    title: str = ""
    h1: str = ""
    meta_description: str = ""
    primary_keyword: str = ""
    secondary_keywords: list = field(default_factory=list)
    search_intent: str = ""
    search_volume: str = ""
    difficulty: str = ""
    target_word_count: int = 0
    image_roles: list = field(default_factory=list)
    schema_stubs: list = field(default_factory=list)
    internal_links_out: list = field(default_factory=list)
    priority: float = 0.0
    status: str = "planned"

    def to_csv_row(self) -> dict:
        return {
            "url_path": self.url_path,
            "archetype": self.archetype,
            "title": self.title,
            "h1": self.h1,
            "meta_description": self.meta_description,
            "primary_keyword": self.primary_keyword,
            "secondary_keywords": "|".join(self.secondary_keywords),
            "search_intent": self.search_intent,
            "search_volume": self.search_volume,
            "difficulty": self.difficulty,
            "target_word_count": self.target_word_count,
            "image_roles": "|".join(self.image_roles),
            "schema_stubs": "|".join(self.schema_stubs),
            "internal_links_out": "|".join(self.internal_links_out),
            "priority": f"{self.priority:.2f}",
            "status": self.status,
        }


CSV_COLUMNS = [
    "url_path", "archetype", "title", "h1", "meta_description",
    "primary_keyword", "secondary_keywords", "search_intent",
    "search_volume", "difficulty", "target_word_count",
    "image_roles", "schema_stubs", "internal_links_out",
    "priority", "status",
]


def _resolved_ctx(inputs: dict, **extra) -> dict:
    """Build the substitution context for a single archetype instantiation."""
    ctx = {"brand": inputs["brand"]}
    ctx.update(extra)
    return ctx


def expand_ia(template: Template, inputs: dict) -> list[Page]:
    pages: list[Page] = []
    brand = inputs["brand"]

    # Singleton fixed pages: home, services-hub, service-areas-hub, blog-index, about, contact
    for arc_name in [
        "home", "services-hub", "service-areas-hub", "blog-index", "about", "contact"
    ]:
        arc = template.archetypes.get(arc_name)
        if not arc:
            continue
        ctx = _resolved_ctx(inputs)
        pages.append(Page(
            url_path=render(arc["path_pattern"], ctx),
            archetype=arc_name,
            vars={},
        ))

    # Service landing pages
    arc = template.archetypes.get("service-landing")
    if arc:
        for service in inputs["services"]:
            ctx = _resolved_ctx(inputs, service=service)
            pages.append(Page(
                url_path=render(arc["path_pattern"], ctx),
                archetype="service-landing",
                vars={"service": service},
            ))

    # Service area pages
    arc = template.archetypes.get("service-area")
    if arc:
        for area in inputs["service_areas"]:
            ctx = _resolved_ctx(inputs, area=area)
            pages.append(Page(
                url_path=render(arc["path_pattern"], ctx),
                archetype="service-area",
                vars={"area": area},
            ))

    # Cross-product service-area-service pages
    if inputs.get("cross_product"):
        arc = template.archetypes.get("service-area-service")
        if arc:
            for area in inputs["service_areas"]:
                for service in inputs["services"]:
                    ctx = _resolved_ctx(inputs, area=area, service=service)
                    pages.append(Page(
                        url_path=render(arc["path_pattern"], ctx),
                        archetype="service-area-service",
                        vars={"area": area, "service": service},
                    ))

    # Blog seed posts — top N by priority, filtered to services the client offers
    arc = template.archetypes.get("blog-post")
    if arc:
        selected_service_slugs = {s["slug"] for s in inputs["services"]}
        candidates = [
            t for t in template.seed_topics
            if not selected_service_slugs.isdisjoint(t.get("services", []))
        ]
        candidates.sort(key=lambda t: t.get("priority", 0), reverse=True)
        take = candidates[: inputs.get("blog_seed_count", 12)]
        for topic in take:
            post = dict(topic)
            post["title"] = render(topic["title_template"], _resolved_ctx(inputs))
            post["slug"] = topic["slug"]
            ctx = _resolved_ctx(inputs, post=post)
            pages.append(Page(
                url_path=f"/blog/{post['slug']}/",
                archetype="blog-post",
                vars={"post": post},
            ))

    # Legal pages
    arc = template.archetypes.get("legal")
    if arc and "instances" in arc:
        for instance in arc["instances"]:
            ctx = _resolved_ctx(inputs, instance=instance)
            pages.append(Page(
                url_path=instance["path"],
                archetype="legal",
                vars={"instance": instance},
            ))

    return pages


# ----------------------------------------------------------------------------
# Pass 2 — keyword + intent enrichment, title/meta substitution
# ----------------------------------------------------------------------------


def enrich_page(page: Page, template: Template, inputs: dict) -> None:
    arc = template.archetypes.get(page.archetype)
    if not arc:
        return

    ctx = _resolved_ctx(inputs, **page.vars)

    # Title / h1 / meta — direct substitution from archetype templates
    if page.archetype == "legal":
        instance = page.vars.get("instance", {})
        page.title = render(instance.get("title", ""), ctx)
        page.h1 = render(instance.get("h1", ""), ctx)
        page.meta_description = render(arc.get("meta_description_template", ""), {
            **ctx, "instance": instance
        })
        page.target_word_count = instance.get("target_word_count", 400)
    else:
        page.title = render(arc.get("title_template", ""), ctx)
        page.h1 = render(arc.get("h1_template", ""), ctx)
        page.meta_description = render(arc.get("meta_description_template", ""), ctx)
        page.target_word_count = arc.get("target_word_count", 700)

    # Primary keyword
    pk_tpl = arc.get("primary_keyword_template", "")
    if pk_tpl:
        page.primary_keyword = render(pk_tpl, ctx)
    elif page.archetype == "blog-post":
        # Derive from post title (lowercased, no punctuation), as a sane MVP fallback
        page.primary_keyword = re.sub(r"[^a-z0-9 ]+", "", page.title.lower()).strip()
    elif page.archetype == "legal":
        ref = page.vars.get("instance", {}).get("ref", "")
        page.primary_keyword = f"{inputs['brand']['display_name']} {ref}".lower()

    # Secondary keywords
    sec_keys: list[str] = []
    # Static list on archetype
    for k in arc.get("secondary_keywords", []) or []:
        sec_keys.append(render(k, ctx))
    # Service-supplied list for service-landing and service-area-service
    if page.archetype in ("service-landing", "service-area-service"):
        service = page.vars.get("service", {})
        for k in service.get("secondary_keywords", []) or []:
            sec_keys.append(k)
    # Blog post: pull related-service supporting terms
    if page.archetype == "blog-post":
        post = page.vars.get("post", {})
        for svc_slug in post.get("services", []):
            svc = template.services_by_slug.get(svc_slug)
            if svc:
                sec_keys.append(svc["display_name"].lower())
    # Dedupe preserving order
    seen = set()
    page.secondary_keywords = [k for k in sec_keys if not (k in seen or seen.add(k))]

    # Intent
    intent_ref = arc.get("search_intent_default_ref")
    if intent_ref == "services[].primary_intent":
        service = page.vars.get("service", {})
        page.search_intent = service.get("primary_intent", "local_commercial")
    elif intent_ref == "seed-blog-topics[].intent":
        post = page.vars.get("post", {})
        page.search_intent = post.get("intent", "informational")
    else:
        page.search_intent = arc.get("search_intent_default", "local_commercial")

    # Image roles + schema stubs (from archetype as-is)
    page.image_roles = list(arc.get("image_roles", []))
    if page.archetype == "legal":
        page.schema_stubs = []
    else:
        page.schema_stubs = list(arc.get("schema_stubs", []))

    # Priority
    base = ARCHETYPE_PRIORITY.get(page.archetype, 5)
    instance_priority = 5
    if page.archetype in ("service-landing", "service-area-service"):
        service = page.vars.get("service", {})
        instance_priority = service.get("priority", 5)
    elif page.archetype == "blog-post":
        post = page.vars.get("post", {})
        instance_priority = post.get("priority", 5)
    elif page.archetype == "service-area":
        # Primary city ranked higher than secondary areas
        area = page.vars.get("area", {})
        instance_priority = 9 if area.get("primary") else 6
    page.priority = round(base * (instance_priority / 10.0), 2)

    # search_volume / difficulty placeholders — DataForSEO integration goes here.
    # TODO(DataForSEO): wire bulk_keyword_difficulty + bulk_traffic_estimation per
    # primary_keyword. Cache responses under plan/.cache/ to keep reruns free.
    page.search_volume = ""
    page.difficulty = ""


# ----------------------------------------------------------------------------
# Pass 3 — internal link graph
# ----------------------------------------------------------------------------


def _pages_by_archetype(pages: list[Page]) -> dict[str, list[Page]]:
    out: dict[str, list[Page]] = defaultdict(list)
    for p in pages:
        out[p.archetype].append(p)
    return out


def _fixed_lookup(pages: list[Page]) -> dict[str, Page]:
    """Return ref-name -> page for archetypes that are singletons."""
    refs = {
        "home": "home",
        "about": "about",
        "contact": "contact",
        "services-hub": "services-hub",
        "service-areas-hub": "service-areas-hub",
        "blog-index": "blog-index",
    }
    out = {}
    for ref, arc_name in refs.items():
        match = next((p for p in pages if p.archetype == arc_name), None)
        if match:
            out[ref] = match
    return out


def build_link_graph(pages: list[Page], template: Template) -> dict[str, list[str]]:
    by_archetype = _pages_by_archetype(pages)
    fixed = _fixed_lookup(pages)

    def resolve_rule(source: Page, rule: dict) -> list[Page]:
        kind = rule.get("kind")
        archetype = rule.get("archetype")
        ref = rule.get("ref")
        limit = rule.get("limit")
        targets: list[Page] = []

        if kind == "fixed":
            page = fixed.get(ref)
            if page:
                targets.append(page)
        elif kind == "all":
            targets.extend(by_archetype.get(archetype, []))
        elif kind == "siblings_same_service":
            svc_slug = source.vars.get("service", {}).get("slug")
            targets.extend([
                p for p in by_archetype.get("service-area-service", [])
                if p.vars.get("service", {}).get("slug") == svc_slug
                and p.url_path != source.url_path
            ])
        elif kind == "siblings_same_area":
            area_slug = source.vars.get("area", {}).get("slug")
            targets.extend([
                p for p in by_archetype.get("service-area-service", [])
                if p.vars.get("area", {}).get("slug") == area_slug
                and p.url_path != source.url_path
            ])
        elif kind == "cousins_same_service":
            svc_slug = source.vars.get("service", {}).get("slug")
            area_slug = source.vars.get("area", {}).get("slug")
            targets.extend([
                p for p in by_archetype.get("service-area-service", [])
                if p.vars.get("service", {}).get("slug") == svc_slug
                and p.vars.get("area", {}).get("slug") != area_slug
            ])
        elif kind == "children_same_area":
            area_slug = source.vars.get("area", {}).get("slug")
            targets.extend([
                p for p in by_archetype.get("service-area-service", [])
                if p.vars.get("area", {}).get("slug") == area_slug
            ])
        elif kind == "parent_service":
            svc_slug = source.vars.get("service", {}).get("slug")
            match = next(
                (p for p in by_archetype.get("service-landing", [])
                 if p.vars.get("service", {}).get("slug") == svc_slug),
                None,
            )
            if match:
                targets.append(match)
        elif kind == "parent_area":
            area_slug = source.vars.get("area", {}).get("slug")
            match = next(
                (p for p in by_archetype.get("service-area", [])
                 if p.vars.get("area", {}).get("slug") == area_slug),
                None,
            )
            if match:
                targets.append(match)
        elif kind == "geographic_neighbors":
            # MVP heuristic: same state, different slug. Lat/lng distance left for later.
            area = source.vars.get("area", {})
            state = area.get("state")
            slug = area.get("slug")
            targets.extend([
                p for p in by_archetype.get("service-area", [])
                if p.vars.get("area", {}).get("state") == state
                and p.vars.get("area", {}).get("slug") != slug
            ])
        elif kind == "related_services":
            # Pages whose service shares ≥1 secondary keyword with this service.
            svc = source.vars.get("service", {})
            svc_keys = set(svc.get("secondary_keywords", []))
            scored = []
            for p in by_archetype.get("service-landing", []):
                other_svc = p.vars.get("service", {})
                if other_svc.get("slug") == svc.get("slug"):
                    continue
                overlap = len(svc_keys & set(other_svc.get("secondary_keywords", [])))
                if overlap > 0:
                    scored.append((overlap, p))
            scored.sort(key=lambda x: (-x[0], x[1].url_path))
            targets.extend(p for _, p in scored)
        elif kind == "related_blog_posts":
            # Blog posts whose services overlap this page's service tag.
            target_slugs: set[str] = set()
            if source.archetype in ("service-landing", "service-area-service"):
                target_slugs = {source.vars.get("service", {}).get("slug")}
            elif source.archetype == "blog-post":
                target_slugs = set(source.vars.get("post", {}).get("services", []))
            for p in by_archetype.get("blog-post", []):
                if p.url_path == source.url_path:
                    continue
                if set(p.vars.get("post", {}).get("services", [])) & target_slugs:
                    targets.append(p)
        elif kind == "tagged_services":
            tagged = source.vars.get("post", {}).get("services", [])
            for slug in tagged:
                match = next(
                    (p for p in by_archetype.get("service-landing", [])
                     if p.vars.get("service", {}).get("slug") == slug),
                    None,
                )
                if match:
                    targets.append(match)

        # Sort deterministically by priority desc then url
        targets.sort(key=lambda p: (-p.priority, p.url_path))
        # Dedupe preserving order
        seen = set()
        deduped = []
        for t in targets:
            if t.url_path not in seen:
                seen.add(t.url_path)
                deduped.append(t)
        if limit:
            deduped = deduped[:limit]
        return deduped

    graph: dict[str, list[str]] = {}
    for page in pages:
        rules = template.linking_rules.get(page.archetype, [])
        all_targets: list[str] = []
        seen = set()
        for rule in rules:
            for t in resolve_rule(page, rule):
                if t.url_path not in seen and t.url_path != page.url_path:
                    seen.add(t.url_path)
                    all_targets.append(t.url_path)
        graph[page.url_path] = all_targets
        page.internal_links_out = all_targets
    return graph


# ----------------------------------------------------------------------------
# Pass 4 — schema stubs
# ----------------------------------------------------------------------------


def collect_schema_stubs(pages: list[Page], template: Template) -> dict:
    """Return per-URL list of schema stub names (template files) the build skill
    must hydrate. Stubs themselves live in templates/{name}/schema/."""
    out: dict[str, dict] = {}
    for page in pages:
        if not page.schema_stubs:
            continue
        out[page.url_path] = {
            "archetype": page.archetype,
            "stubs": [s for s in page.schema_stubs if s in template.schema_stubs_available],
            "missing_stubs": [s for s in page.schema_stubs if s not in template.schema_stubs_available],
        }
    return out


# ----------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------


def validate_plan(pages: list[Page], graph: dict, schema_stubs: dict, template: Template) -> list[str]:
    issues: list[str] = []
    paths = {p.url_path for p in pages}

    # 1. Internal links point at real URLs
    for src, targets in graph.items():
        for t in targets:
            if t not in paths:
                issues.append(f"Dead internal link {src} -> {t}")

    # 2. No URL collisions
    seen = set()
    for p in pages:
        if p.url_path in seen:
            issues.append(f"Duplicate URL path: {p.url_path}")
        seen.add(p.url_path)

    # 3. Primary keyword non-empty
    for p in pages:
        if not p.primary_keyword.strip():
            issues.append(f"Empty primary_keyword on {p.url_path} ({p.archetype})")

    # 4. Schema stubs resolve
    for url, meta in schema_stubs.items():
        if meta["missing_stubs"]:
            issues.append(f"Schema stubs missing for {url}: {meta['missing_stubs']}")

    # 5. URL-safe service-area slugs
    for p in pages:
        area = p.vars.get("area", {})
        if area:
            slug = area.get("slug", "")
            if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", slug):
                issues.append(f"Service area slug not URL-safe: {slug!r} on {p.url_path}")

    return issues


# ----------------------------------------------------------------------------
# Output writers
# ----------------------------------------------------------------------------


def write_url_plan(path: Path, pages: list[Page], template: Template, inputs: dict) -> None:
    payload = {
        "template": template.name,
        "template_version": template.version,
        "generated_at": now_iso(),
        "input_summary": {
            "service_count": len(inputs["services"]),
            "service_area_count": len(inputs["service_areas"]),
            "cross_product": inputs.get("cross_product"),
            "blog_seed_count": inputs.get("blog_seed_count"),
        },
        "pages": [
            {
                "url_path": p.url_path,
                "archetype": p.archetype,
                "vars_keys": sorted(p.vars.keys()),
                "title": p.title,
                "h1": p.h1,
                "meta_description": p.meta_description,
                "primary_keyword": p.primary_keyword,
                "secondary_keywords": p.secondary_keywords,
                "search_intent": p.search_intent,
                "target_word_count": p.target_word_count,
                "image_roles": p.image_roles,
                "schema_stubs": p.schema_stubs,
                "priority": p.priority,
                "status": p.status,
                "internal_links_out": p.internal_links_out,
            }
            for p in pages
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def write_content_map(path: Path, pages: list[Page]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for p in sorted(pages, key=lambda p: (-p.priority, p.url_path)):
            writer.writerow(p.to_csv_row())


def write_internal_links(path: Path, graph: dict) -> None:
    path.write_text(json.dumps(graph, indent=2) + "\n")


def write_schema_stubs(path: Path, stubs: dict) -> None:
    path.write_text(json.dumps(stubs, indent=2) + "\n")


def write_report(path: Path, pages: list[Page], graph: dict, template: Template,
                 inputs: dict, issues: list[str]) -> None:
    by_arc: dict[str, int] = defaultdict(int)
    for p in pages:
        by_arc[p.archetype] += 1
    total_links = sum(len(v) for v in graph.values())

    lines = []
    lines.append(f"# Site Plan Report — {inputs['brand']['display_name']}")
    lines.append("")
    lines.append(f"- Template: `{template.name}` v{template.version}")
    lines.append(f"- Generated: {now_iso()}")
    lines.append(f"- Domain: `{inputs['brand']['domain']}`")
    lines.append(f"- Services selected: {len(inputs['services'])} of "
                 f"{len(template.services_by_slug)} catalog entries")
    lines.append(f"- Service areas: {len(inputs['service_areas'])}")
    lines.append(f"- Cross-product enabled: {inputs.get('cross_product')}")
    lines.append(f"- Total URLs: **{len(pages)}**")
    lines.append(f"- Total internal links: {total_links} (avg "
                 f"{total_links / max(len(pages),1):.1f} per page)")
    lines.append("")
    lines.append("## URLs by archetype")
    lines.append("")
    lines.append("| Archetype | Count |")
    lines.append("| --- | --- |")
    for arc, n in sorted(by_arc.items(), key=lambda x: -x[1]):
        lines.append(f"| `{arc}` | {n} |")
    lines.append("")

    lines.append("## Selected services")
    lines.append("")
    for s in inputs["services"]:
        lines.append(f"- `{s['slug']}` — {s['display_name']} ({s.get('tier','?')}, priority {s.get('priority','?')})")
    lines.append("")

    lines.append("## Service areas")
    lines.append("")
    for a in inputs["service_areas"]:
        primary = " *(primary)*" if a.get("primary") else ""
        lines.append(f"- `{a['slug']}` — {a['city']}, {a['state']}{primary}")
    lines.append("")

    lines.append("## Top 10 priority pages")
    lines.append("")
    lines.append("| URL | Archetype | Priority | Primary keyword |")
    lines.append("| --- | --- | --- | --- |")
    for p in sorted(pages, key=lambda p: (-p.priority, p.url_path))[:10]:
        lines.append(f"| `{p.url_path}` | `{p.archetype}` | {p.priority} | {p.primary_keyword} |")
    lines.append("")

    if issues:
        lines.append("## Validation issues")
        lines.append("")
        for i in issues:
            lines.append(f"- ⚠ {i}")
    else:
        lines.append("## Validation")
        lines.append("")
        lines.append("All checks passed.")
    lines.append("")

    lines.append("## Next steps")
    lines.append("")
    lines.append("1. Open `content-map.csv` and skim the URL list. Edit titles/keywords inline if needed.")
    lines.append("2. Run `plan_site.py validate --slug {slug}` after edits.")
    lines.append("3. Hand the plan dir off to Skill 3 (`rank-ai-build-site`) when it exists.")
    lines.append("")

    path.write_text("\n".join(lines))


# ----------------------------------------------------------------------------
# Client-record update
# ----------------------------------------------------------------------------


def update_client_plan_status(slug: str, template: Template, page_count: int) -> None:
    rec_path = client_record_path(slug)
    if not rec_path.exists():
        return
    rec = json.loads(rec_path.read_text())
    rec["plan"] = {
        "template": template.name,
        "template_version": template.version,
        "url_count": page_count,
        "generated_at": now_iso(),
    }
    rec["plan_status"] = "planned"
    rec["updated_at"] = now_iso()
    rec_path.write_text(json.dumps(rec, indent=2) + "\n")


# ----------------------------------------------------------------------------
# Subcommands
# ----------------------------------------------------------------------------


def cmd_generate(args) -> int:
    slug = args.slug

    # Load client record (required, comes from Skill 1)
    client = load_json(client_record_path(slug))

    # Load plan-input.json — required for this run
    input_path = CLIENTS_DIR / slug / "plan-input.json"
    if not input_path.exists():
        die(
            f"Missing plan input: {input_path}\n"
            f"Create it with this client's services, service_areas, brand details.\n"
            f"See rank-ai/docs/site-plan-skill-spec.md for the full schema."
        )
    plan_input = load_json(input_path)

    # Resolve template
    template_name = args.template or plan_input.get("template", "restoration")
    template = load_template(template_name)

    # Normalize inputs
    inputs = expand_inputs(template, plan_input, client)

    print(f"==> Generating plan for {slug} ({client['domain']})")
    print(f"    Template:        {template.name} v{template.version}")
    print(f"    Services:        {len(inputs['services'])}")
    print(f"    Service areas:   {len(inputs['service_areas'])}")
    print(f"    Cross-product:   {inputs.get('cross_product')}")
    print(f"    Blog seed count: {inputs.get('blog_seed_count')}")
    print()

    # Mark client as planning
    rec = json.loads(client_record_path(slug).read_text())
    rec["plan_status"] = "planning"
    client_record_path(slug).write_text(json.dumps(rec, indent=2) + "\n")

    # Pass 1
    pages = expand_ia(template, inputs)
    print(f"[1/4] IA expansion: {len(pages)} URLs.")

    # Pass 2
    for page in pages:
        enrich_page(page, template, inputs)
    print(f"[2/4] Keyword + intent enrichment: done.")

    # Pass 3
    graph = build_link_graph(pages, template)
    total_links = sum(len(v) for v in graph.values())
    print(f"[3/4] Internal link graph: {total_links} edges.")

    # Pass 4
    schema_stubs = collect_schema_stubs(pages, template)
    print(f"[4/4] Schema stubs: {len(schema_stubs)} pages with stubs.")

    # Output
    out_dir = plan_dir(slug)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Audit copy of inputs
    (CLIENTS_DIR / slug / "plan" / "plan-input.json").write_text(
        json.dumps(plan_input, indent=2) + "\n"
    )
    write_url_plan(out_dir / "url-plan.json", pages, template, inputs)
    write_content_map(out_dir / "content-map.csv", pages)
    write_internal_links(out_dir / "internal-links.json", graph)
    write_schema_stubs(out_dir / "schema-stubs.json", schema_stubs)

    # Validate before report so the report includes issues
    issues = validate_plan(pages, graph, schema_stubs, template)
    write_report(out_dir / "plan-report.md", pages, graph, template, inputs, issues)

    # Update client record
    update_client_plan_status(slug, template, len(pages))

    print()
    print("==> Plan generation complete.")
    print(f"    {out_dir}/url-plan.json")
    print(f"    {out_dir}/content-map.csv")
    print(f"    {out_dir}/internal-links.json")
    print(f"    {out_dir}/schema-stubs.json")
    print(f"    {out_dir}/plan-report.md")
    if issues:
        print()
        print(f"    {len(issues)} validation issue(s) — see plan-report.md.")
    return 0


def cmd_validate(args) -> int:
    slug = args.slug
    out_dir = plan_dir(slug)
    if not (out_dir / "url-plan.json").exists():
        die(f"No plan found at {out_dir}. Run `generate` first.")
    payload = load_json(out_dir / "url-plan.json")
    template = load_template(payload["template"])
    pages = []
    for d in payload["pages"]:
        p = Page(url_path=d["url_path"], archetype=d["archetype"])
        p.title = d.get("title", "")
        p.h1 = d.get("h1", "")
        p.meta_description = d.get("meta_description", "")
        p.primary_keyword = d.get("primary_keyword", "")
        p.secondary_keywords = d.get("secondary_keywords", [])
        p.schema_stubs = d.get("schema_stubs", [])
        # vars: we only need area.slug for the URL-safe check; pull from url_path heuristically
        pages.append(p)
    graph = load_json(out_dir / "internal-links.json")
    schema_stubs = load_json(out_dir / "schema-stubs.json")
    issues = validate_plan(pages, graph, schema_stubs, template)
    if issues:
        print(f"==> {len(issues)} validation issue(s):")
        for i in issues:
            print(f"  - {i}")
        return 2
    print("==> Plan validates clean.")
    return 0


def cmd_report(args) -> int:
    slug = args.slug
    out_dir = plan_dir(slug)
    if not (out_dir / "url-plan.json").exists():
        die(f"No plan found at {out_dir}. Run `generate` first.")
    payload = load_json(out_dir / "url-plan.json")
    template = load_template(payload["template"])
    plan_input = load_json(out_dir / "plan-input.json")
    client = load_json(client_record_path(slug))
    inputs = expand_inputs(template, plan_input, client)

    # Rebuild lightweight Page objects from the persisted plan
    pages: list[Page] = []
    for d in payload["pages"]:
        p = Page(
            url_path=d["url_path"],
            archetype=d["archetype"],
            title=d.get("title", ""),
            h1=d.get("h1", ""),
            meta_description=d.get("meta_description", ""),
            primary_keyword=d.get("primary_keyword", ""),
            secondary_keywords=d.get("secondary_keywords", []),
            search_intent=d.get("search_intent", ""),
            image_roles=d.get("image_roles", []),
            schema_stubs=d.get("schema_stubs", []),
            internal_links_out=d.get("internal_links_out", []),
            priority=d.get("priority", 0.0),
            status=d.get("status", "planned"),
        )
        pages.append(p)

    graph = load_json(out_dir / "internal-links.json")
    schema_stubs = load_json(out_dir / "schema-stubs.json")
    issues = validate_plan(pages, graph, schema_stubs, template)
    write_report(out_dir / "plan-report.md", pages, graph, template, inputs, issues)
    print(f"==> Wrote {out_dir / 'plan-report.md'}")
    return 0


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="plan_site",
        description="Rank AI — generate a deterministic URL plan + content map.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pg = sub.add_parser("generate", help="Produce all plan artifacts from inputs")
    pg.add_argument("--slug", required=True)
    pg.add_argument("--template", default=None, help="Override template name (default: from plan-input.json or 'restoration')")
    pg.set_defaults(func=cmd_generate)

    pv = sub.add_parser("validate", help="Lint an existing plan")
    pv.add_argument("--slug", required=True)
    pv.set_defaults(func=cmd_validate)

    pr = sub.add_parser("report", help="Regenerate plan-report.md from existing artifacts")
    pr.add_argument("--slug", required=True)
    pr.set_defaults(func=cmd_report)

    return p


def main() -> int:
    return build_parser().parse_args().func(build_parser().parse_args())


if __name__ == "__main__":
    args = build_parser().parse_args()
    sys.exit(args.func(args))
