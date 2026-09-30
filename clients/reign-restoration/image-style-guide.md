# Reign Restoration: Image Style Guide

## CLIENT DIRECTION — NON-NEGOTIABLE (Jerrott Gray, 2026-08-04 / 2026-08-05)

> **RULE 0 — TRUE REPRESENTATION (round 4, 2026-08-05, superseded round 3 the
> same day).** Round 3 read his SMS as "stop generating" and banned generation
> and vehicles outright. **On the phone at 16:03 he said the opposite**, twice:
> *"I don't mind the AI generated photos"* and *"if we're going to use AI
> photos, let's make sure they at least represent like reality."* He also asked
> for the generated About shot to be put BACK: *"I did like the about photo that
> was made prior. I just wanted the logos to match on the company vehicles."*
> Transcript: `calls/2026-08-05-jerrott.md`.
>
> The bar is **not** "real photo". The bar is **true representation** — a
> generated frame is fine as long as nothing in it is false to how the work is
> actually done or how his brand actually looks.
>
> * **Generated images are ALLOWED, and so are vehicles in them.** The round-3
>   blanket ban is withdrawn. What is rejected is an UNTRUE frame, not a
>   generated one.
> * **Every vehicle in a frame wears the identical livery in the identical
>   position on the vehicle.** This is the failure he actually reported: two
>   vans facing opposite ways, each with the crest on the same side of the
>   SCREEN, which puts it at the nose of one van and the tail of the other.
>   *"one, you have the my logo and then rain restoration, and then it would
>   flip the other way on the other vehicles ... it didn't look professional."*
>   Mirroring the crest is the reject condition, not the vehicle itself.
> * **No garbled lettering.** "2A HOUR EMERGENCY SERVICE" shipped in round 2.
>   Let small text fall to natural photographic softness rather than invent
>   substitute characters (see the Scale rule below).
> * **A real photo of his still wins a slot outright** where one exists and
>   suits the slot — but it does NOT get to displace a generated image he has
>   already told us he likes.
> * **PPE is worn SEALED or not at all** — *"PPE worn corectly. Full PPE needs
>   to be depicted."* / on the call: *"if they're in PPE, suit them and boot
>   them fully in PPE ... the hood's up, just to make it look like realistic."*
>   Tyvek zipped to the throat, hood UP, respirator sealed, gloves on, wrists
>   taped. Open like a jacket, hood down, tied at the waist, or a branded
>   T-shirt showing through an unzipped suit = REJECTED image.

> **This block outranks everything below the horizontal rule.** The sections
> under it are the canonical restoration boilerplate and are regenerated from
> the template on every `plan_site.py generate`, so they will keep saying
> generic things like "golden hour" and "polo in the primary brand colour."
> Where they disagree with this block, this block wins — Reign's uniforms are
> BLACK with a gold crest, the light is low-key and overcast, and the vans are
> black with the exact livery specified below.

1. **COMPANY VEHICLES ARE BLACK.** Satin-black cargo vans — black body, black bumpers, black wheels, black trim. NO white vans, NO red vans, NO red or white stripe, panel or swoosh anywhere. A non-black vehicle is a REJECTED image, not a fixable one.
2. **EVERY VEHICLE WEARS THE IDENTICAL LIVERY** — see THE LIVERY below. Jerrott Gray, 2026-08-05: *"the company vehicle decals need to match from photo to photo."* Two vehicles in one frame, or the same vehicle across two pages, that differ in crest, wordmark, size, placement or added text = REJECTED image.
3. **DARK, MOODY, EXPENSIVE — IN THE GRADE, NOT THE SKY (skies re-directed 2026-08-09, see rule 6).** Low-key lighting, deep shadows, near-black values on the vehicles, uniforms and interiors; dim interiors lit by practical work lights; never a cheerful golden-hour postcard. Blacks and charcoals dominate the frame; warm gold is the ONLY accent colour. Luxury-automotive advertising applied to a restoration company: restrained, high-contrast, expensive. Skies are governed by rule 6 and are BRIGHT.
4. **NO STOCK-PHOTO CHEER.** Nobody smiles at the camera, nobody lines up for a posed group portrait. Crew wear all-black uniforms with a small gold chest mark.
5. **MOLD CONTAINMENT MUST BE DEPICTED TRUTHFULLY (Jerrott Gray, 2026-08-06).** *"When you click on service page first photo for mold remediation, the man in the photo is vacuuming plastic covered mold. Containment is correct, but depiction of containment is not."* He is NOT objecting to the poly sheeting being present — he is saying you do not clean mold THROUGH the plastic. On the mold-remediation image the technician works the **EXPOSED, uncovered mold-stained surface directly** — HEPA-vacuum nozzle or scrub tool in contact with the bare contaminated wall, visible black/green mold growth on that surface. The clear poly-sheeting containment is the **barrier that walls off the room** — hung on the surrounding walls, stapled over the doorway, draped behind and beside the worker — and NEVER laid over, taped across, or covering the surface being cleaned. AUTOMATIC REJECT: any frame where the containment plastic covers the mold being worked, where the tool contacts the plastic instead of the exposed mold, or where the worker is cleaning a plastic-covered surface. The plastic is the wall of the tent, not the thing he vacuums.
6. **SKIES ARE BRIGHT, SITE-WIDE (Jerrott Gray, 2026-08-08 on the mold hero; broadened by him 2026-08-09 after seeing that fix: *"Looks good can we see what it would look like with out the dark ominous skies"*).** In EVERY image, any visible sky reads BRIGHT and clear: soft daylight or light overcast, clearly lighter than the frame's shadows — never dark, gloomy, stormy or ominous, no storm clouds. The luxury lives in the vehicles, uniforms, interiors and grade, not in the weather. This outranks rule 3's mood wording wherever they touch skies. AUTOMATIC REJECT: dark storm clouds or an ominous sky in ANY frame.

