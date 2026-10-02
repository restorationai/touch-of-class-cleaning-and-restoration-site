# Dry County Restoration: Image Style Guide

## CLIENT DIRECTION — AI-FIRST POLISHED LOOK (doctrine 2026-08-10)

**Fleet-wide imagery doctrine (Santino 2026-08-10, see scripts/dev_agent.md
"Imagery doctrine"): AI-FIRST.** Launch slots on this site carry the polished
AI-generated look. Dry County's REAL photos serve as REFERENCES: two PPE
photos pin the sealed suit, the drying-equipment photo pins the gear, and
their GBP/website library establishes the facts below. Exactly ONE real photo
is exceptional and holds its slot outright: the blue-cabinet kitchen remodel
holds the general-contracting card (pinned in `photo-manifest.json`). Nothing
in a generated frame may be false to what the real photos document.

1. **THE SITE IS LIGHT: WHITE + LOGO BLUE.** Theme is light/white with primary
   blue `#007fb2`, sampled from the wordmark of the real logo
   (`public/images/logo.png`); red `#fe0000` is the logo's tagline accent and
   appears in site chrome only, NEVER as invented red-painted objects, red
   uniforms or red vehicles in scenes. Generated frames read bright, clean and
   premium under dry Southern California light. Never dark, moody or
   desaturated.
2. **FLEET OF THREE BRANDED VANS (Santino 2026-08-18, reversing the 08-10
   no-vehicle rule for this client).** Their photo library has no vehicle
   photos, so generate the classic professional restoration fleet: THREE
   matching clean white panel vans carrying the ROUND Dry County logo badge
   (see rule 3 and VAN-OVERRIDE — the full circular emblem; no separate
   wordmark and no other readable text on the wrap). Vans appear in the hero
   and wherever the scene allows. Bob is sending real van photos (meeting
   2026-08-19); the moment those land in `harvested/`, real livery replaces
   this invented default.
3. **THE ROUND LOGO IS THE BRAND MARK ON VANS AND UNIFORMS (Bob,
   09-21-2026, "Website Updates 1-3").** Bob asked to switch every van wrap
   from the plain blue wordmark to the full ROUND Dry County logo badge — the
   circular emblem in `public/images/logo.png`: blue `#007fb2` "DRY COUNTY
   RESTORATION" curved across the top, the cartoon water-drop cowboy mascot in
   the center, red "PUTTING THE HEAT ON WATER DAMAGE" curved across the
   bottom. That round badge — and only that badge — is the mark that rides on
   the vans and on the crew's chest. The mascot is therefore permitted INSIDE
   the round badge wherever the badge appears; it is still NEVER rendered as a
   free-standing cartoon character loose in a photographic scene (no giant
   water-drop cowboy in a driveway, no cowboy-hat motif floating in frame).
