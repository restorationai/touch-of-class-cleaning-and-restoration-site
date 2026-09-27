---
name: gbp-photo-intake
description: "Public no-login photo-upload links for field crews (branded restorationai.io/gbpphotos/{slug}); feeds GBP + website"
metadata: 
  node_type: memory
  type: project
  originSessionId: acdb19a7-afd6-4946-9442-cbe973522dd1
---

Field crews upload real job photos (before/after, crew, equipment, trucks) via a **public, no-login link** they save as a phone shortcut. Built 2026-07-01, working + tested on narestco.

**Architecture:**
- **Edge function `job-photos`** (app repo, `supabase/functions/job-photos/`, deployed `--no-verify-jwt`): GET serves a mobile upload page, POST stores the image. Uses an HMAC token (payload `{k:"jobphotos", cid, name, exp}`) signed with `CONNECT_LINK_SIGNING_SECRET` (same value the connect-link flow uses). Photos land in the **`branding`** bucket at `{company_id}/job-photos/`.
- **Privacy:** the page re-draws each photo to a `<canvas>` before upload → strips EXIF/**GPS** (job photos are inside customers' homes) + any metadata. Verified on a real upload: 0 GPS tags, no EXIF, only JFIF. Also resizes to ≤2000px @ 0.85.
- **Branded URL:** Cloudflare Worker **`gbpphotos-proxy`** serves `restorationai.io/gbpphotos/{slug}` — maps slug→{cid,name} (embedded MAP), mints the token, proxies to the function. MUST force `Content-Type: text/html` for GET because **Supabase serves function HTML as text/plain** (anti-phishing on *.supabase.co) — else the browser shows raw source. Worker source versioned at `cloudflare/gbpphotos-proxy.worker.js`.

**Cloudflare gotcha (important):** there are **two CF accounts**; restorationai.io is in account `5920ebccc5be1810cc288681e1383608`. The main `CLOUDFLARE_API_TOKEN` can create **routes** but NOT deploy **Workers** (auth error); the MCP cloudflare tools default to the *other* account. **`CLOUDFLARE_R2_API_TOKEN` is the one with Workers-Scripts access** on the right account — use it to deploy Workers there.

**Not yet built (consumers):** GBP weekly photo uploader (picks new photos from the folder → GBP) and website before/after gallery. Adding a new client currently needs a 1-line Worker MAP redeploy (later: move to Workers KV or wire into onboarding). Related: [[gbp-api-access-reapplication]], [[gbp-optimizer-system]].
