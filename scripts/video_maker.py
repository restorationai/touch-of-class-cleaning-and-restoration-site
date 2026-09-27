#!/usr/bin/env python3
"""
Rank AI — System 5: Blog Post to YouTube Video.

Converts a published blog post into a ~90-second image-montage video and
uploads it to the client's YouTube channel.

Pipeline per run:
  1. Read blog post markdown (title, body, FAQ)
  2. Claude generates: 10-scene video script, per-scene image prompts,
     YouTube title / description / tags / category
  3. Google Cloud TTS synthesises narration → MP3
     Fallback: macOS `say` command (no API key needed, for testing)
  4. Gemini generates one 16:9 PNG per scene (same API as hero images)
  5. FFmpeg assembles: images + Ken Burns zoom + audio → 1920x1080 MP4
  6. SRT captions written from scene timing
  7. YouTube Data API v3: upload video + captions, set public (default)
  8. Blog post frontmatter updated: youtube_id: <id>
  9. Monorepo commit + sync-deploy so the embed shows on the live post

Subcommands:
  auth --slug <slug>              One-time OAuth setup per client YouTube channel
  make --slug <slug> --post <slug> [--no-upload] [--public] [--flash] [--tts macos]
                                  [--title ...] [--description-file ...]
                                  [--max-ai-images N] [--defer-writeback]
  brand --slug <slug>             Brand-authority video (company overview)
  geo --slug <slug> --service <svc> --city <city>
                                  Standalone local-ranker video (Merchynt style),
                                  claims-gated to brand truth fields
  publish --slug <slug> --post <slug> [--video-id ID]
                                  Flip an uploaded video public + write youtube_id
                                  into the post frontmatter + queue item + commit
  list --slug <slug>              Show uploaded videos for a client

Required env vars (rank-ai/.env):
  ANTHROPIC_API_KEY               Script generation
  GOOGLE_AI_API_KEY               Gemini scene images
  GOOGLE_CLOUD_API_KEY            Google Cloud TTS (see docs/system5-setup.md)
  GITHUB_PERSONAL_ACCESS_TOKEN    Commit + sync-deploy

Per-client OAuth token (created by `auth`):
  clients/{slug}/.youtube-token.json

Shared OAuth client secret (agency-wide, same as GSC):
  .youtube-oauth-client.json  (or reuse .gsc-oauth-client.json if scopes allow)
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import image_utils  # noqa: E402

REPO_ROOT = SCRIPT_DIR.parent
CLIENTS_DIR = REPO_ROOT / "clients"
SITES_DIR = REPO_ROOT / "sites"

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-5"

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_PRO_MODEL = "gemini-3-pro-image-preview"
GEMINI_FLASH_MODEL = "gemini-3.1-flash-image-preview"

TTS_API_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
TTS_VOICE = "en-US-Neural2-D"  # Google fallback voice

ELEVENLABS_API = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_VOICE_ID = "HIGUfNOdjuWQwwapnTRW"
ELEVENLABS_MODEL = "eleven_turbo_v2_5"  # Fast + high quality; upgrade to eleven_multilingual_v2 for max quality

PEXELS_API = "https://api.pexels.com/videos/search"

# Images-only mode: when False, scenes never use Pexels stock video — every scene is a
# still (client photo or Gemini AI image) with a Ken Burns zoom. Set True to re-enable stock.
USE_STOCK_VIDEO = False

# Output dimensions. Default landscape 16:9 (watch-page embeds). Flip to vertical 9:16
# (GBP video posts / YouTube Shorts) via set_orientation(vertical=True).
OUT_W, OUT_H = 1920, 1080
GEMINI_ASPECT = "16:9"


def set_orientation(vertical: bool) -> None:
    """Set output dimensions + Gemini aspect ratio. Vertical = 9:16 for GBP/Shorts."""
    global OUT_W, OUT_H, GEMINI_ASPECT
    OUT_W, OUT_H, GEMINI_ASPECT = (1080, 1920, "9:16") if vertical else (1920, 1080, "16:9")

XFADE_DURATION = 0.4  # seconds of dissolve between clips
# Trailing pad held on the final frame so the narration ALWAYS finishes before
# the video ends. Each xfade dissolve overlaps two clips by XFADE_DURATION, so a
# video of N clips is (N-1)*XFADE_DURATION shorter than the sum of its clips.
# Since clip durations are derived from the narration length, that deficit made
# the video shorter than the audio and `-shortest` truncated the last words of
# the narration — the CTA/phone number (fleet-wide, reported by Alfredo 09-18).
END_PAD_SEC = 1.0

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",  # required for captions().insert()
]
# Reuse the same Desktop app OAuth client as GSC — same Google Cloud project,
# YouTube Data API v3 enabled separately. Fall back to .youtube-oauth-client.json
# if the GSC file is absent (e.g. on a fresh clone).
YOUTUBE_OAUTH_CLIENT_PATH = (
    REPO_ROOT / ".gsc-oauth-client.json"
    if (REPO_ROOT / ".gsc-oauth-client.json").exists()
    else REPO_ROOT / ".youtube-oauth-client.json"
)
YOUTUBE_CATEGORY_HOWTO = "26"  # Howto & Style — best fit for restoration guides


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def die(msg: str) -> None:
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def load_client(slug: str) -> dict:
    path = CLIENTS_DIR / f"{slug}.json"
    if not path.exists():
        die(f"Client record not found: {path}")
    return json.loads(path.read_text())


def require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        die(f"Missing env var {name}. Source rank-ai/.env first.")
    return val


def load_post(slug: str, post_slug: str) -> dict:
    """Return parsed frontmatter + body dict from a blog post markdown file."""
    path = SITES_DIR / slug / "src" / "content" / "blog" / f"{post_slug}.md"
    if not path.exists():
        die(f"Blog post not found: {path}")
    text = path.read_text()

    # Parse YAML frontmatter
    match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not match:
        die(f"Could not parse frontmatter in {path}")

    fm_raw, body = match.group(1), match.group(2)
    fm: dict = {}
    for line in fm_raw.splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            fm[k.strip()] = v.strip().strip('"')

    return {"path": path, "frontmatter": fm, "body": body.strip()}


def update_post_youtube_id(
    post_path: Path, youtube_id: str, transcript: str | None = None
) -> None:
    """Patch youtube_id + video_transcript into frontmatter and append transcript section."""
    text = post_path.read_text()

    # Patch youtube_id
    if "youtube_id:" in text:
        text = re.sub(r"youtube_id:.*", f'youtube_id: "{youtube_id}"', text)
    else:
        text = text.replace("\n---\n", f'\nyoutube_id: "{youtube_id}"\n---\n', 1)

    # Patch video_transcript in frontmatter (used by VideoObject JSON-LD schema)
    if transcript:
        safe_transcript = transcript.replace('"', "'")
        if "video_transcript:" in text:
            text = re.sub(
                r"video_transcript:.*",
                f'video_transcript: "{safe_transcript}"',
                text,
            )
        else:
            text = text.replace(
                "\n---\n",
                f'\nvideo_transcript: "{safe_transcript}"\n---\n',
                1,
            )
        # Append visible transcript section to post body (crawlable text)
        if "## Video Transcript" not in text:
            text = text.rstrip() + f"\n\n## Video Transcript\n\n{transcript}\n"

    post_path.write_text(text)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def collect_post_stills(slug: str, post: dict) -> list[Path]:
    """Real images tied to a post: frontmatter hero/og/inline, body markdown images,
    the hero image of each service the post is tagged with, plus site brand images
    (hero-bg, team). Local files under sites/{slug}/public only; logos excluded."""
    fm, body = post["frontmatter"], post["body"]
    pub = SITES_DIR / slug / "public"
    rel_paths: list[str] = []
    for key in ("hero", "og"):
        if fm.get(key):
            rel_paths.append(fm[key])
    for key in ("inline", "services"):
        raw = fm.get(key)
        if raw and raw.startswith("["):
            try:
                vals = [v for v in json.loads(raw) if isinstance(v, str)]
            except Exception:
                vals = []
            if key == "inline":
                rel_paths += vals
            else:
                rel_paths += [f"/services/{s}.webp" for s in vals]
    rel_paths += re.findall(r"!\[[^\]]*\]\(([^)\s]+)", body)
    rel_paths += ["/images/hero-bg.webp", "/images/team.webp"]

    out: list[Path] = []
    seen: set[str] = set()
    for rp in rel_paths:
        if rp.startswith("http"):
            rp = urllib.parse.urlparse(rp).path  # images.{domain} paths mirror /public
        p = pub / rp.lstrip("/")
        if (p.exists() and p.suffix.lower() in PHOTO_EXTENSIONS
                and "logo" not in p.name.lower() and str(p) not in seen):
            seen.add(str(p))
            out.append(p)
    return out


def image_style_suffix(slug: str) -> str:
    """Distil clients/{slug}/image-style-guide.md into a prompt suffix appended to
    every Gemini scene image, so video stills match the site's photography style."""
    guide = CLIENTS_DIR / slug / "image-style-guide.md"
    if not guide.exists():
        return ""
    text = guide.read_text()
    m = re.search(r"Primary brand color[^#\n]*\|[^#\n]*(#[0-9a-fA-F]{6})", text)
    color = m.group(1) if m else ""
    m = re.search(r"\*\*Primary setting\*\*:\s*([^\n]+)", text)
    region = m.group(1).strip() if m else ""
    parts = [
        "Professional restoration-company photography, full-frame mirrorless look,",
        "true-to-life color, no oversaturation; cool neutral diffused light indoors,",
        "golden-hour light outdoors.",
    ]
    if color:
        parts.append(
            f"Any worker wears a branded {color} polo, face never clearly visible "
            "(shot from behind, side angle, or shadowed cap brim)."
        )
    if region:
        parts.append(f"Setting: {region}.")
    parts.append("No on-screen text, no visible logos, no smiling at camera, "
                 "no stock-photo poses.")
    return " ".join(parts)


# Rough per-unit cost estimates (USD) for the video cost log. Same JSONL file +
# shape as build_site.log_cost (sites/{slug}/.rank-ai/cost-log.jsonl).
_COST_PER_MTOK_IN, _COST_PER_MTOK_OUT = 3.0, 15.0        # claude-sonnet-4-6
_COST_PER_IMAGE = {"pro": 0.134, "flash": 0.039}          # gemini image gen
_COST_PER_TTS_CHAR = 0.00011                               # elevenlabs turbo


def log_video_cost(slug: str, label: str, model: str, claude_usage: dict,
                   ai_images: int, tts_chars: int) -> None:
    tier = "flash" if "flash" in model else "pro"
    dollars = (
        claude_usage.get("input_tokens", 0) * _COST_PER_MTOK_IN / 1_000_000
        + claude_usage.get("output_tokens", 0) * _COST_PER_MTOK_OUT / 1_000_000
        + ai_images * _COST_PER_IMAGE[tier]
        + tts_chars * _COST_PER_TTS_CHAR
    )
    log = SITES_DIR / slug / ".rank-ai" / "cost-log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as f:
        f.write(json.dumps({
            "ts": now_iso(),
            "url": label,
            "archetype": "video",
            "model": model,
            "usage": {"claude": claude_usage, "ai_images": ai_images,
                      "tts_chars": tts_chars, "estimated": True},
            "dollars": round(dollars, 6),
        }) + "\n")
    print(f"  [cost] ~${dollars:.3f} logged to {log.relative_to(REPO_ROOT)}")


def record_video(slug: str, video_id: str, title: str, status: str, kind: str,
                 post_slug: str | None = None, service: str | None = None,
                 city: str | None = None, published_at: str | None = None) -> None:
    """Ledger every uploaded video into Supabase marketing_videos (the app's
    Marketing video feed). Best-effort: a ledger failure must never fail the
    run itself — the video is already on YouTube. Mirrors gbp_post.record_post."""
    try:
        cid = _company_id_for(slug)
        if not cid or not os.environ.get("SUPABASE_URL"):
            return
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"],
                           os.environ["SUPABASE_SERVICE_ROLE_KEY"])
        sb.table("marketing_videos").upsert({
            "company_id": cid,
            "video_id": video_id,
            "title": title,
            "status": status,
            "kind": kind,
            "post_slug": post_slug,
            "service": service,
            "city": city,
            "url": f"https://youtu.be/{video_id}",
            "published_at": published_at,
        }, on_conflict="company_id,video_id").execute()
        print(f"  [ledger] marketing_videos: {video_id} ({kind}, {status})")
    except Exception as e:
        print(f"  warn: uploaded OK but not recorded in marketing_videos ({str(e)[:140]})")


def video_publish_mode(client: dict) -> str:
    """Per-client default upload privacy from clients/{slug}.json
    (`video_publish_mode`). 'public' by default (Santino 2026-07-11: publish
    even before channel renames — renames re-attribute retroactively). Set
    'unlisted' per-client only if one specifically needs to stay dark —
    owner's personal name."""
    mode = str(client.get("video_publish_mode", "public")).lower()
    return mode if mode in ("unlisted", "public") else "public"


