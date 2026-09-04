# {brand.display_name}: Image Style Guide

This guide is consulted by every image-generation call (Skill 3 launch images, Skill 4 blog hero images, future image regenerations). The goal: a viewer scrolling through the site should feel like one professional photographer documented one company on one continuous inspection day. No stylistic drift from page to page.

The values below are auto-populated from `plan-input.json` at planning time. Per-client brand colors come from the client's logo / brand identity — NOT from the canonical starter palette. The structural conventions (camera, lens, lighting, composition) are environmental-vertical canonical and shared across all Rank AI clients.
---

## STANDING BRAND RULES (2026-07-11) — apply to EVERY image, every client

1. **Vehicles carry the client's REAL logo.** Any generated image featuring a company vehicle must show the client's actual logo mark on the vehicle. Supply the real logo file (rasterize SVGs to a clean PNG on white first) as a reference image to `gemini_edit_image` / `gemini_generate_image`, and iterate until the mark on the vehicle reads faithfully — correct shape and colors, sized so lettering stays clean or is naturally implied at distance. The no-text rule still applies to everything EXCEPT the logo mark itself (no phone numbers, URLs, license numbers, or other readable text). If the model cannot render the wordmark cleanly at vehicle-side size after 3 attempts on an image, fall back to a two-color mark impression (brand-color blocks/swoosh, no letters) or a naturally defocused decal, and note the fallback.

2. **One crew uniform color per client, everywhere.** Each client's style guide declares exactly one uniform color (derived from their real-world crew wear / brand identity), and every image — hero, team, services, per-service, blog heroes — uses it. Never mix uniform colors across a client's image library.

3. **If the client has an existing website, harvest its photos FIRST.** Before generating any imagery, crawl the client's existing site (e.g. wp-content/uploads on WordPress) and collect real inspector / vehicle / jobsite photos. Use real photos directly where quality allows; otherwise use them as style and livery references for generation (real fleet photos define what the vehicles must look like). Save the harvest to `clients/{slug}/harvested/`.
4. **Fleet of THREE branded vehicles, everywhere (2026-08-18, was two-three since 2026-07-29).** Hero images always show a fleet of exactly THREE matching branded vehicles (staggered; for this vertical the natural fleet is clean compact SUVs, small vans, or light pickups — inspection outfits don't run box trucks — unless the client's real fleet documents otherwise), and the branded vehicles also appear in the About/team photo and the Services imagery whenever the scene allows. The client's real logo rides on every vehicle per rule 1. One vehicle alone is the exception (tight interior shots), never the default.
   **No vehicle photos is NOT a reason to skip vehicles (Santino 2026-08-18, reversing the 2026-08-10 no-invented-livery rule):** when the client's photo library has no vehicle, generate the classic professional livery anyway — clean vehicles in the brand's primary color scheme carrying the real logo mark per rule 1. A branded fleet is part of the polished look even when the real fleet is one unmarked sedan. PRECEDENCE: real documented livery always beats invented livery — the moment real fleet photos exist (harvest or client-sent), they define the vehicles and this default retires for that client. A client's explicit no-vehicles instruction (VAN-OVERRIDE) still wins over everything.



## Camera & Lens Setup

- **Camera**: Sony A7 IV (full-frame mirrorless) — implied; the LLM prompt should reference "professional photography, mirrorless full-frame look"
- **Lens**: Sony 24-70mm f/2.8 GM II — covers wide environment to tight detail

### Focal Length by Shot Type

| Shot Type | Focal Length | Use Case |
|-----------|-------------|----------|
| Wide environment | 24-28mm | Hero shots, full-property exteriors, whole-room inspection context |
| Medium service | 35-50mm | Inspectors performing sampling, instruments in use, mid-range documentation |
| Close-up detail | 60-70mm | Air sampling cassettes, moisture meter readouts, swab/tape-lift sampling, labeled sample bags |
| Portrait / team | 50-70mm | Inspectors, faces obscured (back, side angle, cap-brim shadow) |

---

## Exposure Settings

### Exterior Scenes
- **Aperture**: f/4 to f/5.6 — full scene in sharp focus from foreground (inspector, equipment case) to background (the property, surrounding neighborhood)
- **ISO**: 100-400

### Interior Inspection Scenes (most common)
- **Aperture**: f/2.8 to f/4 — slight subject isolation while keeping context legible
- **ISO**: 400-1600 — attics, crawl spaces, and utility rooms run dim; clean noise acceptable

### Detail / Close-up
- **Aperture**: f/2.8 — shallow depth of field to isolate a spore trap cassette, an air quality meter display, a moisture reading, a labeled sample vial
- **ISO**: 100-400

