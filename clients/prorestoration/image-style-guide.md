# ProRestoration Services: Image Style Guide

This guide is consulted by every image-generation call (Skill 3 launch images, Skill 4 blog hero images, future image regenerations). The goal: a viewer scrolling through the site should feel like one professional photographer documented one company on one continuous job. No stylistic drift from page to page.

The values below are auto-populated from `plan-input.json` at planning time. Per-client brand colors come from the client's logo / brand identity — NOT from the canonical starter palette. The structural conventions (camera, lens, lighting, composition) are restoration-vertical canonical and shared across all Rank AI clients.

## CLIENT DIRECTION (2026-08-16) — homepage hero fleet

1. **The homepage hero shows EXACTLY THREE vans — never four or more.** The
   client reviewed the hero and asked for three vans, not four.
   AUTOMATIC REJECT: any hero with four or more vehicles in frame.
2. **Every van's logo must read crisply — never blurred, faded, or smeared.**
   The full ProRestoration wordmark + blue water-swoosh must be sharp and
   legible on every van in the hero, including the ones set further back. Keep
   the three vans close together in the staggered row so none recedes far
   enough to lose its mark. AUTOMATIC REJECT: any van whose logo is blurred,
   melted, or unreadable.

VAN-OVERRIDE: a fleet of EXACTLY THREE matching white service vans, parked in a gently staggered row with clear space between them so each van's side panel and logo stay visible, all facing the same direction, each side panel carrying ONLY the company logo mark from the reference image reproduced faithfully at vehicle-wrap scale with a subtle red accent stripe and no other small text or decals — the logo sharp, crisp and clearly legible on every van, never blurred or faded

---

## STANDING BRAND RULES (Santino, 2026-07-11) — apply to EVERY image

1. **Vehicles carry the client's REAL logo.** Any generated image featuring a company vehicle must show the client's actual logo mark on the vehicle — supply the real logo file as a reference image to `gemini_edit_image` / `gemini_generate_image` and iterate until the mark reads faithfully (shape + colors; sized so lettering stays clean or is naturally implied at distance). The no-text rule still applies to everything EXCEPT the logo mark itself. For this client: `clients/prorestoration/LOGO.svg` (rasterized reference: `clients/prorestoration/logo-raster-white.png`) — slanted red "ProRestoration" wordmark + blue triple-line water swoosh + blue "Services INC". Fallback after 3 failed attempts on an image: two-color mark impression (red block + blue swoosh, no letters) or naturally defocused decal.
2. **One crew uniform color per client, everywhere.** Declared once here, used in every image (hero, team, services, per-service, blog heroes). **This client's uniform: DEEP RED polos** (brick red, ~#A6242A fabric tone; brand red #C80106) with subtle navy collar trim, charcoal/navy work pants. Never navy/blue polos.
3. **If the client has an existing website, harvest its photos FIRST.** Real photos take priority for direct use where quality allows; otherwise they serve as style/livery references for generation. This client: https://prorestorationca.com harvested 2026-07-11 → `clients/prorestoration/harvested/` (real fleet livery photo `pro-restoration-trucks.jpg` — white Ram ProMaster vans, blue roofline band, red swoosh, full wordmark; owner photo `Jack-Bispo-ProRestoration-Services.jpg` — red shirt, confirms uniform color).

---

## Camera & Lens Setup

- **Camera**: Sony A7 IV (full-frame mirrorless) — implied; the LLM prompt should reference "professional photography, mirrorless full-frame look"
- **Lens**: Sony 24-70mm f/2.8 GM II — covers wide environment to tight detail

### Focal Length by Shot Type

| Shot Type | Focal Length | Use Case |
|-----------|-------------|----------|
| Wide environment | 24-28mm | Hero shots, full-property exteriors, large damaged areas before/during restoration |
| Medium service | 35-50mm | Workers performing tasks, equipment in action, mid-range jobsite documentation |
| Close-up detail | 60-70mm | Moisture meters, hand tools, technical detail shots, equipment readouts |
| Portrait / team | 50-70mm | Workers, faces obscured (back, side angle, hard hat shadow) |

---

## Exposure Settings

### Exterior Scenes
- **Aperture**: f/4 to f/5.6 — full scene in sharp focus from foreground (worker, equipment) to background (the property, surrounding neighborhood)
- **ISO**: 100-400

### Interior Restoration Scenes (most common)
- **Aperture**: f/2.8 to f/4 — slight subject isolation while keeping context legible
- **ISO**: 400-1600 — restoration sites often have lower interior light; clean noise acceptable

### Detail / Close-up
- **Aperture**: f/2.8 — shallow depth of field to isolate moisture meter readouts, soot residue, mold growth, water damage texture
- **ISO**: 100-400

### General
- Shutter speed fast enough to freeze action (1/250+ for crew movement)
- No motion blur except intentional water flow or extraction equipment in operation

