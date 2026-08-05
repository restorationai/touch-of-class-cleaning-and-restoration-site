# Reign Restoration: Image Style Guide

## CLIENT DIRECTION — NON-NEGOTIABLE (Jerrott Gray, 2026-08-04 / 2026-08-05)

> **RULE 0 — REAL PHOTOGRAPHS ONLY, AND NO GENERATED VEHICLES (round 3, 2026-08-05).**
> Jerrott: *"the two vans on the left side had the logo reversed. Logos on
> company vehicles need to match."* / *"make photos looks realistic and not AI
> slop."* Two rounds of livery references could not stop the generator
> mirroring his crest and inventing lettering, so we stopped asking it to. His
> own photographs now hold 8 of 9 slots (`photo-manifest.json`).
>
> * **No vehicle in ANY generated image** — not in the background, not through
>   a doorway, not at a curb. A generated van is a REJECTED image with no
>   fix-forward; the livery is only ever right in a real photograph.
> * **Generation is a gap-filler, never a replacement.** A real photo of his
>   wins the slot outright.
> * **PPE is worn SEALED or not at all** — *"PPE worn corectly. Full PPE needs
>   to be depicted."* Tyvek zipped to the throat, hood UP, respirator sealed,
>   gloves on, wrists taped. Open like a jacket, hood down, or tied at the
>   waist = REJECTED image.

> **This block outranks everything below the horizontal rule.** The sections
> under it are the canonical restoration boilerplate and are regenerated from
> the template on every `plan_site.py generate`, so they will keep saying
> generic things like "golden hour" and "polo in the primary brand colour."
> Where they disagree with this block, this block wins — Reign's uniforms are
> BLACK with a gold crest, the light is low-key and overcast, and the vans are
> black with the exact livery specified below.

1. **COMPANY VEHICLES ARE BLACK.** Satin-black cargo vans — black body, black bumpers, black wheels, black trim. NO white vans, NO red vans, NO red or white stripe, panel or swoosh anywhere. A non-black vehicle is a REJECTED image, not a fixable one.
2. **EVERY VEHICLE WEARS THE IDENTICAL LIVERY** — see THE LIVERY below. Jerrott Gray, 2026-08-05: *"the company vehicle decals need to match from photo to photo."* Two vehicles in one frame, or the same vehicle across two pages, that differ in crest, wordmark, size, placement or added text = REJECTED image.
3. **DARK, MOODY, EXPENSIVE.** Low-key lighting, deep shadows, near-black values. Blue hour, overcast, twilight, or dim interiors lit by practical work lights — never bright midday sun, never a bright open sky, never a cheerful golden-hour postcard. Blacks and charcoals dominate the frame; warm gold is the ONLY accent colour. Luxury-automotive advertising applied to a restoration company: restrained, high-contrast, expensive.
4. **NO STOCK-PHOTO CHEER.** Nobody smiles at the camera, nobody lines up for a posed group portrait. Crew wear all-black uniforms with a small gold chest mark.

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

**Scale rule.** The gold-on-black wordmark block only reads at close range. In wide/dusk fleet shots, render the crest large and clean and let the smaller lines fall to natural photographic softness — do NOT invent substitute lettering to fill the space. Garbled text ("REIGN BESTONATION" and similar) is an automatic reject.

**Consistency rule.** Vehicle images are generated with the real photo as a reference AND with the already-approved hero as a second reference, so each new image copies the wrap we already shipped rather than inventing one. Any image whose livery does not match the master is regenerated, not accepted.

**Standing preference.** Real photographs of Jerrott's actual fleet beat any generated vehicle, every time, and should replace these images as soon as he sends them (hub upload link).

NO-VEHICLES: no vehicle of any kind anywhere in the frame — no van, truck, car or trailer, not parked at a curb, not in a driveway, not in the background and not glimpsed between objects; the scene is a FULLY ENCLOSED interior with no open garage door, no open exterior doorway and no driveway or street visible through any window, so there is nowhere for a vehicle to be

**RULE 0 supersedes the VAN-OVERRIDE below.** `NO-VEHICLES:` is what `scripts/gen_site_images.py` actually reads now: it drops the livery photo and the logo from the reference list and negates the fleet wording, because with those references present the model parks a van in the shot even when the scene never asked for one. The VAN-OVERRIDE line and THE LIVERY table are kept as the acceptance standard for REAL fleet photographs when Jerrott sends them, and as the spec to restore if he ever asks for generated vehicles again.

VAN-OVERRIDE: a fleet of two to three matching satin-BLACK cargo vans, black bumpers and blacked-out wheels and no white or red panels or stripes anywhere, every van wrapped in EXACTLY the livery in the reference photograph of the company's real vehicle — the silver-white shield with its gold inner border and gold crown over an interlocking silver-white RR monogram on the forward third of the side panel, with the silver-white REIGN / RESTORATION wordmark set to its right — reproduced identically and at identical scale and position on every vehicle in the frame, inventing no additional stripe, badge, swoosh or lettering of any kind

