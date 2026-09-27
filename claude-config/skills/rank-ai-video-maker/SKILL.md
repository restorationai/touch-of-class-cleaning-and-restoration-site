---
name: rank-ai-video-maker
description: System 5 in the Rank AI SEO operations layer. Converts a published blog post into a ~90-second YouTube image-montage video using Claude (script), ElevenLabs TTS (narration), client Photos + Gemini AI images (visuals — IMAGES ONLY, no stock video), an upbeat licensed music bed, FFmpeg Ken Burns + xfade (assembly), and YouTube Data API (upload). One video per invocation. Wraps rank-ai/scripts/video_maker.py. Use when the user says "make a video for {client}", "YouTube video for {post}", "run system 5", "video maker", or "turn this post into a video".
---

# Rank AI — Video Maker (System 5)

Converts a published blog post into a ~90-second YouTube image-montage video.

**Source of truth:** `rank-ai/docs/system5-setup.md`

## When to invoke

- "make a video for {client}" / "YouTube video" / "video maker"
- "turn the latest post into a video for {client}"
- "run system 5" / "rank-ai-video-maker"

## Project root

`/Users/santino/Desktop/mywebsitecode/rank-ai/` — the monorepo.

## Pre-flight

1. **Determine client slug and post slug.** Ask via `AskUserQuestion` if not provided.
   - Client must have `status: "active"` and `build_status` of `pushed_main` or `cut_over`
   - Post must exist at `sites/{slug}/src/content/blog/{post-slug}.md`
2. **Check YouTube auth:** `clients/{slug}/.youtube-token.json` must exist.
   If missing, run `auth` command first (see One-time setup below).
3. **Source env:** `set -a; . rank-ai/.env; set +a`
   Required: `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `GOOGLE_AI_API_KEY` (Gemini scene images — now primary, not a fallback), `GITHUB_PERSONAL_ACCESS_TOKEN`
   Optional: `GOOGLE_CLOUD_API_KEY` (Google TTS only if `--tts google`). `PEXELS_API_KEY` is no longer used (images-only mode, `USE_STOCK_VIDEO=False`).

## One-time setup (first time per client)

Read `rank-ai/docs/system5-setup.md` in full. Key steps:

1. **YouTube OAuth client** — reuses `rank-ai/.gsc-oauth-client.json` (same Desktop app credential as GSC,
   same Google Cloud project, client ID `936081984190-3e6p9vu7qc3r270m0r2uc4i1vn65ccno`).
   The script auto-detects `.gsc-oauth-client.json` and falls back to `.youtube-oauth-client.json`.
   YouTube Data API v3 must be enabled in the same Google Cloud project.
2. **Client must add agency as Manager** — YouTube Studio → Settings → Permissions → Invite:
   add `contact@restorationai.io` as Channel Manager (not just editor).
3. **Per-client auth** (opens browser once, saves token to `clients/{slug}/.youtube-token.json`):
   ```bash
   cd ~/Desktop/mywebsitecode/rank-ai
   set -a; . .env; set +a
   python3 scripts/video_maker.py auth --slug {slug}
   ```

## Run the video maker

Standard (uploads unlisted — review before publishing):

```bash
cd ~/Desktop/mywebsitecode/rank-ai
set -a; . .env; set +a
python3 scripts/video_maker.py make --slug {slug} --post {post-slug}
```

Test run (no upload, saves MP4 locally):

```bash
python3 scripts/video_maker.py make --slug {slug} --post {post-slug} --no-upload
```

Test with macOS TTS (free, no API key needed):

```bash
python3 scripts/video_maker.py make --slug {slug} --post {post-slug} --tts macos --no-upload
```

## Brand-authority videos (`brand` subcommand) — Merchynt/Paige style

A SECOND video type, NOT tied to a blog post: a short "who we are / where we serve / what we do / call us"
company-overview video. Structure: **logo intro card → per-service scenes (client photos + short service-label
captions) → CTA outro card** (logo + brand-red "Call {phone}" pill). Its transcript is entity/local/service
dense — that density IS the SEO/AI-citation signal. Use it for **service & service×location pages, GBP video
posts, and Shorts** (especially to rank in markets the Maps proximity penalty blocks).

```bash
# Company overview (landscape):
python3 scripts/video_maker.py brand --slug {slug} --no-upload

# Localized service×location, vertical for GBP/Shorts:
python3 scripts/video_maker.py brand --slug {slug} \
    --service water-damage-restoration --city "Tacoma, WA" --vertical --no-upload