def mark_queue_video(slug: str, post_slug: str, video_id: str) -> bool:
    """Stamp youtube_id + video_published_at onto the matching content-queue item."""
    qpath = CLIENTS_DIR / slug / "content-queue.json"
    if not qpath.exists():
        return False
    q = json.loads(qpath.read_text())
    items = q if isinstance(q, list) else q.get("items", [])
    for it in items:
        url = it.get("post_url") or ""
        if it.get("suggested_slug") == post_slug or f"/{post_slug}" in url:
            it["youtube_id"] = video_id
            it["video_published_at"] = now_iso()
            qpath.write_text(json.dumps(q, indent=2) + "\n")
            return True
    return False


# ---------------------------------------------------------------------------
# Step 1 — Claude: generate video script
# ---------------------------------------------------------------------------

VIDEO_SCRIPT_PROMPT = """You are writing a script for a 90-second YouTube video for a home restoration company.
The video uses a mix of the client's real photos and stock footage from Pexels.
Turn the blog post below into an engaging, helpful video script.

Blog post title: {title}
Blog post body:
{body}

Available client photo categories (use these for "client_photo" scenes):
{photo_categories}

Produce a JSON object with these exact keys:
{{
  "scenes": [
    {{
      "narration": "...",         // 20-30 words, conversational, no hashtags
      "scene_type": "...",        // one of: "client_photo", "stock", "ai"
      "photo_keywords": [...],    // if scene_type="client_photo": 1-3 keywords matching categories above
      "stock_query": "...",       // if scene_type="stock": 3-5 word Pexels search (e.g. "water damage restoration crew")
      "image_prompt": "..."       // if scene_type="ai": detailed Gemini prompt, photorealistic 16:9
    }},
    ... (exactly 10 scenes)
  ],
  "youtube_title": "...",         // 60 chars max, includes primary keyword naturally
  "youtube_description": "...",  // 1000-1500 chars, includes the blog URL and call to action
  "tags": ["...", "...", ...],    // 15-20 tags, mix of broad + specific + local
  "thumbnail_prompt": "..."      // Gemini prompt for custom thumbnail (bold text, left side clear for text overlay)
}}

RULES for scene_type assignment (this video uses IMAGES ONLY — no stock video):
- Use "client_photo" for intro scenes, team/company credibility scenes, and job-result scenes
  — pick keywords matching the available categories above (e.g. "team", "before_after", "equipment")
- Use "ai" for every other scene (topic-specific visuals the client's photos won't cover — flooded room,
  moisture meter, drying equipment, specific damage type). ALWAYS include a detailed "image_prompt": a
  photorealistic 16:9 scene (specific subject, setting, lighting, mood; NO on-screen text; avoid showing
  faces — shoot from behind, hands-only, or wide framing, so auto-blur never triggers).
- Do NOT use "stock" — there is no stock-video step anymore.
- If photo categories are available, aim for 3-4 "client_photo" scenes; make every other scene "ai".

RULES for narration:
- HARD LENGTH CAP: total narration across ALL scenes must be 200-220 words (~90 seconds at
  ~2.4 words/second spoken). Count the words. Do NOT exceed 220 words total.
- Warm, direct voice. Say "your contractor" not "we"
- No jargon the homeowner would not understand
- End with a clear CTA: "Call {company} at {phone} for a free estimate."

RULES for youtube_description:
- First 2 lines: hook + primary keyword (visible before "show more")
- Include: "For emergency help, call {company} at {phone}"
- Include: "Read the full guide: {post_url}"
- End with 3-5 relevant hashtags

Respond with ONLY valid JSON. No prose before or after.
"""


# 90-second tightening: blog-video narration is validated against this band
# (target 200-220 spoken words). One retry with a firmer instruction, then
# scenes are trimmed if the estimate still exceeds ~100s at the TTS rate.
VIDEO_WORDS_MIN, VIDEO_WORDS_MAX = 180, 230
TTS_WORDS_PER_SEC = 2.4           # measured ElevenLabs turbo pace
MAX_NARRATION_SEC = 100.0


def _narration_words(scenes: list[dict]) -> int:
    return sum(len(s.get("narration", "").split()) for s in scenes)


def _trim_scenes_to_cap(scenes: list[dict],
                        max_sec: float = MAX_NARRATION_SEC,
                        wps: float = TTS_WORDS_PER_SEC) -> list[dict]:
    """Drop scenes (from just before the CTA outro) until estimated narration
    time fits the cap. Keeps the opener and the CTA closer intact."""
    max_words = int(max_sec * wps)
    sc = list(scenes)
    while len(sc) > 3 and _narration_words(sc) > max_words:
        drop = len(sc) - 2  # scene just before the CTA outro
        print(f"  [cap] narration {_narration_words(sc)} words > {max_words} "
              f"(~{max_sec:.0f}s @ {wps} w/s) — trimming scene {drop + 1}")
        sc.pop(drop)
    return sc


def parse_script_json(raw: str) -> dict:
    """LLM JSON with self-repair (D2, 2026-09-17: an unescaped quote in a
    narration string crashed the whole fleet run for 3 weeks). Try strict,
    then repair the classic failure (bare interior double-quotes inside
    string values), then a trailing-comma cleanup. Raises only when all
    three fail — and the caller treats that as THIS client failing, never
    the run."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # State-machine repair: walk the text; inside a string, a double-quote
    # only legitimately CLOSES it when the next non-space char is a JSON
    # delimiter (, : } ] or end). Any other interior quote gets escaped.
    out, in_str, esc = [], False, False
    for idx, ch in enumerate(raw):
        if esc:
            out.append(ch); esc = False; continue
        if ch == "\\" and in_str:
            out.append(ch); esc = True; continue
        if ch == '"':
            if not in_str:
                in_str = True; out.append(ch); continue
            j = idx + 1
            while j < len(raw) and raw[j] in " \t\r\n":
                j += 1
            if j >= len(raw) or raw[j] in ",:}]":
                in_str = False; out.append(ch)
            else:
                out.append('\\"')   # interior quote — escape it
            continue
        out.append(ch)
    repaired = "".join(out)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass
    cleaned = re.sub(r",\s*([}\]])", r"\1", repaired)
    return json.loads(cleaned)


def generate_video_script(post: dict, client: dict) -> dict:
    api_key = require_env("ANTHROPIC_API_KEY")

    brand_name = client.get("display_name", "")
    phone = ""
    try:
        plan_input = json.loads(
            (CLIENTS_DIR / client["slug"] / "plan-input.json").read_text()
        )
        phone = plan_input.get("brand", {}).get("phone", "")
    except Exception:
        pass

    post_url = f"https://{client.get('domain', '')}/blog/{post['frontmatter'].get('slug', '')}"

    # Detect available client photo categories for scene assignment guidance
    photos_map = load_client_photos(client["slug"])
    if photos_map:
        cat_list = ", ".join(
            f"{cat} ({len(paths)} photo{'s' if len(paths) > 1 else ''})"
            for cat, paths in sorted(photos_map.items())
        )
        photo_categories = f"Available: {cat_list}"
    else:
        photo_categories = "None — use stock or ai for all scenes"

    prompt = VIDEO_SCRIPT_PROMPT.format(
        title=post["frontmatter"].get("title", ""),
        body=post["body"][:6000],  # stay within token budget
        company=brand_name,
        phone=phone,
        post_url=post_url,
        photo_categories=photo_categories,
    )

    # Word-cap validation: one firmer retry if narration lands outside the
    # 200-220-word target band, then a hard scene-trim as the backstop.
    script: dict = {}
    usage_total = {"input_tokens": 0, "output_tokens": 0}
    attempt_prompt = prompt
    for attempt in (1, 2):
        # max_tokens sized for a 200-220-word narration + prompts/metadata JSON
        body = json.dumps({
            "model": ANTHROPIC_MODEL,
            "max_tokens": 3500,
            "messages": [{"role": "user", "content": attempt_prompt}],
        }).encode()
        req = urllib.request.Request(
            ANTHROPIC_API, data=body, method="POST",
            headers={
                "content-type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode())

        raw = payload["content"][0]["text"].strip()
        # Strip ```json fences if present
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        script = parse_script_json(raw)
        for k in usage_total:
            usage_total[k] += payload.get("usage", {}).get(k, 0)

        words = _narration_words(script.get("scenes", []))
        if VIDEO_WORDS_MIN <= words <= VIDEO_WORDS_MAX:
            print(f"  narration: {words} words (within {VIDEO_WORDS_MIN}-{VIDEO_WORDS_MAX})")
            break
        if attempt == 1:
            print(f"  narration: {words} words — outside {VIDEO_WORDS_MIN}-"
                  f"{VIDEO_WORDS_MAX}, retrying with firmer cap...")
            attempt_prompt = prompt + (
                f"\n\nIMPORTANT: a previous draft of this script had {words} words of "
                "narration, which violates the hard length cap. Rewrite so the TOTAL "
                "narration across all scenes is 200-220 words — count them before "
                "responding. Shorten every scene evenly; keep the CTA."
            )
        else:
            print(f"  narration: {words} words after retry — accepting; "
                  "scene-trim backstop will enforce the runtime cap")

    # Backstop: never let narration exceed ~100s at the TTS speaking rate
    script["scenes"] = _trim_scenes_to_cap(script.get("scenes", []))
    script["_usage"] = usage_total
    return script


# ---------------------------------------------------------------------------
# Step 1b — Claude: generate a BRAND-AUTHORITY script (Merchynt/Paige style)
# ---------------------------------------------------------------------------

BRAND_SCRIPT_PROMPT = """You are writing a ~35-second brand-authority video script for a home restoration company.
This is NOT a how-to. It is a short "who we are, where we serve, what we do, call us" video — modeled on the
best local-SEO brand videos. Its transcript is indexed by Google and cited by AI search, so it must be DENSE
with the company name, the service-area city names, and the service names (these are the ranking signals).

Company: {company}
Phone: {phone}
Service-area cities: {cities}
Services to feature: {services}
Credibility: {credibility}
Available client photo categories (prefer these): {photo_categories}
{focus}

CRITICAL LENGTH: the TOTAL narration across ALL scenes must be 75-90 words MAXIMUM (~30-35 seconds
spoken). This is a punchy brand short, NOT a 90-second video. Each scene = ONE short sentence (8-14
words). Count your words and stay under 90 total. Structure the narration to flow like this:
1. LOCAL HOOK naming 2-3 service-area cities + the core problem ("From {{city}} to {{city}}, when water hits fast...")
2. The company name + a speed/trust value prop ("{company} shows up ready.")
3. The services, grouped naturally (name each service clearly — these are keywords)
4. A credibility/reassurance beat
5. A clear CTA ending with the phone number

Produce a JSON object with these exact keys:
{{
  "scenes": [
    {{
      "scene_type": "client_photo" | "ai",   // prefer client_photo when a category fits; else ai
      "narration": "the spoken line for this segment (one sentence)",
      "caption": "SHORT on-screen label (3-6 words, e.g. 'Emergency water removal')",
      "photo_keywords": ["team","truck",...],  // for client_photo — match the categories above
      "image_prompt": "for ai scenes: photoreal 16:9 scene, NO on-screen text, NO faces (behind/hands/wide)"
    }}
    // 5-6 scenes total: scene 1 = company/team intro, then service groups, last = CTA/credibility
  ],
  "youtube_title": "{company} — {primary_service} in {primary_city} | 60 chars max",
  "youtube_description": "2-3 sentences naming the company, cities, and services + 'Call {company} at {phone}'",
  "tags": ["...", 15-20 tags mixing company name + services + city names],
  "thumbnail_prompt": "Gemini prompt: bold branded thumbnail, company name area clear"
}}

RULES:
- LENGTH IS CRITICAL: combined narration across all scenes must be <= 90 words TOTAL. Count them. A
  35-second punchy short beats a comprehensive 90-second one. If in doubt, cut words.
