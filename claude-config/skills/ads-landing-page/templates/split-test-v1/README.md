# Split-Test Champion — v1

The current best-performing ad landing page design, owned by the `ads-landing-page` skill so it persists across sessions. This is the **baseline** every new ad campaign starts from.

## What this is

| | |
|---|---|
| **Version** | v1 (first champion) |
| **Style** | "TrustedRestorationPros" — hot-pink `#f01e5a` + light gray, image-driven |
| **Status** | CHAMPION (current default for new client LPs) |
| **File** | `LandingPage.astro` |
| **Imagery** | `image-prompts.json` (generate per client via Nano Banana) |

### Sections (top → bottom)
1. White header — logo + click-to-call
2. Full-height hero (`min-h-[90vh]`) — bg photo + overlay, location pill, large H1 (keyword), subtitle, "Get Help Now" CTA, stars, 4 boxless trust icons
3. Insurance carrier strip ("Insurance May Cover 100%")
4. Feature section — photo + "Fast Restoration When Every Minute Counts" + dual CTA
5. "Support You Can Rely On" — copy + equipment photo, bullet list, second paragraph
6. "An Easy Process With Support" — 4 numbered step cards
7. Dark urgency banner
8. Closing section — restored-home bg photo, white card + location CTA
9. Footer with disclaimer
10. Scroll-triggered floating call bar (appears once the hero leaves the viewport)

## Deploy into a client site

1. Copy the layout into the site as the `v2` variant component (the `lp/[slug].astro` router renders this for manifest entries with `"variant": "v2"`):
   ```bash
   cp templates/split-test-v1/LandingPage.astro \
      sites/{slug}/src/components/lp/LpLayoutV2.astro
   ```
2. Generate the 4 client photos from `image-prompts.json` (Nano Banana, model `pro`), saving to `sites/{slug}/public/images/lp/`. Apply `niche_overrides` if the client isn't water-damage restoration.
3. In the manifest entry add the image paths:
   ```json
   "heroImageUrl": "/images/lp/hero-flood.png",
   "featureImageUrl": "/images/lp/feature-van.png",
   "supportImageUrl": "/images/lp/support-airmover.png",
   "closingImageUrl": "/images/lp/closing-restored.png"
   ```

## Requirements
- `~/styles/global.css` and `~/lib/brand` (present in every scaffolded site)
- `@lucide/astro`
- Tailwind JIT (arbitrary values like `min-h-[90vh]`, `bg-gray-950/55`)
- The layout's palette is self-contained — it does **not** use the brand `primary` token, so only brand name / phone / logo are dynamic.

## Quality Score guardrail
The hero `<h1>` MUST render the manifest `h1` (the exact keyword). Never hardcode a generic headline here — that's what keeps Landing Page Experience "Above Average."

## Rotation convention
When a new split-test winner beats this design:
1. Save the winner as `templates/split-test-v{N}/LandingPage.astro` (+ its own `image-prompts.json`, `README.md`).
2. Update the "current champion" pointer in the skill's `SKILL.md` to v{N}.
3. Keep older champions in their folders for reference / rollback.

History:
- **v1** — TrustedRestorationPros pink design. First champion (baseline).
