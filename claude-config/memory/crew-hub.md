---
name: crew-hub
description: "Crew hub LIVE 2026-07-17: restorationai.io/hub/{slug}/{token} — on-phone review QR, request-a-review (PARKED enrollment), photo/file links; tokens derived from CONNECT_LINK_SIGNING_SECRET; worker source now in repo workers/"
metadata:
  type: project
---

Crew hub (Igler-adoption review-ops) LIVE 2026-07-17 on the gbpphotos-proxy worker (source now versioned at rank-ai/workers/gbpphotos-proxy.js; deploy via CF REST multipart with keep_bindings=["secret_text"] — worker holds SIGNING_SECRET (value NOT in .env) + SB_SERVICE_KEY + KV UPLOAD_MAP 404d46bf0c72404495ab66d15157c499).

URL: `restorationai.io/hub/{slug}/{token}`; token = HMAC(CONNECT_LINK_SIGNING_SECRET, "hub:"+slug)[:10], printed by `scripts/upload_links_sync.py` (also syncs KV values {cid,name,hub,review_url}). Zone route restorationai.io/hub/* added with CLOUDFLARE_API_TOKEN (the R2 token lacks zone-route perms; PAGES token lacks them too).

Tiles: (1) Show Review QR — full-screen on the crew's phone (api.qrserver.com render of gbp.google_review_url; swap for inline QR lib later); (2) Request a Review — name+cell → find-or-create contacts row + review_requests row with next_send_at NULL (**PARKED by design** — send gates/sender approval decide; prevents the DryMedic-fallback hazard) tagged 'Crew Hub'; (3) Upload Job Photos → /gbpphotos/{slug}; (4) Send Us Files → /logo/{slug}.

google_review_url backfilled into all client jsons (from place_id or the app's marketing_gbp_profiles). Tested end-to-end on narestco (4 tiles, bad-token 404, POST enroll + cleanup). Hub URLs for all 9 clients: run upload_links_sync.py to print.

Related: [[checklist-jul15]] (build queue: LSA panel → multi-GBP Phase 1 are NEXT).

## Large-file uploads (2026-08-03, Greg/PuroClean 75MB brand kit)
250MB per file everywhere. Limits raised: Supabase GLOBAL fileSizeLimit + branding bucket 50MB→250MB (262144000), bucket allowed_mime_types now include zip/office/csv/postscript/fonts (zips were flat-out disallowed before). /logo/{slug} page: ≤8MB keeps the inline worker-proxied POST; bigger files call `?action=sign` (logo-upload edge fn mints createSignedUploadUrl scoped to ONE path, 2h) and the browser PUTs DIRECT to storage w/ progress bar, then `?action=complete` verifies + pins the ops row (brand-kit files → 'Brand kit uploaded — extract palette + fonts' dedupe-keyed row; land in {cid}/docs/brand-kit/). App BrandKitFields: >50MB = true TUS resumable (tus-js-client, 6MB chunks, session JWT). GOTCHA: Supabase TUS endpoint 403s signed-upload tokens — only RLS-bearing JWTs work, hence signed-URL PUT for the anonymous hub. restorationai.io zone is CF FREE = 100MB body hard cap; worker now streams (never buffers) small-path bodies. Oversize message: "That file is too big — try zipping it or sending it in parts (250MB max per file)."