4. **CREW WEAR THE DOCUMENTED UNIFORM, OR SEALED TYVEK IN CONTAINMENT.** Bob
   documented the crew uniform (09-21-2026, "Website Updates 1-3"): a BLACK
   company t-shirt or polo carrying the round Dry County logo small on the
   left chest, BLUE denim jeans, and BROWN leather work boots. Every non-PPE
   people shot sitewide uses exactly this — hero, team, and all trade scenes.
   This RETIRES the old "no uniform documented, use neutral gray" rule: the
   black-shirt / blue-jeans / brown-boots kit is now the documented uniform.
   Keep the chest logo small and cleanly implied at that scale — a garbled or
   invented chest wordmark is a REJECT, so favor a small legible round mark or
   a clean impression over fake lettering. In containment services the sealed
   white Tyvek suit (hood UP, zipped to the throat, respirator with MAGENTA
   P100 cartridges, black gloves, boot covers — see PPE references) goes OVER
   the uniform; worn open, hood down, or tied at the waist is a REJECT.
   **PPE IS SITUATIONAL, NEVER THE UNIFORM (2026-08-18, Bob's complaint):**
   sealed Tyvek + respirator ONLY where the service warrants it (mold,
   sewage, biohazard, Cat-3 water). The HERO, team photo, and trade scenes
   use the documented uniform (rule 4) — a full-hazmat hero or a sealed suit
   on a roof is an AUTOMATIC REJECT (both shipped in v1).
   **EVERY SLOT GETS ITS OWN COMPOSITION:** hero, team and service frames
   must be visibly different scenes — v1's hero and team photo were the same
   three suited figures at the same house, and the About page showed the
   hero file verbatim. Blue is an ACCENT (logo wordmark, real blue
   equipment where it belongs), not the dominant color of every frame.
5. **EQUIPMENT MATCHES THEIR REAL GEAR.** Documented in their own job photos:
   BLUE axial air movers, blue-and-gray LGR dehumidifiers (staged in a black
   condensate tray on finished floors), poly containment sheeting taped with
   TEAL painter's tape, zippered containment doorways, red extraction hose,
   thermal imaging camera, moisture meters. No invented brand labels and no
   readable text on any unit. (Human reference, not auto-injected:
   `harvested/real-equipment-drying-2026-08-10.jpg`.)
6. **CORONA / INLAND EMPIRE CA, ALWAYS.** Tan and cream stucco homes, Spanish
   tile roofs, palms, dry golden light, brown foothills in the distance. No
   lush eastern lawns, no evergreens, no colonial housing stock, no rain.
7. **QUALITY GATES (every generated image, before install):** zero readable or
   garbled lettering anywhere; correct hand/limb anatomy; no crisp
   recognizable faces; equipment per rule 5; damage honest but never
   gratuitous; no stock-photo grins or thumbs-up. Two or three attempts per
   image is normal. Reject, don't rationalize.

PPE reference photos on file (harvested/real-ppe-sealed-2026-08-10.jpg, harvested/real-ppe-containment-2026-08-10.jpg) are intentionally NOT injected as global references (2026-08-18 revamp): they document the sealed suit for the mold / sewage / biohazard / Category-3 CONTAINMENT scenes only, and feeding them into every generation is exactly what put a hazmat suit on the hero and on the roof in v1. The sealed-suit spec now lives in the CREW-OVERRIDE and in the containment scene text; re-attach a reference for a targeted redo of a single containment slug only if its sealed suit renders loose.

VAN-OVERRIDE: a fleet of exactly THREE matching clean white panel vans, each side panel carrying the ROUND Dry County Restoration logo badge from the reference image reproduced faithfully and legibly at vehicle-wrap scale — the circular emblem with "DRY COUNTY RESTORATION" curved across the top in blue #007fb2, the water-drop cowboy mascot centered, and the red "PUTTING THE HEAT ON WATER DAMAGE" arc across the bottom; that round badge is the ONLY graphic on the wrap (no separate wordmark, no phone number, no URL, no other lettering anywhere on the wrap); all three vans identical and photographed from the same side so the badge reads the same on each; classic professional restoration fleet, bright, clean and premium under dry Southern California daylight

CREW-OVERRIDE: the crew's documented uniform is a BLACK company t-shirt or polo with the round Dry County logo small on the left chest, BLUE denim jeans, and BROWN leather work boots, worn in EVERY non-PPE scene (the hero, the team photo, roof tarping, board-up, storm work, water extraction, air-duct cleaning, carpet cleaning, contents packing, post-construction cleaning and general contracting); PPE IS SITUATIONAL AND NEVER THE DEFAULT — a FULL sealed white Tyvek coverall (zipper closed to the throat, hood UP over the head, respirator sealed to the face with magenta P100 cartridges, black nitrile gloves, boot covers) is worn OVER the uniform ONLY inside an active mold, sewage, biohazard or Category-3 water containment scene; fire and smoke/soot cleanup is the one middle case — soot is a real respiratory hazard, so a respirator and a coverall inside a contained, soot-darkened interior are appropriate there; a sealed hazmat suit anywhere outside a containment interior — and ANY sealed suit on a roof or in the hero — is an AUTOMATIC REJECT; the chest logo must stay small and legible or a clean impression, never garbled or invented lettering; work shots frame from behind or three-quarter profile with no face crisply visible; the team photo shows 3-4 crew in the black-shirt, blue-jeans and brown-boots uniform standing together confidently at a modest camera distance in front of a Corona-style tan stucco home with blue drying equipment staged beside them, calm professional bearing, faces softly rendered not crisp, no stock-photo grins, no thumbs-up

MOOD-OVERRIDE: bright, clean, high-key dry Southern California daylight, light, airy and premium to match a white-and-blue light-theme site; interiors neutral, clean and well-lit by daylight or work lights; never dark, moody, stormy or ominous

EQUIPMENT-OVERRIDE: drying and remediation gear matches the company's real equipment photographs: BLUE axial air movers, blue-and-gray LGR dehumidifiers staged in a black condensate tray when on finished flooring, poly containment sheeting taped with teal painter's tape and zippered containment doorways; equipment carries no readable brand text

**This block outranks everything below the horizontal rule.** The sections
below are canonical restoration boilerplate regenerated from the template;
where they disagree with this block (branded polos, vehicle logos, multi-van
fleets), this block wins.

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
| Primary brand color (uniforms, vehicle, signage glimpsed in shots) | `#007fb2` | **#007fb2** |
| Accent (emergency markings, CTAs that appear in promo shots) | `#fe0000` | **#fe0000** |
| Logo color (if a worker's uniform back is visible) | derived from brand logo | match Dry County Restoration's logo |
| Skin / texture / restoration materials | natural and neutral | warm wood tones for housing stock, cool concrete grays, real surface textures |
| Environment-specific atmospherics | regional | varies — see "Setting & Environment" below for Corona |

### Color Treatment Rules

- True-to-life, not pumped up. Restoration scenes are not Instagram travel content.
- Slight warmth on golden-hour exteriors (white balance ~5800-6200K); neutral white balance for interior damage shots (~5000-5500K)
- The client's primary brand color should appear at least once per worker shot (on a uniform polo, hat, vehicle wrap, or equipment case label). NOT garish — just present.
- No oversaturation. Real damaged drywall is not vivid. Real soot is matte black-gray. Real wet wood is dull.

---

## Mood & Atmosphere

- **Professional and competent**: The viewer should feel they hired the right team. No hero-shot smiles or staged enthusiasm.
- **Calm under stress**: Restoration customers are panicked. Imagery should be the visual antidote — methodical, equipped, in-command.
- **Authentic**: Real residential and commercial properties in Corona and surrounding areas. Real materials. Real water damage, real soot residue, real mold containment.
- **Restrained**: When depicting damage, show it honestly but not gratuitously. The viewer wants to see we can handle it, not be made queasy.

---

## **Worker in Uniform — Required in every people-shot**

Every image that depicts a person must show a worker in branded company uniform. This is non-negotiable for visual consistency and trust signaling.

### Uniform specifications
- **Top**: Polo or work shirt in the client's primary brand color (`#007fb2`). For darker brand colors (navy, deep red, charcoal), use that color directly. For lighter brand colors, render as a darker navy or charcoal uniform with the brand color visible as logo embroidery, accent stripe, or branded hat.
- **Bottom**: Neutral work pants (charcoal, dark navy, or khaki). Subordinate to the top.
- **Branding**: Dry County Restoration or Dry County Restoration embroidered on chest or back. IICRC certification badge visible on sleeve or chest where it makes sense.
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

## Setting & Environment (Corona / CA)

- **Primary setting**: Corona and surrounding CA residential and commercial properties
- **Local housing stock cues**: Other cities served: Riverside, Anaheim, Santa Ana, Ontario, Fullerton. — these details should appear in backgrounds and environmental context, NOT as the subject. They quietly anchor "this was shot in Corona."
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
- [ ] (continue for each of Air Duct Cleaning, Basement Flooding Cleanup, Basement Remodeling, Burst Pipe Cleanup and Repair, Carpet Cleaning, Ceiling Water Damage Repair, Commercial Restoration, Contents Restoration and Storage, Emergency Board-Up and Tarping, Fire Damage Restoration, Flood Damage Restoration, Renovations, Remodels and General Contracting, Industrial Restoration, Large Loss and Catastrophic Response, Mold Inspection and Testing, Mold Remediation, Odor Removal and Deodorization, Post-Construction and Specialty Cleaning, Reconstruction Services, Roofing Installation and Replacement, Sewage Cleanup and Sanitization, Smoke Damage Restoration, Storm Damage Restoration, Upholstery Cleaning, Water Damage Restoration, Water Heater Flood Cleanup, Water Leak Detection, Emergency Water Removal & Cleanup)

### Service area pages (one image per city served)
- [ ] Corona hero — exterior shot, regional housing stock, evocative of the city
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
