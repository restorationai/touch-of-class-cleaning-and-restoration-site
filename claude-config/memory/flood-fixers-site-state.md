---
name: flood-fixers-site-state
description: "LIVE as of 2026-07-04: apex cutover done (zone had NO web DNS records — created CNAMEs manually), GSC provisioned, IndexNow accepted, status=active, S1 queue seeded w/ 5 question-format posts. Remaining: CSLB #, GBP identity/place_id (shared-Gmail quirk), geo-grid setup."
metadata: 
  node_type: memory
  type: project
  originSessionId: acdb19a7-afd6-4946-9442-cbe973522dd1
---

**Flood Fixers site build — PAUSED 2026-06-30, resume in a couple days.** See [[flood-fixers-onboarding]] for the infra/email/DNS details.

Done: onboarded (CF zone `0e9dec42e9729ffd6424b2472144d4b4`, email preserved), planned (129 URLs, water+reconstruction × 15 San Diego cities), rendered all 129 pages, **light (white/black) theme** applied, **compact services grid promoted to the template**. Homepage fully imaged via Gemini/Nano Banana (session id `floodfixers`): AI logo (`/images/logo.webp`), branded-van hero (`/images/hero-bg.webp`), team About photo (`/images/team.webp`), 6 dramatic/distinct service card images (`/services/{slug}.webp`), branded favicon. Images served from `public/` (relative paths, work local + on Pages — NOT via R2/images.flood-fixers.com). ServicesStrip tuned to Davis-style cards + tight gap; Process connectors fixed for light bg. All committed to monorepo main.

Preview: **localhost dev via `node ./node_modules/astro/astro.js dev --port 4323 --host` from sites/flood-fixers** (the `.bin/astro` symlink is broken — use astro.js directly). Also on `staging.rankai-flood-fixers.pages.dev` (older, pre-image).

**REMAINING to launch:** push to staging (redeploy w/ images), get **CSLB license #** (CA compliance, still blank), production push, then **NS cutover** (GoDaddy NS → amos/anastasia.ns.cloudflare.com; email records already staged so mail survives). Raw images in `/tmp/ff_images/`.

Follow-up idea: bake the image flow (logo → branded hero → dramatic service images → favicon, GBP-photo-first fallback) into `build_site.py` so every client comes out imaged automatically.

**WENT LIVE 2026-07-04.** GoDaddy NS switched by Santino -> zone active -> Pages custom domains (apex+www) attached. GOTCHA that cost an hour: the mirrored zone had ONLY MX/TXT records (no A/CNAME for apex — the old site's web records never made it into mirror-dns), and Pages domain-attach does NOT create the DNS record — created proxied CNAMEs to rankai-flood-fixers.pages.dev manually. GSC sc-domain provisioned + sitemap submitted; IndexNow 202 (130 URLs); status=active (S1-S4 scheduled); first S1 run seeded 5 question-format queue items. Still needed: CSLB license number (badges conservative until then), GBP listing identity/place_id (shared-Gmail mislabel issue) -> then rank-ai-geogrid + GBP flows.

**2026-07-05: light-theme migration COMPLETE sitewide** (interior templates were still dark-on-dark: area hubs, city-service, services, blog, legal, 404, GoogleMap section — all converted to the white-hero + bg-white pattern, live-verified). Also live: fleet hero image, 4 trust badges, accent-blue CTAs, services/areas nav grids, estimate form. Remaining client data: CSLB license number, GBP identity/place_id, founded year.
