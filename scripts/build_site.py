#!/usr/bin/env python3
"""
Rank AI build-site implementation. Phase 1 = scaffold (deterministic, free).

  scaffold   Copy starter to sites/{slug}/, substitute brand tokens, generate
             one content-collection markdown per planned URL, init git, create
             GitHub repo at restorationai/{slug}-site, push initial commit,
             attempt Cloudflare Pages project creation (gated).

  status     Show current build state for a client.

Run `render`, `push-staging`, `push-main`, `cut-over` are phase 2/3 (not
implemented yet).

Environment (from rank-ai/.env):
  CLOUDFLARE_API_TOKEN          Pages API access (uses R2 token in our setup)
  CLOUDFLARE_R2_API_TOKEN       R2 PUT (future render step)
  CLOUDFLARE_ACCOUNT_ID
  GITHUB_PERSONAL_ACCESS_TOKEN  Used for both repo create and git push

Spec: rank-ai/docs/build-site-skill-spec.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = REPO_ROOT / "clients"
TEMPLATES_DIR = REPO_ROOT / "templates"
SITES_DIR = REPO_ROOT / "sites"
STARTER_DIR = TEMPLATES_DIR / "astro-starter"

GH_OWNER = "restorationai"   # locked per architectural decision
GH_API = "https://api.github.com"
CF_API = "https://api.cloudflare.com/client/v4"

BINARY_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".ttf"}


# ----------------------------------------------------------------------------
# IO helpers
# ----------------------------------------------------------------------------


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict:
    if not path.exists():
        die(f"Missing required file: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        die(f"Invalid JSON in {path}: {e}")


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


# ----------------------------------------------------------------------------
# Token resolution
# ----------------------------------------------------------------------------


DEFAULTS = {
    # Canonical restoration-industry palette (probritegen template).
    # Per-client overrides flow through plan-input.json's brand block.
    "BRAND_PRIMARY_COLOR": "#0d1b3e",   # navy — dominant background
    "BRAND_PRIMARY_DARK": "#1e5ad4",    # saturated blue — CTAs, links, hovers
    "BRAND_PRIMARY_LIGHT": "#bdd0ff",
    "BRAND_ACCENT_COLOR": "#f97316",    # orange — emergency / accent
    "BRAND_FONT_SANS": "Inter",
    "BRAND_FONT_DISPLAY": "Inter",
}


def resolve_tokens(client: dict, plan_input: dict) -> tuple[dict, dict]:
    """Return (string_tokens, json_tokens). JSON tokens substitute as bare
    JS literals (no surrounding quotes)."""
    brand = plan_input.get("brand", {})
    domain = client["domain"]
    slug = client["slug"]

    # Resolve primary area for derived city/state
    areas = plan_input.get("service_areas", [])
    primary_area = next((a for a in areas if a.get("primary")), areas[0] if areas else {})

    # Phone — keep both formatted and raw forms
    phone_display = brand.get("phone", "")
    phone_raw = "+1" + re.sub(r"\D", "", phone_display) if phone_display else ""

    # Display defaults
    display_name = brand.get("display_name", client.get("display_name", slug))
    short_name = brand.get("short_name", display_name)
    initials = "".join(w[0].upper() for w in display_name.split()[:2]) or slug[:2].upper()

    string_tokens = {
        "BRAND_SLUG": slug,
        "BRAND_DISPLAY_NAME": display_name,
        "BRAND_SHORT_NAME": short_name,
        "BRAND_LEGAL_NAME": brand.get("legal_name", display_name),
        "BRAND_DOMAIN": domain,
        "BRAND_CANONICAL_URL": f"https://{domain}",
        "BRAND_PHONE": phone_display,
        "BRAND_PHONE_RAW": phone_raw,
        "BRAND_EMAIL": brand.get("email", ""),
        "BRAND_HOURS": brand.get("hours", "24/7"),
        "BRAND_FOUNDED_YEAR": str(brand.get("founded_year", "")),
        "BRAND_PRIMARY_CITY": primary_area.get("city", ""),
        "BRAND_PRIMARY_STATE": primary_area.get("state", ""),
        "BRAND_STREET_ADDRESS": brand.get("street_address", ""),
        "BRAND_POSTAL_CODE": brand.get("postal_code", ""),
        "BRAND_LAT": str(brand.get("lat", "")),
        "BRAND_LNG": str(brand.get("lng", "")),
        "BRAND_PLACE_ID": brand.get("place_id", ""),
        "BRAND_GOOGLE_CID": brand.get("google_cid", ""),
        "BRAND_LICENSE_AUTHORITY": brand.get("license_authority", ""),
        "BRAND_LICENSE_TYPE": brand.get("license_type", ""),
        "BRAND_GBP_RATING_VALUE": str(brand.get("gbp_rating_value", "")),
        "BRAND_GBP_REVIEW_COUNT": str(brand.get("gbp_review_count", "")),
        "BRAND_TAGLINE": brand.get(
            "tagline",
            f"24/7 restoration services in {primary_area.get('city','')}, "
            f"{primary_area.get('state','')}.",
        ),
        "BRAND_CTA_LABEL": brand.get(
            "cta_label",
            "Call for a Free Estimate"
            if "construction" in plan_input.get("verticals", [])
            else "24/7 Emergency Hotline",
        ),
        "BRAND_LOGO_URL": brand.get("logo_url", f"https://images.{domain}/brand/logo.png"),
        "BRAND_INITIALS": initials,
        "BRAND_IMAGES_BASE": f"https://images.{domain}",
        "BRAND_GOOGLE_MAPS_API_KEY": brand.get("google_maps_api_key", ""),
        **DEFAULTS,
    }

    # Per-client override for any DEFAULTS-style fields
    for k in DEFAULTS:
        bk = k.replace("BRAND_", "").lower()
        if bk in brand:
            string_tokens[k] = str(brand[bk])

    json_tokens = {
        "BRAND_LICENSE_NUMBERS_JSON": json.dumps(brand.get("license_numbers", [])),
        "BRAND_CERTIFICATIONS_JSON": json.dumps(brand.get("certifications", [])),
        "BRAND_SAME_AS_URLS_JSON": json.dumps(brand.get("same_as_urls", [])),
    }

    return string_tokens, json_tokens


def build_llms_substitutions(plan_input: dict, client: dict) -> dict:
    """Computed llms.txt fields — services list, areas list, etc."""
    domain = client["domain"]
    services = plan_input.get("services", [])
    areas = plan_input.get("service_areas", [])
    certs = plan_input.get("brand", {}).get("certifications", [])

    # Note: services here are slugs; the human display name comes from the
    # restoration template's services catalog. We re-load it for display.
    catalog_path = TEMPLATES_DIR / "restoration" / "services.json"
    catalog = {s["slug"]: s for s in load_json(catalog_path)["services"]}

    svc_lines = []
    for slug in services:
        s = catalog.get(slug, {"display_name": slug})
        svc_lines.append(f"- {s['display_name']}: https://{domain}/services/{slug}/")
    area_lines = []
    for a in areas:
        area_lines.append(f"- {a['city']}, {a['state']}: https://{domain}/service-areas/{a['slug']}/")

    radius_default = f"Greater {areas[0]['city']} region" if areas else "Local area"
    radius = plan_input.get("service_radius_description") or radius_default

    return {
        "LLMS_SERVICES_INDEX": "\n".join(svc_lines) if svc_lines else "(no services)",
        "LLMS_SERVICE_AREAS_INDEX": "\n".join(area_lines) if area_lines else "(no areas)",
        "LLMS_CERTIFICATIONS": ", ".join(certs) if certs else "Licensed and insured",
        "LLMS_SERVICE_RADIUS": radius,
    }


def substitute_text(text: str, tokens: dict) -> tuple[str, set]:
    for k, v in tokens.items():
        text = text.replace(f"{{{{{k}}}}}", v)
    return text, set(re.findall(r"\{\{[A-Z_]+\}\}", text))


# ----------------------------------------------------------------------------
# Starter copy + substitution
# ----------------------------------------------------------------------------


def copy_starter(site_dir: Path) -> None:
    if site_dir.exists():
        # Preserve node_modules / .astro between scaffolds
        for child in STARTER_DIR.iterdir():
            target = site_dir / child.name
            if target.exists() and target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
            if child.is_dir():
                shutil.copytree(child, target)
            else:
                shutil.copy2(child, target)
    else:
        site_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(STARTER_DIR, site_dir, dirs_exist_ok=True)


def substitute_in_tree(root: Path, tokens: dict) -> tuple[int, set]:
    """Walk root, substitute tokens in every text file, return (files_changed, unsubstituted_set)."""
    files_changed = 0
    leftover: set = set()
    SKIP_DIRS = {"node_modules", ".astro", "dist", ".git"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(p in SKIP_DIRS for p in path.parts):
            continue
        if path.suffix in BINARY_EXTS:
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        new_text, leftover_here = substitute_text(text, tokens)
        if new_text != text:
            path.write_text(new_text)
            files_changed += 1
        leftover |= leftover_here
    # README's literal {{TOKEN}} doc strings are expected leftovers — strip from set
    leftover.discard("{{TOKEN}}")
    leftover.discard("{{TOKENS}}")
    return files_changed, leftover


# ----------------------------------------------------------------------------
# Content collection markdown generation
# ----------------------------------------------------------------------------


# Map archetype → (collection_dir, filename_template)
ARCHETYPE_TO_COLLECTION = {
    "home":               ("pages", "home"),
    "about":              ("pages", "about"),
    "contact":            ("pages", "contact"),
    "services-hub":       ("pages", "services"),
    "service-areas-hub":  ("pages", "service-areas"),
    "blog-index":         ("pages", "blog-index"),
    "service-landing":    ("services", None),       # derived
    "service-area":       ("serviceAreas", None),   # derived
    "service-area-service": ("locations", None),    # derived
    "blog-post":          ("blog", None),           # derived
    "legal":              ("legal", None),          # derived
}


def derive_filename(page: dict) -> str:
    """Compute the markdown filename (without .md) for a given plan page."""
    arc = page["archetype"]
    url = page["url_path"]
    coll, fixed_name = ARCHETYPE_TO_COLLECTION[arc]
    if fixed_name:
        return fixed_name
    # Strip trailing slash, split
    parts = [p for p in url.split("/") if p]
    if arc == "service-landing":
        # /services/{slug}/ -> slug
        return parts[-1]
    if arc == "service-area":
        # /service-areas/{slug}/ -> slug
        return parts[-1]
    if arc == "service-area-service":
        # /service-areas/{area}/{service}/ -> area__service
        return f"{parts[1]}__{parts[2]}"
    if arc == "blog-post":
        # /blog/{slug}/ -> slug
        return parts[-1]
    if arc == "legal":
        # /privacy/ -> privacy
        return parts[-1]
    return slugify(url)


def page_hash(page: dict) -> str:
    """SHA-256 of plan-relevant fields. Used for idempotency on re-scaffold."""
    payload = json.dumps({
        k: page.get(k) for k in [
            "url_path", "archetype", "title", "h1", "meta_description",
            "primary_keyword", "secondary_keywords", "search_intent",
            "target_word_count", "image_roles", "schema_stubs", "priority",
            "internal_links_out",
        ]
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def derive_breadcrumb(page: dict, services_lookup: dict, areas_lookup: dict) -> list[dict]:
    """Compute breadcrumb trail from URL structure."""
    arc = page["archetype"]
    url = page["url_path"]
    parts = [p for p in url.split("/") if p]

    crumbs = [{"name": "Home", "url": "/"}]
    if arc == "home":
        return crumbs
    if arc == "blog-index":
        crumbs.append({"name": "Blog"})
        return crumbs
    if arc == "service-landing":
        crumbs.append({"name": "Services", "url": "/services/"})
        svc = services_lookup.get(parts[-1])
        crumbs.append({"name": svc["display_name"] if svc else parts[-1]})
        return crumbs
    if arc == "service-area":
        crumbs.append({"name": "Service Areas", "url": "/service-areas/"})
        area = areas_lookup.get(parts[-1])
        crumbs.append({"name": area["city"] if area else parts[-1]})
        return crumbs
    if arc == "service-area-service":
        area_slug, service_slug = parts[1], parts[2]
        crumbs.append({"name": "Service Areas", "url": "/service-areas/"})
        area = areas_lookup.get(area_slug)
        crumbs.append({
            "name": area["city"] if area else area_slug,
            "url": f"/service-areas/{area_slug}/",
        })
        svc = services_lookup.get(service_slug)
        crumbs.append({"name": svc["display_name"] if svc else service_slug})
        return crumbs
    if arc == "blog-post":
        crumbs.append({"name": "Blog", "url": "/blog/"})
        crumbs.append({"name": page["title"]})
        return crumbs
    if arc == "legal":
        crumbs.append({"name": page["title"].split(" |")[0]})
        return crumbs
    # services-hub, service-areas-hub, about, contact — single segment
    name_map = {
        "services-hub": "Services",
        "service-areas-hub": "Service Areas",
        "about": "About",
        "contact": "Contact",
    }
    crumbs.append({"name": name_map.get(arc, parts[0].title())})
    return crumbs


PLACEHOLDER_BODY = (
    "<!-- Page body not yet generated. Run `build_site.py render --slug {slug}` "
    "to populate. The frontmatter above is the source-of-truth metadata from the plan. -->\n"
    "\nPlaceholder content for {h1}.\n"
)


def write_content_md(
    site_dir: Path,
    page: dict,
    plan_input: dict,
    services_lookup: dict,
    areas_lookup: dict,
    blog_topics_lookup: dict,
    internal_links: dict,
) -> Path:
    arc = page["archetype"]
    coll, _ = ARCHETYPE_TO_COLLECTION[arc]
    fname = derive_filename(page)
    out = site_dir / "src" / "content" / coll / f"{fname}.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    url = page["url_path"]
    parts = [p for p in url.split("/") if p]

    # Build collection-specific frontmatter fields
    fm: dict = {
        "archetype": arc,
        "title": page["title"],
        "h1": page["h1"],
        "meta_description": page["meta_description"],
        "primary_keyword": page["primary_keyword"],
        "secondary_keywords": page.get("secondary_keywords", []),
        "search_intent": page.get("search_intent", ""),
        "priority": page.get("priority", 0),
        "plan_hash": page_hash(page),
        "generated_at": now_iso(),
        "manual_override": False,
        "internal_links": internal_links.get(url, []),
        "breadcrumb": derive_breadcrumb(page, services_lookup, areas_lookup),
        "faq": [],
    }

    if arc == "service-landing":
        svc = services_lookup.get(parts[-1])
        fm["service_slug"] = parts[-1]
        fm["service_display"] = svc["display_name"] if svc else parts[-1]
    elif arc == "service-area":
        area = areas_lookup.get(parts[-1])
        fm["area_slug"] = parts[-1]
        fm["city"] = area["city"] if area else ""
        fm["state"] = area["state"] if area else ""
        fm["primary"] = bool(area.get("primary")) if area else False
    elif arc == "service-area-service":
        area = areas_lookup.get(parts[1])
        svc = services_lookup.get(parts[2])
        fm["area_slug"] = parts[1]
        fm["service_slug"] = parts[2]
        fm["city"] = area["city"] if area else ""
        fm["state"] = area["state"] if area else ""
        fm["service_display"] = svc["display_name"] if svc else parts[2]
        if svc and svc.get("content_guardrails") == "sensitive":
            fm["content_guardrails"] = "sensitive"
    elif arc == "blog-post":
        slug = parts[-1]
        topic = blog_topics_lookup.get(slug, {})
        fm["published_at"] = topic.get("published_at", now_iso()[:10])
        fm["services"] = topic.get("services", [])
    elif arc == "legal":
        fm["ref"] = parts[-1]

    body = PLACEHOLDER_BODY.format(slug=plan_input.get("_slug", ""), h1=page["h1"])

    # YAML frontmatter — use json.dumps for arrays/objects which is valid YAML
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, (list, dict, bool)):
            lines.append(f"{k}: {json.dumps(v)}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        else:
            # String — needs quoting if it contains : or special chars
            escaped = str(v).replace('"', '\\"')
            lines.append(f'{k}: "{escaped}"')
    lines.append("---")
    lines.append(body)

    out.write_text("\n".join(lines))
    return out


def render_all_content(
    site_dir: Path,
    plan_input: dict,
    url_plan: dict,
    internal_links: dict,
) -> int:
    """Write one content collection markdown file per planned URL."""
    # Build lookups
    services_lookup = {s["slug"]: s for s in plan_input.get("services_resolved", [])}
    # If services_resolved isn't present (it's not — services in plan-input is a slug list),
    # rebuild from the restoration template
    if not services_lookup:
        catalog = load_json(TEMPLATES_DIR / "restoration" / "services.json")
        catalog_by_slug = {s["slug"]: s for s in catalog["services"]}
        services_lookup = {
            s: catalog_by_slug[s] for s in plan_input.get("services", []) if s in catalog_by_slug
        }

    areas_lookup = {a["slug"]: a for a in plan_input.get("service_areas", [])}

    blog_topics = load_json(TEMPLATES_DIR / "restoration" / "seed-blog-topics.json")
    blog_topics_lookup = {t["slug"]: t for t in blog_topics["topics"]}

    count = 0
    for page in url_plan["pages"]:
        write_content_md(
            site_dir, page, plan_input,
            services_lookup, areas_lookup, blog_topics_lookup,
            internal_links,
        )
        count += 1
    return count


# ----------------------------------------------------------------------------
# Git + GitHub operations
# ----------------------------------------------------------------------------


def gh_token() -> str:
    t = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not t:
        die("Missing GITHUB_PERSONAL_ACCESS_TOKEN env var (see rank-ai/.env).")
    return t


def gh_api(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{GH_API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {gh_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read().decode()
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise RuntimeError(f"GitHub {method} {path} -> HTTP {e.code}: {body_text}")


def gh_repo_exists(name: str) -> bool:
    try:
        gh_api("GET", f"/repos/{GH_OWNER}/{name}")
        return True
    except RuntimeError as e:
        if "HTTP 404" in str(e):
            return False
        raise


def gh_create_repo(name: str, description: str, private: bool = False) -> dict:
    return gh_api("POST", "/user/repos", {
        "name": name,
        "description": description,
        "private": private,
        "auto_init": False,
        "has_issues": True,
        "has_projects": False,
        "has_wiki": False,
    })


def git(cmd: list[str], cwd: Path) -> str:
    out = subprocess.run(
        ["git"] + cmd, cwd=str(cwd),
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(cmd)} failed (exit {out.returncode}):\n"
            f"  stdout: {out.stdout.strip()}\n  stderr: {out.stderr.strip()}"
        )
    return out.stdout.strip()


def git_init_and_push(site_dir: Path, repo_name: str, commit_message: str) -> None:
    token = gh_token()
    remote = f"https://x-access-token:{token}@github.com/{GH_OWNER}/{repo_name}.git"

    is_new = not (site_dir / ".git").exists()
    if is_new:
        git(["init", "-b", "main"], site_dir)
        # Set local committer for the repo. The user can override globally.
        git(["config", "user.name", "Rank AI Build"], site_dir)
        git(["config", "user.email", "build@restorationai.io"], site_dir)
        git(["remote", "add", "origin", remote], site_dir)
    else:
        # Update remote URL (token may have rotated)
        try:
            git(["remote", "set-url", "origin", remote], site_dir)
        except RuntimeError:
            git(["remote", "add", "origin", remote], site_dir)

    git(["add", "."], site_dir)
    # Skip commit if nothing changed
    try:
        git(["commit", "-m", commit_message], site_dir)
    except RuntimeError as e:
        if "nothing to commit" in str(e).lower():
            print("      (no changes to commit)")
        else:
            raise

    git(["push", "-u", "origin", "main"], site_dir)

    # Create or update staging branch (mirror of main initially)
    branches = git(["branch", "-a"], site_dir)
    if "staging" not in branches:
        git(["checkout", "-b", "staging"], site_dir)
    else:
        git(["checkout", "staging"], site_dir)
        try:
            git(["merge", "main", "--ff-only"], site_dir)
        except RuntimeError:
            pass
    git(["push", "-u", "origin", "staging"], site_dir)
    git(["checkout", "main"], site_dir)


# ----------------------------------------------------------------------------
# Cloudflare Pages project creation (gated on OAuth)
# ----------------------------------------------------------------------------


def cf_api(method: str, path: str, token: str, body: dict | None = None) -> dict:
    url = f"{CF_API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise RuntimeError(f"Cloudflare {method} {path} -> HTTP {e.code}: {body_text}")


def cf_pages_project_exists(account_id: str, project_name: str, token: str) -> bool:
    try:
        cf_api("GET", f"/accounts/{account_id}/pages/projects/{project_name}", token)
        return True
    except RuntimeError as e:
        if "HTTP 404" in str(e):
            return False
        raise


def cf_create_pages_project(account_id: str, project_name: str, repo_name: str, token: str) -> dict:
    body = {
        "name": project_name,
        "production_branch": "main",
        "source": {
            "type": "github",
            "config": {
                "owner": GH_OWNER,
                "repo_name": repo_name,
                "production_branch": "main",
                "pr_comments_enabled": True,
                "deployments_enabled": True,
                "preview_branch_includes": ["staging"],
                "preview_deployment_setting": "custom",
            },
        },
        "build_config": {
            "build_command": "npm run build",
            "destination_dir": "dist",
            "root_dir": "",
        },
    }
    return cf_api("POST", f"/accounts/{account_id}/pages/projects", token, body)


def cf_creds() -> tuple[str, str]:
    token = (
        os.environ.get("CLOUDFLARE_PAGES_API_TOKEN")
        or os.environ.get("CLOUDFLARE_R2_API_TOKEN")
        or os.environ.get("CLOUDFLARE_API_TOKEN")
        or ""
    )
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    if not token or not account_id:
        die("Missing CLOUDFLARE_* env vars (see rank-ai/.env).")
    return token, account_id


# ----------------------------------------------------------------------------
# Anthropic API + prompt template handling (render phase)
# ----------------------------------------------------------------------------

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-6"


def anthropic_call(system: str, user: str, *, model: str = ANTHROPIC_DEFAULT_MODEL,
                   max_tokens: int = 4096, temperature: float = 0.6,
                   max_retries: int = 3) -> tuple[str, dict]:
    import socket
    import time

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        die("Missing ANTHROPIC_API_KEY env var (see rank-ai/.env).")
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    data = json.dumps(body).encode()

    last_err: str = ""
    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(ANTHROPIC_API, data=data, method="POST",
                                     headers={
                                         "x-api-key": api_key,
                                         "anthropic-version": "2023-06-01",
                                         "content-type": "application/json",
                                     })
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                payload = json.loads(resp.read().decode())
            content = payload["content"][0]["text"]
            usage = payload.get("usage", {})
            return content, usage
        except urllib.error.HTTPError as e:
            err = e.read().decode(errors="replace")
            # 429 / 5xx are retryable. 4xx (except 429) usually mean malformed request.
            if e.code == 429 or 500 <= e.code < 600:
                last_err = f"HTTP {e.code}: {err[:300]}"
                wait = 2 ** attempt
                print(f"      retry {attempt}/{max_retries} in {wait}s ({last_err[:100]}...)")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Anthropic POST -> HTTP {e.code}: {err}")
        except (urllib.error.URLError, socket.timeout, ConnectionResetError) as e:
            last_err = str(e)
            wait = 2 ** attempt
            print(f"      retry {attempt}/{max_retries} in {wait}s (network: {last_err[:100]})")
            time.sleep(wait)
            continue

    raise RuntimeError(f"Anthropic POST failed after {max_retries} retries. Last error: {last_err}")


# Simple {dotted.key} + {dotted.key|filter} substitution. Empty value if missing.
PROMPT_VAR_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_.]*(?:\|[a-z]+)*)\}")

PROMPT_FILTERS = {
    "lower": str.lower,
    "upper": str.upper,
    "title": str.title,
}


def _resolve_dot(ctx: dict, dotted: str) -> str:
    cur = ctx
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return ""
        if cur is None:
            return ""
    if isinstance(cur, (list, dict)):
        return json.dumps(cur)
    return str(cur)


def prompt_render(template: str, ctx: dict) -> str:
    def repl(m: re.Match) -> str:
        expr = m.group(1)
        parts = expr.split("|")
        value = _resolve_dot(ctx, parts[0])
        for f in parts[1:]:
            if f in PROMPT_FILTERS:
                value = PROMPT_FILTERS[f](value)
        return value
    return PROMPT_VAR_RE.sub(repl, template)


def load_prompt(site_dir: Path, archetype: str) -> tuple[str, str, dict]:
    """Return (system_prompt, user_prompt_template, frontmatter)."""
    system_path = site_dir / "prompts" / "_system.md"
    if not system_path.exists():
        die(f"Missing system prompt at {system_path}")
    system_prompt = system_path.read_text().strip()

    user_path = site_dir / "prompts" / f"{archetype}.md"
    if not user_path.exists():
        return system_prompt, "", {}

    raw = user_path.read_text()
    # Parse frontmatter
    fm: dict = {}
    body = raw
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 4)
        if end > 0:
            fm_block = raw[4:end]
            body = raw[end + 5:]
            for line in fm_block.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    v = v.strip()
                    if v.isdigit():
                        fm[k.strip()] = int(v)
                    else:
                        fm[k.strip()] = v
    return system_prompt, body.strip(), fm


SENSITIVE_BLOCK = (
    "# Sensitive content guardrails (REQUIRED)\n\n"
    "This service involves sensitive contexts. Apply these additional rules:\n\n"
    "- Use a clinical, empathetic tone. Avoid graphic detail.\n"
    "- Do not describe the scene, the substances, or the trauma directly.\n"
    "- Focus on logistics: discretion, certifications, insurance, response, what the visitor can expect from us.\n"
    "- FAQ topics should be: privacy, response time, certifications, insurance, family/property coordination — NOT details of the incident.\n"
    "- Acknowledge difficulty briefly; do not dwell.\n"
)


def build_prompt_context(
    page: dict,
    plan_input: dict,
    client: dict,
    services_lookup: dict,
    areas_lookup: dict,
    blog_topics_lookup: dict,
    prompt_fm: dict,
) -> dict:
    """Resolve a flat ctx dict for prompt substitution."""
    arc = page["archetype"]
    url = page["url_path"]
    parts = [p for p in url.split("/") if p]

    brand = dict(plan_input.get("brand", {}))
    primary_area = next((a for a in plan_input.get("service_areas", []) if a.get("primary")),
                        plan_input.get("service_areas", [{}])[0])
    brand.setdefault("primary_city", primary_area.get("city", ""))
    brand.setdefault("primary_state", primary_area.get("state", ""))
    brand.setdefault("display_name", client.get("display_name", ""))
    brand["domain"] = client["domain"]
    brand["canonical_url"] = f"https://{client['domain']}"
    # license_numbers_suffix is " (#X, #Y)" or ""
    licnums = brand.get("license_numbers", [])
    if licnums:
        brand["license_numbers_suffix"] = " (#" + ", #".join(licnums) + ")"
    else:
        brand["license_numbers_suffix"] = ""

    ctx = {
        "brand": brand,
        "page": page,
        "target_word_count": prompt_fm.get("target_word_count", 700),
        "faq_count": prompt_fm.get("faq_count", 4),
        "sensitive_block": "",
    }

    # Archetype-specific extras
    if arc == "service-landing":
        svc = services_lookup.get(parts[-1], {})
        svc["short_or_display_name"] = svc.get("short_name") or svc.get("display_name", "")
        ctx["service"] = svc
        if svc.get("content_guardrails") == "sensitive":
            ctx["sensitive_block"] = SENSITIVE_BLOCK
    elif arc == "service-area":
        ctx["area"] = areas_lookup.get(parts[-1], {})
    elif arc == "service-area-service":
        area = areas_lookup.get(parts[1], {})
        svc = services_lookup.get(parts[2], {})
        svc["short_or_display_name"] = svc.get("short_name") or svc.get("display_name", "")
        ctx["area"] = area
        ctx["service"] = svc
        if svc.get("content_guardrails") == "sensitive":
            ctx["sensitive_block"] = SENSITIVE_BLOCK
    elif arc == "blog-post":
        slug = parts[-1]
        ctx["post"] = blog_topics_lookup.get(slug, {})
    elif arc == "legal":
        ctx["legal_ref"] = parts[-1]

    return ctx


def parse_llm_json(text: str) -> dict:
    """Robust JSON parse — strip code fences if present."""
    text = text.strip()
    if text.startswith("```"):
        # Strip opening fence (```json or ```)
        text = re.sub(r"^```[a-z]*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    return json.loads(text)


def update_content_md(
    site_dir: Path,
    page: dict,
    body_markdown: str,
    faq: list,
) -> Path:
    """Re-write the markdown for a page, updating body and faq while preserving
    the existing frontmatter structure."""
    arc = page["archetype"]
    coll, _ = ARCHETYPE_TO_COLLECTION[arc]
    fname = derive_filename(page)
    path = site_dir / "src" / "content" / coll / f"{fname}.md"
    if not path.exists():
        die(f"Cannot render — content file missing: {path}. Did you run scaffold?")

    raw = path.read_text()
    # Split frontmatter from body
    if not raw.startswith("---\n"):
        die(f"Malformed frontmatter in {path}")
    end = raw.find("\n---\n", 4)
    if end < 0:
        die(f"Unclosed frontmatter in {path}")
    fm_block = raw[4:end]
    # Parse fm_block line-by-line — same shape we wrote in write_content_md
    fm: dict = {}
    for line in fm_block.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip()
        if v.startswith("[") or v.startswith("{") or v in ("true", "false", "null"):
            try:
                fm[k] = json.loads(v)
            except json.JSONDecodeError:
                fm[k] = v
        elif v.startswith('"') and v.endswith('"'):
            fm[k] = json.loads(v) if v.startswith('"') else v
        elif re.match(r"^-?\d+(\.\d+)?$", v):
            fm[k] = float(v) if "." in v else int(v)
        else:
            fm[k] = v

    # Update render-specific fields
    fm["faq"] = faq
    fm["generated_at"] = now_iso()
    # Mark as rendered (not just scaffolded) by clearing the placeholder marker
    fm["rendered"] = True

    # Re-serialize
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, (list, dict, bool)):
            lines.append(f"{k}: {json.dumps(v)}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        else:
            escaped = str(v).replace('"', '\\"')
            lines.append(f'{k}: "{escaped}"')
    lines.append("---")
    lines.append(body_markdown.strip())

    path.write_text("\n".join(lines) + "\n")
    return path


def cost_estimate(usage: dict, model: str) -> float:
    """Rough USD cost estimate for one Anthropic call."""
    # Sonnet 4.6 (as of 2026): $3/MTok input, $15/MTok output, $0.30 cache read, $3.75 cache create (5m)
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    cache_r = usage.get("cache_read_input_tokens", 0)
    cache_w = usage.get("cache_creation_input_tokens", 0)
    return (inp * 3 + cache_r * 0.30 + cache_w * 3.75 + out * 15) / 1_000_000


def log_cost(site_dir: Path, page: dict, usage: dict, model: str, dollars: float) -> None:
    log = site_dir / ".rank-ai" / "cost-log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as f:
        f.write(json.dumps({
            "ts": now_iso(),
            "url": page["url_path"],
            "archetype": page["archetype"],
            "model": model,
            "usage": usage,
            "dollars": round(dollars, 6),
        }) + "\n")


# ----------------------------------------------------------------------------
# Subcommand: render
# ----------------------------------------------------------------------------


def _is_already_rendered(site_dir: Path, page: dict) -> bool:
    """Check if the content file already has rendered: true in frontmatter."""
    arc = page["archetype"]
    coll, _ = ARCHETYPE_TO_COLLECTION[arc]
    fname = derive_filename(page)
    path = site_dir / "src" / "content" / coll / f"{fname}.md"
    if not path.exists():
        return False
    try:
        raw = path.read_text()
        if not raw.startswith("---\n"):
            return False
        end = raw.find("\n---\n", 4)
        if end < 0:
            return False
        fm_block = raw[4:end]
        for line in fm_block.splitlines():
            if line.startswith("rendered: true"):
                return True
            if line.startswith("manual_override: true"):
                return True
    except Exception:
        pass
    return False


def cmd_render(args) -> int:
    import concurrent.futures
    import threading

    slug = args.slug
    client = load_json(CLIENTS_DIR / f"{slug}.json")
    plan_input = load_json(CLIENTS_DIR / slug / "plan-input.json")
    plan_input["_slug"] = slug
    url_plan = load_json(CLIENTS_DIR / slug / "plan" / "url-plan.json")

    site_dir = SITES_DIR / slug
    if not site_dir.exists():
        die(f"Site dir {site_dir} doesn't exist. Run scaffold first.")

    # Build lookups
    catalog = load_json(TEMPLATES_DIR / "restoration" / "services.json")
    catalog_by_slug = {s["slug"]: s for s in catalog["services"]}
    services_lookup = {
        s: catalog_by_slug[s] for s in plan_input.get("services", []) if s in catalog_by_slug
    }
    areas_lookup = {a["slug"]: a for a in plan_input.get("service_areas", [])}
    blog_topics = load_json(TEMPLATES_DIR / "restoration" / "seed-blog-topics.json")
    blog_topics_lookup = {t["slug"]: t for t in blog_topics["topics"]}

    # Filter pages
    pages = url_plan["pages"]
    if args.archetype:
        pages = [p for p in pages if p["archetype"] == args.archetype]
    if args.url:
        pages = [p for p in pages if p["url_path"] == args.url]
    # Order by priority desc so high-value pages render first (best output if interrupted)
    pages.sort(key=lambda p: -p.get("priority", 0))
    if args.limit:
        pages = pages[: args.limit]

    if not pages:
        die("No pages matched the filter.")

    # Skip already-rendered unless --force
    skipped_pre = 0
    if not args.force:
        filtered = []
        for p in pages:
            if _is_already_rendered(site_dir, p):
                skipped_pre += 1
            else:
                filtered.append(p)
        pages = filtered

    total_target = len(pages)
    print(f"==> Rendering {total_target} page(s) for {slug}")
    if skipped_pre:
        print(f"    Skipping {skipped_pre} already-rendered (use --force to override).")
    print(f"    Model: {args.model}")
    print(f"    Workers: {args.workers}")
    if args.archetype:
        print(f"    Archetype filter: {args.archetype}")
    if args.limit:
        print(f"    Limit: {args.limit}")
    print()

    cost_lock = threading.Lock()
    print_lock = threading.Lock()
    done_counter = {"n": 0}
    total_cost = 0.0
    succeeded = 0
    failed: list = []

    def render_one(page: dict) -> tuple[str, dict | str]:
        """Returns (status, info). status ∈ {success, no_prompt, api_error, non_json, empty}."""
        arc = page["archetype"]
        url = page["url_path"]
        system_prompt, user_template, prompt_fm = load_prompt(site_dir, arc)
        if not user_template:
            return ("no_prompt", url)
        ctx = build_prompt_context(page, plan_input, client, services_lookup,
                                   areas_lookup, blog_topics_lookup, prompt_fm)
        user_prompt = prompt_render(user_template, ctx)
        try:
            raw, usage = anthropic_call(system_prompt, user_prompt,
                                        model=args.model,
                                        max_tokens=prompt_fm.get("max_tokens", 4096),
                                        temperature=prompt_fm.get("temperature", 0.6))
        except RuntimeError as e:
            return ("api_error", str(e)[:200])
        try:
            data = parse_llm_json(raw)
        except json.JSONDecodeError:
            return ("non_json", raw[:200])
        body = data.get("body_markdown", "").strip()
        faq = data.get("faq", [])
        if not body:
            return ("empty", "")
        update_content_md(site_dir, page, body, faq)
        dollars = cost_estimate(usage, args.model)
        with cost_lock:
            log_cost(site_dir, page, usage, args.model, dollars)
        return ("success", {
            "body_len": len(body),
            "faq_count": len(faq),
            "dollars": dollars,
            "usage": usage,
        })

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_page = {executor.submit(render_one, p): p for p in pages}
        for future in concurrent.futures.as_completed(future_to_page):
            page = future_to_page[future]
            arc = page["archetype"]
            url = page["url_path"]
            try:
                status, info = future.result()
            except Exception as e:
                status, info = ("exception", str(e)[:200])

            with print_lock:
                done_counter["n"] += 1
                n = done_counter["n"]
                if status == "success":
                    nonlocal_cost = info["dollars"]
                    total_cost += nonlocal_cost
                    succeeded += 1
                    print(f"[{n:3}/{total_target}] ✓ {arc} :: {url}")
                    print(f"           {info['body_len']:>5} chars + {info['faq_count']} FAQ  "
                          f"${nonlocal_cost:.4f}  "
                          f"{info['usage'].get('input_tokens',0)}+{info['usage'].get('output_tokens',0)} tok")
                elif status == "no_prompt":
                    print(f"[{n:3}/{total_target}] ⚠ {arc} :: {url} — no prompt for archetype")
                    failed.append((url, "no_prompt"))
                else:
                    print(f"[{n:3}/{total_target}] ✗ {arc} :: {url} — {status}: {info}")
                    failed.append((url, f"{status}: {str(info)[:120]}"))

    print()
    print(f"==> Render summary")
    print(f"    Succeeded:   {succeeded}/{total_target}")
    print(f"    Failed:      {len(failed)}")
    print(f"    Skipped:     {skipped_pre} (already rendered)")
    print(f"    Total cost:  ${total_cost:.4f}")
    if failed:
        print()
        print("    Failures (first 10):")
        for url, reason in failed[:10]:
            print(f"      {url} :: {reason}")

    # Update client record
    client.setdefault("build", {})
    if succeeded:
        client["build"]["last_rendered_at"] = now_iso()
        client["build_status"] = "content_rendered" if succeeded == len(pages) else "content_partial"
    save_json(CLIENTS_DIR / f"{slug}.json", client)

    if args.push and succeeded > 0:
        print()
        print("==> Pushing to staging branch...")
        git_init_and_push(
            site_dir,
            client["build"]["github_repo"].split("/", 1)[1],
            f"Render {succeeded} page(s) via build_site.py at {now_iso()}",
        )
        print("    Pushed.")

    return 0 if not failed else 2


# ----------------------------------------------------------------------------
# Subcommand: scaffold
# ----------------------------------------------------------------------------


def cmd_scaffold(args) -> int:
    slug = args.slug
    client = load_json(CLIENTS_DIR / f"{slug}.json")
    plan_input_path = CLIENTS_DIR / slug / "plan-input.json"
    if not plan_input_path.exists():
        die(f"Missing plan input at {plan_input_path}. Run rank-ai-plan-site first.")
    plan_input = load_json(plan_input_path)
    plan_input["_slug"] = slug   # carry slug for placeholder body

    url_plan_path = CLIENTS_DIR / slug / "plan" / "url-plan.json"
    internal_links_path = CLIENTS_DIR / slug / "plan" / "internal-links.json"
    if not url_plan_path.exists() or not internal_links_path.exists():
        die(f"Missing plan artifacts in {url_plan_path.parent}. Run rank-ai-plan-site generate.")
    url_plan = load_json(url_plan_path)
    internal_links = load_json(internal_links_path)

    site_dir = SITES_DIR / slug
    repo_name = f"{slug}-site"

    print(f"==> Scaffolding {slug} → {site_dir}")
    print(f"    Plan URLs: {len(url_plan['pages'])}")
    print(f"    GitHub repo: {GH_OWNER}/{repo_name}")
    print()

    # Step 1: Copy starter + substitute tokens
    print("[1/5] Copying starter and substituting brand tokens...")
    copy_starter(site_dir)
    string_tokens, json_tokens = resolve_tokens(client, plan_input)
    llms_tokens = build_llms_substitutions(plan_input, client)
    all_tokens = {**string_tokens, **json_tokens, **llms_tokens}
    files_changed, leftover = substitute_in_tree(site_dir, all_tokens)
    if leftover:
        print(f"      WARNING: {len(leftover)} unsubstituted tokens: {sorted(leftover)}")
    print(f"      Files modified: {files_changed}")

    # Step 2: Generate content collection markdown
    print(f"[2/5] Generating {len(url_plan['pages'])} content collection entries...")
    # Make sure src/content has fresh subdirectories
    content_root = site_dir / "src" / "content"
    for sub in ("pages", "services", "serviceAreas", "locations", "blog", "legal"):
        (content_root / sub).mkdir(parents=True, exist_ok=True)
    count = render_all_content(site_dir, plan_input, url_plan, internal_links)
    print(f"      Wrote {count} markdown files.")

    # Step 3: Create GitHub repo (idempotent)
    print(f"[3/5] Ensuring GitHub repo {GH_OWNER}/{repo_name} exists...")
    if gh_repo_exists(repo_name):
        print("      Repo already exists, reusing.")
    else:
        description = f"Rank AI restoration site for {client['display_name']}."
        gh_create_repo(repo_name, description, private=args.private)
        print("      Repo created.")

    # Step 4: Git init + commit + push (main + staging)
    print("[4/5] Pushing to GitHub (main + staging)...")
    commit = args.message or f"Scaffold from rank-ai-build-site at {now_iso()}"
    git_init_and_push(site_dir, repo_name, commit)
    # Remove the nested .git so the monorepo tracks files directly instead of
    # recording sites/{slug}/ as a submodule (which breaks git subtree split).
    nested_git = site_dir / ".git"
    if nested_git.exists():
        import shutil as _shutil
        _shutil.rmtree(nested_git)
        print("      Removed nested .git (monorepo-safe).")
    print("      Pushed to main and staging.")

    # Step 5: Cloudflare Pages project (gated on OAuth)
    print(f"[5/5] Creating Cloudflare Pages project rankai-{slug} (Git-connected)...")
    cf_token, account_id = cf_creds()
    project_name = f"rankai-{slug}"
    pages_status = "skipped"
    if cf_pages_project_exists(account_id, project_name, cf_token):
        print(f"      Pages project {project_name} already exists, reusing.")
        pages_status = "exists"
    else:
        try:
            cf_create_pages_project(account_id, project_name, repo_name, cf_token)
            print(f"      Pages project created.")
            pages_status = "created"
        except RuntimeError as e:
            err = str(e)
            if "github" in err.lower() and ("not authorized" in err.lower() or "10000" in err or "permission" in err.lower()):
                print()
                print("      ⚠ Cloudflare ↔ GitHub OAuth not yet authorized for this account.")
                print("        One-time manual step required:")
                print(f"          1. Open https://dash.cloudflare.com/{account_id}/workers-and-pages")
                print("          2. Create application → Pages → Connect to Git → authorize 'restorationai'")
                print("          3. Re-run this scaffold command (it's idempotent)")
                print()
                print("        Everything else succeeded; the repo is on GitHub and ready.")
                pages_status = "oauth_required"
            else:
                print(f"      Pages create failed: {err}")
                pages_status = "failed"

    # Step 6: Update client record
    client["build"] = client.get("build", {})
    client["build"].update({
        "scaffolded_at": now_iso(),
        "github_repo": f"{GH_OWNER}/{repo_name}",
        "pages_project": project_name,
        "starter_version": (STARTER_DIR / "VERSION").read_text().strip(),
        "url_count": len(url_plan["pages"]),
        "pages_status": pages_status,
    })
    client["build_status"] = "scaffolded"
    client["updated_at"] = now_iso()
    save_json(CLIENTS_DIR / f"{slug}.json", client)

    print()
    print("==> Scaffold complete.")
    print(f"    Local working tree: {site_dir}")
    print(f"    GitHub repo:        https://github.com/{GH_OWNER}/{repo_name}")
    if pages_status in ("created", "exists"):
        print(f"    Pages project:      https://dash.cloudflare.com/{account_id}/pages/view/{project_name}")
    print()
    print("    Next: implement render to populate page body content + images,")
    print("          then push-staging to preview at *.pages.dev.")
    return 0


# ----------------------------------------------------------------------------
# Subcommand: status
# ----------------------------------------------------------------------------


def cmd_status(args) -> int:
    slug = args.slug
    client = load_json(CLIENTS_DIR / f"{slug}.json")
    print(json.dumps({
        "slug": slug,
        "display_name": client.get("display_name"),
        "domain": client.get("domain"),
        "status": client.get("status"),
        "plan_status": client.get("plan_status"),
        "build_status": client.get("build_status"),
        "plan": client.get("plan"),
        "build": client.get("build"),
    }, indent=2))
    return 0


# ----------------------------------------------------------------------------
# Subcommand: sync-deploy  (push monorepo subtree → per-client GitHub repo)
# ----------------------------------------------------------------------------
#
# The Rank AI pipeline lives in a single monorepo (rank-ai/) for orchestration
# and AI-agent context. Each client's deployable site lives at sites/{slug}/.
# Cloudflare Pages can only watch ONE git repo per project, so we push each
# client's subtree to a dedicated per-client GitHub repo at
# github.com/{GH_OWNER}/{slug}-site. Cloudflare watches that repo and rebuilds
# on every push.
#
# Implementation: `git subtree split --prefix=sites/{slug}` builds a synthetic
# branch containing only the subtree's commits, which we then force-push to
# the per-client repo. Force-push because the per-client repo's history (from
# the original scaffold) is incompatible with the subtree's synthetic history.
# The per-client repo is a derived deploy artifact — git history there is not
# meant to be authoritative or human-meaningful. The monorepo is the source of
# truth.


def repo_root() -> Path:
    """Return the monorepo root (where rank-ai/.git lives)."""
    return REPO_ROOT


def _ensure_remote(name: str, url: str, cwd: Path) -> None:
    try:
        existing = git(["remote", "get-url", name], cwd)
        if existing.strip() != url:
            git(["remote", "set-url", name, url], cwd)
    except RuntimeError:
        git(["remote", "add", name, url], cwd)


def cmd_sync_deploy(args) -> int:
    slug = args.slug
    branch = args.branch
    site_dir = SITES_DIR / slug
    if not site_dir.exists():
        die(f"No subtree at {site_dir}. Run scaffold first.")

    mono = repo_root()
    if not (mono / ".git").exists():
        die(
            f"Expected monorepo at {mono} with a .git directory. The new topology "
            f"keeps everything in one repo and uses subtree push to ship per-client. "
            f"Run `git init` at {mono} or fix the topology before sync-deploy."
        )

    # Repo name: default to convention, but a client can override via
    # build.github_repo in their client record (useful for clients onboarded
    # before the {slug}-site convention was locked in).
    client_repo = f"{slug}-site"
    client_record_path = mono / "clients" / f"{slug}.json"
    if client_record_path.exists():
        client_record = json.loads(client_record_path.read_text())
        gh_field = client_record.get("build", {}).get("github_repo")
        if gh_field and "/" in gh_field:
            # Stored as "owner/repo" — extract repo part
            client_repo = gh_field.split("/", 1)[1]
    remote_name = f"deploy-{slug}"
    remote_url = f"https://x-access-token:{gh_token()}@github.com/{GH_OWNER}/{client_repo}.git"

    print(f"==> Syncing sites/{slug}/ → github.com/{GH_OWNER}/{client_repo}")
    print(f"    Target branch: {branch}")
    print(f"    Monorepo: {mono}")
    print()

    # Step 1: Working tree must be clean for subtree split to work cleanly
    status = git(["status", "--porcelain"], mono)
    if status.strip() and not args.allow_dirty:
        die(
            "Working tree has uncommitted changes. Subtree push from a dirty tree "
            "is risky. Either commit/stash changes, or re-run with --allow-dirty."
        )

    # Step 2: Ensure the per-client GitHub repo exists
    print(f"[1/4] Checking that github.com/{GH_OWNER}/{client_repo} exists...")
    if not gh_repo_exists(client_repo):
        print(f"      Repo missing. Creating it now...")
        client = load_json(CLIENTS_DIR / f"{slug}.json") if (CLIENTS_DIR / f"{slug}.json").exists() else {}
        description = f"Rank AI restoration site for {client.get('display_name', slug)}."
        gh_create_repo(client_repo, description, private=args.private)
        print(f"      Created.")
    else:
        print(f"      Repo exists, reusing.")

    # Step 3: Configure remote on the monorepo
    print(f"[2/4] Configuring remote {remote_name!r} on monorepo...")
    _ensure_remote(remote_name, remote_url, mono)
    print(f"      Remote set.")

    # Step 4: Subtree split — create a synthetic branch containing only sites/{slug}/'s history
    temp_branch = f"_sync-deploy-{slug}-{branch}"
    print(f"[3/4] Splitting subtree sites/{slug}/ into temp branch {temp_branch!r}...")
    # Clean up any leftover temp branch from a previous run
    try:
        git(["branch", "-D", temp_branch], mono)
    except RuntimeError:
        pass
    git(["subtree", "split", "--prefix", f"sites/{slug}", "-b", temp_branch], mono)
    print(f"      Split complete.")

    # Step 5: Force-push to per-client repo's target branch
    print(f"[4/4] Force-pushing {temp_branch} → {remote_name}/{branch}...")
    git(["push", "--force", remote_name, f"{temp_branch}:{branch}"], mono)
    print(f"      Pushed.")

    # Cleanup
    try:
        git(["branch", "-D", temp_branch], mono)
    except RuntimeError:
        pass

    # Step 6: Update client record
    rec_path = CLIENTS_DIR / f"{slug}.json"
    if rec_path.exists():
        client = load_json(rec_path)
        client.setdefault("build", {})
        client["build"]["github_repo"] = f"{GH_OWNER}/{client_repo}"
        if branch == "main":
            client["build"]["last_pushed_main_at"] = now_iso()
            client["build_status"] = "pushed_main"
        else:
            client["build"]["last_pushed_staging_at"] = now_iso()
            client["build_status"] = "pushed_staging"
        client["updated_at"] = now_iso()
        save_json(rec_path, client)

    print()
    print("==> Sync complete.")
    print(f"    GitHub repo:    https://github.com/{GH_OWNER}/{client_repo}")
    print(f"    Cloudflare Pages will auto-build the {branch} branch.")
    if branch == "main":
        print(f"    Production URL: https://rankai-{slug}.pages.dev/")
    else:
        print(f"    Preview URL:    https://staging.rankai-{slug}.pages.dev/")
    return 0


def cmd_sync_deploy_all(args) -> int:
    """Bulk sync — push every client subtree to its per-client repo on the given branch."""
    slugs = []
    for site_dir in sorted(SITES_DIR.iterdir()):
        if site_dir.is_dir() and not site_dir.name.startswith("_"):
            slugs.append(site_dir.name)
    if not slugs:
        die("No client subtrees found under sites/.")

    print(f"==> Bulk sync-deploy for {len(slugs)} client(s), branch={args.branch}")
    print(f"    Slugs: {', '.join(slugs)}")
    print()

    failures = []
    for slug in slugs:
        print(f"────────────── {slug} ──────────────")
        sub_args = argparse.Namespace(
            slug=slug, branch=args.branch,
            private=args.private, allow_dirty=args.allow_dirty,
        )
        try:
            cmd_sync_deploy(sub_args)
        except SystemExit as e:
            failures.append((slug, str(e)))
        except Exception as e:
            failures.append((slug, str(e)[:200]))
        print()

    print(f"==> Bulk sync done. Succeeded: {len(slugs) - len(failures)}/{len(slugs)}")
    if failures:
        print("    Failures:")
        for s, e in failures:
            print(f"      {s}: {e[:120]}")
        return 2
    return 0


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="build_site",
        description="Rank AI — build site (Skill 3, phase 1: scaffold + GitHub + Pages).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("scaffold", help="Copy starter, substitute tokens, push to GitHub, create Pages project")
    ps.add_argument("--slug", required=True)
    ps.add_argument("--private", action="store_true", help="Create the GitHub repo as private (default public)")
    ps.add_argument("--message", help="Override the commit message")
    ps.set_defaults(func=cmd_scaffold)

    pst = sub.add_parser("status", help="Show current build state of a client")
    pst.add_argument("--slug", required=True)
    pst.set_defaults(func=cmd_status)

    pr = sub.add_parser("render", help="Generate body content + FAQ for planned URLs via Anthropic")
    pr.add_argument("--slug", required=True)
    pr.add_argument("--archetype", help="Filter to one archetype (e.g., service-area-service)")
    pr.add_argument("--url", help="Filter to one URL path (e.g., /services/water-damage-restoration/)")
    pr.add_argument("--limit", type=int, help="Render at most N pages")
    pr.add_argument("--model", default=ANTHROPIC_DEFAULT_MODEL,
                    help=f"Anthropic model (default: {ANTHROPIC_DEFAULT_MODEL})")
    pr.add_argument("--workers", type=int, default=4,
                    help="Concurrent render workers (default: 4)")
    pr.add_argument("--force", action="store_true",
                    help="Re-render pages even if rendered: true in frontmatter")
    pr.add_argument("--push", action="store_true",
                    help="Commit and push to staging after rendering")
    pr.set_defaults(func=cmd_render)

    # sync-deploy: monorepo subtree → per-client GitHub repo
    psd = sub.add_parser(
        "sync-deploy",
        help="Push sites/{slug}/ subtree to per-client GitHub repo (Cloudflare auto-builds)",
    )
    psd.add_argument("--slug", required=True)
    psd.add_argument("--branch", required=True, choices=["main", "staging"],
                     help="Target branch on the per-client repo. main = production, staging = preview.")
    psd.add_argument("--private", action="store_true",
                     help="If the per-client repo needs to be created, make it private (default: public).")
    psd.add_argument("--allow-dirty", action="store_true",
                     help="Allow sync even if monorepo working tree has uncommitted changes.")
    psd.set_defaults(func=cmd_sync_deploy)

    # sync-deploy-all: bulk version
    psda = sub.add_parser(
        "sync-deploy-all",
        help="Run sync-deploy for every client under sites/",
    )
    psda.add_argument("--branch", required=True, choices=["main", "staging"])
    psda.add_argument("--private", action="store_true")
    psda.add_argument("--allow-dirty", action="store_true")
    psda.set_defaults(func=cmd_sync_deploy_all)

    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