- Name the COMPANY, the CITIES, and the SERVICES explicitly and often — that density IS the SEO/AI signal.
- Captions are SHORT service labels, not the spoken sentence.
- Warm, confident, local. End with the phone number.
- Respond with ONLY valid JSON. No prose before or after.
"""


def generate_brand_script(client: dict, service: str | None = None,
                          city: str | None = None) -> dict:
    """Claude → a Merchynt-style brand-authority script (entity/local/service dense)."""
    api_key = require_env("ANTHROPIC_API_KEY")
    brand_name = client.get("display_name", "")
    phone = founded = ""
    services: list[str] = []
    areas: list[str] = []
    certs: list[str] = []
    try:
        plan = json.loads((CLIENTS_DIR / client["slug"] / "plan-input.json").read_text())
        b = plan.get("brand", {})
        phone = b.get("phone", "")
        founded = str(b.get("founded_year", "") or "")
        certs = b.get("certifications", []) or []
        services = plan.get("services", []) or []
        areas = [f"{a['city']}, {a['state']}" for a in plan.get("service_areas", [])]
    except Exception:
        pass

    feat_services = [service] if service else services
    svc_pretty = ", ".join(s.replace("-", " ") for s in feat_services[:10])
    cities = ", ".join([city] if city else areas[:6])
    credibility = ", ".join(filter(None, [
        f"founded {founded}" if founded else "",
        ", ".join(certs[:3]),
    ])) or "licensed, insured, and certified"
    focus = ""
    if service or city:
        focus = "FOCUS this video on " + " in ".join(filter(None, [
            (service or "").replace("-", " "), city or ""])) + "."

    photos_map = load_client_photos(client["slug"])
    photo_categories = (", ".join(sorted(photos_map)) if photos_map
                        else "None — use ai scenes")

    prompt = BRAND_SCRIPT_PROMPT.format(
        company=brand_name, phone=phone, cities=cities, services=svc_pretty,
        credibility=credibility, photo_categories=photo_categories, focus=focus,
        primary_service=(feat_services[0].replace("-", " ") if feat_services else "restoration"),
        primary_city=(city or (areas[0] if areas else "")),
    )
    body = json.dumps({
        "model": ANTHROPIC_MODEL, "max_tokens": 4000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(ANTHROPIC_API, data=body, method="POST", headers={
        "content-type": "application/json", "x-api-key": api_key,
        "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode())
    raw = payload["content"][0]["text"].strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    script = parse_script_json(raw)
    script["_usage"] = payload.get("usage", {})
    return script


# ---------------------------------------------------------------------------
# Step 2 — TTS: synthesise narration
# ---------------------------------------------------------------------------


def synthesise_speech_google(narration_text: str, output_path: Path) -> None:
    """Call Google Cloud TTS REST API. Requires GOOGLE_CLOUD_API_KEY."""
    api_key = require_env("GOOGLE_CLOUD_API_KEY")
    body = json.dumps({
        "input": {"text": narration_text},
        "voice": {
            "languageCode": "en-US",
            "name": TTS_VOICE,
            "ssmlGender": "MALE",
        },
        "audioConfig": {"audioEncoding": "MP3"},
    }).encode()
    url = f"{TTS_API_URL}?key={api_key}"
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        err = exc.read().decode(errors="replace")
        die(f"TTS API error {exc.code}: {err[:300]}")

    audio_bytes = base64.b64decode(result["audioContent"])
    output_path.write_bytes(audio_bytes)


def synthesise_speech_macos(narration_text: str, output_path: Path) -> None:
    """Fallback: use macOS `say` command. No API key needed."""
    if not shutil.which("say"):
        die("macOS `say` command not found. Use --tts google or install a TTS provider.")
    aiff_path = output_path.with_suffix(".aiff")
    subprocess.run(
        ["say", "-v", "Samantha", "-r", "165", "-o", str(aiff_path), narration_text],
        check=True,
    )
    # Convert AIFF to MP3 via ffmpeg
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(aiff_path), "-c:a", "libmp3lame", "-b:a", "128k",
         str(output_path)],
        check=True, capture_output=True,
    )
    aiff_path.unlink(missing_ok=True)


def synthesise_speech_elevenlabs(narration_text: str, output_path: Path) -> None:
    """ElevenLabs TTS — highest quality, human-sounding narration."""
    api_key = require_env("ELEVENLABS_API_KEY")
    url = f"{ELEVENLABS_API}/{ELEVENLABS_VOICE_ID}"
    body = json.dumps({
        "text": narration_text,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "xi-api-key": api_key,
            "content-type": "application/json",
            "accept": "audio/mpeg",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            output_path.write_bytes(resp.read())
    except urllib.error.HTTPError as exc:
        err = exc.read().decode(errors="replace")
        die(f"ElevenLabs API error {exc.code}: {err[:300]}")


def synthesise_speech(narration_text: str, output_path: Path, tts: str = "elevenlabs") -> None:
    print(f"  [TTS] Synthesising {len(narration_text)} chars via {tts}...")
    if tts == "elevenlabs":
        synthesise_speech_elevenlabs(narration_text, output_path)
    elif tts == "macos":
        synthesise_speech_macos(narration_text, output_path)
    else:
        synthesise_speech_google(narration_text, output_path)


# ---------------------------------------------------------------------------
# Step 3 — Scene sources: client photos → Pexels stock → Gemini AI fallback
# ---------------------------------------------------------------------------

# Map category names to filename keywords used to auto-classify Photos folder contents
PHOTO_CATEGORIES = {
    "team":        ["team", "crew", "staff", "worker", "people", "group", "full"],
    "before_after": ["before", "after"],
    "equipment":   ["blower", "dryer", "equipment", "machine", "fan", "tool"],
    "hazmat":      ["hazmat", "suit", "protective", "gear"],
    "truck":       ["truck", "vehicle", "van"],
    "job_site":    ["job", "site", "damage", "restoration", "water", "fire", "mold"],
}
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def load_client_photos(slug: str) -> dict[str, list[Path]]:
    """Return {category: [paths]} from clients/{slug}/Photos/. Logos excluded."""
    photos_dir = CLIENTS_DIR / slug / "Photos"
    if not photos_dir.exists():
        return {}
    result: dict[str, list[Path]] = {}
    for p in sorted(photos_dir.iterdir()):
        if p.suffix.lower() not in PHOTO_EXTENSIONS:
            continue
        name_lower = p.name.lower()
        if "logo" in name_lower or "favicon" in name_lower:
            continue
        matched = False
        for category, keywords in PHOTO_CATEGORIES.items():
            if any(kw in name_lower for kw in keywords):
                result.setdefault(category, []).append(p)
                matched = True
                break
        if not matched:
            result.setdefault("misc", []).append(p)
    return result


def match_client_photo(keywords: list[str], photos_map: dict, used: set) -> Path | None:
    """Find the best unused client photo matching the given keywords."""
    for kw in keywords:
        kw_lower = kw.lower()
        for category, photos in photos_map.items():
            if kw_lower in category or any(kw_lower in p.name.lower() for p in photos):
                for p in photos:
                    if str(p) not in used:
                        return p
    # Fallback: any unused photo in preferred order
    for category in ("before_after", "job_site", "equipment", "team", "hazmat", "truck", "misc"):
        for p in photos_map.get(category, []):
            if str(p) not in used:
                return p
    return None


def pexels_search_video(query: str, min_duration: int = 6) -> str | None:
    """Search Pexels for a landscape video clip. Returns download URL or None."""
    api_key = require_env("PEXELS_API_KEY")
    url = (PEXELS_API + "?query=" + urllib.parse.quote(query)
           + "&per_page=10&size=medium&orientation=landscape")
    req = urllib.request.Request(url, headers={
        "Authorization": api_key,
        "User-Agent": "RankAI/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:
        print(f"      [pexels] search error: {exc}")
        return None
    for video in data.get("videos", []):
        if video.get("duration", 0) < min_duration:
            continue
        best_url, best_w = None, 0
        for f in video.get("video_files", []):
            if f.get("file_type") != "video/mp4":
                continue
            w = f.get("width", 0)
            if f.get("quality") in ("hd", "uhd") and w > best_w:
                best_url, best_w = f.get("link"), w
        if best_url:
            return best_url
    return None


def download_and_trim_pexels(url: str, clip_path: Path, duration: float) -> bool:
    """Download a Pexels video, trim to duration, scale to 1920x1080."""
    tmp = clip_path.with_suffix(".pexels_raw.mp4")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RankAI/1.0"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            tmp.write_bytes(resp.read())
    except Exception as exc:
        print(f"      [pexels] download failed: {exc}")
        tmp.unlink(missing_ok=True)
        return False
    cmd = [
        "ffmpeg", "-y", "-i", str(tmp),
        "-t", str(duration),
        "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1",
        "-r", "30",
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p", "-an",
        str(clip_path),
    ]
    result = subprocess.run(cmd, capture_output=True)
    tmp.unlink(missing_ok=True)
    return result.returncode == 0


def gemini_generate_image(prompt: str, model: str, max_retries: int = 3) -> bytes:
    """Generate a 16:9 PNG via Gemini REST API."""
    api_key = require_env("GOOGLE_AI_API_KEY")
    url = f"{GEMINI_API_BASE}/{model}:generateContent?key={api_key}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": GEMINI_ASPECT},
        },
    }).encode()

    last = ""
    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                payload = json.loads(resp.read().decode())
            for cand in payload.get("candidates", []):
                for part in cand.get("content", {}).get("parts", []):
                    inline = part.get("inlineData") or part.get("inline_data")
                    if inline and inline.get("data"):
                        return base64.b64decode(inline["data"])
            raise RuntimeError(f"Gemini: no image in response: {json.dumps(payload)[:300]}")
        except urllib.error.HTTPError as exc:
            err = exc.read().decode(errors="replace")
            if exc.code in (429,) or 500 <= exc.code < 600:
                wait = 2 ** attempt
                last = f"HTTP {exc.code}"
                print(f"      retry {attempt}/{max_retries} in {wait}s ({last})")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Gemini HTTP {exc.code}: {err}")
        except (urllib.error.URLError, socket.timeout) as exc:
            last = str(exc)
            wait = 2 ** attempt
            print(f"      retry {attempt}/{max_retries} in {wait}s (net: {last[:60]})")
            time.sleep(wait)
    raise RuntimeError(f"Gemini failed after {max_retries} retries. Last: {last}")


def generate_scene_clips(
    scenes: list[dict],
    work_dir: Path,
    model: str,
    slug: str,
    scene_duration: float,
    post_stills: list[Path] | None = None,
    max_ai_images: int | None = None,
) -> list[Path]:
    """Build one .mp4 clip per scene using IMAGES ONLY: post still > client photo >
    Gemini AI image.

    post_stills (post hero / section images / service heroes / brand shots) are pinned
    to evenly-spaced anchor scenes so real photography bookends the AI stills.
    max_ai_images caps the number of UNIQUE Gemini generations; further AI scenes
    reuse earlier stills (different Ken Burns direction + subtitle keeps them fresh).
    Stock video (Pexels) is disabled (USE_STOCK_VIDEO=False) — every scene renders as a
    still with a Ken Burns zoom, for a consistent look."""
    photos_map = load_client_photos(slug)
    used_photos: set[str] = set()
    clip_paths: list[Path] = []
    style_suffix = image_style_suffix(slug)

    # Pin post stills to evenly-spaced scene indices (first still opens, last closes)
    still_slots: dict[int, Path] = {}
    stills = list(post_stills or [])
    if stills:
        n, k = len(scenes), min(len(stills), len(scenes))
        for j in range(k):
            idx = round(j * (n - 1) / max(k - 1, 1))
            if idx not in still_slots:
                still_slots[idx] = stills[j]

    ai_pool: list[Path] = []  # unique Gemini stills already generated (for reuse)

    for i, scene in enumerate(scenes):
        clip_path = work_dir / f"clip_{i:02d}.mp4"
        zoom_dir = "in" if i % 2 == 0 else "out"
        scene_type = scene.get("scene_type", "ai")

        narration = scene.get("narration", "")
        # Brand videos carry a short on-screen "caption" (service label, like the
        # Merchynt style); blog videos burn the spoken narration. Prefer caption.
        subtitle = scene.get("caption") or narration

        # --- 0. Pinned post still (real site imagery) ---
        if i in still_slots:
            still = still_slots[i]
            print(f"  [clip {i+1}/{len(scenes)}] post still: {still.name[:45]}")
            build_still_clip(still, clip_path, scene_duration, zoom_dir,
                             subtitle_text=subtitle)
            clip_paths.append(clip_path)
            continue

        # --- 1. Client photo ---
        if scene_type == "client_photo" and photos_map:
            photo = match_client_photo(scene.get("photo_keywords", []), photos_map, used_photos)
            if photo:
                print(f"  [clip {i+1}/{len(scenes)}] client photo: {photo.name[:45]}")
                build_still_clip(photo, clip_path, scene_duration, zoom_dir,
                                 subtitle_text=subtitle)
                used_photos.add(str(photo))
                clip_paths.append(clip_path)
                continue
            print(f"  [clip {i+1}/{len(scenes)}] no matching client photo, using AI image...")

        # --- 2. Pexels stock video (disabled — images only) ---
        if USE_STOCK_VIDEO and scene_type in ("client_photo", "stock"):
            query = scene.get("stock_query") or narration[:50]
            print(f"  [clip {i+1}/{len(scenes)}] pexels: '{query[:45]}'...")
            video_url = pexels_search_video(query, min_duration=int(scene_duration))
            if video_url:
                if download_and_trim_pexels(video_url, clip_path, scene_duration):
                    print(f"      [subtitle] burning captions on pexels clip...")
                    _burn_subtitles_on_video(clip_path, narration)
                    clip_paths.append(clip_path)
                    continue
            print(f"      falling back to Gemini AI...")

        # --- 3. Gemini AI image (capped) or reuse of an earlier still ---
        if max_ai_images is not None and len(ai_pool) >= max_ai_images and ai_pool:
            reuse = ai_pool[(i - len(still_slots)) % len(ai_pool)]
            print(f"  [clip {i+1}/{len(scenes)}] reuse still: {reuse.name[:45]} "
                  f"(ai cap {max_ai_images} reached)")
            build_still_clip(reuse, clip_path, scene_duration, zoom_dir,
                             subtitle_text=subtitle)
            clip_paths.append(clip_path)
            continue

        img_prompt = scene.get("image_prompt") or (
            f"Photorealistic {GEMINI_ASPECT} professional restoration scene: {narration[:80]}, "
            "dramatic professional lighting, hyperrealistic, restoration industry"
        )
        if style_suffix:
            img_prompt = f"{img_prompt} {style_suffix}"
        print(f"  [clip {i+1}/{len(scenes)}] gemini: {img_prompt[:50]}...")
        png_bytes = gemini_generate_image(img_prompt, model=model)
        img_path = work_dir / f"scene_{i:02d}.png"
        img_path.write_bytes(png_bytes)
        ai_pool.append(img_path)
        build_still_clip(img_path, clip_path, scene_duration, zoom_dir,
                         subtitle_text=subtitle)
        clip_paths.append(clip_path)
        time.sleep(1)  # Gemini rate limit courtesy

    return clip_paths


def generate_thumbnail(thumbnail_prompt: str, work_dir: Path, model: str) -> Path:
    """Generate the YouTube thumbnail image (legacy Gemini path)."""
    print("  [thumbnail] generating...")
    png_bytes = gemini_generate_image(thumbnail_prompt, model=model)
    thumb_path = work_dir / "thumbnail.png"
    thumb_path.write_bytes(png_bytes)
    return thumb_path


def build_branded_thumbnail(slug: str, lines: list[str], work_dir: Path) -> Path:
    """Deterministic branded thumbnail: the client's consistent hero image as
    background + per-video text overlay (Santino 2026-07-23: 'same background
    image but add text to differentiate each one'). Brand color bar + logo +
    phone. Replaces the Gemini thumbnail — consistent, free, on-brand.
    """
    from PIL import Image as PILImage
    from PIL import ImageDraw, ImageFilter

    W, H = 1280, 720
    brand = {}
    try:
        brand = json.loads((CLIENTS_DIR / slug / "plan-input.json").read_text()).get("brand", {})
    except Exception:
        pass

    def _hex_rgb(h, fallback=(168, 50, 39)):
        h = str(h or "").lstrip("#")
        try:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        except Exception:
            return fallback
    accent = _hex_rgb(brand.get("primary_color"))

    # background: the client's hero image, cover-cropped (consistent per client)
    canvas = PILImage.new("RGB", (W, H), (16, 24, 39))
    bg_path = SITES_DIR / slug / "public" / "images" / "hero-bg.webp"
    if bg_path.exists():
        try:
            bg = PILImage.open(bg_path).convert("RGB")
            scale = max(W / bg.width, H / bg.height)
            bg = bg.resize((int(bg.width * scale) + 1, int(bg.height * scale) + 1), PILImage.LANCZOS)
            canvas.paste(bg, (int((W - bg.width) / 2), int((H - bg.height) / 2)))
        except Exception:
            pass
    # left-weighted dark gradient for text legibility
    grad = PILImage.new("L", (W, 1), 0)
    for x in range(W):
        grad.putpixel((x, 0), int(200 * max(0.0, 1.0 - x / (W * 0.85))))
    grad = grad.resize((W, H))
    canvas = PILImage.composite(PILImage.new("RGB", (W, H), (8, 12, 20)), canvas, grad)

    draw = ImageDraw.Draw(canvas)
    # big text lines, top-left, white with soft shadow; each line auto-shrinks
    # until it fits inside the safe width (long service names overflowed)
    max_w = int(W * 0.88)
    y = int(H * 0.13)
    for i, line in enumerate([l for l in lines if l][:3]):
        size = int(H * (0.15 if i == 0 else 0.115))
        font = _load_subtitle_font(size=size)
        while size > int(H * 0.06):
            bb = draw.textbbox((0, 0), line, font=font)
            if bb[2] - bb[0] <= max_w - int(W * 0.055):
                break
            size = int(size * 0.92)
            font = _load_subtitle_font(size=size)
        draw.text((int(W * 0.055) + 3, y + 4), line, font=font, fill=(0, 0, 0))
        draw.text((int(W * 0.055), y), line, font=font, fill=(255, 255, 255))
        bb = draw.textbbox((0, 0), line, font=font)
        y += (bb[3] - bb[1]) + int(H * 0.05)

    # brand color bar with phone at the bottom
    bar_h = int(H * 0.11)
    draw.rectangle([0, H - bar_h, W, H], fill=accent)
    phone = brand.get("phone", "")
    label = (brand.get("display_name", "") + ("   •   " + phone if phone else "")).strip()
    if label:
        f2 = _load_subtitle_font(size=int(bar_h * 0.44))
        bb = draw.textbbox((0, 0), label, font=f2)
        draw.text((int(W * 0.055), H - bar_h + (bar_h - (bb[3] - bb[1])) // 2 - bb[1]),
                  label, font=f2, fill=(255, 255, 255))

    # logo chip top-right on a white pill
    logo_path = SITES_DIR / slug / "public" / "images" / "logo.webp"
    if logo_path.exists():
        try:
            logo = PILImage.open(logo_path).convert("RGBA")
            lw = int(W * 0.18)
            logo = logo.resize((lw, int(logo.height * lw / logo.width)), PILImage.LANCZOS)
            pad = int(H * 0.02)
            pill = PILImage.new("RGBA", (logo.width + pad * 2, logo.height + pad * 2), (255, 255, 255, 235))
            canvas.paste(pill, (W - pill.width - pad, pad), pill)
            canvas.paste(logo, (W - pill.width, pad * 2), logo)
        except Exception:
            pass

    out = work_dir / "thumbnail.png"
    canvas.save(out)
    print("  [thumbnail] branded template rendered ({} lines)".format(len([l for l in lines if l][:3])))
    return out


def _title_thumb_lines(title: str) -> list[str]:
    """Split a video title into <=3 short uppercase lines for the thumbnail."""
    head = title.split("|")[0].strip()
    words = head.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > 16 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
        if len(lines) == 3:
            break
    if cur and len(lines) < 3:
        lines.append(cur)
    return [l.upper() for l in lines[:3]]


# ---------------------------------------------------------------------------
# Step 4 — FFmpeg: assemble video
# ---------------------------------------------------------------------------


def get_audio_duration(audio_path: Path) -> float:
    """Return audio duration in seconds via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", str(audio_path),
        ],
        capture_output=True, text=True, check=True,
    )
    probe = json.loads(result.stdout)
    for stream in probe.get("streams", []):
        dur = stream.get("duration")
        if dur:
            return float(dur)
    die("Could not determine audio duration from ffprobe.")
    return 0.0  # unreachable, satisfy type checker


