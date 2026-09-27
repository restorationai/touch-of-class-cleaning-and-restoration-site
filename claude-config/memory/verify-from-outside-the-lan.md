---
name: verify-from-outside-the-lan
description: "Santino's LAN intercepts port-53 DNS (every server returns the same cached answer, identical counting-down TTL) — use DoH for truth; and a domain attached AFTER scaffold leaves brand.ts canonicalUrl=https://None on the LIVE site (bit go-green + crew 08-09; sync-deploy rehydrate guard exists since 08-11 but llms/ai.txt need hand-healing)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-08-20T12:28:06.008Z
---

Two verification traps confirmed 2026-08-09, both burned earlier sessions:

**1. Port-53 DNS on Santino's Mac/LAN is intercepted.** `dig @anastasia.ns.cloudflare.com`, `@amos`, `@1.1.1.1` and `@8.8.8.8` ALL returned the same stale A record with the IDENTICAL counting-down TTL — the router answers for every server. The 08-09 handoff's "stale Cloudflare-cached A record, wait for TTL" diagnosis of prorestorationca.com was this artifact; the cutover was actually live globally.
**Why:** identical TTL across "different" resolvers is the tell — independent caches never agree to the second.
**How to apply:** verify DNS via DoH (`https://dns.google/resolve?name=...` or cloudflare-dns.com), and verify HTTP with `curl --resolve domain:443:<DoH-IP>`. Never trust local dig for cutover verdicts.

**2. A domain attached after scaffold leaves the live site shipping `https://None`.** brand.ts is hydrated at scaffold time; if the client record had no domain then, canonicalUrl stays `https://None` and every canonical, og:url, schema @id, plus public/llms.txt + ai.txt (and robots before the 08-08 guard) ship it — LIVE. Bit gogreenrestorationofnc.com and crew3r.com on 08-09 (fixed a8166bbf). The scaffold-time guard added 08-08 does NOT cover the attach-domain-later path.
**2b. `astro.config.mjs` `site:` is a SECOND hydration point the a8166bbf fix missed** — crew3r.com served its entire sitemap (668 URLs) on host `https://none` for 3 days post-launch; Crew's outside SEO (Stuti) read it as "city pages not on the website." Fixed crew + go-green 08-11. Any launch check must grep BOTH brand.ts and astro.config.mjs; 7 preview-only sites still carry `https://None` in astro.config awaiting the launch-path rehydration guard.
**How to apply:** at every cutover/launch verification, grep live HTML + llms.txt for `https://None`, and check `sites/{slug}/src/lib/brand.ts` domain/canonicalUrl + `clients/{slug}.json` domain are set. UPDATE 08-20: a rehydration guard EXISTS since 08-11 — `_rehydrate_domain` in build_site.py runs at the top of every sync-deploy (any branch) and heals brand.ts/astro.config from the client record's domain. It does NOT touch `public/llms.txt`/`ai.txt` (QCI 08-20: those still carried https://None after rehydrate ran; healed by hand), and it can only help when `clients/{slug}.json` HAS a domain — record the domain the moment it's known. Also brand.ts `imagesBase: "https://images.None"` is a third None carrier (broke og:image on 32 QCI pages); fix = imagesBase "" + local public/brand/hero.webp.

Related: the llms.txt liveness probe requires body starting `#` AND containing `https://{domain}/` ([[site-build-pipeline]]); `marketing_sites.apex_live` mystery SOLVED 08-09: supabase_sync derives it from the client record's `cut_over_at` on every run (fires after each content deploy) and the four newest launches never wrote that stamp, so the sync clobbered True->False in a loop against the daily ops-sync probe. Backfilled cut_over_at for puroclean/crew/prorestoration/go-green (older launches all had it); flag is stable now. THE LAUNCH-PATH GUARD MUST WRITE domain + cut_over_at at cutover — until it exists, every new launch reintroduces the tug-of-war.
