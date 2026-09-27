---
name: allpro-prorestoration-site-state
description: BOTH LIVE — All Pro 07-22, ProRestoration 08-09 on prorestorationca.com (zone active, Google MX intact, apex_live set, Jack notified via Monica); Angie = preferred contact
metadata: 
  node_type: memory
  type: project
  originSessionId: b7646e8b-4a3a-42b9-809a-4dc1c55c9f5c
  modified: 2026-08-09T22:10:50.898Z
---

**Owner of BOTH companies: Jack Bispo (Lawrence Jack Bispo — two $498.50 Stripe charges 07-06). He does NOT own Flood Fixers.** Both sister-company sites fully built 2026-07-08 (commit e7f385e), client previews live during Santino's meeting:
- **all-pro-plumbing-preview.pages.dev** — 204 pages, FIRST plumbing-vertical build, light theme, round badge logo
- **prorestoration-preview.pages.dev** — 224 pages, light theme, wordmark SVG logo
Both direct-upload Cloudflare Pages projects (wrangler, use CLOUDFLARE_PAGES_API_TOKEN from rank-ai/.env — the generic token 401s on Pages API). All pages rendered (~$15 total), claims_lint 0 errors, images via nanobanana (hero-bg/team/services + responsive variants, image-meta.json manifests).

**Production cutover checklist (when clients approve):**
1. brand.ts logoUrl + all image fallbacks are LOCAL `/images/...` with `// preview: switch to images.{domain}` comments — upload brand assets to R2 and flip URLs
2. Add both slugs to scripts/resize_images.py whitelist (agents made variants manually with Pillow/cwebp)
3. scaffold `--push` / sync-deploy to real client GitHub repos + Pages projects (status still "local-only"), then NS cutover (zones pre-staged, NS pair amos/anastasia)
4. Per-service card images still shared (one services.webp per site) — style-guide tables ready for per-service generation
5. ProRestoration SPF/DKIM/DMARC post-launch

**Fixed along the way:** starter emergency.astro had invented 60-min response claims (fixed in templates/astro-starter too); All Pro emergency page was restoration copy → rewritten plumbing-correct; empty-token bugs ("since .", "in  (Without Getting Burned)") from planner when foundedYear/city token empty — planner should guard empty tokens. Blog-post renders fail ~5% with non_json (```json fences) — just re-run render, it skips completed pages.

**Known deferred:** flood-fixers components/lp/* light conversion is broken (dark text on navy/pink buttons) — both new sites kept original LP styling deliberately. MCC Restoration still held on Jeff's domain answer. Related: [[flood-fixers-site-state]], [[firedex-butler-onboarding]].


**2026-07-22 ALL PRO IS LIVE**: allproplumbingheatingandair.com cut over to CF NS (amos/anastasia) — production project rankai-all-pro-plumbing (git-connected to all-pro-plumbing-site repo), apex+www 200 w/ SSL, M365 mail records mirrored + verified from public resolvers post-flip. Hero: dual CTA + "24/7 Emergency Line". Images still local /images/ (R2 flip = optional optimization, not blocking). ProRestoration (prorestorationca.com) NOT cut over — Jack was retrieving domain access. Office contact: Angie (Office Manager, angie@prorestorationca.com, (661) 437-9345) = PREFERRED contact + concierge allowlisted; own GHL contact 4ANSPmr7AhkUG10LSzwE.