CREW-OVERRIDE: the technician wears an all-black company uniform (black work shirt, black work pants) with a small gold crest embroidered on the chest and clean fitted nitrile work gloves on BOTH hands whenever handling anything, plus the full sealed PPE the service calls for, working in low-key moody light with deep shadows, shown from behind or in three-quarter profile with the face turned away from the camera and never smiling at it

MOOD-OVERRIDE: shot at blue hour or under heavy overcast in low-key cinematic light, deep shadows and near-black values, dark moody sky with no bright or blown-out highlights, graded like luxury-automotive advertising — expensive and restrained, never sunny or cheerful

---

This guide is consulted by every image-generation call (Skill 3 launch images, Skill 4 blog hero images, future image regenerations). The goal: a viewer scrolling through the site should feel like one professional photographer documented one company on one continuous job. No stylistic drift from page to page.

The values below are auto-populated from `plan-input.json` at planning time. Per-client brand colors come from the client's logo / brand identity — NOT from the canonical starter palette. The structural conventions (camera, lens, lighting, composition) are restoration-vertical canonical and shared across all Rank AI clients.
---

## STANDING BRAND RULES (2026-07-11) — apply to EVERY image, every client

1. **Vehicles carry the client's REAL logo.** Any generated image featuring a company vehicle must show the client's actual logo mark on the vehicle. Supply the real logo file (rasterize SVGs to a clean PNG on white first) as a reference image to `gemini_edit_image` / `gemini_generate_image`, and iterate until the mark on the vehicle reads faithfully — correct shape and colors, sized so lettering stays clean or is naturally implied at distance. The no-text rule still applies to everything EXCEPT the logo mark itself (no phone numbers, URLs, license numbers, or other readable text). If the model cannot render the wordmark cleanly at vehicle-side size after 3 attempts on an image, fall back to a two-color mark impression (brand-color blocks/swoosh, no letters) or a naturally defocused decal, and note the fallback.

2. **One crew uniform color per client, everywhere.** Each client's style guide declares exactly one uniform color (derived from their real-world crew wear / brand identity), and every image — hero, team, services, per-service, blog heroes — uses it. Never mix uniform colors across a client's image library.

3. **If the client has an existing website, harvest its photos FIRST.** Before generating any imagery, crawl the client's existing site (e.g. wp-content/uploads on WordPress) and collect real crew / vehicle / job photos. Use real photos directly where quality allows; otherwise use them as style and livery references for generation (real fleet photos define what the vans must look like). Save the harvest to `clients//harvested/`.
4. **Multi-van fleet, everywhere (2026-07-29).** Hero images always show MULTIPLE matching branded vans (two-three, staggered), and the branded vans also appear in the About/team photo and the Services imagery whenever the scene allows. The client's real logo rides on every van per rule 1. One van alone is the exception (tight interior shots), never the default.



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
- [ ] (continue for each of Water Damage Restoration, Fire Damage Restoration, Mold Remediation, Storm Damage Restoration, Renovations, Remodels and General Contracting, Contents Restoration and Storage)

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

### Changelog

- **v1.2-reign (2026-08-04)** — Jerrott Gray reviewed the staging preview: *"Viewed it and it is not ready to go live."* / *"Id like the over all feel to be dark moody and expensive looking. The company vehicles need to be black."* Added the CLIENT DIRECTION block plus `VAN-OVERRIDE:` / `CREW-OVERRIDE:` / `MOOD-OVERRIDE:`, which `scripts/gen_site_images.py` reads out of this file. Full image set regenerated the same day.
- **v1.3-reign (2026-08-05)** — Round 2: *"The yellow need to to match the logo color and the company vehicle decals need to match from photo to photo."* He also sent a photo of his ACTUAL wrapped trailer. That photo is now the livery master (`harvested/real-trailer-livery-2026-08-05.jpeg`), declared via `LIVERY-REFERENCE:` and passed to every vehicle generation as a reference image alongside the logo and the already-approved hero (fleet-continuity anchor). Added THE LIVERY spec table so the wrap can be checked without opening the file, and a precedence note making this block outrank the regenerated boilerplate below it. Brand gold corrected to the logo's true `#f2b623`. All 9 site images regenerated against the new reference chain. `plan_site.py` no longer overwrites this block on re-plan — it did, silently, on 2026-08-05, destroying the v1.2 direction during an unrelated `generate` run; recovered by hand and guarded in code.
- **v1.4-reign (2026-08-05)** — Round 3, and the round that ends the generation argument. *"The first picture on the websites with three vans the two vans on the left side had the logo reversed."* / *"Photos of employees on fir damage restoration and mold remediation need to have there PPE worn corectly."* / *"please make photos looks realistic and not AI slop."* Round 2's reference chain still shipped a mirrored crest and invented lettering, so RULE 0 was added: no generated vehicle in any image, ever, and real photographs outrank generation for every slot. Eight of nine site images are now Jerrott's OWN photographs, harvested from his GBP and his existing site (`scripts/photo_harvest.py`, manifest at `photo-manifest.json`): hero, team, services, and the water / fire / mold / storm / general-contracting cards. Only `contents-restoration` had no qualifying real photo and stayed generated — regenerated vehicle-free under RULE 0.

