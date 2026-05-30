# System 5 — YouTube Video Pipeline: One-Time Setup

`video_maker.py` turns published blog posts into 90-second image-montage YouTube videos.

## What you need (one-time, agency-wide unless noted)

### 1. Google Cloud TTS API key

The narration voice uses Google Cloud Text-to-Speech (Neural2 voices).

1. Go to `console.cloud.google.com` → same project where Maps Embed API is enabled
2. APIs & Services → Library → search "Cloud Text-to-Speech API" → **Enable**
3. APIs & Services → Credentials → **Create Credentials → API key**
4. Edit the key → Application restrictions: **None** (server-side key, not browser-restricted)
5. API restrictions → Restrict key → select **Cloud Text-to-Speech API**
6. Copy the key → add to `rank-ai/.env`:
   ```
   GOOGLE_CLOUD_API_KEY=AIza...
   ```

Cost: ~$0.016 per 90-second video (Neural2 voice, ~225 chars per scene × 10 scenes).

**Alternative (free, no API key):** Pass `--tts macos` to use the macOS `say` command.
Lower quality but good for testing the rest of the pipeline.

### 2. YouTube OAuth client secret (agency-wide, one file)

The YouTube Data API requires OAuth 2.0 to upload to a channel.

1. Same Google Cloud project → APIs & Services → Library → search "YouTube Data API v3" → **Enable**
2. APIs & Services → Credentials → **Create Credentials → OAuth 2.0 Client ID**
3. Application type: **Desktop app**
4. Download the JSON → save to `rank-ai/.youtube-oauth-client.json`
5. APIs & Services → OAuth consent screen:
   - If app is in "Testing" mode, add each client channel's Google account as a **test user**
   - For production (>100 users), submit for verification (not needed for an agency tool with <100 users)

### 3. YouTube channel per client (one-time per client)

Each client needs their own YouTube channel. The channel owner's Google account must be
authorized once via the `auth` command.

Per-client setup:
```bash
# One-time: authorize the channel owner's Google account
python3 scripts/video_maker.py auth --slug narestco
```

This opens a browser. The client's Google account logs in and grants upload access.
The refresh token is saved to `clients/{slug}/.youtube-token.json`.

**Important:** `.youtube-token.json` files are gitignored (they contain refresh tokens).
Store them securely. If lost, re-run `auth`.

---

## Running System 5

```bash
set -a; . rank-ai/.env; set +a

# Full run (generates + uploads, defaults to unlisted)
python3 scripts/video_maker.py make --slug narestco --post what-to-do-after-a-house-fire

# Test run: skip YouTube upload, save MP4 locally
python3 scripts/video_maker.py make --slug narestco --post what-to-do-after-a-house-fire --no-upload

# Test with macOS TTS (no GOOGLE_CLOUD_API_KEY needed)
python3 scripts/video_maker.py make --slug narestco --post what-to-do-after-a-house-fire --tts macos --no-upload

# Upload as public (once you've reviewed the unlisted version)
python3 scripts/video_maker.py make --slug narestco --post what-to-do-after-a-house-fire --public

# Use Gemini Flash (cheaper, lower quality images)
python3 scripts/video_maker.py make --slug narestco --post what-to-do-after-a-house-fire --flash

# List uploaded videos
python3 scripts/video_maker.py list --slug narestco
```

## Cost per video

| Component | Cost |
|---|---|
| Anthropic Sonnet 4.6 script | ~$0.04 |
| Google Cloud TTS (Neural2) | ~$0.02 |
| Gemini Pro (10 scene images + thumbnail) | ~$0.44 |
| FFmpeg processing | free |
| YouTube upload | free |
| **Total** | **~$0.50 per video** |

Using `--flash` for images: ~$0.14 for images → **~$0.20 per video**.

## Output

The script:
1. Creates a `{post-slug}.mp4` video in a temp directory (deleted after upload)
2. Uploads to YouTube with the blog post URL in the description
3. Updates the blog post frontmatter: `youtube_id: "{video_id}"`
4. Commits + sync-deploys so an embed `<iframe>` shows on the live post

Videos are uploaded as **unlisted** by default. Review at `youtu.be/{video_id}` then
manually set to public on YouTube Studio, or re-run with `--public`.

## Workflow integration

System 5 is independent — invoke it manually after a blog post is live:
```bash
# After content_writer writes a post:
python3 scripts/video_maker.py make --slug {slug} --post {post-slug}
```

The master_scheduler.py does NOT run System 5 automatically (YouTube quota limits
and the unlisted review step make automation premature). Add it to the scheduler
once you've validated the pipeline on a few posts.

## gitignore additions

These are already in `.gitignore`:
- `.youtube-oauth-client.json`
- `clients/*/.youtube-token.json`
