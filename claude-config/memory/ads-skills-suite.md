---
name: ads-skills-suite
description: Six Google Ads skills built for Rank AI restoration clients — full campaign lifecycle from scaffold to weekly maintenance
metadata: 
  node_type: memory
  type: project
  originSessionId: 21d0ec84-6cbd-44c9-9288-94a65a2b411d
---

Six `ads-*` skills built 2026-06-11, covering the full Google Ads lifecycle for water damage restoration clients. All live in `~/.claude/skills/`.

| Skill | Source file in Ads/ | Purpose | Cadence |
|-------|-------------------|---------|---------|
| `ads-campaigns` | `build-your-first-skag.md` | Scaffold SKAG campaign structure via `ads_manager.py scaffold` | Once per client |
| `ads-generate-ads` | `anatomy-of-a-good-ad.md` + `ad-assets-best-practices.md` | Generate 3 RSAs (speed/trust/value angles) + sitelinks/callouts/snippets | Once per campaign |
| `ads-landing-page` | — | Generate dedicated Astro LPs (one per service × city), `getStaticPaths()`, gclid via inline JS, Cloudflare Pages Function for form | Once per client |
| `ads-tracking` | `setup-conversion-tracking-and-audience.md` | Conversion action via API, wire label into `brand.ts` + `thank-you.astro`, warm-pixel RLSA audience +50% bid | Once per client |
| `ads-negative-kw` | `universal-negative-keywords.md` | One-time 150-term universal negative list setup | Once per campaign |
| `ads-negative-search-terms` | `find-and-add-negatives.md` | Weekly search term pruning — SERP intent check + human approval before adding | Weekly |

**Why:** Why dedicated landing pages (not DTR): Google's QS crawler doesn't execute JS — dedicated pages with keyword in URL + H1 get "Above Average" Landing Page Experience vs. "Average" with a generic fallback. Lower CPC.

**How to apply:** When the user wants to run ads for a client, the natural order is: `ads-campaigns` → `ads-generate-ads` → `ads-landing-page` → `ads-tracking` → `ads-negative-kw` → then `ads-negative-search-terms` weekly.
