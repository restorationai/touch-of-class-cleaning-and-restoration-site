# Rank AI — Content Differentiation Rules

**Status:** Mandatory. Enforced via prompt templates in `rank-ai/templates/astro-starter/prompts/` and via layout requirements in `rank-ai/templates/astro-starter/`. Every render must satisfy these rules or be re-rendered.

**Why this exists:** Google's spam policies and the helpful-content updates (2022 onward) penalize thin and near-duplicate content sitewide. A 229-page restoration site is exactly the shape that triggers algorithmic demotion if pages are templates with only the city or service name swapped in. The defense isn't writing 229 essays — it's making each page meaningfully unique on the dimensions Google's algorithms detect.

## The 40-50% rule

Every page must be at least **40-50% unique from any other page on the site**. This is non-negotiable. Uniqueness is measured by:

- Distinct opening paragraph (no template with the variable swapped in)
- Distinct headings (each page's H2s should reflect that page's specific angle, not a fixed template)
- Page-specific facts that don't appear on other pages (named landmarks, ZIP codes, neighborhood characteristics, local risk factors)
- Service-specific or location-specific FAQs (not a recycled FAQ list with words swapped)
- Service-specific or location-specific CTAs (not a generic "Contact us today")

If two pages would read the same with a find-and-replace, the differentiation has failed.

---

## Service landing pages — `service-landing` archetype

Path: `/services/{service-slug}/`. There are ~18 of these per client.

### Required

1. **Unique opening paragraph** that names the specific problem THIS service solves — not "We handle X damage." Bad: *"Water damage restoration is what we do."* Good: *"Mold can begin colonizing wet drywall within 24-48 hours — which is why our IICRC-certified water extraction crew arrives within 60 minutes of your call."*

2. **Service-specific FAQs.** Every FAQ on a water-damage page must be about water damage. Every FAQ on a mold-remediation page must be about mold. Do not write generic restoration FAQs ("How fast can you respond? Do you bill insurance?") on every service page.

   Examples that pass:
   - **Water damage:** "How long does structural drying typically take?" "What's the difference between Category 1, 2, and 3 water?" "Can carpet padding be salvaged or does it always need replacement?"
   - **Mold remediation:** "What level of mold remediation is considered IICRC S520-compliant?" "When does the EPA require a third-party air clearance test?" "How do you contain mold from spreading during removal?"
   - **Biohazard cleanup:** "What licenses are required to transport biohazard waste in this state?" "Do you coordinate with law enforcement before beginning work?" "What's typical insurance billing for unattended death cleanup?"

   Examples that fail:
   - Generic: "How much does {service} cost?" on every page
   - Generic: "Do you bill insurance?" on every page
   - Generic: "How fast can you respond?" on every page (acceptable once per site, not on every page)

3. **Service-specific process steps, common problems, and seasonal considerations** that only apply to THAT service. The water-damage page covers extraction → drying → moisture monitoring → containment. The mold page covers air sampling → containment → HEPA filtration → clearance testing. These are different processes, not different names for the same process.

4. **Unique CTAs that reference the service directly.** Bad: *"Contact us today."* Good: *"Schedule your moisture assessment"* (water damage), *"Request an air quality test"* (mold), *"Begin discreet cleanup"* (biohazard).

### Forbidden

- Reusing the FAQ block from another service page with words swapped
- Generic "About us" filler in the body content (the about page handles that)
- Listing other services in the body content (the services hub handles that)

---

## Location / service-area pages — `service-area` archetype

Path: `/service-areas/{area-slug}/`. There are 5-15 of these per client.

### Required

1. **2-3 LOCAL LANDMARKS specific to that area.** Named parks, neighborhoods, well-known streets, community centers, lakes, shopping districts. For Seattle: *Pike Place, Ballard, Capitol Hill, Lake Union, Queen Anne.* For Federal Way: *Dash Point State Park, Twin Lakes, Steel Lake, 320th Street corridor, The Commons.* For Tacoma: *Point Defiance Park, Stadium District, Proctor District, Hilltop, Pacific Avenue.* Restoration sites are local — Google reads "is this page actually written for THIS city" via specific named entities.

