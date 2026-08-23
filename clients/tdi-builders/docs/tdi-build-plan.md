# TDI Builders — Site Build Plan

Prepared 2026-08-23. Companion doc: [rank-ai-beyond-sop.md](rank-ai-beyond-sop.md)
(what we add beyond their SOP + the access ask list for the kickoff meeting).
Source docs archived in this folder: their 47-page Website Architecture SOP
(May 2026) and the TDI Branding Guidelines.

## What's agreed (Santino, 2026-08-23)

- **Platform**: our Astro static build on Cloudflare Pages. Settled; the SOP's
  WordPress recommendation is dismissed. Beats every performance target in SOP
  Section 7 (LCP < 2.5s, 90+ mobile, 95+ desktop).
- **Phasing**: SOP's 22-page Phase 1 is bypassed. We launch roughly half the
  full architecture up front and hold the rest back deliberately so the
  ongoing-content story has runway.
- **License**: CSLB number is not yet provided. Site scaffolds with a
  placeholder and a launch-block flag: preview/staging can proceed, cutover to
  tdiusa.com CANNOT happen until the real number is in.
- **Font**: Futura PT licensing gets raised with Rob; until resolved we ship
  the SOP's own approved fallback stack (Inter, system-ui).

## Initial build scope (~280 pages)

| Silo | Pages | Notes |
|---|---|---|
| Residential services | ~70 | full silo: water, fire/smoke, mold, storm, reconstruction, contents, biohazard, specialty |
| Commercial services | ~50 | full silo incl. large-loss (their differentiator) |
| Insurance claims | 14 | their strategic moat; Rob reviews this silo personally per SOP |
| Geo: top 15 cities | ~120 | 15 city hubs + 15 x 7 service pages (Tier 1: Sacramento, Roseville, Elk Grove, Folsom, Modesto + 10 strongest Tier 2) |
| Sacramento neighborhoods | ~6 | Tier 1 neighborhood layer |
| Local services layer | 14 | trust/capability pages |
| About / trust / contact / legal | ~18 | incl. Rob Carpenter bio (E-E-A-T anchor), certifications, contact forms |
| Case studies | 2 | hub + Fair Oaks church hero (needs their photos) |

**Held back on purpose** (the ongoing-content story): remaining 15 cities
(~105 pages), all 14 industry verticals (~70), expert services silo, resources
library growth, additional case studies.

**Render cost**: ~280 pages x $0.03-0.05 ≈ **$9-14**, runs overnight.

## URL structure decision (flag for Rob)

The SOP prescribes exact slugs (/residential-services/water-damage/... etc).
We implement the same page set and internal-linking logic through our proven
URL system (/services/..., /service-areas/{city}-ca/{service}/). tdiusa.com is
a fresh domain, so there are no legacy URLs to preserve except the 16
buildwithtdi.com mappings, and those 301 wherever we choose. Exact-slug parity
with the SOP is possible but adds template engineering for zero SEO gain;
recommend our structure.

## Lead routing (their stack, not ours)

- Forms post into **their HubSpot** (portal 48033708) via the Forms API with
  full source/UTM attribution; their tracking code embedded site-wide.
  Needs from Rob: a user seat for contact@restorationai.io OR the form GUIDs
  for estimate / commercial / adjuster forms.
- **CallRail** DNI snippet embedded once they send the invite/snippet; until
  then the site renders their main line (877) 688-0866.
- Their speed-to-lead SLAs (SOP Section 8) live in their HubSpot workflows and
  dispatch staffing, on their side; we document the handoff.

## Migration (SOP Section 12, we execute as written)

1. Build + verify on staging → production pages.dev
2. GSC property + sitemap for tdiusa.com at cutover (gsc_setup.py provision)
3. 16-URL 301 map from buildwithtdi.com (Scorpion coordinates), Change of
   Address in GSC, keep buildwithtdi.com registered
4. GBP website URL flip, citations update, launch press release

## Blockers before cutover (not before build)

1. CSLB license number
2. tdiusa.com DNS/registrar control
3. GBP + GSC access
4. Scorpion cooperation on 301s

## Next steps

1. Kick off: intake/bootstrap → plan-site (~280-page map) → scaffold → render
   (overnight) → staging preview link for Santino + Rob
2. Kickoff meeting (2026-08-24): walk rank-ai-beyond-sop.md, collect access
   list, settle URL structure + Futura licensing
3. After staging approval: production push; cutover waits on blockers above
