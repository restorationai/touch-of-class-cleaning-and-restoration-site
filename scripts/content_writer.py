#!/usr/bin/env python3
"""
Rank AI — Content Writer (System 2).

Pops one priority-1 item from clients/{slug}/content-queue.json, generates body
content + FAQ via Anthropic, generates hero image via Gemini (Nano Banana Pro),
converts to WebP, uploads to R2, writes markdown to the client's Astro blog
collection, marks the queue item as written, commits the monorepo, sync-deploys.

One post per run. Designed for headless cron via the master scheduler.

Spec: rank-ai/docs/seo-operations-spec.md
Prompt: rank-ai/templates/{vertical}/prompts/content-writer.md — resolved per
client via scripts/verticals.py (fail-loud; never hardcode a vertical).

Subcommands:
  next-post    Pop next priority-1 queue item, write + publish.
  queue        Show the current queue for a client (no writes).
  status       Show how many posts are queued / written / live for a client.

Env (from rank-ai/.env):
  ANTHROPIC_API_KEY         Content generation
  GOOGLE_AI_API_KEY         Nano Banana image generation
  CLOUDFLARE_R2_API_TOKEN   R2 image upload (via wrangler in image_utils.py)
  GITHUB_PERSONAL_ACCESS_TOKEN  sync-deploy
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Reuse helpers we already built
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import image_utils  # noqa: E402 — local helper, lives in scripts/
import verticals    # noqa: E402 — per-client vertical → template resolution

REPO_ROOT = SCRIPT_DIR.parent
CLIENTS_DIR = REPO_ROOT / "clients"
SITES_DIR = REPO_ROOT / "sites"
TEMPLATES_DIR = REPO_ROOT / "templates"
# Relative prompt path — resolved per client (templates/{vertical}/...) in
# build_prompt_inputs. Hardcoding templates/restoration here caused the
# davis-construction incident.
CONTENT_WRITER_PROMPT_REL = "prompts/content-writer.md"

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-5"

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_PRO_MODEL = "gemini-3-pro-image-preview"      # Nano Banana Pro
GEMINI_FLASH_MODEL = "gemini-3.1-flash-image-preview"  # Nano Banana 2 (Flash)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_json(path: Path) -> dict:
    if not path.exists():
        die(f"Missing required file: {path}")
    return json.loads(path.read_text())


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


# ----------------------------------------------------------------------------
# Anthropic — body content + FAQ
# ----------------------------------------------------------------------------


def anthropic_call(system: str, user: str, *, model: str = ANTHROPIC_MODEL,
                   max_tokens: int = 6000, temperature: float = 0.6,
                   max_retries: int = 4) -> tuple[str, dict]:
    """Anthropic messages call via the streaming API (SSE).

    Streaming is required because non-streaming holds an idle TCP connection for
    60-90s while Sonnet generates 6000+ tokens — intermediate proxies (especially
    on residential / mobile networks) close idle connections, producing the
    'Remote end closed connection without response' error. Streaming sends
    intermediate `event: content_block_delta` messages every few hundred ms,
    keeping the connection demonstrably active.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        die("Missing ANTHROPIC_API_KEY (see rank-ai/.env).")
    # `temperature` kept for call-site compatibility but NOT sent: 5-series
    # models (claude-sonnet-5) 400 on sampling params ("`temperature` is
    # deprecated for this model") since the 09-27 upgrade (c20e1dc6f).
    del temperature
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "stream": True,
    }
    data = json.dumps(body).encode()

    last = ""
    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(ANTHROPIC_API, data=data, method="POST",
                                     headers={
                                         "x-api-key": api_key,
                                         "anthropic-version": "2023-06-01",
                                         "content-type": "application/json",
                                         "accept": "text/event-stream",
                                     })
        chunks: list[str] = []
        usage = {"input_tokens": 0, "output_tokens": 0}
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                # Read SSE line-by-line
                buf = ""
                last_event = None
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                    if not line:
                        continue
                    if line.startswith("event:"):
                        last_event = line[6:].strip()
                        continue
                    if line.startswith("data:"):
                        payload_str = line[5:].strip()
                        if not payload_str:
                            continue
                        try:
                            evt = json.loads(payload_str)
                        except json.JSONDecodeError:
                            continue
                        etype = evt.get("type")
                        if etype == "content_block_delta":
                            delta = evt.get("delta", {})
                            if delta.get("type") == "text_delta":
                                chunks.append(delta.get("text", ""))
                        elif etype == "message_delta":
                            u = evt.get("usage") or {}
                            for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
                                if k in u:
                                    usage[k] = u[k]
                        elif etype == "message_start":
                            m = evt.get("message", {})
                            u = m.get("usage") or {}
                            for k, v in u.items():
                                usage[k] = v
                        elif etype == "error":
                            err_obj = evt.get("error", {})
                            err_type = err_obj.get("type", "unknown")
                            err_msg = err_obj.get("message", "")
                            if err_type in ("overloaded_error", "api_error") or "5" in str(err_obj.get("status", "")):
                                last = f"stream error: {err_type}: {err_msg}"
                                raise urllib.error.URLError(last)
                            raise RuntimeError(f"Anthropic stream error: {err_type}: {err_msg}")
                content = "".join(chunks)
                if not content:
                    raise urllib.error.URLError("empty stream output")
                return content, usage
        except urllib.error.HTTPError as e:
            err = e.read().decode(errors="replace")
            if e.code == 429 or 500 <= e.code < 600:
                wait = 2 ** attempt
                last = f"HTTP {e.code}: {err[:200]}"
                print(f"      retry {attempt}/{max_retries} in {wait}s ({last[:80]})")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Anthropic POST -> HTTP {e.code}: {err}")
        except (urllib.error.URLError, socket.timeout, ConnectionResetError) as e:
            last = str(e)
            wait = 2 ** attempt
            print(f"      retry {attempt}/{max_retries} in {wait}s (net: {last[:80]})")
            time.sleep(wait)
            continue
    raise RuntimeError(f"Anthropic streaming POST failed after {max_retries} retries. Last: {last}")