## THE LIVERY — one spec, copied exactly, every image (2026-08-05)

Jerrott sent a photograph of his ACTUAL wrapped trailer (`harvested/real-trailer-livery-2026-08-05.jpeg`). That photo is the master. It is passed to the image generator as a reference image on every vehicle shot via `LIVERY-REFERENCE` below, and it is the acceptance standard a generated vehicle is judged against.

LIVERY-REFERENCE: harvested/real-trailer-livery-2026-08-05.jpeg

The wrap, described so it can be checked without opening the file:

| Element | Spec — identical on every vehicle, every image |
|---|---|
| Body | Gloss/satin BLACK, black wheels, black trim. Nothing else. |
| Crest | A pointed shield outlined in **silver-white** with a **gold #f2b623** inner border, containing an interlocking **"RR" monogram in silver-white** under a small **gold crown**. Sits on the FORWARD third of the side panel, vertically centred, roughly one-third of the panel height. |
| Wordmark | **"REIGN"** in large silver-white serif capitals, with **"RESTORATION"** in smaller silver-white capitals directly beneath, both set to the RIGHT of the crest, baseline-aligned with the crest's centre. |
| Top line | **"24 HOUR EMERGENCY SERVICE"** in small gold capitals, above REIGN. |
| Service line | **"WATER \| FIRE \| MOLD \| STORM DAMAGE"** in small gold capitals, below RESTORATION. |
| Phone | **214.304.0621** in silver-white, largest text after REIGN, bottom of the block. |
| Everything else | NOTHING. No stripes, no swooshes, no badges, no URLs, no licence numbers, no second crest on the same panel, no tagline. |

**Hero composition (locked 2026-08-09, Santino).** The accepted hero is TWO satin-black Transits nose-to-tail at close-mid range, full livery readable on the foreground van exactly per the master trailer photo, rear van's small strips naturally soft, left third calm with NO overlaid or floating text rendered into the image. A three-van staggered wide shot makes the gold strips too small to render and they garble — do NOT regenerate the hero with the default wide prompt; keep this framing.