### General
- Shutter speed fast enough to freeze action (1/250+ for inspector movement)
- No motion blur — inspection work is deliberate and steady; the images should be too

---

## Lighting

- **Exterior primary**: Golden hour natural light (first 2 hours after sunrise, last 2 hours before sunset) for property shots and arrival framing
- **Interior primary**: Clean, neutral diffused daylight supplemented by a bright LED work light or headlamp in attics/crawl spaces. Brighter and cleaner than restoration-scene lighting — inspection imagery should feel precise and laboratory-adjacent, not distressed.
- **Suspect-area lighting**: A flashlight beam or thermal-camera glow on a suspect wall corner is a strong storytelling device. Keep the surrounding room normally lit; this is investigation, not horror.
- **Avoid**: Direct overhead noon sun, harsh flash, heavy HDR, oversaturated processing, moody underexposure
- **Dusk/blue hour**: Rarely used in this vertical — testing is daytime appointment work. Reserve it only for a client who genuinely markets urgent-response assessment.

---

## Color Palette

Per-client brand colors take priority. The values below are substituted from `plan-input.json`'s `brand` block. The vertical's default direction is **blues and greens over clean whites**: cool, clinical, trustworthy — lab coats and calibrated instruments, not demolition.

| Role | Source | Value for this client |
|------|--------|----------------------|
| Primary brand color (uniforms, vehicle, equipment case accents) | `{brand.primary_color}` | **{brand.primary_color}** |
| Accent (instrument screens, sample labels glimpsed in shots) | `{brand.accent_color}` | **{brand.accent_color}** |
| Logo color (if an inspector's uniform back is visible) | derived from brand logo | match {brand.display_name}'s logo |
| Interiors / surfaces | natural and neutral | clean whites and light grays for living spaces, warm wood tones for housing stock, cool concrete for basements and crawl spaces |
| Environment-specific atmospherics | regional | varies — see "Setting & Environment" below for {brand.primary_city} |

### Color Treatment Rules

- True-to-life, not pumped up. Inspection scenes should read calm, bright, and orderly.
- Slight warmth on golden-hour exteriors (white balance ~5800-6200K); neutral-to-cool white balance for interior inspection shots (~5000-5500K) — the cool cast reinforces the clinical, lab-adjacent feel.
- The client's primary brand color should appear at least once per inspector shot (on a uniform polo, hat, vehicle, or equipment case). NOT garish — just present.
- No oversaturation. A real water stain is faint tan, not orange. Real suspect growth is subtle gray-green speckling, not vivid black slime. Instrument screens glow softly, not neon.

---

## Mood & Atmosphere

- **Precise and scientific**: The viewer should feel they hired a measured professional who works to a protocol. Calibrated instruments, labeled samples, methodical technique.
- **Calm under worry**: Testing customers are anxious about their health, their kids, or a closing deadline. Imagery should be the visual antidote — orderly, unhurried, in-command.
- **Independent and neutral**: No demolition tools, no remediation theatrics, no tear-out in progress. This company measures and documents; the imagery must never suggest they do the cleanup.
- **Authentic**: Real residential and commercial properties in {brand.primary_city} and surrounding areas. Real instruments. Suspect areas rendered subtly (light staining, faint discoloration), never gratuitously.

---

## **Inspector in Uniform — Required in every people-shot**

Every image that depicts a person must show an inspector in branded company uniform. This is non-negotiable for visual consistency and trust signaling.

### Uniform specifications
- **Top**: Polo or work shirt in the client's primary brand color (`{brand.primary_color}`). For darker brand colors (navy, deep teal, forest green), use that color directly. For lighter brand colors, render as a darker navy or charcoal uniform with the brand color visible as logo embroidery, accent stripe, or branded hat.
- **Bottom**: Neutral work pants (charcoal, dark navy, or khaki). Subordinate to the top.
- **Branding**: {brand.display_name} or {brand.short_name} embroidered on chest or back. Certification badge visible on sleeve or chest where it makes sense.
- **PPE**: Match the service context (see service-specific notes below) — nitrile gloves for sampling; N95/half-face respirators and Tyvek only where the service genuinely warrants it (asbestos sampling, sewage assessment, heavy crawl-space entry). Default is CLEAN, light PPE: this is assessment work, not abatement.
- **Footwear**: Sturdy work boots or clean shoe covers on finished floors, never sneakers.

### Inspector positioning
- **Faces**: Generally NOT shown clearly. Photograph from behind, side angle, or with face partially in shadow under a cap brim. This avoids generating recognizable faces and lets the image library represent any team member.
- **Hands and arms**: Fully visible is fine. Show competent technique — holding an air sampling pump steady, pressing a tape-lift to a surface, logging a moisture reading on a tablet, sealing a labeled sample bag.
- **Action**: Mid-task, not posed. The inspector should be doing the work, not standing for a portrait.

### Per-service uniform + equipment context (REQUIRED — match the service)

The inspector's uniform stays the same; their PPE and instruments shift per service. Every image should be unmistakably "this is a {service} visit," not generic.

| Service | Inspector context |
|---------|---------------|
| Mold inspection & testing | Inspector with air sampling pump + spore trap cassette on a tripod, or pressing a tape-lift/swab to a suspect wall corner. Moisture meter or thermal camera in the scene. Nitrile gloves, clipboard-and-camera vibe. |
| Indoor air quality testing | Inspector reading a handheld air quality meter (particle counter / IAQ monitor) in a bright living room, logging values on a tablet. Clean, minimal PPE. |
| Asbestos testing | Inspector in half-face respirator + nitrile gloves collecting a small material sample (ceiling texture, floor tile edge) into a labeled zip bag, misting bottle in hand. Sample area small and controlled — never demolition. |
| Lead paint testing | Inspector holding an XRF analyzer against a painted window frame or door casing in an older home, tablet nearby. Light PPE. |
| Water quality testing | Inspector filling labeled sample vials at a kitchen tap or wellhead, cooler with ice packs and chain-of-custody paperwork visible. |
| Clearance testing / post-remediation verification | Inspector running an air pump inside a clean, empty, dust-free room where poly containment is coming down or has come down — the room reads FINISHED, the inspector verifies. Never show them doing the remediation. |
| Environmental site assessments | Inspector in hi-vis vest + hard hat walking a commercial property exterior or reviewing site plans on a hood/tailgate, camera around neck. B2B scale. |
| Radon testing | Inspector placing a continuous radon monitor on a basement shelf or lowest-level floor, noting placement on a form. |
| VOC / formaldehyde testing | Inspector deploying a small sampling canister or badge in a freshly renovated interior (new cabinets/flooring visible), meter in hand. |
| Sewage contamination assessment | **CONTENT GUARDRAIL — sensitive.** Inspector in Tyvek + gloves + boot covers swabbing a baseboard in a STABILIZED, drained, visually clean space. NO visible sewage, standing black water, or filth. Focus on the professionalism and the sampling. |
| Post-flood mold assessment | Inspector with moisture meter + thermal camera against a wall with a subtle dry waterline, air movers absent or off in the background (someone else's drying job, not ours). Urgency shown through focus, not chaos. |
| Allergen testing | Inspector collecting a dust sample with a small vacuum cassette from a carpet or sofa in a tidy family living room. |
| HVAC / duct assessments | Inspector at an open supply register or air handler with an inspection camera or flashlight, clean drop cloth below. Never rotary brushes or cleaning gear — assessment only. |
| Remediation oversight / project management | Inspector with clipboard observing (NOT performing) work in a contained area from outside the poly barrier, hard hat + respirator hung at the chest. The visual grammar: we watch, verify, and document. |
| Compliance consulting | Inspector reviewing air-monitoring pumps clipped to a workspace railing, or at a table with reports and floor plans in a commercial setting. |
| Litigation support sampling | Inspector photographing a documented sample location with a scale ruler card beside it, evidence-style. Neutral, meticulous. |

---

## Setting & Environment ({brand.primary_city} / {brand.primary_state})

- **Primary setting**: {brand.primary_city} and surrounding {brand.primary_state} residential and commercial properties
- **Local housing stock cues**: {regional_housing_notes} — these details should appear in backgrounds and environmental context, NOT as the subject. They quietly anchor "this was shot in {brand.primary_city}."
- **Regional weather / season**: {regional_climate_notes} — affects exterior shots especially. Central Valley California: flat horizons, orchard rows or vineyards at the edge of town, stucco ranch homes, bright dry-season light. Adapt per client.
- **Time of day**: Mix of golden-hour exteriors and bright neutral-light interiors. Testing is daytime work — keep it feeling like a scheduled morning appointment.

### Specifically AVOID
- **Tropical or non-regional vegetation**. Match the client's actual region.
- **Wrong housing styles**. Don't show a New England colonial for a Central Valley client.
- **Recognizable faces**. Backs, side angles, shadowed-brim cap shots only.
- **Brand competitors in the frame**. No visible competitor trucks or branding (national inspection or remediation chains included).
- **AI-obvious artifacts**: distorted text on instrument screens and labels, melted hand geometry, impossible instrument shapes, extra fingers. If a generated image shows any of these, regenerate.
- **Stock-photo enthusiasm**: no thumbs-up, no smiling-at-camera, no chest-out hero poses.
- **Remediation imagery**: no demolition, no tear-out, no workers hauling moldy drywall, no spray-and-wipe cleanup crews. The client TESTS — imagery that shows them remediating undermines the independence positioning that sells this vertical.
- **Gratuitous contamination**: no walls consumed by black mold, no sewage, no dead animals, no dramatic filth. Suspect areas are subtle: a faint stain, light speckling, a discolored corner. The instrument findings carry the story.
- **Children, pets, vulnerable people**. Even for health-focused services, imagery stays adult and professional.
- **Overly sterile stock-lab scenes**: petri-dish-and-microscope clichés with no connection to fieldwork. When referencing the lab, show the field side: sealed, labeled samples and chain-of-custody paperwork.

---

## Composition Rules

1. **Rule of thirds**: Place the focal point (inspector, instrument, sample point) at the intersection of thirds
2. **Leading lines**: Use baseboards, doorways, sampling pump tubing, hallway sightlines to guide the eye
3. **Foreground interest**: An instrument case, a labeled sample bag, a meter readout in foreground gives depth
4. **Layered depth**: Foreground (subject), middle (instrument / context), background (the property / room)
5. **Horizon placement**: Interior: usually irrelevant. Exterior: place on lower third to emphasize the property or upper third to emphasize the work in progress.
6. **Negative space**: Allow breathing room. Don't cram every inch. The LEFT THIRD of hero-aspect shots should be compositionally calmer so headline text can overlay cleanly.

---

## Image Categories Needed (per client launch)

This list drives the image generation plan. Skill 3 (initial scaffold) generates the hero. Skill 4 (blog routine) generates blog hero + inline images per post. Service and area images are filled in over time.

### Brand-level
- [ ] Homepage hero — **DEFAULT: branded small-fleet scene.** A matched fleet of 3 company vehicles (clean compact SUVs, small vans, or light pickups — inspection-appropriate, not box trucks) in one identical livery built from the client's brand colors (primary color panel/wrap + accent swoosh), parked in a staggered line on a residential street matching the client's region, golden-hour light, editorial-photography look. Livery rules: one small stylized brand mark/wordmark per vehicle only — NO phone numbers, NO website URLs, NO certification badges, NO other readable text (AI-rendered text artifacts fail review). Composition: fleet in the center/right two-thirds; LEFT THIRD calm (open street/sky) for headline overlay. Alternative if the operator prefers: a single-vehicle "morning appointment" composition (inspector carrying an equipment case toward a well-kept home).
- [ ] Logo placement test image (no actual logo — narrative shot with brand color in inspector uniform)
- [ ] OG / social-share card (1200×630) — usually a crop or variant of the hero

### Service landing pages (one image per selected service)
- [ ] mold-inspection-testing — see Per-Service table above
- [ ] indoor-air-quality-testing
- [ ] asbestos-testing
- [ ] clearance-testing
- [ ] (continue for each of {brand.services_selected})

### Service area pages (one image per city served)
- [ ] {brand.primary_city} hero — exterior shot, regional housing stock, evocative of the city
- [ ] Each additional service-area city — same pattern, regional cues per city

### Blog post heroes
- [ ] Generated on-demand by Skill 4 per post, contextually matching the post's topic + the post's primary service tag

### Inline blog images (optional, when budget allows)
- [ ] 1-2 supporting images per blog post, technical detail or process illustration

---

## How this guide is used

1. **Skill 4 (blog routine)** reads this file before every Nano Banana call. The prompt to Nano Banana includes the relevant service/category context block above PLUS the scene-specific description.
2. **Manual regeneration** (e.g., to refresh a stale image) follows the same path — read this guide, generate with consistent style.
3. **Updating the guide** (e.g., the client provides updated brand colors, or you want to shift the lighting policy): edit this file in `clients/{slug}/image-style-guide.md`, then re-run image generation for any pages where consistency matters. Existing images can stay or be regenerated based on cost vs benefit.

---

## Style guide version

This guide is generated from `templates/environmental/image-style-guide.template.md` v1.0 (2026-09-04: environmental-vertical adaptation of the restoration guide v1.1 — inspection instruments over extraction equipment, clean-light clinical mood, blues/greens/clean-whites palette direction, no-remediation-imagery rule). When the canonical template updates, existing clients keep their pinned version unless explicitly regenerated. Bump the version + add a changelog entry when changing structural rules (e.g., adding new mandatory PPE conventions).
