---
name: site-design-color-law
description: "LAW 09-11 — dark surfaces neutral charcoal, brand color never the canvas; hero two-col grid unconditional; restoration = call-first (no hero form)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-09-19T19:22:07.252Z
---

Design laws from the DryCor color saga (2026-09-11), encoded in code the same day:

1. **Dark surfaces are neutral charcoal, never the brand color.** Brand-tinted canvases make the whole site read as one color (DryCor's petrol-blue everything). The brand hue survives only as a whisper (`_neutral_dark()` in build_site.py: hue kept, sat<=0.06, L=0.09). All three palette paths use it (nested-colors mirror, logo extraction, site+logo `_auto_palette`). Brand color lives in small doses: links, icons, logo. ONE saturated action color owns CTAs (buttons, announcement bar, mobile call bar) — red-family reads urgency best for emergency trades.
2. **Palette truth order:** client brand kit (plan-input colors) > client's live-site CSS hue histogram > logo extraction. But even a brand kit's primary never becomes the canvas (see 1).
3. **Hero: two-column grid UNCONDITIONAL** — text block keeps its left-column slot whether or not a form sits right ([[site-build-pipeline]]).
4. **Restoration category is call-first: NO estimate form in the hero** (vertical-gated via brand.vertical token; other verticals keep it).
5. Curated committed logos are truth — scaffold's bucket pull can never overwrite them (guard in build_site).

**Why:** Santino picked the neutral variant over the brand-kit petrol canvas after a side-by-side (rankai-color-preview.pages.dev throwaway).
**How to apply:** never hand-tint dark surfaces to a brand color; when a client says "too much [color]," check whether dark surfaces carry the brand hue.

**Refinement (09-19, Santino, ACS):** CTA color default = the client's BRAND primary, not red. Saw ACS's copper "24/7 Emergency Response" button and said "that should be the default for the template" — which it already is: build_site's CTA pair-resolution fills CTAs with the brand primary whenever contrast clears AA (the Jerrott Gray gold-button logic); red #dc2626 remains only the fallback for clients with NO brand colors on file. Supersedes the "red-family owns CTAs" line above for clients with a real palette.

**Refinement (same day, Santino):** NOT every site goes charcoal. A brand primary that is already dark AND muted (L<=0.22, sat<=0.50: deep navy, forest, near-black) MAY serve as the canvas — that identity survives at wall size. Only saturated or lighter primaries (DryCor petrol, sat 0.70) neutralize to charcoal. Applies to dark-theme surfaces only; light-theme sites unaffected.