**Scale rule (REVERSED 2026-08-09, Santino: hero vans must look like Jerrott's REAL vans).** The TARGET on the hero and on any van panel that fills a meaningful part of the frame is the FULL block exactly as the master trailer photo shows it: gold "24 HOUR EMERGENCY SERVICE" on top, REIGN large with RESTORATION beneath, gold "WATER | FIRE | MOLD | STORM DAMAGE", and "214.304.0621" large beneath — every character correct. Garbled or invented lettering ("REIGN BESTONATION", "STORN CAMASE") remains an AUTOMATIC REJECT: regenerate rather than accept. Only when a van is genuinely small or distant in frame may the two gold strips and phone fall to natural photographic softness — softness is the fallback for distance, never the goal on the hero.

**Consistency rule.** Vehicle images are generated with the real photo as a reference AND with the already-approved hero as a second reference, so each new image copies the wrap we already shipped rather than inventing one. Any image whose livery does not match the master is regenerated, not accepted.

**Standing preference.** Real photographs of Jerrott's actual fleet beat any generated vehicle, every time, and should replace these images as soon as he sends them (hub upload link).

**THE NO-VEHICLE DIRECTIVE IS WITHDRAWN (round 4, 2026-08-05).** It was added earlier the same day on the reading that Jerrott wanted vehicles out of generated frames. On the phone he asked for the opposite: *"I did like the about photo that was made prior. I just wanted the logos to match on the company vehicles."* Vans are back in generated shots and VAN-OVERRIDE below is live again. Do not write that directive's name followed by a colon anywhere in this file, even in prose about it — the generator matches the bare token and would silently strip every vehicle again.

VAN-OVERRIDE: a fleet of two to three matching satin-BLACK cargo vans, black bumpers and blacked-out wheels and no white or red panels or stripes anywhere, every van wrapped in EXACTLY the livery in the reference photograph of the company's real vehicle — the silver-white shield with its gold inner border and gold crown over an interlocking silver-white RR monogram on the forward third of the side panel, with the silver-white REIGN / RESTORATION wordmark set to its right — reproduced identically and at identical scale and position on every vehicle in the frame, inventing no additional stripe, badge, swoosh or lettering of any kind; EVERY VAN FACES THE SAME DIRECTION and is seen from the same side, so the crest sits at the same end of every van relative to its own nose and the wrap reads identically across the whole frame — vans facing opposite ways put the crest at the nose of one and the tail of the next, which is the exact mirroring Jerrott rejected

CREW-OVERRIDE: the technician wears an all-black company uniform (black work shirt, black work pants) with a small gold crest embroidered on the chest and clean fitted nitrile work gloves on BOTH hands whenever handling anything, working in low-key moody light with deep shadows, shown from behind or in three-quarter profile with the face turned away from the camera and never smiling at it; PPE is worn ONLY where the scene shows active remediation work, and where it appears it is FULLY SEALED: white Tyvek coverall zipped ALL the way to the throat with the zipper closed to the chin, hood UP and drawn over the head and hair, respirator strapped and sealed to the face, nitrile gloves ON BOTH HANDS and taped at the wrists, boot covers on. NOT ONE SQUARE INCH of the black company uniform, its gold chest crest, a collar, a T-shirt or any other garment may be visible anywhere through, under or above the suit: the suit is closed over all of it, and if a crest is showing then the suit is open and the image is REJECTED. A hood down, a suit unzipped or worn open like a jacket, a suit tied around the waist, a respirator worn with no hood, or bare hands touching anything is a REJECTED image. In a portrait, group or parked-fleet scene where nobody is working, the crew wear the black uniform and NO PPE at all

MOOD-OVERRIDE: low-key cinematic light with deep shadows on the vehicles, uniforms and interiors, graded like luxury-automotive advertising — expensive, restrained, never posed or cheerful; but any visible sky is BRIGHT and clear (soft daylight or light overcast, never dark, gloomy, stormy or ominous — Jerrott 2026-08-09), so the frame reads premium under a light sky

---

This guide is consulted by every image-generation call (Skill 3 launch images, Skill 4 blog hero images, future image regenerations). The goal: a viewer scrolling through the site should feel like one professional photographer documented one company on one continuous job. No stylistic drift from page to page.

The values below are auto-populated from `plan-input.json` at planning time. Per-client brand colors come from the client's logo / brand identity — NOT from the canonical starter palette. The structural conventions (camera, lens, lighting, composition) are restoration-vertical canonical and shared across all Rank AI clients.
---

## STANDING BRAND RULES (2026-07-11) — apply to EVERY image, every client

1. **Vehicles carry the client's REAL logo.** Any generated image featuring a company vehicle must show the client's actual logo mark on the vehicle. Supply the real logo file (rasterize SVGs to a clean PNG on white first) as a reference image to `gemini_edit_image` / `gemini_generate_image`, and iterate until the mark on the vehicle reads faithfully — correct shape and colors, sized so lettering stays clean or is naturally implied at distance. The no-text rule still applies to everything EXCEPT the logo mark itself (no phone numbers, URLs, license numbers, or other readable text). If the model cannot render the wordmark cleanly at vehicle-side size after 3 attempts on an image, fall back to a two-color mark impression (brand-color blocks/swoosh, no letters) or a naturally defocused decal, and note the fallback.

2. **One crew uniform color per client, everywhere.** Each client's style guide declares exactly one uniform color (derived from their real-world crew wear / brand identity), and every image — hero, team, services, per-service, blog heroes — uses it. Never mix uniform colors across a client's image library.

3. **If the client has an existing website, harvest its photos FIRST.** Before generating any imagery, crawl the client's existing site (e.g. wp-content/uploads on WordPress) and collect real crew / vehicle / job photos. Use real photos directly where quality allows; otherwise use them as style and livery references for generation (real fleet photos define what the vans must look like). Save the harvest to `clients//harvested/`.
4. **Fleet of THREE branded vehicles, everywhere (2026-08-18, was two-three since 2026-07-29).** Hero images always show a fleet of exactly THREE matching branded vehicles (staggered, classic restoration-trade vans unless the client's real fleet documents otherwise), and the branded vehicles also appear in the About/team photo and the Services imagery whenever the scene allows. The client's real logo rides on every vehicle per rule 1. One vehicle alone is the exception (tight interior shots), never the default.
   **No vehicle photos is NOT a reason to skip vehicles (Santino 2026-08-18, reversing the 2026-08-10 no-invented-livery rule):** when the client's photo library has no vehicle, generate the classic professional livery anyway — clean panel vans in the brand's primary color scheme carrying the real logo mark per rule 1. A branded fleet is part of the polished look even when the real fleet is one unmarked pickup. PRECEDENCE: real documented livery always beats invented livery — the moment real fleet photos exist (harvest or client-sent), they define the vehicles and this default retires for that client. A client's explicit no-vehicles instruction (VAN-OVERRIDE) still wins over everything.



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
| Primary brand color (uniforms, vehicle, signage glimpsed in shots) | `#f2b623` | **#f2b623** |
| Accent (emergency markings, CTAs that appear in promo shots) | `#f97316` | **#f97316** |
| Logo color (if a worker's uniform back is visible) | derived from brand logo | match Reign Restoration's logo |
| Skin / texture / restoration materials | natural and neutral | warm wood tones for housing stock, cool concrete grays, real surface textures |
| Environment-specific atmospherics | regional | varies — see "Setting & Environment" below for Royse City |

### Color Treatment Rules

- True-to-life, not pumped up. Restoration scenes are not Instagram travel content.
- Slight warmth on golden-hour exteriors (white balance ~5800-6200K); neutral white balance for interior damage shots (~5000-5500K)
- The client's primary brand color should appear at least once per worker shot (on a uniform polo, hat, vehicle wrap, or equipment case label). NOT garish — just present.
- No oversaturation. Real damaged drywall is not vivid. Real soot is matte black-gray. Real wet wood is dull.

---

## Mood & Atmosphere

- **Professional and competent**: The viewer should feel they hired the right team. No hero-shot smiles or staged enthusiasm.
- **Calm under stress**: Restoration customers are panicked. Imagery should be the visual antidote — methodical, equipped, in-command.
- **Authentic**: Real residential and commercial properties in Royse City and surrounding areas. Real materials. Real water damage, real soot residue, real mold containment.
- **Restrained**: When depicting damage, show it honestly but not gratuitously. The viewer wants to see we can handle it, not be made queasy.

---

## **Worker in Uniform — Required in every people-shot**

Every image that depicts a person must show a worker in branded company uniform. This is non-negotiable for visual consistency and trust signaling.

### Uniform specifications
- **Top**: Polo or work shirt in the client's primary brand color (`#f2b623`). For darker brand colors (navy, deep red, charcoal), use that color directly. For lighter brand colors, render as a darker navy or charcoal uniform with the brand color visible as logo embroidery, accent stripe, or branded hat.
- **Bottom**: Neutral work pants (charcoal, dark navy, or khaki). Subordinate to the top.
- **Branding**: Reign Restoration or Reign Restoration embroidered on chest or back. IICRC certification badge visible on sleeve or chest where it makes sense.
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

## Setting & Environment (Royse City / TX)

- **Primary setting**: Royse City and surrounding TX residential and commercial properties
- **Local housing stock cues**: Other cities served: Rockwall, Fate, Rowlett, Wylie, Garland. — these details should appear in backgrounds and environmental context, NOT as the subject. They quietly anchor "this was shot in Royse City."
- **Regional weather / season**: Regional climate cues per primary city; adapt exterior shots to match. — affects exterior shots especially. Pacific Northwest: wet roads, evergreen silhouettes, cedar siding, low gray cloud cover for "we just arrived in the rain" shots. Adapt per client.
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
- [ ] (continue for each of Contents Restoration and Storage, Fire Damage Restoration, Renovations, Remodels and General Contracting, Mold Remediation, Odor Removal and Deodorization, Roofing Installation and Replacement, Storm Damage Restoration, Water Damage Restoration, Emergency Water Removal & Cleanup, Flood Damage Restoration, Burst Pipe Cleanup and Repair, Basement Flooding Cleanup, Sewage Cleanup and Sanitization, Smoke Damage Restoration, Mold Inspection and Testing, Commercial Restoration, Industrial Restoration, Reconstruction Services, Large Loss and Catastrophic Response, Ceiling Water Damage Repair, Water Heater Flood Cleanup, Water Leak Detection, Emergency Plumbing)

### Service area pages (one image per city served)
- [ ] Royse City hero — exterior shot, regional housing stock, evocative of the city
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

This guide is generated from `templates/restoration/image-style-guide.template.md` v1.1 (2026-07-11: added Standing Brand Rules — real vehicle logos, single declared uniform color, harvest-first). When the canonical template updates, existing clients keep their pinned version unless explicitly regenerated. Bump the version + add a changelog entry when changing structural rules (e.g., adding new mandatory PPE conventions).