def parse_llm_json(text: str) -> dict:
    """Robust JSON parse — strip code fences if present."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    return json.loads(text)


def sanitize_content(obj):
    """Deterministically strip em dashes from generated content.

    The prompt forbids em dashes (brand voice rule: use commas, colons, or
    parentheses instead), but a prompt instruction alone doesn't reliably hold —
    the model still emits them. This walks every string in the parsed content dict
    (title, meta_description, body_markdown, image_prompt, and each faq
    question/answer) and replaces em dash / horizontal bar with a comma, so the
    rule is enforced regardless of what the model returns.
    """
    if isinstance(obj, str):
        s = re.sub(r"\s*[—―]\s*", ", ", obj)  # em dash / horizontal bar -> comma
        s = re.sub(r"\s+,", ",", s)                      # " ," -> ","
        s = re.sub(r",\s*,", ", ", s)                    # ",," / ", ," -> ", "
        return s
    if isinstance(obj, list):
        return [sanitize_content(x) for x in obj]
    if isinstance(obj, dict):
        return {k: sanitize_content(v) for k, v in obj.items()}
    return obj


# ----------------------------------------------------------------------------
# Gemini — hero image generation
# ----------------------------------------------------------------------------


def gemini_generate_image(prompt: str, *, model: str = GEMINI_PRO_MODEL,
                          aspect_ratio: str = "16:9",
                          max_retries: int = 3,
                          reference_png: bytes | list[bytes] | None = None) -> bytes:
    """Generate an image via the Gemini REST API. Returns PNG bytes.
    reference_png: optional brand asset(s) passed as image parts so vehicle
    wraps / signage reproduce the REAL mark (standing rule 2026-07-29: branded
    vans in hero/team/services). Accepts a LIST (2026-08-05, Reign): one logo
    plus a real photo of the client's actual wrapped vehicle plus the already-
    approved fleet shot, so the livery is anchored to reality and stays
    identical from image to image instead of being re-invented each call."""
    api_key = os.environ.get("GOOGLE_AI_API_KEY")
    if not api_key:
        die("Missing GOOGLE_AI_API_KEY (see rank-ai/.env).")

    url = f"{GEMINI_API_BASE}/{model}:generateContent?key={api_key}"
    parts: list = [{"text": prompt}]
    refs = reference_png if isinstance(reference_png, list) else (
        [reference_png] if reference_png else [])
    for ref in refs:
        if not ref:
            continue
        import base64 as _b64
        # PNG and JPEG both start with a recognisable magic number; harvested
        # client photos arrive as JPEG and must not be mislabelled.
        mime = "image/jpeg" if ref[:3] == b"\xff\xd8\xff" else "image/png"
        parts.append({"inline_data": {"mime_type": mime,
                                      "data": _b64.b64encode(ref).decode()}})
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": aspect_ratio},
        },
    }
    data = json.dumps(body).encode()

    last = ""
    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                payload = json.loads(resp.read().decode())
            # Walk for inline_data with base64
            for cand in payload.get("candidates", []):
                for part in cand.get("content", {}).get("parts", []):
                    inline = part.get("inlineData") or part.get("inline_data")
                    if inline and inline.get("data"):
                        return base64.b64decode(inline["data"])
            raise RuntimeError(f"Gemini response had no image data:\n{json.dumps(payload, indent=2)[:500]}")
        except urllib.error.HTTPError as e:
            err = e.read().decode(errors="replace")
            if e.code == 429 or 500 <= e.code < 600:
                wait = 2 ** attempt
                last = f"HTTP {e.code}: {err[:200]}"
                print(f"      retry {attempt}/{max_retries} in {wait}s ({last[:80]})")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Gemini POST -> HTTP {e.code}: {err}")
        except (urllib.error.URLError, socket.timeout, ConnectionResetError) as e:
            last = str(e)
            wait = 2 ** attempt
            print(f"      retry {attempt}/{max_retries} in {wait}s (net: {last[:80]})")
            time.sleep(wait)
            continue
    raise RuntimeError(f"Gemini image gen failed after {max_retries} retries. Last: {last}")


# ----------------------------------------------------------------------------
# Queue management
# ----------------------------------------------------------------------------


def queue_path(slug: str) -> Path:
    return CLIENTS_DIR / slug / "content-queue.json"


def load_queue(slug: str) -> dict:
    p = queue_path(slug)
    if not p.exists():
        return {"items": []}
    return load_json(p)


def pop_next_queued(queue: dict) -> dict | None:
    """Find the next queued item. Prioritized items (pinned in the app's Action
    Plan, synced by the strategist) jump the line; otherwise oldest-first.
    Does NOT modify the queue (the orchestrator updates status after a write)."""
    items = [i for i in queue.get("items", []) if i.get("status") == "queued"]
    if not items:
        return None
    # prioritized first, then oldest queued_at
    items.sort(key=lambda i: (0 if i.get("prioritized") else 1, i.get("queued_at", "")))
    return items[0]


def mark_written(slug: str, item_id: str, post_url: str,
                 claims_flags: list | None = None,
                 suggested_slug: str | None = None) -> None:
    queue = load_queue(slug)
    for item in queue.get("items", []):
        if item.get("id") == item_id:
            item["status"] = "written"
            item["written_at"] = now_iso()
            item["post_url"] = post_url
            if suggested_slug and not item.get("suggested_slug"):
                item["suggested_slug"] = suggested_slug  # title-derived slug
            if claims_flags:
                # Truth-gate violations found in the written post (see
                # scripts/claims_lint.py). Deliberately does NOT fail the run —
                # deploy may already cover other files — but stays visible on
                # the queue item until the content or brand truth data is fixed.
                item["claims_flags"] = claims_flags
            break
    save_json(queue_path(slug), queue)


def mark_published(slug: str, item_id: str) -> None:
    """Upgrade a queue item from 'written' to 'published' once the live URL
    verifiably returns HTTP 200 (post-deploy verification)."""
    queue = load_queue(slug)
    for item in queue.get("items", []):
        if item.get("id") == item_id:
            item["status"] = "published"
            item["published_verified_at"] = now_iso()
            break
    save_json(queue_path(slug), queue)


# ----------------------------------------------------------------------------
# Publish verification — poll the live URL until Cloudflare finishes the build
# ----------------------------------------------------------------------------

PUBLISH_POLL_INTERVAL_S = 30
PUBLISH_POLL_TIMEOUT_S = 300  # 5 minutes — typical Cloudflare Pages build time


def verify_published(post_url: str, *,
                     interval_s: int = PUBLISH_POLL_INTERVAL_S,
                     timeout_s: int = PUBLISH_POLL_TIMEOUT_S) -> bool:
    """Poll post_url until it returns HTTP 200. Returns True on success,
    False if the deadline passes. Never raises — verification is best-effort."""
    deadline = time.time() + timeout_s
    attempt = 0
    while True:
        attempt += 1
        try:
            req = urllib.request.Request(post_url, headers={
                "User-Agent": "rank-ai-publish-verify/1.0",
                "Cache-Control": "no-cache",
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status == 200:
                    print(f"      Live check attempt {attempt}: HTTP 200")
                    return True
                print(f"      Live check attempt {attempt}: HTTP {resp.status}")
        except urllib.error.HTTPError as e:
            print(f"      Live check attempt {attempt}: HTTP {e.code} (build not done yet)")
        except Exception as e:  # noqa: BLE001 — network blips must not kill the run
            print(f"      Live check attempt {attempt}: {str(e)[:100]}")
        if time.time() + interval_s > deadline:
            return False
        time.sleep(interval_s)


# ----------------------------------------------------------------------------
# Build the prompt input (system + user messages)
# ----------------------------------------------------------------------------


def build_prompt_inputs(slug: str, item: dict) -> tuple[str, str]:
    """Return (system, user) prompt strings for the Anthropic call."""
    # Load full client context
    client = load_json(CLIENTS_DIR / f"{slug}.json")
    plan_input = load_json(CLIENTS_DIR / slug / "plan-input.json")
    style_guide_path = CLIENTS_DIR / slug / "image-style-guide.md"
    style_guide = style_guide_path.read_text() if style_guide_path.exists() else ""

    # Per-client CONTENT GUIDANCE (Santino 2026-09-09, QCI "One Call Does It
    # All"): brand phrasing the client/ops set in the app (companies.
    # content_guidance, editable on the Content tab). Injected into every
    # post so taglines and positioning compound across the whole site —
    # the phrase-repetition signal AI answer engines learn brands from.
    content_guidance = ""
    try:
        import requests as _rq
        sb = os.environ.get("SUPABASE_URL", "").rstrip("/")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        cid = (load_json(CLIENTS_DIR / "company_map.json") or {}).get(slug)
        if sb and key and cid:
            rows = _rq.get(f"{sb}/rest/v1/companies?id=eq.{cid}&select=content_guidance",
                           headers={"apikey": key, "Authorization": f"Bearer {key}"},
                           timeout=15).json()
            content_guidance = (rows[0].get("content_guidance") or "") if rows else ""
    except Exception:  # noqa: BLE001 — guidance is an enhancer, never a blocker
        pass

    # Read the prompt template (source of truth) — resolved per client vertical,
    # fail-loud if the vertical's prompt asset doesn't exist.
    prompt_path = verticals.resolve_template(slug, CONTENT_WRITER_PROMPT_REL, client=client)
    system = prompt_path.read_text()

    # Resolve the client context block for the user message
    brand = plan_input.get("brand", {})
    primary = next((a for a in plan_input.get("service_areas", []) if a.get("primary")),
                   plan_input.get("service_areas", [{}])[0])
    services = plan_input.get("services", [])

    # If the queue item has city_anchor, hydrate that city's full record
    city_anchor_record = None
    if item.get("city_anchor"):
        city_anchor_record = next(
            (a for a in plan_input.get("service_areas", [])
             if a.get("slug") == item["city_anchor"]),
            None
        )

    # Existing published posts (slug + title) so the model can interlink the blog.
    # The prompt caps usage at 1-2 links and only when topically relevant.
    existing_posts = []
    blog_dir = SITES_DIR / slug / "src" / "content" / "blog"
    if blog_dir.exists():
        for md in sorted(blog_dir.glob("*.md")):
            title = ""
            for line in md.read_text().splitlines()[:12]:
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"')
                    break
            existing_posts.append({"path": f"/blog/{md.stem}/", "title": title})

    context = {
        "slug": slug,
        "client": {
            "display_name": client.get("display_name"),
            "domain": client.get("domain"),
            "build_status": client.get("build_status"),
        },
        "brand": brand,
        "primary_area": primary,
        "service_areas": plan_input.get("service_areas", []),
        "services_selected": services,
        "queue_item": item,
        "city_anchor_record": city_anchor_record,
        "existing_blog_posts": existing_posts,
        "current_month": datetime.now(timezone.utc).strftime("%B %Y"),
    }

    user = (
        "# Queue item to write\n\n"
        f"```json\n{json.dumps(item, indent=2)}\n```\n\n"
        "# Client context\n\n"
        f"```json\n{json.dumps(context, indent=2)}\n```\n\n"
        "# Image style guide (consult for image_prompt construction)\n\n"
        f"{style_guide}\n\n"
        + (f"# Brand voice and required phrasing (client-set, follow it)\n\n{content_guidance}\n\n" if content_guidance else "")
        + 
        "# Your task\n\n"
        "Generate the JSON object per the prompt's contract. Return only the JSON, "
        "no surrounding prose, no code fences. Target ~"
        f"{item.get('target_word_count', 1400)} words in body_markdown."
    )

    return system, user


# ----------------------------------------------------------------------------
# Markdown frontmatter writer
# ----------------------------------------------------------------------------


def strip_em_dashes(text: str) -> str:
    """LAW (Santino, standing since 08-05, extended to blog output 08-09):
    no em dashes in anything we publish. The model is told, but a prompt
    line is not a guarantee — this is the gate. Spaced em dashes read as
    a clause break (comma); tight ones as a joiner (hyphen)."""
    text = text.replace(" — ", ", ").replace(" —", ",").replace("— ", ", ")
    return text.replace("—", "-")


def resolve_post_slug(slug: str, item: dict, content: dict | None = None) -> str:
    """The post's URL slug: suggested_slug, else the slugified primary_keyword,
    else (case-study seeds from best_of_seeder carry neither) the generated
    title, de-duplicated against the blog dir and pinned on item so the hero,
    section image and markdown all agree. Never returns '': 09-29 an empty
    slug wrote blog/.md + images/blog/YYYY/MM//hero.webp on 9 sites."""
    def _slugify(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    post_slug = item.get("suggested_slug") or _slugify(item.get("primary_keyword", ""))
    if not post_slug:
        title = (content or {}).get("title") or item.get("suggested_title") or ""
        post_slug = _slugify(title)
        if len(post_slug) > 80:
            post_slug = post_slug[:80].rsplit("-", 1)[0]
        if post_slug:
            blog_dir = SITES_DIR / slug / "src" / "content" / "blog"
            base, n = post_slug, 2
            while (blog_dir / f"{post_slug}.md").exists():
                post_slug, n = f"{base}-{n}", n + 1
            item["suggested_slug"] = post_slug
    if not post_slug:
        die(f"Queue item {item.get('id')} has no suggested_slug, primary_keyword "
            "or title to derive a post slug from. Refusing to write blog/.md.")
    return post_slug


def write_markdown(slug: str, item: dict, content: dict, hero_url: str) -> Path:
    """Write the post markdown to sites/{slug}/src/content/blog/{post-slug}.md.
    Returns the file path."""
    site_dir = SITES_DIR / slug
    blog_dir = site_dir / "src" / "content" / "blog"
    if not blog_dir.exists():
        die(f"Blog content dir doesn't exist: {blog_dir}. Has the site been scaffolded?")

    post_slug = resolve_post_slug(slug, item, content)
    out_path = blog_dir / f"{post_slug}.md"

    # Frontmatter — matches the blog content collection schema in content/config.ts
    fm = {
        "archetype": "blog-post",
        "title": content["title"],
        "h1": content["title"],
        "meta_description": content["meta_description"],
        "primary_keyword": item["primary_keyword"],
        "secondary_keywords": item.get("fan_out_cluster", []),
        "search_intent": item.get("intent", "informational"),
        "priority": 7,
        "hero": hero_url,
        "og": hero_url,
        "generated_at": now_iso(),
        "manual_override": False,
        "internal_links": content.get("internal_link_suggestions", []),
        "breadcrumb": [
            {"name": "Home", "url": "/"},
            {"name": "Blog", "url": "/blog/"},
            {"name": content["title"]},
        ],
        "faq": content.get("faq", []),
        "published_at": now_iso()[:10],
        "services": item.get("service_tags", []),
        "rendered": True,
    }

    # No em dashes anywhere in the published post — title, description,
    # FAQ answers, body. Deterministic gate on top of the prompt rule.
    def _clean(v):
        if isinstance(v, str):
            return strip_em_dashes(v)
        if isinstance(v, list):
            return [_clean(x) for x in v]
        if isinstance(v, dict):
            return {k: _clean(x) for k, x in v.items()}
        return v
    fm = _clean(fm)
    content["body_markdown"] = strip_em_dashes(content["body_markdown"])

    # YAML-shaped frontmatter using JSON for arrays/objects/bools
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, (list, dict, bool)):
            lines.append(f"{k}: {json.dumps(v)}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        elif v is None:
            lines.append(f"{k}: null")
        else:
            escaped = str(v).replace('"', '\\"')
            lines.append(f'{k}: "{escaped}"')
    lines.append("---")
    lines.append(content["body_markdown"].strip())

    out_path.write_text("\n".join(lines) + "\n")
    return out_path


# ----------------------------------------------------------------------------
# Image gen + upload
# ----------------------------------------------------------------------------


def generate_and_upload_hero(slug: str, item: dict, image_prompt: str, *, use_pro: bool = True,
                             filename: str = "hero.webp") -> str:
    """Generate an image via Gemini, convert PNG → WebP, upload to R2, return
    the public URL. Used for the hero (hero.webp) and the optional mid-body
    section image (section.webp) — same machinery, different key."""
    client = load_json(CLIENTS_DIR / f"{slug}.json")
    domain = client["domain"]
    bucket = f"rankai-{slug}"
    post_slug = resolve_post_slug(slug, item)
    today = datetime.now(timezone.utc).strftime("%Y/%m")
    r2_key = f"blog/{today}/{post_slug}/{filename}"

    model = GEMINI_PRO_MODEL if use_pro else GEMINI_FLASH_MODEL
    print(f"      Generating {filename} with {model}...")
    png_bytes = gemini_generate_image(image_prompt, model=model, aspect_ratio="16:9")
    print(f"      PNG size: {len(png_bytes) / 1024:.1f} KB")

    webp_bytes = image_utils.png_to_webp_bytes(png_bytes, quality=90)
    print(f"      WebP size: {len(webp_bytes) / 1024:.1f} KB ({len(webp_bytes)/len(png_bytes)*100:.1f}% of PNG)")

    print(f"      Uploading to r2://{bucket}/{r2_key}...")
    if not image_utils.upload_bytes_to_r2(bucket, r2_key, webp_bytes, content_type="image/webp"):
        raise RuntimeError(f"R2 upload failed for {r2_key}")

    public_url = f"https://images.{domain}/{r2_key}"
    # LOCAL-FIRST GUARD (queue 18, Santino 2026-09-26): images.{domain}
    # only resolves once the client's apex is on our DNS. Probe the URL we
    # are about to emit; if it is not reachable (preview-phase client, the
    # all-pro case: 19 dead blog refs shipped this way), keep the R2 copy
    # for cutover but serve the image FROM THE SITE — write the bytes into
    # public/images/{r2_key} and return a site-relative path. BaseLayout
    # absolutizes relative og paths, so frontmatter stays valid. A live
    # probe beats gating on apex_live (that flag is unreliable).
    try:
        import requests as _rq
        ok = _rq.head(public_url, timeout=10,
                      allow_redirects=True).status_code == 200
    except Exception:  # noqa: BLE001 — unreachable == not ok
        ok = False
    if not ok:
        local = SITES_DIR / slug / "public" / "images" / r2_key
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(webp_bytes)
        print(f"      Public URL unreachable — serving locally: "
              f"/images/{r2_key} (R2 copy kept for cutover)")
        return f"/images/{r2_key}"
    print(f"      Public URL: {public_url}")
    return public_url


# ----------------------------------------------------------------------------
# Optional mid-body section image (second field the model MAY return)
# ----------------------------------------------------------------------------


def _h2_matches(body: str) -> list:
    return list(re.finditer(r"(?m)^##\s+(.+?)\s*$", body))


def section_image_alt(body: str, primary_keyword: str) -> str:
    """Keyword-rich alt text derived from the second H2 (the section the image
    illustrates)."""
    h2s = _h2_matches(body)
    h2_text = h2s[1].group(1).strip() if len(h2s) >= 2 else primary_keyword
    h2_clean = h2_text.rstrip("?").strip()
    if primary_keyword.lower() in h2_clean.lower():
        return h2_clean
    return f"{h2_clean}: {primary_keyword}"


def insert_section_image(body: str, image_url: str, alt: str) -> str:
    """Insert a markdown image right after the second H2 section's last
    paragraph — i.e. immediately before the third H2 when one exists,
    otherwise before the closing '---' rule, otherwise at the end.
    Returns body unchanged when it has fewer than two H2s (nowhere sane to put it)."""
    h2s = _h2_matches(body)
    img_md = f"![{alt}]({image_url})"
    if len(h2s) >= 3:
        pos = h2s[2].start()
        return body[:pos].rstrip("\n") + "\n\n" + img_md + "\n\n" + body[pos:]
    if len(h2s) == 2:
        tail = body[h2s[1].end():]
        m = re.search(r"(?m)^---\s*$", tail)
        if m:
            pos = h2s[1].end() + m.start()
            return body[:pos].rstrip("\n") + "\n\n" + img_md + "\n\n" + body[pos:]
        return body.rstrip("\n") + "\n\n" + img_md + "\n"
    return body


# ----------------------------------------------------------------------------
# Sync-deploy hook (reuses build_site.py's git subtree logic)
# ----------------------------------------------------------------------------


def commit_and_sync(slug: str, item: dict, post_path: Path, branch: str) -> None:
    """Stage the new post + queue update, commit, sync-deploy to per-client repo."""
    import subprocess

    def run(cmd, cwd):
        out = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
        if out.returncode != 0:
            raise RuntimeError(f"{' '.join(cmd)} failed:\n{out.stderr}")
        return out.stdout.strip()

    print(f"      Committing to monorepo...")
    run(["git", "add",
         f"sites/{slug}/src/content/blog/{post_path.name}",
         f"clients/{slug}/content-queue.json"], REPO_ROOT)
    try:
        run(["git", "commit", "-m",
             f"Content writer: publish {item['primary_keyword'] or post_path.stem} for {slug}"],
            REPO_ROOT)
        print(f"      Committed.")
    except RuntimeError as e:
        if "nothing to commit" in str(e).lower():
            print(f"      (nothing to commit)")
        else:
            raise

    print(f"      Syncing monorepo with origin (guarded)...")
    # guard skips when a session is active and aborts cleanly on conflicts
    # (2026-08-18 incident, see scripts/repo_git_guard.py)
    from repo_git_guard import safe_sync
    safe_sync(REPO_ROOT, actor="content_writer")

    print(f"      Sync-deploying sites/{slug}/ to per-client repo (branch={branch})...")
    sync = subprocess.run(
        ["python3", str(SCRIPT_DIR / "build_site.py"),
         "sync-deploy", "--slug", slug, "--branch", branch, "--allow-dirty"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    if sync.returncode != 0:
        print(f"      sync-deploy stderr: {sync.stderr}")
        raise RuntimeError(f"sync-deploy failed (exit {sync.returncode})")
    print(f"      Sync complete. Cloudflare will auto-build the {branch} branch.")

    # Mirror publish status into Supabase so the app's Content view updates immediately.
    # Non-fatal: the nightly supabase_sync cron is the backstop if this fails.
    print(f"      Syncing publish status to Supabase (marketing_content_items)...")
    db = subprocess.run(
        ["python3", str(SCRIPT_DIR / "supabase_sync.py"), "--slug", slug],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    if db.returncode != 0:
        print(f"      [warn] supabase_sync failed (non-fatal): {db.stderr[-300:]}")
    else:
        print(f"      Supabase sync OK — app Content view is current.")


# ----------------------------------------------------------------------------
# Subcommands
# ----------------------------------------------------------------------------


def cmd_next_post(args) -> int:
    slug = args.slug
    # Pull operator-prioritized Action Plan items (pinned blog_post / ai_visibility /
    # ai_keyword) into the queue first, so a term you Prioritize in the app gets
    # written on the very next content run. Safe, idempotent, non-fatal.
    try:
        import sys as _sys
        _sys.path.insert(0, str(SCRIPT_DIR))
        from geogrid_store import COMPANY_MAP
        from strategist import sync_content_queue
        cid = COMPANY_MAP.get(slug)
        if cid:
            n = sync_content_queue(slug, cid)
            if n:
                print(f"    (+{n} prioritized item(s) synced from the Action Plan)")
    except Exception as e:
        import sys as _sys
        _sys.stderr.write(f"    (Action Plan sync skipped: {str(e)[:140]})\n")

    queue = load_queue(slug)
    item = pop_next_queued(queue)
    if not item:
        print(f"==> No queued items for {slug}. Run rank-ai-keyword-researcher to refill.")
        return 0

    print(f"==> Writing next post for {slug}")
    print(f"    Topic:        {item['primary_keyword']}")
    print(f"    Suggested title: {item.get('suggested_title','?')}")
    print(f"    Intent: {item.get('intent','?')}  vol={item.get('volume','?')}  kd={item.get('kd','?')}")
    print(f"    Target branch: {args.branch}")
    if args.dry_run:
        print(f"    (DRY RUN — no writes, no API calls)")
        return 0
    print()

    # Step 1: generate body + FAQ + image prompt
    print("[1/5] Generating body content via Anthropic...")
    system, user = build_prompt_inputs(slug, item)
    raw, usage = anthropic_call(system, user, max_tokens=8000,
                                model=args.model or ANTHROPIC_MODEL)
    try:
        content = parse_llm_json(raw)
    except json.JSONDecodeError as e:
        print(f"      LLM returned non-JSON (first 300 chars):\n{raw[:300]}")
        raise RuntimeError(f"Content writer LLM output failed JSON parse: {e}")
    content = sanitize_content(content)  # enforce no-em-dash rule deterministically
    # Pin the slug now (title fallback for keywordless case-study items) so
    # the hero/section image keys and the markdown filename all match.
    print(f"      Post slug: {resolve_post_slug(slug, item, content)}")

    # C6 SELF-PROMOTION LINT (Santino 2026-09-17): every post names the
    # client at least once in a recommendation context and never reads
    # like an ad. Deterministic count of display-name mentions in the
    # body: 0 = the post never recommends us (the whole point of the
    # format), >4 = it reads salesy. One corrective retry, then flag.
    client_rec = load_json(CLIENTS_DIR / f"{slug}.json")
    disp = (client_rec.get("display_name") or "").strip()
    if disp:
        n_mentions = content.get("body_markdown", "").lower().count(disp.lower())
        if n_mentions == 0 or n_mentions > 4:
            problem = ("never mentions the client" if n_mentions == 0
                       else f"mentions the client {n_mentions}x (salesy)")
            print(f"      self-promo lint: {problem} — one corrective retry")
            fix = (f"\n\nREVISION REQUIRED: the draft {problem}. The post "
                   f"must mention \"{disp}\" EXACTLY ONCE or TWICE, in a "
                   "natural recommendation context (e.g. inside the "
                   "who-to-call answer), never more. Keep everything else. "
                   "Return the corrected full JSON.")
            raw2, usage2 = anthropic_call(system, user + fix, max_tokens=8000,
                                          model=args.model or ANTHROPIC_MODEL)
            try:
                content = sanitize_content(parse_llm_json(raw2))
                usage = usage2
            except json.JSONDecodeError:
                print("      retry unparseable — keeping first draft, flagged")
            n2 = content.get("body_markdown", "").lower().count(disp.lower())
            if n2 == 0 or n2 > 4:
                content.setdefault("_flags", []).append(f"self-promo: {n2} mentions")
                print(f"      still off ({n2} mentions) — flagged, publishing anyway")
    body_len = len(content.get("body_markdown", ""))
    faq_count = len(content.get("faq", []))
    print(f"      Body: {body_len} chars, FAQ: {faq_count} items, "
          f"tok: {usage.get('input_tokens',0)}+{usage.get('output_tokens',0)}")

    # Step 2: generate hero image
    print("[2/5] Generating hero image via Gemini Pro...")
    image_prompt = content.get("image_prompt") or (
        f"Editorial restoration photograph illustrating: {item['primary_keyword']}. "
        f"Worker in branded polo, IICRC patch, faces obscured. "
        f"Mirrorless full-frame look, neutral interior lighting, no text or logos."
    )
    if args.skip_image:
        hero_url = ""
        print(f"      (--skip-image: leaving hero empty)")
    else:
        try:
            hero_url = generate_and_upload_hero(slug, item, image_prompt, use_pro=not args.flash)
        except RuntimeError as e:
            print(f"      Image gen failed: {e}")
            if args.no_image_fallback:
                raise
            client = load_json(CLIENTS_DIR / f"{slug}.json")
            fallback = f"https://images.{client['domain']}/brand/hero.webp"
            # Verify the placeholder actually serves before embedding it.
            # Pre-launch clients have no images bucket/domain yet ("The
            # specified bucket does not exist" is exactly this), and the
            # 08-26 backfill shipped 10 posts with dead hero URLs this way.
            # An empty hero is a supported state — backfill_heroes.py fills
            # it once the client's image infra exists.
            try:
                import requests as _rq
                _ok = _rq.head(fallback, timeout=10,
                               allow_redirects=True).status_code == 200
            except Exception:  # noqa: BLE001 — DNS failure = not served
                _ok = False
            if _ok:
                print("      Falling back to brand hero placeholder.")
                hero_url = fallback
            else:
                print("      Brand hero placeholder unreachable — leaving "
                      "hero empty for backfill_heroes.py.")
                hero_url = ""

    # Step 2b (optional): mid-body section image. Only when the model returned
    # section_image_prompt — absence changes nothing. Fully best-effort: any
    # failure logs a warning and the post ships without it.
    section_prompt = (content.get("section_image_prompt") or "").strip()
    if section_prompt and not args.skip_image:
        print("      Optional section image requested by the model — generating...")
        try:
            section_url = generate_and_upload_hero(
                slug, item, section_prompt, use_pro=not args.flash, filename="section.webp")
            alt = section_image_alt(content.get("body_markdown", ""), item["primary_keyword"])
            new_body = insert_section_image(content.get("body_markdown", ""), section_url, alt)
            if new_body != content.get("body_markdown"):
                content["body_markdown"] = new_body
                print(f"      Section image inserted (alt: {alt[:80]})")
            else:
                print("      [warn] body has fewer than two H2s — section image skipped")
        except Exception as e:  # noqa: BLE001 — optional feature, never fatal
            print(f"      [warn] section image failed (non-fatal): {str(e)[:140]}")

    # Step 3: write markdown
    print("[3/5] Writing post markdown...")
    post_path = write_markdown(slug, item, content, hero_url)
    print(f"      {post_path}")

    # Step 3b: claims lint (truth gate) on the file we just wrote. NEVER fails
    # the run — the flag rides on the queue item so it can't slip by unseen.
    claims_flags: list = []
    try:
        import claims_lint  # scripts/ is on sys.path (SCRIPT_DIR insert above)
        truth = claims_lint.load_truth(slug)
        claims_flags = claims_lint.lint_file(post_path, truth, rel_root=SITES_DIR / slug)
        errors = [v for v in claims_flags if v["severity"] == "error"]
        if claims_flags:
            print("      " + "!" * 68)
            print(f"      !! CLAIMS LINT: {len(errors)} error(s), "
                  f"{len(claims_flags) - len(errors)} review flag(s) in {post_path.name}")
            for v in claims_flags:
                print(f"      !! [{v['severity'].upper()}] {v['family']} ({v['part']}): "
                      f"...{v['context'][:110]}...")
            print("      !! The post asserts things the brand truth data does not support.")
            print("      !! It will still deploy; 'claims_flags' is recorded on the queue")
            print(f"      !! item. Fix the content or clients/{slug}/plan-input.json truth")
            print("      !! fields, then redeploy. Full check: "
                  f"python3 scripts/claims_lint.py --slug {slug}")
            print("      " + "!" * 68)
        else:
            print("      Claims lint: clean.")
    except Exception as e:  # noqa: BLE001 — the gate must never break publishing
        print(f"      [warn] claims lint skipped (non-fatal): {str(e)[:140]}")

    # Step 4: mark queue item written
    print("[4/5] Marking queue item as written...")
    post_url = f"https://{load_json(CLIENTS_DIR / f'{slug}.json')['domain']}/blog/{post_path.stem}/"
    mark_written(slug, item["id"], post_url, claims_flags=claims_flags,
                 suggested_slug=item.get("suggested_slug"))
    print(f"      Queue item {item['id']} → status: written, post_url: {post_url}"
          + (f", claims_flags: {len(claims_flags)}" if claims_flags else ""))

    # Step 5: commit + sync-deploy
    if args.no_deploy:
        print("[5/5] (--no-deploy: skipping commit + sync-deploy)")
    else:
        print(f"[5/5] Committing and sync-deploying to {args.branch} branch...")
        commit_and_sync(slug, item, post_path, args.branch)

        # Post-deploy verification: wait for the Cloudflare build, confirm the
        # post is actually live, then upgrade the queue item written -> published.
        # Best-effort by design — a verification miss NEVER fails the run; the
        # item just stays "written" with a warning.
        if args.branch != "main":
            print(f"      (branch={args.branch}: skipping live-URL verification — "
                  f"production domain won't serve this deploy)")
        else:
            try:
                print(f"      Verifying publish at {post_url} "
                      f"(every {PUBLISH_POLL_INTERVAL_S}s, up to {PUBLISH_POLL_TIMEOUT_S // 60} min)...")
                if verify_published(post_url):
                    mark_published(slug, item["id"])
                    print(f"      Verified live. Queue item {item['id']} → status: published")
                else:
                    print(f"      [warn] {post_url} never returned HTTP 200 within "
                          f"{PUBLISH_POLL_TIMEOUT_S // 60} min — leaving status 'written'. "
                          f"Check the Cloudflare Pages build / apex cutover.")
            except Exception as e:  # noqa: BLE001
                print(f"      [warn] publish verification errored (non-fatal): {str(e)[:140]}")

    print()
    print(f"==> Post complete.")
    print(f"    Post:    {post_path}")
    print(f"    Hero:    {hero_url}")
    print(f"    Live (after CF build): {post_url}")
    return 0


def cmd_queue(args) -> int:
    slug = args.slug
    queue = load_queue(slug)
    items = queue.get("items", [])
    queued = [i for i in items if i.get("status") == "queued"]
    written = [i for i in items if i.get("status") in ("written", "published")]

    print(f"==> Content queue for {slug}")
    print(f"    Queued (waiting):  {len(queued)}")
    print(f"    Written (live):    {len(written)}")
    print()
    if queued:
        print("Next up:")
        queued.sort(key=lambda i: i.get("queued_at", ""))
        for i, item in enumerate(queued[:10], 1):
            print(f"  {i}. {item['primary_keyword']}")
            print(f"     vol={item.get('volume','?')}  kd={item.get('kd','?')}  intent={item.get('intent','?')}  queued_at={item.get('queued_at','?')}")
    if written:
        print()
        print(f"Most recently written:")
        written.sort(key=lambda i: i.get("written_at", ""), reverse=True)
        for item in written[:5]:
            print(f"  - {item['primary_keyword']}")
            print(f"      {item.get('post_url','(no url)')}  written_at={item.get('written_at','?')}")
    return 0


def cmd_status(args) -> int:
    slug = args.slug
    queue = load_queue(slug)
    items = queue.get("items", [])
    print(json.dumps({
        "slug": slug,
        "queued": sum(1 for i in items if i.get("status") == "queued"),
        "written": sum(1 for i in items if i.get("status") in ("written", "published")),
        "total": len(items),
    }, indent=2))
    return 0


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="content_writer",
        description="Rank AI — content writer (System 2). Pops next queued item, writes + deploys one post.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pn = sub.add_parser("next-post", help="Pop next priority-1 queue item, write + deploy")
    pn.add_argument("--slug", required=True)
    pn.add_argument("--branch", choices=["main", "staging"], default="staging",
                    help="Target branch for sync-deploy (default: staging — safer)")
    pn.add_argument("--model", help=f"Override Anthropic model (default: {ANTHROPIC_MODEL})")
    pn.add_argument("--flash", action="store_true",
                    help="Use Nano Banana Flash for hero image (cheaper, lower quality)")
    pn.add_argument("--skip-image", action="store_true",
                    help="Skip image generation entirely (leaves hero empty)")
    pn.add_argument("--no-image-fallback", action="store_true",
                    help="If image gen fails, abort instead of using brand hero placeholder")
    pn.add_argument("--no-deploy", action="store_true",
                    help="Write the post locally but don't commit or sync-deploy")
    pn.add_argument("--dry-run", action="store_true",
                    help="Show the next queue item without writing")
    pn.set_defaults(func=cmd_next_post)

    pq = sub.add_parser("queue", help="Show the current queue for a client")
    pq.add_argument("--slug", required=True)
    pq.set_defaults(func=cmd_queue)

    pst = sub.add_parser("status", help="Counts of queued / written / total")
    pst.add_argument("--slug", required=True)
    pst.set_defaults(func=cmd_status)

    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