```

- `generate_brand_script(client, service, city)` → entity/local/service-dense script (target ≤90 words / ~35s).
- `--service` / `--city` localize the hook + focus (uses `plan-input.json` service_areas + services + brand).
- Prefers real client photos (`clients/{slug}/Photos/`), AI images otherwise; captions are SHORT service labels.
- `build_brand_card(slug, "intro"|"outro", work_dir)` renders the white logo/CTA bookend cards.
- Not blog-linked: no frontmatter patch. Saves a draft with `--no-upload`, or uploads standalone.

## Vertical (9:16) output

Both `make` and `brand` accept **`--vertical`** → renders **1080×1920** (GBP posts / YouTube Shorts) instead of
the default landscape 1920×1080 (watch-page embeds). `set_orientation(vertical)` swaps `OUT_W/OUT_H` and the
Gemini aspect ratio; `assemble_video` uses actual per-clip durations so the variable-length brand cards align.

## Pipeline (as of 2026-06)

1. **Read blog post markdown** — title, body, FAQ from `sites/{slug}/src/content/blog/{post-slug}.md`
2. **Claude Sonnet 4.6 → video script** — exactly 10 scenes, each with:
   - `narration` (20-30 words; total ~225 words = ~90s at 2.5 wps)
   - `scene_type`: `"client_photo"` | `"ai"` (IMAGES ONLY — the model is told never to use `"stock"`,
     and even if it did, `USE_STOCK_VIDEO=False` routes it to a Gemini AI image)
   - `photo_keywords` (for client_photo — matches PHOTO_CATEGORIES keys)
   - `image_prompt` (for ai — detailed Gemini prompt; photoreal 16:9, NO on-screen text, NO faces
     — shoot from behind/hands-only/wide so auto-blur never triggers)
   - Plus: `youtube_title`, `youtube_description`, `tags`, `thumbnail_prompt`
3. **ElevenLabs TTS → MP3 narration** (default provider)
   - Voice: `HIGUfNOdjuWQwwapnTRW`, model: `eleven_turbo_v2_5`
   - Settings: stability=0.45, similarity_boost=0.75, style=0.0, speaker_boost=true
4. **Scene visuals — IMAGES ONLY (2-tier per scene; `USE_STOCK_VIDEO=False`):**
   - **Tier 1 — Client photos:** `clients/{slug}/Photos/` scanned by `load_client_photos(slug)`.
     `PHOTO_CATEGORIES` maps category name → filename keywords:
     `team`, `before_after`, `equipment`, `hazmat`, `truck`, `job_site`, `misc`.
     `match_client_photo(keywords, photos_map, used_set)` picks best unused photo.
   - **Tier 2 — Gemini AI image:** `gemini_generate_image(prompt, model)` → 16:9 PNG. Used for every
     scene that isn't a matched client photo. Every scene ends up a **still** with a Ken Burns zoom.
   - **Stock video (Pexels) is disabled** (`USE_STOCK_VIDEO=False` near the top of video_maker.py). The
     Pexels helpers still exist; flip the flag to `True` to re-enable the old 3-tier chain.
5. **PIL frame generation + Ken Burns** via `build_still_clip(img_path, clip_path, duration, zoom_direction, subtitle_text="")`:
   - Opens image with Pillow, resizes to 115% of output (cover), pipes raw RGB frames to FFmpeg stdin
   - Per-frame: `x = int(max_x * t)`, `y = int(max_y * t)` — integer coords, monotonically increasing, no oscillation
   - Eliminates the shaking artifact that affected the FFmpeg `crop` expression approach
   - Subtitle text drawn on every frame via `_draw_subtitle()` (white text, black outline, centered lower-third)
6. **Subtitle burn on Pexels clips** via `_burn_subtitles_on_video(clip_path, subtitle_text)`:
   - Reads frames from existing Pexels MP4 via `ffmpeg pipe:1`, draws captions with PIL, writes new MP4 via `ffmpeg pipe:0`
   - Called immediately after `download_and_trim_pexels()` succeeds in `generate_scene_clips()`
   - All 10 scenes get burned-in captions regardless of source type
7. **xfade dissolve transitions** — `XFADE_DURATION = 0.4s`
   - Offset formula: `offset[i] = i * (scene_duration - 0.4)`, where `scene_duration = audio_duration / n`
   - FFmpeg filter_complex chains all clips: `[0:v][1:v]xfade=dissolve:...[v1]; [v1][2:v]xfade=...; ...`
8. **Background music** (active by default): an upbeat licensed bed ("Raising Me Higher", Mixkit Free
   License — commercial, no attribution) is auto-mixed at -18dB (`volume=0.126`) under the narration,
   with `amix ... normalize=0` so the voiceover stays at FULL level (without it, amix halves the voice).
   File lives at `assets/background_music.mp3` (gitignored; provenance + re-fetch URL are documented next
   to `BACKGROUND_MUSIC_PATH` in video_maker.py). Swap the file to change tracks; tune `0.126` for level.
9. **SRT captions file** written from scene timing (uploaded to YouTube as a separate track)
10. **YouTube Data API v3** → upload unlisted + thumbnail + captions track
10. **Frontmatter patch** — `youtube_id: "{video_id}"` added to blog post
11. **Monorepo commit + sync-deploy** — embed appears on live post (~60s Cloudflare build)

## VideoObject schema

When `youtube_id` is present in frontmatter, the blog post page automatically emits a `VideoObject`
JSON-LD schema block alongside `BlogPosting`. This is wired in `src/pages/blog/[slug].astro`:

```astro
schema_stubs={["blog-posting", ...(data.youtube_id ? ["video-object"] : []), "faq", "breadcrumb-list"]}
schema_ctx={{ youtube_id: data.youtube_id, ... }}
```

No extra code needed after the frontmatter is patched.

## Cost per video

| Component | Cost |
|---|---|
| Claude Sonnet 4.6 script | ~$0.04 |
| ElevenLabs TTS (eleven_turbo_v2_5) | ~$0.02-0.04 |
| Gemini images (now PRIMARY — every non-client-photo scene) | ~$0.13/img Pro, ~$0.04/img Flash |
| Background music | Free (one-time licensed file) |
| **Total (Pro images, ~6-10 AI scenes)** | **~$0.50-0.80** |
| **Total (Flash images)** | **~$0.30** |

Images-only means Gemini runs on most scenes now, so cost is higher than the old Pexels-first pipeline.
Client photos are free and reduce the count — the more `clients/{slug}/Photos/`, the cheaper.
`--flash`: Gemini Flash instead of Pro (~⅓ the cost). `--tts macos`: free, use for testing.

## Flags

- `--flash` — Gemini Flash images (cheaper, lower quality)
- `--tts macos` — macOS `say` command (free, testing only)
- `--tts google` — Google Cloud TTS Neural2-D (requires `GOOGLE_CLOUD_API_KEY`)
- `--no-upload` — generate video locally, skip YouTube upload
- `--no-deploy` — skip sync-deploy after frontmatter update
- `--public` — upload as public instead of unlisted

## Key constants and functions in video_maker.py

```python
ELEVENLABS_VOICE_ID   = "HIGUfNOdjuWQwwapnTRW"
ELEVENLABS_MODEL      = "eleven_turbo_v2_5"
XFADE_DURATION        = 0.4
BACKGROUND_MUSIC_PATH = REPO_ROOT / "assets" / "background_music.mp3"
PHOTO_CATEGORIES = {
    "team":         ["team", "crew", "staff", "worker", "people", "group", "full"],
    "before_after": ["before", "after"],
    "equipment":    ["blower", "dryer", "equipment", "machine", "fan", "tool"],
    "hazmat":       ["hazmat", "suit", "protective", "gear"],
    "truck":        ["truck", "vehicle", "van"],
    "job_site":     ["job", "site", "damage", "restoration", "water", "fire", "mold"],
}
```

| Function | Purpose |
|---|---|
| `generate_video_script(post, client)` | Claude → 10-scene script dict |
| `synthesise_speech(text, path, tts="elevenlabs")` | Dispatcher |
| `synthesise_speech_elevenlabs(text, path)` | ElevenLabs REST |
| `synthesise_speech_google(text, path)` | Google Cloud TTS fallback |
| `synthesise_speech_macos(text, path)` | macOS `say` fallback |
| `load_client_photos(slug)` | Returns `{category: [Path]}` from `clients/{slug}/Photos/` |
| `match_client_photo(keywords, photos_map, used)` | Best unused photo for a scene |
| `pexels_search_video(query, min_duration)` | Pexels search → download URL |
| `download_and_trim_pexels(url, clip_path, duration)` | Download + FFmpeg trim/scale |
| `gemini_generate_image(prompt, model)` | Gemini → 16:9 PNG bytes |
| `generate_scene_clips(scenes, work_dir, model, slug, scene_duration)` | Orchestrates 3-tier per scene |
| `_load_subtitle_font()` | Loads system font (Helvetica → Arial → DejaVu → default) |
| `_wrap_text(text)` | Word-wraps to `SUBTITLE_CHARS_PER_LINE=52` chars |
| `_draw_subtitle(img, lines, font)` | Draws white text + black outline on PIL Image in-place |
| `build_still_clip(img_path, clip_path, duration, zoom_direction, subtitle_text="")` | PIL frame-pipe Ken Burns + captions — shaking fixed |
| `_burn_subtitles_on_video(clip_path, subtitle_text)` | Reads Pexels MP4, burns captions, overwrites in place |
| `assemble_video(clip_paths, audio_path, output_path, work_dir)` | xfade assembly + music mix |
| `update_post_youtube_id(post_path, youtube_id, transcript)` | Patches frontmatter + appends transcript section |

## After upload

- Videos are unlisted by default — review at `youtu.be/{video_id}` before publishing
- Set to public in YouTube Studio, or re-run with `--public`
- Blog post shows embedded player once Cloudflare builds (~60s)
- VideoObject JSON-LD schema fires automatically once `youtube_id` is in frontmatter

## State files this skill writes

| Path | Action |
|---|---|
| `sites/{slug}/src/content/blog/{post-slug}.md` | Patches `youtube_id: "{video_id}"` into frontmatter |
| Per-client GitHub repo branch | sync-deploy pushes the frontmatter update |

## Additional constants

```python
SUBTITLE_FONT_SIZE = 52           # px at 1080p
SUBTITLE_CHARS_PER_LINE = 52      # word-wrap threshold
```

## What this skill does NOT do

- Keyword research — that's `rank-ai-keyword-researcher` (System 1)
- Blog post writing — that's `rank-ai-content-writer` (System 2)
- Onsite audits — that's `rank-ai-onsite-audit` (System 3)
- GBP posts — System 6 (not yet built)
- Scheduled batch runs — add to master_scheduler.py once pipeline is validated
