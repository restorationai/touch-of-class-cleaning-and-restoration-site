# Split-Test Template — v2

A saved split-test design, owned by the `ads-landing-page` skill so it persists across sessions. Currently the primary **challenger** tested against `split-test-v1` (the pink champion).

## What this is

| | |
|---|---|
| **Version** | v2 (challenger) |
| **Style** | "Plumbera" — navy `#17235e` + golden-yellow `#f5c63b` on warm cream `#f4f1ea` |
| **Status** | CHALLENGER (tested 50/50 vs split-test-v1) |
| **File** | `LandingPage.astro` (deploy as `LpLayoutV3.astro`) |
| **Imagery** | `image-prompts.json` — 2 people-focused photos (generate per client) |

### Sections (top → bottom)
1. Floating white pill header — **wordmark** + phone (gold circle icon)
2. Bento hero — `#1 Trusted {Service} Experts` pill, large uppercase H1 (keyword), "Get Emergency Help" CTA, **stats row** (24/7 · 60-Min · {years}+), technician photo in a navy rounded card
3. About / Why us — copy + bullet list, team photo with navy badge accent
4. Testimonials — 6-card grid with initials avatars + gold stars
5. Process — 4 numbered yellow-circle cards
6. FAQ — native `<details>` accordion (no JS)
7. CTA band — "Need Fast {Service}? We're Ready 24/7!" + dual call buttons
8. Footer — working hours / contact / why-choose-us (no nav exit links)
9. Sticky mobile call bar (gold)

## Deploy into a client site
1. Copy the layout in as the `v3` variant component:
   ```bash
   cp templates/split-test-v2/LandingPage.astro \
      sites/{slug}/src/components/lp/LpLayoutV3.astro
   ```
2. Generate the 2 client photos from `image-prompts.json` (Nano Banana, model `pro`), saving to `sites/{slug}/public/images/lp/`. The hero box uses `object-top` — frame faces in the upper-center with headroom.
3. In the manifest entry set `"variant": "v3"` plus:
   ```json
   "heroImageUrl": "/images/lp/v3-hero-tech.png",
   "featureImageUrl": "/images/lp/v3-team.png"
   ```

## Requirements
- `~/styles/global.css` and `~/lib/brand` (present in every scaffolded site)
- `@lucide/astro`, Tailwind JIT (arbitrary values like `rounded-[2.5rem]`)
- Self-contained palette — does **not** use the brand `primary` token.

## Guardrails
- Hero `<h1>` MUST render the manifest `h1` (exact keyword) for Quality Score.
- **Stats must stay verifiable** (24/7, 60-Min arrival, years from `foundedYear`). Do not swap in fabricated volume numbers — Google Ads policy + trust.

## Notes
- The naming maps: code component `LpLayoutV3.astro` ↔ skill template `split-test-v2`.
- Tested against `split-test-v1` (pink). Whichever wins becomes the next champion; promote per the rotation convention in `SKILL.md`.