# ---------------------------------------------------------------------------
# Subtitle rendering helpers (PIL-based — no libass/drawtext needed)
# ---------------------------------------------------------------------------

SUBTITLE_FONT_SIZE = 52
SUBTITLE_CHARS_PER_LINE = 52


def _load_subtitle_font(size: int = None):
    from PIL import ImageFont
    px = size or SUBTITLE_FONT_SIZE
    for fp in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    ]:
        try:
            return ImageFont.truetype(fp, px)
        except Exception:
            pass
    return ImageFont.load_default()


def _wrap_text(text: str) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    curr_len = 0
    for word in words:
        if curr_len + len(word) + 1 > SUBTITLE_CHARS_PER_LINE and current:
            lines.append(" ".join(current))
            current, curr_len = [word], len(word)
        else:
            current.append(word)
            curr_len += len(word) + 1
    if current:
        lines.append(" ".join(current))
    return lines


def _draw_subtitle(img, lines: list[str], font) -> "PILImage":
    """Draw white text with black outline onto img in-place. Returns img."""
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    line_h = SUBTITLE_FONT_SIZE + 12
    total_h = line_h * len(lines)
    y_base = img.height - total_h - 70  # 70px above bottom edge

    for i, line in enumerate(lines):
        bbox = font.getbbox(line)
        tw = bbox[2] - bbox[0]
        x = (img.width - tw) // 2
        y = y_base + i * line_h
        # Black outline in 8 directions
        for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3),
                       (-3, -3), (3, 3), (-3, 3), (3, -3)]:
            draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))
    return img