2. **Neighborhood-specific paragraph** about the area's restoration characteristics — adapted to the vertical. For restoration in Pacific Northwest:
   - Climate micro-differences (Seattle gets more wind-driven rain; Federal Way gets more sustained drizzle from Puget Sound)
   - Housing stock specifics (1920s craftsmen with knob-and-tube wiring; 1970s ramblers with vapor barrier issues; post-2000 townhomes with HOA restoration coordination requirements)
   - Common emergency patterns in that area (flooding-prone basements in older Renton Hill homes; wildfire-smoke intrusion in summer for inland cities; ice-dam roof leaks in Bellevue's higher elevations)
   - Water/utility specifics where relevant (well water vs municipal; septic vs sewer; specific water restriction codes)

3. **Mention specific neighborhoods and ZIP codes** within each area. Bad: *"We serve Seattle."* Good: *"From Magnolia and Queen Anne to Beacon Hill and West Seattle, our team responds across the 98101-98199 ZIP range."* At minimum, name 3 neighborhoods and 1-2 ZIP code ranges per area page.

4. **Local testimonial or case study reference** for that area. The reference can be brief and unattributed: *"A Seattle property manager in Capitol Hill called us after a fire ravaged a four-unit building; we had containment in place within 90 minutes and the full restoration completed in three weeks."* These can be invented for the launch site as illustrative scenarios, clearly marked as representative. They MUST eventually be replaced with real testimonials.

5. **Google Map embed at the bottom of every location page** (before the FAQ / footer). This is a hard layout requirement, not a prompt requirement. The starter's `service-area` route must include a `<GoogleMap>` component that takes the city + state and renders an iframe embed pointing at the Google Maps Embed API. Header text on the map section: *"Serving {City Name} and Surrounding Neighborhoods"*. See the Antigravity contract for the iframe specification.

### Forbidden

- Generic "we serve the greater {region} area" filler
- Identical paragraphs across multiple location pages with only the city name swapped

---

## Service × Location combo pages — `service-area-service` archetype

Path: `/service-areas/{area-slug}/{service-slug}/`. There are ~180 of these per client (the bulk of the site).

This is the SEO money page archetype. It's also the highest cannibalization risk — 180 pages that all look like templates with two variables swapped will get demoted as a group. Every one of these must satisfy ALL the rules below, every time.

### Required

1. **Unique intro that references BOTH the specific service AND local conditions.** Bad: *"We offer water damage restoration in Seattle."* Good: *"Seattle's pre-1950 housing stock combined with persistent winter rain means most water damage we see in the city involves Category 2 water working its way through plaster walls — not the clean Category 1 supply-line leaks more common in newer construction further south. That changes the extraction approach and the timeline."*

2. **Local problems specific to that city × service combo.** Reference altitude (matters for some areas — e.g., Bellevue's higher elevations have ice-dam issues; Tacoma's port-adjacent areas have salt-spray corrosion in commercial restoration). Reference specific soil conditions, local water restrictions, HOA rules common in that area. The mold-remediation page for Bellevue should talk about HOA-mandated post-remediation air clearance testing common in Bellevue's newer townhome developments; the mold-remediation page for Seattle should talk about older home moisture issues in basements and crawl spaces.

3. **Unique FAQs that combine both the service AND location context.** Each FAQ should only make sense on THAT specific combo page. Bad: *"How fast can you respond?"* (same FAQ on every page). Good: *"How quickly can your team reach the Magnolia / Discovery Park area for a water emergency?"* (specific to Seattle's geography), *"Do you coordinate directly with Federal Way property managers for tenant-occupied water damage jobs?"* (specific to Federal Way's denser rental stock), *"Does Tacoma's stormwater management code affect how mold remediation waste must be handled?"* (specific to Tacoma's municipal code).

4. **A "local tip"** — one paragraph that references something only a local would know. Examples:
   - *"In the Eastside, when a HOA insurance claim involves shared walls, the response window from claim opening to contractor selection is typically 7-10 days — significantly tighter than detached single-family loss timelines in Seattle proper."*
   - *"Federal Way's older Lakeland and Twin Lakes neighborhoods often have shared driveway easements that complicate emergency vehicle access — our dispatch crew calls ahead to confirm staging when responding to those addresses."*
   - *"Tacoma's downtown core has a city ordinance requiring HEPA filtration use during any restoration work that produces airborne particulate — most companies miss this and get cited."*

5. **Google Map embed** centered on the city × service combo. Same component as the service-area page; the heading changes to *"{Service} in {City}: Service Coverage Map"*.

### Forbidden

- Using the same opening sentence with city + service variables swapped across pages
- Reusing the same FAQ set on every cross-product page for a given service (each cross-product should have FAQs that only work for THAT city's version of the service)
- Generic "we are IICRC certified" boilerplate that appears word-for-word on every page

---

## Service-specific FAQ banks

To make per-service FAQ uniqueness practical at scale, the prompt provides the LLM with **service-specific FAQ topic banks** to pick from. The bank lives in `rank-ai/templates/restoration/services.json` per service (extension to the existing service catalog).

Each service has 8-12 candidate FAQ topics; the LLM picks 4-6 per page and writes the answer in context. Mixing service-specific topics with location-specific topics on cross-product pages is encouraged — but at least 60% of FAQ content on a cross-product page must reference the city, not just the service.

The bank is non-binding inspiration — the LLM may also generate fresh service-specific FAQs that don't appear in the bank, as long as they meet the specificity rule.

---

## Cross-product cannibalization protection

180 pages × the same template = doorway-page demotion risk. Mitigations baked into the planner + prompts:

1. **Each cross-product page targets a distinct keyword** (`{service} {city}`) — no two cross-products share the same primary keyword.
2. **Each cross-product page must include the city in the H1** (already enforced via the planner's title template).
3. **Each cross-product page must satisfy the local-tip + named-landmark + service-specific-process rules above.**
4. **Internal links between cross-products use city-specific anchor text** (`Water Damage in Auburn` not `Auburn page`) — already enforced via the InternalLinks component.
5. **Sitewide checks** (post-render, separate validator subcommand to be built): no two pages share more than 40% literal-text overlap on the body OR the FAQ. Run quarterly or after any prompt change.

---

## Enforcement

### Where the rules live in the codebase

| File | Role |
| --- | --- |
| `rank-ai/docs/content-differentiation.md` | This doc — the canonical rules |
| `rank-ai/templates/astro-starter/prompts/_system.md` | Tone, format, forbidden patterns |
| `rank-ai/templates/astro-starter/prompts/service-landing.md` | Service-specific enforcement |
| `rank-ai/templates/astro-starter/prompts/service-area.md` | Location-specific enforcement |
| `rank-ai/templates/astro-starter/prompts/service-area-service.md` | Cross-product enforcement |
| `rank-ai/templates/restoration/services.json` | Service-specific FAQ topic banks (extension) |
| `rank-ai/templates/astro-starter/src/components/GoogleMap.astro` | Map embed (Antigravity to build) |

### How to test compliance

Run after any render:

```bash
python3 rank-ai/scripts/build_site.py audit-content --slug {slug}
```

(Subcommand to be implemented.) The audit checks:

- Each location/cross-product page has ≥ 2 named landmarks from the area's expected set
- Each location/cross-product page mentions at least 1 ZIP code
- Each cross-product page's FAQ has ≥ 1 city-specific question
- No two pages share > 40% body text overlap (shingled n-gram comparison)
- Maps embed component renders on every location and cross-product page

Pages that fail audit are flagged for re-render with the strict prompt (which can take their failure reasons as input and tighten the next attempt).

### What changes per client

For a new client, the planner populates the area's landmark / neighborhood / ZIP candidate set from a combination of:

- DataForSEO business listings near the brand's coordinates
- Geoapify reverse geocoding for the city center
- The plan-input.json `local_context_hints` field (a free-text per-area hint that the user can supply — e.g., for Federal Way: `"Twin Lakes, Dash Point, Steel Lake, Lakeland, 320th Street corridor, The Commons, ZIPs 98003 and 98023"`)

The hints are passed into the prompt as a high-priority context block that the LLM is required to reference (per the rules above). Without hints, the LLM falls back to whatever it knows about the city from training data — which is often partial. So always populate hints in plan-input.json for production clients.

---

## What this doesn't replace

- Real, named testimonials from real customers (those replace the illustrative scenarios over time)
- Real photos of the team and completed work (those replace generated hero images over time)
- Genuine local link earning — citations, partnerships, regional press
- Google Business Profile completeness (separate workstream)

This doc is about making **the launch site itself** SEO-defensible for sites with many similar-shape pages. Long-term local rankings still need the rest of the local SEO playbook.

---

*Version 1.0 — 2026-05-14. Bump version when the rules change or the audit subcommand spec evolves.*