---

## Lighting

- **Exterior primary**: Golden hour natural light (first 2 hours after sunrise, last 2 hours before sunset) for property shots and "we just arrived" framing
- **Interior primary**: Cool, neutral diffused light — what you'd actually see in a water/fire/mold-damaged interior with portable work lights. NOT overly warm or staged.
- **Damaged-scene lighting**: Slightly underexposed or overcast feel acceptable. Restoration is serious work — images should feel professional and competent, not sunny and cheerful.
- **Avoid**: Direct overhead noon sun, harsh flash, heavy HDR, oversaturated processing
- **Dusk/blue hour**: Reserved for "arrival" hero shots (truck pulled up, technician approaching). Conveys urgency, the 24/7 response promise.

---

## Color Palette

Per-client brand colors take priority. The values below are substituted from `plan-input.json`'s `brand` block.

| Role | Source | Value for this client |
|------|--------|----------------------|
| Primary brand color (uniforms, vehicle, signage glimpsed in shots) | brand logo | **#C80106 red** (uniform polos read as deep brick red ~#A6242A on camera) |
| Secondary (vehicle swoosh, logo lettering) | brand logo | **#0B338D navy** |
| Vehicles | real fleet | **WHITE vans** with blue roofline band + red swoosh + real ProRestoration logo decal |
| Logo color (if a worker's uniform back is visible) | derived from brand logo | match ProRestoration Services's logo |
| Skin / texture / restoration materials | natural and neutral | warm wood tones for housing stock, cool concrete grays, real surface textures |
| Environment-specific atmospherics | regional | varies — see "Setting & Environment" below for Bakersfield |

### Color Treatment Rules

- True-to-life, not pumped up. Restoration scenes are not Instagram travel content.
- Slight warmth on golden-hour exteriors (white balance ~5800-6200K); neutral white balance for interior damage shots (~5000-5500K)
- The client's primary brand color should appear at least once per worker shot (on a uniform polo, hat, vehicle wrap, or equipment case label). NOT garish — just present.
- No oversaturation. Real damaged drywall is not vivid. Real soot is matte black-gray. Real wet wood is dull.

---

## Mood & Atmosphere

- **Professional and competent**: The viewer should feel they hired the right team. No hero-shot smiles or staged enthusiasm.
- **Calm under stress**: Restoration customers are panicked. Imagery should be the visual antidote — methodical, equipped, in-command.
- **Authentic**: Real residential and commercial properties in Bakersfield and surrounding areas. Real materials. Real water damage, real soot residue, real mold containment.
- **Restrained**: When depicting damage, show it honestly but not gratuitously. The viewer wants to see we can handle it, not be made queasy.

---

## **Worker in Uniform — Required in every people-shot**

Every image that depicts a person must show a worker in branded company uniform. This is non-negotiable for visual consistency and trust signaling.

### Uniform specifications
- **Top**: **DEEP RED polo** (brick red ~#A6242A fabric tone, brand red #C80106) with subtle navy collar trim — the declared standing uniform color for this client (see Standing Brand Rules above). Never navy or blue polos.
- **Bottom**: Neutral work pants (charcoal, dark navy, or khaki). Subordinate to the top.
- **Branding**: ProRestoration Services or ProRestoration embroidered on chest or back. IICRC certification badge visible on sleeve or chest where it makes sense.
- **PPE**: Match the service context (see service-specific notes below) — gloves always, respirators / face shields / Tyvek suits when the service warrants it.
- **Footwear**: Sturdy work boots, never sneakers.

### Worker positioning
- **Faces**: Generally NOT shown clearly. Photograph from behind, side angle, or with face partially in shadow under a cap brim. This avoids generating recognizable faces and lets the image library represent any team member.
- **Hands and arms**: Fully visible is fine. Show competent technique — holding a moisture meter correctly, operating an air mover, applying containment plastic, etc.
- **Action**: Mid-task, not posed. The worker should be doing the job, not standing for a portrait.

### Per-service uniform + equipment context (REQUIRED — match the service)

The worker's uniform stays the same; their PPE and equipment shift per service. Every image should be unmistakably "this is a  job," not generic.

| Service | Worker context |
|---------|---------------|
| Water damage restoration | Worker operating truck-mounted extractor, LGR dehumidifier, or holding a moisture meter against wet drywall. Wet floors visible. Air movers in background. |
| Flood damage | Worker pumping standing water, extraction in progress, wet boots, water still visible in the scene. |
| Burst pipe / appliance leak | Worker shutting off a water supply valve OR examining a failed appliance line, with extraction equipment staged. |
| Basement flooding | Worker in waders or rubber boots, sump pump or extraction wand in use, basement walls visible, exposed framing showing waterline. |
| Fire damage restoration | Worker in HEPA-respirator + Tyvek, charred drywall visible, soot on contents, HEPA air scrubber or thermal fogger in scene. |
| Smoke damage / soot removal | Worker wiping soot from walls or operating ozone generator, charcoal-gray residue visible on surfaces. |
| Odor removal | Worker setting up hydroxyl generator or thermal fogger, scene shows interior with subtle yellowing or smoke staining. |
| Mold remediation | Worker in **full Tyvek suit + N95 respirator + face shield**, containment plastic (poly sheeting) visible, HEPA vacuum or air scrubber running. |
| Mold inspection / testing | Worker with air sampling pump cassette, surface swab kit, or moisture meter near suspected mold area. Less PPE — clipboard-and-camera vibe. |
| Storm / wind / hail damage | Worker tarping a damaged roof, securing window plywood, or assessing exterior siding damage. Property exterior visible. |
| Emergency board-up & tarping | Worker installing plywood over broken window or roof tarp at dusk, ladder visible. Urgency. |
| Biohazard / trauma cleanup | **CONTENT GUARDRAIL — sensitive.** Show worker in full PPE (Tyvek, respirator, double gloves) and a CLEAN, prepped, neutral interior space. NO visible blood, bodily fluids, weapons, or traumatic detail. Focus on the team's professionalism and discretion. Vehicle parked discreetly (no large branded wrap). |
| Crime scene cleanup | Same guardrails as biohazard. Clean spaces only, never the scene itself. |
| Hoarding cleanup | **Sensitive.** Show team in PPE staging cleanup supplies, mid-progress organized rooms, NOT before-state extreme clutter. |
| Meth lab decontamination | Sensitive. Show worker in full PPE + respirator in a prepped, mostly-cleaned space. NEVER show chemicals, paraphernalia, or active hazards. |
| Commercial / industrial restoration | Worker in scaled-up scene — warehouse, office, multi-family building. Commercial equipment, larger air movers. |
| Reconstruction | Worker with framing tools, drywall, lumber, partially-rebuilt space. Tool belt with hammer / nail gun. |
| General contracting | Worker mid-build on a kitchen, bath, or living-area remodel. Tools and materials staged. |
| Asbestos / lead-paint abatement | **Full HAZMAT-style Tyvek with hood, P100 respirator, full face seal.** Containment area, negative-pressure ducting. |
| Air duct cleaning / HVAC decontamination | Worker with rotary brush or HEPA vacuum at ductwork, ceiling registers visible. |
| Vandalism cleanup | Worker repairing graffiti'd wall, replacing broken glass, or cleaning damaged storefront. |
| Carpet cleaning | Worker operating truck-mount carpet extraction wand, clean stripes visible behind. |

---

## Setting & Environment (Bakersfield / CA)

- **Primary setting**: Bakersfield and surrounding CA residential and commercial properties
- **Local housing stock cues**: Bakersfield, CA — named neighborhoods: Downtown Bakersfield, Oleander/Sunset, Westchester, Seven Oaks, Stockdale Estates · landmarks: Buck Owens' Crystal Palace, Fox Theater, Mechanics Bank Arena · Kern County seat, ~410k people. Slab-on-grade construction plus very hard water makes slab leaks and burst supply lines the top water-damage source; pre-1970 homes in Oleander, Westchester and East Bakersfield add failing galvanized pipe and cast-iron drains. Kern River high-flow years (2023 snowmelt) put riverside neighborhoods on alert, and aging evaporative coolers leak through roofs and attics every summer. Dry 100°F+ summers help drying times but push electrical-fire and AC-condensate risks; winter tule fog season brings space-heater house fires. Other cities served: Oildale, Rosedale, Delano, Shafter, Wasco. — these details should appear in backgrounds and environmental context, NOT as the subject. They quietly anchor "this was shot in Bakersfield."
- **Regional weather / season**: Slab-on-grade construction plus very hard water makes slab leaks and burst supply lines the top water-damage source; pre-1970 homes in Oleander, Westchester and East Bakersfield add failing galvanized pipe and cast-iron drains. — affects exterior shots especially. Pacific Northwest: wet roads, evergreen silhouettes, cedar siding, low gray cloud cover for "we just arrived in the rain" shots. Adapt per client.
- **Time of day**: Mix of golden-hour exteriors and neutral-light interiors. Reserve dusk/blue-hour for "arrival" hero shots specifically.

### Specifically AVOID
- **Tropical or non-regional vegetation**. Match the client's actual region.
- **Wrong housing styles**. Don't show a Texas ranch home for a Seattle client.
- **Recognizable faces**. Backs, side angles, shadowed-brim cap shots only.
- **Brand competitors in the frame**. No visible Servpro / Stanley Steemer / Restoration 1 trucks or branding.
- **AI-obvious artifacts**: distorted text on equipment labels, melted hand geometry, impossible tool shapes, extra fingers. If a generated image shows any of these, regenerate.
- **Stock-photo enthusiasm**: no thumbs-up, no smiling-at-camera, no chest-out hero poses.
- **Overly clean / staged**: a real restoration jobsite has dust, tools, deployed equipment. Sterile spaces look fake.
- **Children, pets, vulnerable people**. Restoration imagery should feel adult and professional.
- **Active hazardous scenes**: no visible blood, biohazard materials, drug paraphernalia, weapons, fire in progress, structural collapse risk. For sensitive services, show post-stabilization clean spaces only.

---

## Composition Rules

1. **Rule of thirds**: Place the focal point (worker, equipment, damaged area) at the intersection of thirds
2. **Leading lines**: Use baseboards, doorways, equipment hose lines, hallways to guide the eye
3. **Foreground interest**: A piece of equipment, a moisture meter, a piece of damaged material in foreground gives depth
4. **Layered depth**: Foreground (subject), middle (equipment / context), background (the property / scene)
5. **Horizon placement**: Interior: usually irrelevant. Exterior: place on lower third to emphasize the property or upper third to emphasize the work in progress.
6. **Negative space**: Allow breathing room. Don't cram every inch. The LEFT THIRD of hero-aspect shots should be compositionally calmer so headline text can overlay cleanly.

---

## Image Categories Needed (per client launch)

This list drives the image generation plan. Skill 3 (initial scaffold) generates the hero. Skill 4 (blog routine) generates blog hero + inline images per post. Service and area images are filled in over time.

### Brand-level
- [ ] Homepage hero — **DEFAULT: branded small-fleet scene.** A matched fleet of 3-5 company vehicles (Transit-style cargo vans and/or box trucks) in one identical livery built from the client's brand colors (primary color panel/wrap + accent swoosh), parked in a staggered line on a residential street matching the client's region, golden-hour light, editorial-photography look. Livery rules: one small stylized brand mark/wordmark per vehicle only — NO phone numbers, NO website URLs, NO certification badges, NO other readable text (AI-rendered text artifacts fail review). Composition: fleet in the center/right two-thirds; LEFT THIRD calm (open street/sky) for headline overlay. Alternative if the operator prefers: the "arrival at dusk" single-van composition (worker + branded van + lit property).
- [ ] Logo placement test image (no actual logo — narrative shot with brand color in worker uniform)
- [ ] OG / social-share card (1200×630) — usually a crop or variant of the hero

### Service landing pages (one image per selected service)
- [ ] water-damage-restoration — see Per-Service table above
- [ ] flood-damage-restoration
- [ ] burst-pipe-repair
- [ ] basement-flooding-cleanup
- [ ] (continue for each of Water Damage Restoration, Flood Damage Restoration, Burst Pipe Cleanup and Repair, Appliance Leak Cleanup, Sewage Cleanup and Sanitization, Fire Damage Restoration, Smoke Damage Restoration, Soot Removal, Odor Removal and Deodorization, Mold Remediation, Mold Inspection and Testing, Storm Damage Restoration, Carpet Cleaning, Reconstruction Services, Home Remodeling, Renovations, Remodels and General Contracting)

### Service area pages (one image per city served)
- [ ] Bakersfield hero — exterior shot, regional housing stock, evocative of the city
- [ ] Each additional service-area city — same pattern, regional cues per city

### Blog post heroes
- [ ] Generated on-demand by Skill 4 per post, contextually matching the post's topic + the post's primary service tag

### Inline blog images (optional, when budget allows)
- [ ] 1-2 supporting images per blog post, technical detail or process illustration

---

## How this guide is used

1. **Skill 4 (blog routine)** reads this file before every Nano Banana call. The prompt to Nano Banana includes the relevant service/category context block above PLUS the scene-specific description.
2. **Manual regeneration** (e.g., to refresh a stale image) follows the same path — read this guide, generate with consistent style.
3. **Updating the guide** (e.g., the client provides updated brand colors, or you want to shift the lighting policy): edit this file in `clients//image-style-guide.md`, then re-run image generation for any pages where consistency matters. Existing images can stay or be regenerated based on cost vs benefit.

---

## Style guide version

This guide is generated from `templates/restoration/image-style-guide.template.md` v1.0. When the canonical template updates, existing clients keep their pinned version unless explicitly regenerated. Bump the version + add a changelog entry when changing structural rules (e.g., adding new mandatory PPE conventions).

**Changelog**
- **v1.1 (2026-07-11)**: Added Standing Brand Rules (real logo on vehicles, one uniform color per client = DEEP RED for ProRestoration, harvest existing-site photos first). Corrected brand palette to #C80106/#0B338D. hero-bg/team/services + flood/storm/carpet service images updated to red uniforms + real logo vans.