def build_still_clip(img_path: Path, clip_path: Path, duration: float,
                     zoom_direction: str, fps: int = 30,
                     subtitle_text: str = "") -> None:
    """Ken Burns clip from a still image via Pillow frame-pipe to FFmpeg.

    Generates exact integer crop coordinates per-frame — eliminates the
    floating-point rounding oscillation that caused the shaking artifact
    in the previous FFmpeg crop-expression approach.
    """
    from PIL import Image as PILImage

    frames = int(duration * fps)
    img = PILImage.open(img_path).convert("RGB")
    orig_w, orig_h = img.size

    # Scale image to 115% of output so there's room to pan
    target_w, target_h = OUT_W, OUT_H
    scale = max(target_w * 1.15 / orig_w, target_h * 1.15 / orig_h)
    scaled_w = int(orig_w * scale)
    scaled_h = int(orig_h * scale)
    scaled_w += scaled_w % 2  # x264 requires even dimensions
    scaled_h += scaled_h % 2
    img = img.resize((scaled_w, scaled_h), PILImage.LANCZOS)

    max_x = scaled_w - target_w  # total horizontal travel in pixels
    max_y = scaled_h - target_h  # total vertical travel in pixels

    # Pre-compute subtitle lines and font once
    font = sub_lines = None
    if subtitle_text:
        font = _load_subtitle_font()
        sub_lines = _wrap_text(subtitle_text)

    proc = subprocess.Popen(
        [
            "ffmpeg", "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{target_w}x{target_h}", "-pix_fmt", "rgb24",
            "-r", str(fps), "-i", "pipe:0",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            str(clip_path),
        ],
        stdin=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        for n in range(frames):
            t = n / max(frames - 1, 1)        # 0.0 → 1.0
            if zoom_direction == "out":
                t = 1.0 - t                    # reverse direction
            # Integer coords — monotonically increase, never oscillate
            x = int(max_x * t)
            y = int(max_y * t)
            frame = img.crop((x, y, x + target_w, y + target_h))
            if sub_lines:
                _draw_subtitle(frame, sub_lines, font)
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
        proc.wait()


def build_brand_card(slug: str, kind: str, work_dir: Path) -> Path:
    """Render a branded title/CTA card (white bg + centered logo, + CTA text on outro).

    Used as the intro/outro bookends of a brand-authority video (Merchynt style)."""
    from PIL import Image as PILImage
    from PIL import ImageDraw

    card = PILImage.new("RGB", (OUT_W, OUT_H), (255, 255, 255))
    # Logo (slightly above center so CTA text has room below)
    logo_path = SITES_DIR / slug / "public" / "images" / "logo.webp"
    logo_cy = int(OUT_H * (0.42 if kind == "outro" else 0.5))
    if logo_path.exists():
        try:
            logo = PILImage.open(logo_path).convert("RGBA")
            target_w = int(OUT_W * 0.6)
            ratio = target_w / logo.width
            logo = logo.resize((target_w, int(logo.height * ratio)), PILImage.LANCZOS)
            card.paste(logo, (int((OUT_W - logo.width) / 2), int(logo_cy - logo.height / 2)), logo)
        except Exception:
            pass

    if kind == "outro":
        phone = ""
        try:
            phone = json.loads((CLIENTS_DIR / slug / "plan-input.json").read_text()) \
                .get("brand", {}).get("phone", "")
        except Exception:
            pass
        draw = ImageDraw.Draw(card)
        text = f"Call {phone}" if phone else "Call for a free estimate"
        font = _load_subtitle_font(size=int(OUT_H * 0.05))
        bb = draw.textbbox((0, 0), text, font=font)
        tx = (OUT_W - (bb[2] - bb[0])) / 2
        ty = int(OUT_H * 0.6)
        # brand-red pill behind the CTA
        pad = int(OUT_H * 0.018)
        draw.rounded_rectangle([tx - pad * 2, ty - pad, tx + (bb[2] - bb[0]) + pad * 2, ty + (bb[3] - bb[1]) + pad * 2],
                               radius=pad * 2, fill=(168, 50, 39))
        draw.text((tx, ty - bb[1] + pad // 2), text, font=font, fill=(255, 255, 255))

    out = work_dir / f"card_{kind}.png"
    card.save(out)
    return out


def _burn_subtitles_on_video(clip_path: Path, subtitle_text: str, fps: int = 30) -> None:
    """Read an existing clip frame-by-frame and burn subtitle text onto each frame."""
    from PIL import Image as PILImage

    font = _load_subtitle_font()
    lines = _wrap_text(subtitle_text)
    frame_bytes = 1920 * 1080 * 3
    tmp = clip_path.with_suffix(".sub_tmp.mp4")

    reader = subprocess.Popen(
        ["ffmpeg", "-i", str(clip_path),
         "-vf", "scale=1920:1080",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    writer = subprocess.Popen(
        ["ffmpeg", "-y",
         "-f", "rawvideo", "-vcodec", "rawvideo",
         "-s", "1920x1080", "-pix_fmt", "rgb24", "-r", str(fps), "-i", "pipe:0",
         "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
         str(tmp)],
        stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    try:
        while True:
            data = reader.stdout.read(frame_bytes)
            if len(data) < frame_bytes:
                break
            frame = PILImage.frombuffer("RGB", (1920, 1080), data, "raw", "RGB", 0, 1)
            _draw_subtitle(frame, lines, font)
            writer.stdin.write(frame.tobytes())
    finally:
        reader.stdout.close()
        reader.wait()
        writer.stdin.close()
        writer.wait()

    if tmp.exists() and tmp.stat().st_size > 10_000:
        tmp.replace(clip_path)
    else:
        tmp.unlink(missing_ok=True)
        print(f"      [subtitle] burn failed for {clip_path.name}, keeping original")


# Background-music bed (auto-mixed when present; the file itself is gitignored — see
# .gitignore:9 — so it stays out of the repo and is sourced locally). Current track:
# "Raising Me Higher" — Mixkit Stock Music Free License (commercial use, no attribution).
# Re-fetch with: curl -A "Mozilla/5.0" -o assets/background_music.mp3 \
#   https://assets.mixkit.co/music/34/34.mp3
BACKGROUND_MUSIC_PATH = REPO_ROOT / "assets" / "background_music.mp3"


def assemble_video(
    clip_paths: list[Path],
    audio_path: Path,
    output_path: Path,
    work_dir: Path,
) -> None:
    """Join clips with xfade dissolve transitions, mux narration + optional music."""
    audio_duration = get_audio_duration(audio_path)
    n = len(clip_paths)
    print(f"  [video] {n} clips, audio={audio_duration:.1f}s, dissolve={XFADE_DURATION}s")

    # Mix narration with optional background music
    use_music = BACKGROUND_MUSIC_PATH.exists()
    if use_music:
        mixed_audio = work_dir / "mixed_audio.mp3"
        subprocess.run([
            "ffmpeg", "-y",
            "-i", str(audio_path),
            "-stream_loop", "-1", "-i", str(BACKGROUND_MUSIC_PATH),
            "-filter_complex",
            f"[1:a]volume=0.126,atrim=0:duration={audio_duration:.3f}[bg];"
            # normalize=0 keeps the narration at full level; without it amix scales
            # every input by 1/n, which halves the voiceover when music is mixed in.
            "[0:a][bg]amix=inputs=2:duration=first:dropout_transition=3:normalize=0[out]",
            "-map", "[out]",
            "-c:a", "libmp3lame", "-b:a", "128k",
            str(mixed_audio),
        ], check=True, capture_output=True)
        final_audio = mixed_audio
        print("  [video] background music mixed in")
    else:
        final_audio = audio_path

    print("  [video] assembling with xfade transitions...")

    # Target length: the full narration plus a breathing tail, so the last
    # words (the phone-number CTA) always complete before the video ends.
    target_total = audio_duration + END_PAD_SEC

    if n == 1:
        # Single clip — no transitions needed. Still hold the final frame and
        # pad the audio with trailing silence so the narration never gets
        # clipped by a clip that rounds a hair short of the audio.
        clip_dur = get_audio_duration(clip_paths[0])
        video_extra = max(target_total - clip_dur, 0.0)
        cmd = [
            "ffmpeg", "-y", "-i", str(clip_paths[0]), "-i", str(final_audio),
            "-filter_complex",
            f"[0:v]tpad=stop_mode=clone:stop_duration={video_extra:.3f}[vout]; "
            f"[1:a]apad=whole_dur={target_total:.3f}[aout]",
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-shortest", str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return

    # Build filter_complex for N clips with xfade dissolve.
    # offset[i] = sum(durations[0:i]) - i*XFADE_DURATION  — uses ACTUAL per-clip
    # durations so variable-length clips (e.g. brand-video logo/CTA cards) align
    # correctly. For uniform clips this is identical to the old i*(scene_dur - t).
    t = XFADE_DURATION
    durs = [get_audio_duration(cp) for cp in clip_paths]

    # Input args: one -i per clip
    input_args: list[str] = []
    for cp in clip_paths:
        input_args += ["-i", str(cp)]

    # Build chained xfade filter
    filter_parts: list[str] = []
    prev_label = "[0:v]"
    cum = 0.0
    for i in range(1, n):
        out_label = "[vx]" if i == n - 1 else f"[v{i}]"
        cum += durs[i - 1] - t
        filter_parts.append(
            f"{prev_label}[{i}:v]xfade=transition=dissolve:"
            f"duration={t}:offset={cum:.3f}{out_label}"
        )
        prev_label = out_label

    # The xfade timeline is sum(durs) - (n-1)*t, which is shorter than the
    # audio. Hold the last frame so the video reaches target_total, and pad the
    # narration with trailing silence to the same length — together with
    # -shortest this guarantees the narration completes and leaves a clean tail.
    video_timeline = sum(durs) - (n - 1) * t
    video_extra = max(target_total - video_timeline, 0.0)
    filter_parts.append(
        f"[vx]tpad=stop_mode=clone:stop_duration={video_extra:.3f}[vout]"
    )
    filter_parts.append(
        f"[{n}:a]apad=whole_dur={target_total:.3f}[aout]"
    )

    filter_complex = "; ".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        *input_args,
        "-i", str(final_audio),
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-shortest",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


# ---------------------------------------------------------------------------
# Step 5 — SRT captions
# ---------------------------------------------------------------------------


def seconds_to_srt_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt(scenes: list[dict], audio_duration: float, output_path: Path) -> None:
    scene_dur = audio_duration / len(scenes)
    lines: list[str] = []
    for i, scene in enumerate(scenes):
        start = i * scene_dur
        end = start + scene_dur
        lines.append(str(i + 1))
        lines.append(f"{seconds_to_srt_time(start)} --> {seconds_to_srt_time(end)}")
        lines.append(scene["narration"])
        lines.append("")
    output_path.write_text("\n".join(lines))


def format_chapter_timestamps(scenes: list[dict], audio_duration: float) -> str:
    """Return a 'Chapters:' block for the YouTube description.

    YouTube detects chapter markers from lines formatted as 'M:SS Title'
    (or H:MM:SS) — the first entry must be at 0:00.
    """
    scene_dur = audio_duration / len(scenes)
    lines = ["Chapters:"]
    for i, scene in enumerate(scenes):
        t = i * scene_dur
        m = int(t // 60)
        s = int(t % 60)
        # Trim narration to a short chapter title (max 50 chars, no mid-word cut)
        narration = scene.get("narration", "")
        if len(narration) > 50:
            narration = narration[:50].rsplit(" ", 1)[0]
        lines.append(f"{m}:{s:02d} {narration}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step 6 — YouTube OAuth
# ---------------------------------------------------------------------------


def youtube_token_path(slug: str) -> Path:
    return CLIENTS_DIR / slug / ".youtube-token.json"


# company_id (app companies.id) per slug — used to find the client's user_integrations
# row. Reads the client record first; falls back to clients/company_map.json (the
# single source of truth shared with api/runner.py, supabase_sync.py, geogrid_store.py).
try:
    _COMPANY_MAP = json.loads((CLIENTS_DIR / "company_map.json").read_text())
except Exception:
    _COMPANY_MAP = {}


def _company_id_for(slug: str) -> str | None:
    rec = CLIENTS_DIR / f"{slug}.json"
    if rec.exists():
        cid = json.loads(rec.read_text()).get("company_id")
        if cid:
            return cid
    return _COMPANY_MAP.get(slug)


def youtube_integration(slug: str) -> dict | None:
    """The client's connected-via-app YouTube integration (connection_metadata), or None.

    The app writes this when a client clicks "Connect YouTube": user_integrations row,
    provider='youtube', connection_metadata={refresh_token, channel_id, channel_title, scopes}."""
    company_id = _company_id_for(slug)
    if not company_id or not os.environ.get("SUPABASE_URL"):
        return None
    try:
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
        # NB: the client/company is keyed by the `client_id` column (= CO-... companies.id).
        r = (sb.table("user_integrations").select("connection_metadata,refresh_token,status")
             .eq("provider", "youtube").eq("client_id", company_id).limit(1).execute())
        if r.data and r.data[0].get("status") in (None, "connected", "active"):
            row = r.data[0]
            md = dict(row.get("connection_metadata") or {})
            # refresh_token may live in connection_metadata OR the top-level column
            md.setdefault("refresh_token", row.get("refresh_token"))
            return md if md.get("refresh_token") else None
    except Exception as e:
        sys.stderr.write(f"  youtube user_integrations lookup failed: {str(e)[:120]}\n")
    return None


def youtube_channel_state(slug: str) -> dict:
    """Does this client's connected YouTube account actually HAVE a channel?

    "Connected" and "has a channel" are different things. A Google account can
    complete the whole OAuth consent flow while owning NO YouTube channel — the
    tokens are valid, every read succeeds, and only videos().insert fails, at the
    very END of the pipeline (ProRestoration 2026-08-04: connected since setup,
    zero videos, no error anyone saw). Every caller that is about to spend money
    or nag a client must ask this first.

    Returns:
      {"connected": bool,          # a usable youtube integration row exists
       "has_channel": bool|None,   # None = COULD NOT VERIFY
       "channel_id": str|None, "channel_title": str|None,
       "reason": str}              # short human-readable why

    has_channel=None means the Google side could not be read (no OAuth client
    env, refresh rejected, API error). Callers MUST treat None as "do nothing" —
    never skip a client's videos and never nag them on an unverified read.
    """
    out = {"connected": False, "has_channel": None, "channel_id": None,
           "channel_title": None, "reason": ""}
    md = youtube_integration(slug)
    if not md:
        out["reason"] = "no connected YouTube integration"
        return out
    out["connected"] = True

    # Fast path: the app stamps channel_id/channel_title at connect time when a
    # channel exists. Present = settled, no API call, no quota.
    if md.get("channel_id"):
        out.update(has_channel=True, channel_id=md["channel_id"],
                   channel_title=md.get("channel_title"), reason="channel_id in metadata")
        return out

    # Missing channel_id is AMBIGUOUS — it can mean "no channel" or just "the
    # metadata backfill never ran". Only the live API can tell the two apart.
    rt = md.get("refresh_token")
    cid_env = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    sec_env = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if not (rt and cid_env and sec_env):
        out["reason"] = "cannot verify (no refresh token / app OAuth client env)"
        return out
    try:
        import requests as _rq
        tok = _rq.post("https://oauth2.googleapis.com/token", data={
            "client_id": cid_env, "client_secret": sec_env,
            "refresh_token": rt, "grant_type": "refresh_token"},
            timeout=30).json().get("access_token")
        if not tok:
            out["reason"] = "cannot verify (refresh token rejected)"
            return out
        ch = _rq.get("https://www.googleapis.com/youtube/v3/channels?part=id,snippet&mine=true",
                     headers={"Authorization": f"Bearer {tok}"}, timeout=30).json()
        if ch.get("error"):
            out["reason"] = f"cannot verify ({str(ch['error'].get('message'))[:60]})"
            return out
        items = ch.get("items") or []
        if items:
            out.update(has_channel=True, channel_id=items[0].get("id"),
                       channel_title=(items[0].get("snippet") or {}).get("title"),
                       reason="verified live via YouTube API")
        else:
            out.update(has_channel=False,
                       reason="Google account is connected but owns NO YouTube channel")
    except Exception as e:  # noqa: BLE001 — an unverifiable read must never act
        out["reason"] = f"cannot verify ({str(e)[:60]})"
    return out


def load_youtube_credentials(slug: str):
    """Load + refresh YouTube OAuth credentials for a client.

    Prefers the app-connected token in Supabase user_integrations (the self-serve model:
    client clicks "Connect YouTube" -> token stored by the app). The refresh_token was
    minted by the APP's OAuth client, so we refresh it with GOOGLE_OAUTH_CLIENT_ID/SECRET
    (the same env creds ads_sync uses). Falls back to the local .youtube-token.json (the
    dev / agency Channel-Manager flow from `auth --slug`)."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        die("Missing google-auth. Run: pip install google-auth google-auth-oauthlib")

    # 1) App-connected token from Supabase (production / Railway)
    md = youtube_integration(slug)
    if md and (md.get("refresh_token") or md.get("access_token")):
        creds = Credentials(
            token=md.get("access_token"),
            refresh_token=md.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ.get("GOOGLE_OAUTH_CLIENT_ID"),
            client_secret=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET"),
            scopes=YOUTUBE_SCOPES,
        )
        # With the app's OAuth client creds we mint a fresh access token (required for
        # automated/cron uploads, where the stored access_token has expired). Without them,
        # fall back to the stored access_token (valid right after a connect — fine for tests).
        if creds.refresh_token and creds.client_id and creds.client_secret:
            creds.refresh(Request())
        elif not creds.token:
            die(f"YouTube token for {slug} has no usable access_token and no "
                f"GOOGLE_OAUTH_CLIENT_ID/SECRET (the app's OAuth client) to refresh it.")
        print(f"    [youtube] using app-connected channel: {md.get('channel_title') or md.get('channel_id')}")
        return creds

    # 2) Local token file (dev / agency Channel-Manager flow)
    token_path = youtube_token_path(slug)
    if not token_path.exists():
        die(
            f"No YouTube token for {slug} — neither an app 'Connect YouTube' integration "
            f"(user_integrations) nor a local token.\n"
            f"Either have the client connect in the app, or run: "
            f"python3 scripts/video_maker.py auth --slug {slug}"
        )
    token_data = json.loads(token_path.read_text())
    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=YOUTUBE_SCOPES,
    )
    if not creds.valid:
        creds.refresh(Request())
        token_data["token"] = creds.token
        token_path.write_text(json.dumps(token_data, indent=2))
    return creds


def cmd_auth(slug: str, console: bool = False) -> int:
    """One-time OAuth flow to authorise a YouTube channel for a client.

    Agency workflow (recommended): have the client add contact@restorationai.io
    as a YouTube Channel Manager (YouTube Studio → Settings → Permissions → Invite),
    then run this command and log in as contact@restorationai.io. No client password
    needed; the token is stored locally on this machine.

    Remote workflow (--console): prints an auth URL. Paste it to the client, they
    visit it, paste the resulting code back. Use this when screen-sharing is not possible.
    """
    if not YOUTUBE_OAUTH_CLIENT_PATH.exists():
        die(
            f"OAuth client secret not found at {YOUTUBE_OAUTH_CLIENT_PATH}.\n\n"
            "To create one:\n"
            "  1. Go to console.cloud.google.com → APIs & Services → Credentials\n"
            "  2. Create Credentials → OAuth 2.0 Client ID → Desktop app\n"
            "  3. Download the JSON and save it to rank-ai/.youtube-oauth-client.json\n"
            "  4. Enable YouTube Data API v3 in the same project\n"
            "  5. Add contact@restorationai.io as a test user on the OAuth consent screen\n"
            "     (only needed while the app is in 'Testing' mode, i.e. <100 users)"
        )
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        die("Missing google-auth-oauthlib. Run: pip install google-auth-oauthlib")

    print(f"==> YouTube OAuth for client: {slug}")

    flow = InstalledAppFlow.from_client_secrets_file(
        str(YOUTUBE_OAUTH_CLIENT_PATH), scopes=YOUTUBE_SCOPES
    )

    if console:
        # Print URL — client (or you) visits it, pastes back the code
        flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
        auth_url, _ = flow.authorization_url(prompt="consent")
        print("\n  Visit this URL in any browser (you can send it to the client):")
        print(f"\n  {auth_url}\n")
        print("  After authorising, Google will show a code. Paste it here:")
        code = input("  Code: ").strip()
        flow.fetch_token(code=code)
        creds = flow.credentials
    else:
        print("    Opening browser. Log in as the YouTube channel owner")
        print("    (or contact@restorationai.io if they added you as channel manager).")
        creds = flow.run_local_server(port=0)

    client_config = json.loads(YOUTUBE_OAUTH_CLIENT_PATH.read_text())
    installed = client_config.get("installed") or client_config.get("web", {})

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "client_id": installed.get("client_id"),
        "client_secret": installed.get("client_secret"),
        "scopes": list(creds.scopes or YOUTUBE_SCOPES),
    }
    token_path = youtube_token_path(slug)
    token_path.write_text(json.dumps(token_data, indent=2))
    print(f"\n    Token saved to {token_path}")
    print("    YouTube auth complete. Run `make` to create your first video.")
    return 0


# ---------------------------------------------------------------------------
# Step 7 — YouTube upload
# ---------------------------------------------------------------------------


def _sanitize_tags(tags: list | None) -> list[str]:
    """YouTube rejects the ENTIRE upload over one bad tag (invalidTags, three
    uploads failed 2026-07-31): angle brackets are forbidden, single tags cap
    at ~100 chars, and the combined budget is ~500 (multi-word tags cost +2
    for implicit quotes). Clamp to a safe 450 so LLM-generated tag lists can
    never sink a video again."""
    out: list[str] = []
    total = 0
    for t in tags or []:
        t = re.sub(r"[<>]", "", str(t)).strip()[:80]
        if not t:
            continue
        cost = len(t) + (2 if " " in t else 0)
        if total + cost > 450:
            break
        out.append(t)
        total += cost
    return out


def upload_to_youtube(
    slug: str,
    video_path: Path,
    thumbnail_path: Path | None,
    srt_path: Path,
    metadata: dict,
    privacy: str = "unlisted",
) -> str:
    """Upload video + thumbnail + captions. Returns video_id."""
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        die("Missing google-api-python-client. Run: pip install google-api-python-client")

    creds = load_youtube_credentials(slug)
    youtube = build("youtube", "v3", credentials=creds)

    # Upload video
    print("  [youtube] uploading video...")
    body = {
        "snippet": {
            "title": metadata["youtube_title"],
            "description": metadata["youtube_description"],
            "tags": _sanitize_tags(metadata.get("tags", [])),
            "categoryId": YOUTUBE_CATEGORY_HOWTO,
        },
        "status": {"privacyStatus": privacy},
    }
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"    Uploading... {pct}%", end="\r")
    print()

    video_id = response["id"]
    print(f"  [youtube] video uploaded: https://youtu.be/{video_id}")

    # Upload thumbnail — non-fatal: channels without phone verification cannot set
    # custom thumbnails (403 youtube.thumbnail/forbidden). The video is already up,
    # so a channel-level restriction must not kill the run.
    if thumbnail_path and thumbnail_path.exists():
        print("  [youtube] uploading thumbnail...")
        try:
            media_thumb = MediaFileUpload(str(thumbnail_path), mimetype="image/png")
            youtube.thumbnails().set(videoId=video_id, media_body=media_thumb).execute()
        except Exception as exc:
            print(f"  [youtube] thumbnail skipped: {str(exc)[:160]}")
            print("            (channel likely needs phone verification at "
                  "youtube.com/verify to allow custom thumbnails)")

    # Upload captions — non-fatal for the same reason.
    if srt_path and srt_path.exists():
        print("  [youtube] uploading captions...")
        try:
            caption_body = {
                "snippet": {
                    "videoId": video_id,
                    "language": "en",
                    "name": "English",
                    "isDraft": False,
                }
            }
            media_cap = MediaFileUpload(str(srt_path), mimetype="text/plain")
            youtube.captions().insert(
                part="snippet", body=caption_body, media_body=media_cap
            ).execute()
        except Exception as exc:
            print(f"  [youtube] captions skipped: {str(exc)[:160]}")

    return video_id


# ---------------------------------------------------------------------------
# Step 8 — Commit
# ---------------------------------------------------------------------------


def commit_video_update(slug: str, post_slug: str, youtube_id: str) -> None:
    result = subprocess.run(
        ["git", "add",
         f"sites/{slug}/src/content/blog/{post_slug}.md"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  [git] warning: could not stage post file: {result.stderr[:200]}")
        return

    msg = (
        f"video: add youtube_id to {slug}/{post_slug}\n\n"
        f"System 5 uploaded https://youtu.be/{youtube_id}\n"
        f"Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
    )
    result = subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"  [git] committed youtube_id update")
    else:
        print(f"  [git] commit skipped (nothing new or already committed)")


# ---------------------------------------------------------------------------
# Main: make-video
# ---------------------------------------------------------------------------


def cmd_make(args) -> int:
    slug = args.slug
    post_slug = args.post
    model = GEMINI_FLASH_MODEL if args.flash else GEMINI_PRO_MODEL
    tts = args.tts
    set_orientation(getattr(args, "vertical", False))

    client = load_client(slug)
    # --public overrides; otherwise the client record's video_publish_mode
    # (default PUBLIC — Santino 2026-07-15: no more unlisted-until-reviewed
    # gate; set video_publish_mode: unlisted per client only to stay dark).
    privacy = "public" if args.public else video_publish_mode(client)
    post = load_post(slug, post_slug)

    print(f"\n==> System 5: Video for {client.get('display_name', slug)}")
    print(f"    Post:   {post['frontmatter'].get('title', post_slug)}")
    print(f"    Model:  {model}")
    print(f"    TTS:    {tts}")
    print(f"    Upload: {'no' if args.no_upload else privacy}")

    with tempfile.TemporaryDirectory(prefix=f"rankai-video-{slug}-") as tmp:
        work_dir = Path(tmp)

        # Step 1 — script
        print("\n[1/6] Generating video script via Claude...")
        script = generate_video_script(post, client)
        scenes = script["scenes"]
        if len(scenes) != 10:
            print(f"  warning: Claude returned {len(scenes)} scenes (expected 10), adjusting...")
        claude_usage = script.pop("_usage", {})
        # Operator overrides (pilot / manual runs)
        if getattr(args, "title", None):
            script["youtube_title"] = args.title
        if getattr(args, "description_file", None):
            script["youtube_description"] = Path(args.description_file).read_text().strip()
        (work_dir / "script.json").write_text(json.dumps(script, indent=2))
        print(f"  YouTube title: {script['youtube_title'][:60]}")

        # Step 2 — TTS
        print("\n[2/6] Synthesising narration...")
        narration = " ".join(s["narration"] for s in scenes)
        audio_path = work_dir / "narration.mp3"
        synthesise_speech(narration, audio_path, tts=tts)
        audio_duration = get_audio_duration(audio_path)
        print(f"  Audio: {audio_duration:.1f}s ({len(narration)} chars)")

        # Inject chapter timestamps into YouTube description now that we know audio_duration
        chapters = format_chapter_timestamps(scenes, audio_duration)
        script["youtube_description"] = (
            script.get("youtube_description", "") + "\n\n" + chapters
        )

        # Step 3 — scene clips (post stills → client photos → Gemini AI)
        scene_duration = audio_duration / len(scenes)
        post_stills = collect_post_stills(slug, post)
        if post_stills:
            print(f"  Post stills: {', '.join(p.name for p in post_stills)}")
        print(f"\n[3/6] Building scene clips ({len(scenes)} scenes x {scene_duration:.1f}s)...")
        clip_paths = generate_scene_clips(
            scenes, work_dir, model, slug, scene_duration,
            post_stills=post_stills,
            max_ai_images=getattr(args, "max_ai_images", None),
        )

        # thumbnail: deterministic branded template (same client background,
        # per-video text) — replaced the Gemini one-off 2026-07-23
        thumb_path = build_branded_thumbnail(
            slug, _title_thumb_lines(script.get("youtube_title") or post_slug.replace("-", " ")),
            work_dir)

        # Step 4 — FFmpeg assembly
        print("\n[4/6] Assembling video with FFmpeg...")
        video_path = work_dir / f"{post_slug}.mp4"
        assemble_video(clip_paths, audio_path, video_path, work_dir)
        size_mb = video_path.stat().st_size / 1_000_000
        print(f"  Video: {video_path.name} ({size_mb:.1f} MB)")

        # Step 5 — SRT captions
        srt_path = work_dir / f"{post_slug}.srt"
        generate_srt(scenes, audio_duration, srt_path)

        # Cost log (rough estimate; same JSONL as build_site renders)
        n_ai = len(list(work_dir.glob("scene_*.png"))) + 1  # + thumbnail
        log_video_cost(slug, f"/video/{post_slug}", model, claude_usage,
                       ai_images=n_ai, tts_chars=len(narration))

        if args.no_upload:
            out_video = REPO_ROOT / "sites" / slug / f"{post_slug}-draft.mp4"
            shutil.copy(video_path, out_video)
            print(f"\n==> Draft saved (no upload): {out_video}")
            return 0

        # Step 6 — YouTube upload
        print("\n[5/6] Uploading to YouTube...")
        video_id = upload_to_youtube(
            slug, video_path, thumb_path, srt_path, script, privacy=privacy
        )
        record_video(
            slug, video_id, script.get("youtube_title", ""), privacy, "blog",
            post_slug=post_slug,
            published_at=now_iso() if privacy == "public" else None,
        )

        if getattr(args, "defer_writeback", False):
            # Pilot / unlisted-first flow: leave the post untouched. Run
            # `video_maker.py publish --slug {slug} --post {post} --video-id {id}`
            # after operator review to flip public + write the embed.
            print(f"\n[6/6] Write-back DEFERRED (--defer-writeback).")
            print(f"  Review: https://youtu.be/{video_id}  (privacy: {privacy})")
            print(f"  Then:   python3 scripts/video_maker.py publish --slug {slug} "
                  f"--post {post_slug} --video-id {video_id}")
            return 0

        # Step 7 — update frontmatter + append transcript
        print("\n[6/6] Updating blog post frontmatter...")
        update_post_youtube_id(post["path"], video_id, transcript=narration)
        commit_video_update(slug, post_slug, video_id)

    # Deploy the frontmatter update
    if not args.no_deploy:
        print("\nDeploying updated post...")
        subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "build_site.py"),
             "sync-deploy", "--slug", slug, "--branch", "main", "--allow-dirty"],
            cwd=str(REPO_ROOT),
        )

    domain = client.get("domain", "")
    print(f"""
==> System 5 complete

  YouTube:   https://youtu.be/{video_id}
  Privacy:   {privacy}
  Blog post: https://{domain}/blog/{post_slug}/
  Embed:     Will show on the live post after Cloudflare build (~60s)

Next: If this is your first video for {slug}, set up the channel's channel art
and verify the upload looks correct before setting to public.
""")
    return 0


def cmd_brand(args) -> int:
    """Generate a Merchynt-style BRAND-AUTHORITY video (company/service/location overview).

    Not tied to a blog post. Logo intro -> per-service scenes (client photos / AI images
    with short service captions) -> CTA outro. Landscape by default; --vertical for GBP/Shorts."""
    slug = args.slug
    model = GEMINI_FLASH_MODEL if args.flash else GEMINI_PRO_MODEL
    tts = args.tts
    privacy = "public" if args.public else "unlisted"
    set_orientation(getattr(args, "vertical", False))
    client = load_client(slug)

    focus = " · ".join(filter(None, [args.service, args.city])) or "company overview"
    print(f"\n==> System 5 (brand-authority): {client.get('display_name', slug)} — {focus}")
    print(f"    Orientation: {'vertical 9:16' if args.vertical else 'landscape 16:9'} | "
          f"Upload: {'no' if args.no_upload else privacy}")

    INTRO, OUTRO = 2.0, 2.8  # silent branded bookend durations (seconds)

    with tempfile.TemporaryDirectory(prefix=f"rankai-brand-{slug}-") as tmp:
        work_dir = Path(tmp)

        print("\n[1/5] Generating brand script via Claude...")
        script = generate_brand_script(client, service=args.service, city=args.city)
        scenes = script["scenes"]
        (work_dir / "script.json").write_text(json.dumps(script, indent=2))
        print(f"  scenes: {len(scenes)} | title: {script.get('youtube_title','')[:55]}")

        print("\n[2/5] Synthesising narration...")
        narration = " ".join(s["narration"] for s in scenes)
        raw_audio = work_dir / "narration_raw.mp3"
        synthesise_speech(narration, raw_audio, tts=tts)
        narr_dur = get_audio_duration(raw_audio)
        # Pad with silence so the audio spans intro + scenes + outro cards
        audio_path = work_dir / "narration.mp3"
        total_dur = INTRO + narr_dur + OUTRO
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(raw_audio),
            "-af", f"adelay={int(INTRO*1000)}:all=1,apad=pad_dur={OUTRO}",
            "-t", f"{total_dur:.3f}", "-c:a", "libmp3lame", "-b:a", "128k", str(audio_path),
        ], check=True)
        print(f"  narration {narr_dur:.1f}s -> padded {total_dur:.1f}s")

        print("\n[3/5] Building clips (logo intro + scenes + CTA outro)...")
        scene_duration = narr_dur / len(scenes)
        scene_clips = generate_scene_clips(scenes, work_dir, model, slug, scene_duration)
        intro_clip = work_dir / "clip_intro.mp4"
        outro_clip = work_dir / "clip_outro.mp4"
        build_still_clip(build_brand_card(slug, "intro", work_dir), intro_clip, INTRO, "in")
        build_still_clip(build_brand_card(slug, "outro", work_dir), outro_clip, OUTRO, "out")
        clip_paths = [intro_clip] + scene_clips + [outro_clip]

        print("\n[4/5] Assembling...")
        out_name = "brand-" + "-".join(filter(None, [
            (args.service or "company"),
            (args.city.lower().replace(", ", "-").replace(" ", "-") if args.city else ""),
        ]))
        video_path = work_dir / f"{out_name}.mp4"
        assemble_video(clip_paths, audio_path, video_path, work_dir)
        thumb_path = generate_thumbnail(
            script.get("thumbnail_prompt") or scenes[0].get("image_prompt", ""), work_dir, model)
        print(f"  video: {video_path.stat().st_size/1e6:.1f} MB")

        if args.no_upload:
            dest = REPO_ROOT / "sites" / slug / f"{out_name}-draft.mp4"
            shutil.copy(video_path, dest)
            print(f"\n==> Brand video saved (no upload): {dest}")
            return 0

        print("\n[5/5] Uploading to YouTube...")
        srt_path = work_dir / f"{out_name}.srt"  # not created -> upload skips captions (burned-in labels suffice)
        video_id = upload_to_youtube(slug, video_path, thumb_path, srt_path, script, privacy=privacy)
        print(f"\n==> Brand video: https://youtu.be/{video_id}  ({privacy})")
    return 0


GEO_SCRIPT_PROMPT = """You are writing a 45-60 second STANDALONE local-SEO YouTube video script for a home
restoration company. It is NOT tied to a blog post. It is a Merchynt-style local ranker: direct answer
opener, a few proof points, strong call-to-action. Its transcript is indexed by Google, so the company
name, the city, and the service name must each appear multiple times.

Company: {company}
Phone: {phone}
Service: {service}
City: {city}
Proof points (these are the ONLY factual claims you may make about the company — do NOT invent
ratings, review counts, response times, years in business, licenses, or certifications not listed):
{proof_points}
Available client photo categories (prefer these for scene_type=client_photo): {photo_categories}

STRUCTURE (5-6 scenes, one sentence each, 12-25 words per sentence):
1. Direct-answer opener that begins with the pattern: "Need {service} in {city}? {company}..." —
   answer the search immediately.
2-4. One beat per proof point above, woven naturally (name the company/city/service again where natural).
5. Strong CTA: call now, free estimate, and say the phone number clearly.

LENGTH IS CRITICAL: total narration across all scenes must be 110-140 words (~45-55 seconds spoken).

Produce a JSON object with these exact keys:
{{
  "scenes": [
    {{
      "scene_type": "client_photo" | "ai",
      "narration": "the spoken sentence for this segment",
      "caption": "SHORT on-screen label (3-6 words, e.g. 'Serving {city} 24/7')",
      "photo_keywords": ["team","truck",...],
      "image_prompt": "for ai scenes: photoreal {aspect} scene, NO on-screen text, NO visible faces"
    }}
  ],
  "thumbnail_prompt": "Gemini prompt: bold local-service thumbnail, left third clear for text overlay"
}}

Do NOT include youtube_title / description / tags — the caller sets those deterministically.
Respond with ONLY valid JSON. No prose before or after.
"""


def geo_proof_points(slug: str) -> list[str]:
    """Claims-gated proof points from brand truth fields only (plan-input.json,
    cross-checked with clients/{slug}/claims-lint.json truth block when present)."""
    brand: dict = {}
    try:
        brand = json.loads((CLIENTS_DIR / slug / "plan-input.json").read_text()).get("brand", {})
    except Exception:
        pass
    truth: dict = {}
    try:
        truth = json.loads((CLIENTS_DIR / slug / "claims-lint.json").read_text()).get("truth", {})
    except Exception:
        pass

    pts: list[str] = []
    hours = brand.get("hours", "") or truth.get("hours", "")
    if truth.get("is_247") or "24/7" in hours or "24 hours" in hours.lower():
        pts.append("24/7 emergency response — crews answer day and night")
    certs = brand.get("certifications") or truth.get("certifications") or []
    if certs:
        pts.append(f"{certs[0]} technicians")
    lic_nums = brand.get("license_numbers") or truth.get("license_numbers") or []
    if lic_nums:
        pts.append(f"Licensed (License #{lic_nums[0]}) and insured")
    elif brand.get("licensed_insured_attested"):
        pts.append("Licensed and insured")
    if truth.get("response_minutes"):
        pts.append(f"~{truth['response_minutes']}-minute average on-site response")
    rating, reviews = brand.get("rating"), brand.get("review_count") or truth.get("gbp_review_count")
    if rating and reviews:
        pts.append(f"Rated {rating} stars across {reviews} Google reviews")
    if brand.get("insurance_billing"):
        pts.append("Direct insurance billing — we work with your adjuster")
    founded = brand.get("founded_year") or truth.get("founded_year")
    if founded:
        pts.append(f"Serving the area since {founded}")
    return pts[:3]


def generate_geo_script(client: dict, service: str, city: str,
                        proof_points: list[str]) -> dict:
    """Claude → geo local-ranker script. Narration only; metadata is set by cmd_geo."""
    api_key = require_env("ANTHROPIC_API_KEY")
    phone = ""
    try:
        phone = json.loads((CLIENTS_DIR / client["slug"] / "plan-input.json").read_text()) \
            .get("brand", {}).get("phone", "")
    except Exception:
        pass
    photos_map = load_client_photos(client["slug"])
    photo_categories = ", ".join(sorted(photos_map)) if photos_map else "None — use ai scenes"
    prompt = GEO_SCRIPT_PROMPT.format(
        company=client.get("display_name", ""),
        phone=phone,
        service=service.replace("-", " "),
        city=city,
        proof_points="\n".join(f"- {p}" for p in proof_points) or "- (none available — stick to service + city + phone)",
        photo_categories=photo_categories,
        aspect=GEMINI_ASPECT,
    )
    body = json.dumps({
        "model": ANTHROPIC_MODEL, "max_tokens": 4000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(ANTHROPIC_API, data=body, method="POST", headers={
        "content-type": "application/json", "x-api-key": api_key,
        "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode())
    raw = payload["content"][0]["text"].strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    script = parse_script_json(raw)
    script["_usage"] = payload.get("usage", {})
    return script


def _area_url_slug(city: str, state: str) -> str:
    return f"{city.lower().replace(' ', '-')}-{state.lower()}"


def geo_metadata(client: dict, service: str, city: str,
                 proof_points: list[str]) -> dict:
    """Deterministic (non-LLM) title / description / tags for a geo video.
    Title: '{Service} {City} | {Brand}'. Description: NAP + service-area links + phone."""
    slug = client["slug"]
    brand = client.get("display_name", slug)
    domain = client.get("domain", "")
    plan: dict = {}
    try:
        plan = json.loads((CLIENTS_DIR / slug / "plan-input.json").read_text())
    except Exception:
        pass
    b = plan.get("brand", {})
    phone, hours = b.get("phone", ""), b.get("hours", "")
    areas = plan.get("service_areas", [])
    svc_pretty = service.replace("-", " ").title()

    title = f"{svc_pretty} {city} | {brand}"

    # Target city first, then the rest of the service area
    ordered = sorted(areas, key=lambda a: 0 if a.get("city") == city else 1)
    area_lines = [
        f"{a['city']}, {a['state']}: https://{domain}/service-areas/{_area_url_slug(a['city'], a['state'])}/"
        for a in ordered[:8]
    ]
    city_names = ", ".join(a["city"] for a in ordered)

    # Pre-launch / siteless clients get their Google listing instead of dead
    # site links (day-one videos, 2026-07-23).
    site_live = bool(client.get("cut_over_at")
                     or (client.get("apex_cutover") or {}).get("completed_at"))
    maps_link = ("https://www.google.com/maps/place/?q=place_id:" + b["place_id"]
                 if b.get("place_id") else "")

    desc_parts = [
        f"Need {svc_pretty.lower()} in {city}? {brand} serves {city} and the surrounding area"
        + (f" — {hours}." if hours else "."),
    ]
    if proof_points:
        desc_parts.append("\n".join(f"• {p}" for p in proof_points))
    desc_parts.append(f"Call {brand} now: {phone}")
    if site_live:
        desc_parts.append(
            f"{brand}\nPhone: {phone}\nWebsite: https://{domain}/\nServing: {city_names}"
        )
        desc_parts.append("Service areas:\n" + "\n".join(area_lines))
    else:
        desc_parts.append(
            f"{brand}\nPhone: {phone}"
            + (f"\nFind us on Google: {maps_link}" if maps_link else "")
            + f"\nServing: {city_names}"
        )
    description = "\n\n".join(desc_parts)

    svc_lower = svc_pretty.lower()
    tags = [brand, svc_lower, f"{svc_lower} {city}", f"{svc_lower} near me", city]
    for a in ordered[1:]:
        cand = f"{svc_lower} {a['city']}"
        if sum(len(t) for t in tags) + len(cand) > 420:  # YouTube ~500-char tag budget
            break
        tags.append(cand)

    return {"youtube_title": title, "youtube_description": description, "tags": tags}


def cmd_geo(args) -> int:
    """Merchynt-style standalone local ranker: '{Service} {City}' video not tied to a
    blog post. Claims-gated narration (truth fields only), deterministic metadata."""
    slug, service, city = args.slug, args.service, args.city
    model = GEMINI_FLASH_MODEL if args.flash else GEMINI_PRO_MODEL
    set_orientation(getattr(args, "vertical", False))
    client = load_client(slug)
    # --public overrides; otherwise the client record's video_publish_mode
    # (default PUBLIC — Santino 2026-07-15: no more unlisted-until-reviewed
    # gate; set video_publish_mode: unlisted per client only to stay dark).
    privacy = "public" if args.public else video_publish_mode(client)

    plan_services = []
    try:
        plan_services = json.loads(
            (CLIENTS_DIR / slug / "plan-input.json").read_text()).get("services", [])
    except Exception:
        pass
    if plan_services and service not in plan_services:
        print(f"  warning: '{service}' not in plan services {plan_services}")

    proof = geo_proof_points(slug)
    meta = geo_metadata(client, service, city, proof)
    print(f"\n==> System 5 (geo): {client.get('display_name', slug)} — "
          f"{service.replace('-', ' ')} in {city}")
    print(f"    Title: {meta['youtube_title']}")
    print(f"    Proof points (claims-gated): {proof or 'none'}")
    print(f"    Upload: {'no' if args.no_upload else privacy}")

    INTRO, OUTRO = 2.0, 2.8  # silent branded bookends (logo card / CTA card)

    with tempfile.TemporaryDirectory(prefix=f"rankai-geo-{slug}-") as tmp:
        work_dir = Path(tmp)

        print("\n[1/5] Generating geo script via Claude...")
        script = generate_geo_script(client, service, city, proof)
        claude_usage = script.pop("_usage", {})
        scenes = script["scenes"]
        script.update(meta)  # deterministic title/description/tags win
        (work_dir / "script.json").write_text(json.dumps(script, indent=2))
        narration = " ".join(s["narration"] for s in scenes)
        print(f"  scenes: {len(scenes)} | narration: {len(narration.split())} words")

        print("\n[2/5] Synthesising narration...")
        raw_audio = work_dir / "narration_raw.mp3"
        synthesise_speech(narration, raw_audio, tts=args.tts)
        narr_dur = get_audio_duration(raw_audio)
        audio_path = work_dir / "narration.mp3"
        total_dur = INTRO + narr_dur + OUTRO
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(raw_audio),
            "-af", f"adelay={int(INTRO*1000)}:all=1,apad=pad_dur={OUTRO}",
            "-t", f"{total_dur:.3f}", "-c:a", "libmp3lame", "-b:a", "128k", str(audio_path),
        ], check=True)
        print(f"  narration {narr_dur:.1f}s -> padded {total_dur:.1f}s")

        print("\n[3/5] Building clips (logo intro + scenes + CTA outro)...")
        pub = SITES_DIR / slug / "public"
        stills = [p for p in (pub / "services" / f"{service}.webp",
                              pub / "images" / "hero-bg.webp",
                              pub / "images" / "team.webp") if p.exists()]
        scene_duration = narr_dur / len(scenes)
        scene_clips = generate_scene_clips(
            scenes, work_dir, model, slug, scene_duration,
            post_stills=stills, max_ai_images=getattr(args, "max_ai_images", None))
        intro_clip = work_dir / "clip_intro.mp4"
        outro_clip = work_dir / "clip_outro.mp4"
        build_still_clip(build_brand_card(slug, "intro", work_dir), intro_clip, INTRO, "in")
        build_still_clip(build_brand_card(slug, "outro", work_dir), outro_clip, OUTRO, "out")
        clip_paths = [intro_clip] + scene_clips + [outro_clip]

        print("\n[4/5] Assembling...")
        city_slug = city.lower().replace(",", "").replace(" ", "-")
        out_name = f"geo-{service}-{city_slug}"
        video_path = work_dir / f"{out_name}.mp4"
        assemble_video(clip_paths, audio_path, video_path, work_dir)
        thumb_path = build_branded_thumbnail(
            slug, _title_thumb_lines(service.replace("-", " "))[:2] + [city.upper()],
            work_dir)
        srt_path = work_dir / f"{out_name}.srt"
        generate_srt(scenes, narr_dur, srt_path)
        print(f"  video: {video_path.stat().st_size/1e6:.1f} MB")

        n_ai = len(list(work_dir.glob("scene_*.png"))) + 1  # + thumbnail
        log_video_cost(slug, f"/video/{out_name}", model, claude_usage,
                       ai_images=n_ai, tts_chars=len(narration))

        if args.no_upload:
            dest = REPO_ROOT / "sites" / slug / f"{out_name}-draft.mp4"
            shutil.copy(video_path, dest)
            print(f"\n==> Geo video saved (no upload): {dest}")
            return 0

        print("\n[5/5] Uploading to YouTube...")
        video_id = upload_to_youtube(slug, video_path, thumb_path, srt_path,
                                     script, privacy=privacy)
        record_video(
            slug, video_id, script.get("youtube_title", ""), privacy, "geo",
            service=service, city=city,
            published_at=now_iso() if privacy == "public" else None,
        )
        # register for the on-page embed (service-area-service pages read
        # src/data/geo-videos.json; goes live with the site's next deploy)
        try:
            plan = json.loads((CLIENTS_DIR / slug / "plan-input.json").read_text())
            area = next((a for a in plan.get("service_areas", [])
                         if a.get("city", "").lower() == city.lower()), None)
            if area and privacy == "public":
                data_p = SITES_DIR / slug / "src" / "data" / "geo-videos.json"
                data_p.parent.mkdir(exist_ok=True)
                m = json.loads(data_p.read_text()) if data_p.exists() else {}
                m[f"{service}|{area['slug']}"] = video_id
                data_p.write_text(json.dumps(m, indent=1) + "\n")
                print(f"  [embed] registered {service}|{area['slug']} -> page embed on next deploy")
        except Exception as e:
            print(f"  [embed] mapping skipped: {str(e)[:100]}")
        print(f"\n==> Geo video: https://youtu.be/{video_id}  ({privacy})")
    return 0


def cmd_publish(args) -> int:
    """Close the loop on a reviewed video: flip it PUBLIC on YouTube, write
    youtube_id into the post frontmatter + content-queue item, commit, deploy."""
    slug, post_slug = args.slug, args.post
    client = load_client(slug)
    post = load_post(slug, post_slug)
    video_id = args.video_id or post["frontmatter"].get("youtube_id")
    if not video_id:
        die("No --video-id given and the post frontmatter has no youtube_id.")

    print(f"\n==> Publish: {client.get('display_name', slug)} / {post_slug} "
          f"-> https://youtu.be/{video_id}")

    # 1. Flip the video public
    try:
        from googleapiclient.discovery import build
    except ImportError:
        die("Missing google-api-python-client. Run: pip install google-api-python-client")
    creds = load_youtube_credentials(slug)
    youtube = build("youtube", "v3", credentials=creds)
    youtube.videos().update(
        part="status",
        body={"id": video_id, "status": {"privacyStatus": "public"}},
    ).execute()
    print("  [youtube] privacy -> public")
    record_video(
        slug, video_id, post["frontmatter"].get("title", post_slug), "public",
        "blog", post_slug=post_slug, published_at=now_iso(),
    )

    # 2. Frontmatter write-back (idempotent)
    update_post_youtube_id(post["path"], video_id, transcript=args.transcript or None)
    print(f"  [post] youtube_id written to {post['path'].relative_to(REPO_ROOT)}")

    # 3. Queue item write-back
    if mark_queue_video(slug, post_slug, video_id):
        print("  [queue] content-queue item stamped with youtube_id")
    else:
        print("  [queue] no matching content-queue item (ok for seeded posts)")

    # 4. Commit post + queue
    subprocess.run(
        ["git", "add", f"sites/{slug}/src/content/blog/{post_slug}.md",
         f"clients/{slug}/content-queue.json"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    msg = (
        f"video: publish youtube_id for {slug}/{post_slug}\n\n"
        f"System 5 video flipped public: https://youtu.be/{video_id}\n"
        f"Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
    )
    r = subprocess.run(["git", "commit", "-m", msg], cwd=str(REPO_ROOT),
                       capture_output=True, text=True)
    print("  [git] committed" if r.returncode == 0
          else "  [git] commit skipped (nothing new)")

    # 5. Deploy so the embed goes live
    if not args.no_deploy:
        print("  Deploying updated post...")
        subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "build_site.py"),
             "sync-deploy", "--slug", slug, "--branch", "main", "--allow-dirty"],
            cwd=str(REPO_ROOT),
        )
    print(f"\n==> Published. https://youtu.be/{video_id} is public; embed live after build.")
    return 0


def cmd_list(slug: str) -> int:
    """List uploaded videos for a client's YouTube channel."""
    try:
        from googleapiclient.discovery import build
    except ImportError:
        die("Missing google-api-python-client. Run: pip install google-api-python-client")

    creds = load_youtube_credentials(slug)
    youtube = build("youtube", "v3", credentials=creds)

    # Get the channel's uploads playlist
    channel = youtube.channels().list(part="contentDetails", mine=True).execute()
    playlist_id = channel["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    items = youtube.playlistItems().list(
        part="snippet,contentDetails", playlistId=playlist_id, maxResults=25
    ).execute()

    print(f"\nYouTube videos for {slug}:")
    print(f"{'Title':<55} {'ID':<15} {'Published':<12}")
    print("-" * 85)
    for item in items.get("items", []):
        sn = item["snippet"]
        vid_id = item["contentDetails"]["videoId"]
        pub = sn.get("publishedAt", "")[:10]
        print(f"{sn['title'][:54]:<55} {vid_id:<15} {pub}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser(prog="video_maker", description="Rank AI System 5 — Blog to YouTube")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("auth", help="One-time YouTube OAuth setup for a client channel")
    pa.add_argument("--slug", required=True)
    pa.add_argument("--console", action="store_true",
                    help="Print auth URL instead of opening browser (for remote/headless setup)")
    pa.set_defaults(func=lambda a: cmd_auth(a.slug, console=a.console))

    pm = sub.add_parser("make", help="Generate and upload a video for a blog post")
    pm.add_argument("--slug", required=True, help="Client slug")
    pm.add_argument("--post", required=True, help="Blog post slug (filename without .md)")
    pm.add_argument("--flash", action="store_true", help="Use Gemini Flash (cheaper images)")
    pm.add_argument("--tts", choices=["elevenlabs", "google", "macos"], default="elevenlabs",
                    help="TTS provider (default: elevenlabs; google uses Neural2; macos uses system `say`)")
    pm.add_argument("--no-upload", action="store_true", help="Skip YouTube upload, save draft MP4 locally")
    pm.add_argument("--no-deploy", action="store_true", help="Skip sync-deploy after frontmatter update")
    pm.add_argument("--public", action="store_true", help="Upload as public (default: unlisted)")
    pm.add_argument("--vertical", action="store_true", help="Render 9:16 (1080x1920) instead of 16:9")
    pm.add_argument("--title", help="Override the Claude-generated YouTube title")
    pm.add_argument("--description-file", help="Path to a file whose contents override the YouTube description")
    pm.add_argument("--max-ai-images", type=int, default=None,
                    help="Cap unique Gemini stills; further AI scenes reuse earlier images")
    pm.add_argument("--defer-writeback", action="store_true",
                    help="Upload but do NOT write youtube_id into the post (use `publish` after review)")
    pm.set_defaults(func=cmd_make)

    pb = sub.add_parser("brand", help="Generate a brand-authority video (company/service/location overview)")
    pb.add_argument("--slug", required=True, help="Client slug")
    pb.add_argument("--service", help="Focus on one service (slug, e.g. water-damage-restoration)")
    pb.add_argument("--city", help='Focus on one city (e.g. "Tacoma, WA")')
    pb.add_argument("--vertical", action="store_true", help="Render 9:16 (1080x1920) for GBP/Shorts")
    pb.add_argument("--flash", action="store_true", help="Use Gemini Flash (cheaper images)")
    pb.add_argument("--tts", choices=["elevenlabs", "google", "macos"], default="elevenlabs",
                    help="TTS provider (default elevenlabs)")
    pb.add_argument("--no-upload", action="store_true", help="Skip YouTube upload, save draft MP4 locally")
    pb.add_argument("--public", action="store_true", help="Upload as public (default: unlisted)")
    pb.set_defaults(func=cmd_brand)

    pg = sub.add_parser("geo", help="Standalone local-ranker video: '{Service} {City} | {Brand}' (Merchynt style)")
    pg.add_argument("--slug", required=True, help="Client slug")
    pg.add_argument("--service", required=True, help="Service slug (e.g. water-damage-restoration)")
    pg.add_argument("--city", required=True, help='City (e.g. "San Diego")')
    pg.add_argument("--vertical", action="store_true", help="Render 9:16 (1080x1920) for GBP/Shorts")
    pg.add_argument("--flash", action="store_true", help="Use Gemini Flash (cheaper images)")
    pg.add_argument("--tts", choices=["elevenlabs", "google", "macos"], default="elevenlabs",
                    help="TTS provider (default elevenlabs)")
    pg.add_argument("--max-ai-images", type=int, default=None,
                    help="Cap unique Gemini stills; further AI scenes reuse earlier images")
    pg.add_argument("--no-upload", action="store_true", help="Skip YouTube upload, save draft MP4 locally")
    pg.add_argument("--public", action="store_true", help="Upload as public (default: unlisted)")
    pg.set_defaults(func=cmd_geo)

    pp = sub.add_parser("publish", help="Flip a reviewed video public + write youtube_id into post/queue + commit")
    pp.add_argument("--slug", required=True, help="Client slug")
    pp.add_argument("--post", required=True, help="Blog post slug (filename without .md)")
    pp.add_argument("--video-id", help="YouTube video id (default: post frontmatter youtube_id)")
    pp.add_argument("--transcript", help="Optional narration transcript to write into frontmatter")
    pp.add_argument("--no-deploy", action="store_true", help="Skip sync-deploy after write-back")
    pp.set_defaults(func=cmd_publish)

    pl = sub.add_parser("list", help="List videos uploaded to a client's YouTube channel")
    pl.add_argument("--slug", required=True)
    pl.set_defaults(func=lambda a: cmd_list(a.slug))

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
