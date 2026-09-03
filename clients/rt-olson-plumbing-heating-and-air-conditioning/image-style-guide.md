# RT Olson Plumbing, Heating and Air Conditioning: Image Style Guide

## CLIENT DIRECTION — NON-NEGOTIABLE (Bobby Olson, 2026-09-02 call)

> **This block outranks everything below the first horizontal rule** — that is
> canonical boilerplate. Where it disagrees, THIS BLOCK WINS. Every rule below is
> a hard gate: a frame that breaks it is REJECTED and regenerated, never shipped.

1. **FULL BLUE HOODS ON THE VANS — never white.** Bobby, verbatim: *"Update hero
   truck imagery to full blue hoods; keep trucks consistent."* The entire front
   hood/bonnet of every van is solid blue, matching the blue upper body. A van
   with a white or two-tone hood is a REJECTED image. See VAN-OVERRIDE below.
2. **ONE IDENTICAL VAN FLEET, EVERYWHERE.** Bobby: *"keep trucks consistent."*
   Every image that shows a vehicle shows the SAME van — same make (Mercedes
   Sprinter-style high-roof panel van), same blue-hood two-tone paint, same logo.
   No white Ford Transit, no mismatched body styles across pages. Mixing van
   types or colours across the site = REJECTED.
3. **NO READABLE TEXT ON THE VANS.** The RT Olson logo mark only — no phone
   number, no website URL, no "www.rtolsonplumbing.com", no readable lettering
   beyond the mark itself. AI-rendered van text is a REJECTED image.
4. **UNIFORM: NAVY-BLUE SHIRT, GRAY PANTS, FLAG PATCH.** Bobby, verbatim:
   *"Uniforms: gray pants, blue shirts; add American flag patches on sleeves."*
   This is the crew's REAL uniform (see harvested/uniform-crew-tim.jpg): a
   navy-blue button-up work shirt with the RT Olson logo on the left chest, gray
   work pants, and a small American flag patch on the sleeve. A tan/khaki shirt,
   dark non-gray pants, or a missing flag patch = REJECTED image. This is the ONE
   uniform for the whole site — no drift between pages. See CREW-OVERRIDE.
5. **RESIDENTIAL SCENES AND GEAR ONLY.** Bobby: *"Replace any commercial-only gear
   imagery (e.g., hydrostatic pump) with appropriate residential visuals."* No
   commercial-only equipment (hydrostatic test pumps, trailer jetters, commercial
   fixtures). Toilet, faucet and fixture work happens INSIDE a residential
   bathroom on a finished floor — NEVER outdoors on a driveway or against an
   exterior wall. A toilet or fixture being serviced outside is a REJECTED image.

VAN-OVERRIDE: RT Olson's real high-roof Mercedes Sprinter van with a FULL SOLID BLUE HOOD and blue front (the entire hood is blue, never white), a white body panel crossed by a red diagonal accent stripe, and the RT Olson crossed-pipe-wrench logo mark — matching harvested/van-sprinter-blue-hood-007.jpg; carry only the logo mark with NO phone number, NO website URL and NO readable text anywhere on the vehicle, and keep every van in the site identical to this one
CREW-OVERRIDE: the technician wears a navy-blue button-up work shirt with the RT Olson logo on the left chest, gray work pants, and a small American flag patch on the sleeve, the identical uniform in every image, never a tan or khaki shirt and never dark non-gray pants
EQUIPMENT-OVERRIDE: residential service gear only in a residential setting — no commercial-only equipment such as hydrostatic test pumps or trailer-mounted jetters, and toilet, faucet and fixture work is shown inside a residential bathroom, never outdoors
LIVERY-REFERENCE: harvested/van-sprinter-blue-hood-007.jpg

---

This guide is consulted by every image-generation call (Skill 3 launch images, Skill 4 blog hero images, future image regenerations). The goal: a viewer scrolling through the site should feel like one professional photographer documented one company on one continuous service day. No stylistic drift from page to page.

The values below are auto-populated from `plan-input.json` at planning time. Per-client brand colors come from the client's logo / brand identity — NOT from the canonical starter palette. The structural conventions (camera, lens, lighting, composition) are plumbing-vertical canonical and shared across all Rank AI clients.
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
| Wide environment | 24-28mm | Hero shots, full-property exteriors, mechanical rooms, attic/crawlspace context, rooftop condenser scenes |
| Medium service | 35-50mm | Technicians performing tasks, tools in action, mid-range jobsite documentation |
| Close-up detail | 60-70mm | Pipe joints, solder work, press fittings, manifold gauges, thermostat readouts, water heater connections |
| Portrait / team | 50-70mm | Technicians, faces obscured (back, side angle, cap shadow) |

---

## Exposure Settings

### Exterior Scenes
- **Aperture**: f/4 to f/5.6 — full scene in sharp focus from foreground (technician, equipment) to background (the property, surrounding neighborhood)
- **ISO**: 100-400

### Interior Service Scenes (most common)
- **Aperture**: f/2.8 to f/4 — slight subject isolation while keeping context legible
- **ISO**: 400-1600 — under-sink cabinets, garages, mechanical closets, and crawlspaces are dim; clean noise acceptable

### Detail / Close-up
- **Aperture**: f/2.8 — shallow depth of field to isolate a press fitting, a manifold gauge set, a freshly sweated copper joint, a smart thermostat screen
- **ISO**: 100-400

### General
- Shutter speed fast enough to freeze action (1/250+ for technician movement)
- No motion blur except intentional water flow from an open valve test or steam off a hot line

---

## Lighting

- **Exterior primary**: Golden hour natural light (first 2 hours after sunrise, last 2 hours before sunset) for property and finished-install shots, bright mid-morning daylight for rooftop or condenser-pad work
- **Interior primary**: Natural daylight through windows plus a clean headlamp or work-light fill — what you'd actually see on a well-run service call. NOT overly warm or staged.
- **Mechanical-space lighting**: Garages, basements, and utility closets read slightly cooler and dimmer; the technician's work light picks out the subject. Professional and competent, not gloomy.
- **Avoid**: Direct overhead noon sun for portraits, harsh flash, heavy HDR, oversaturated processing
- **Dusk/blue hour arrival shots**: Reserved for brands whose `brand.hours` are actually 24/7 (van pulled up, technician approaching with a flashlight — the after-hours dispatch promise). For business-hours brands, keep every scene in daylight; never imply after-hours availability the brand doesn't offer.

---

## Color Palette

Per-client brand colors take priority. The values below are substituted from `plan-input.json`'s `brand` block.

| Role | Source | Value for this client |
|------|--------|----------------------|
| Primary brand color (uniforms, vehicle, signage glimpsed in shots) | `#0d1b3e` | **#0d1b3e** |
| Accent (van striping, CTAs that appear in promo shots) | `#f97316` | **#f97316** |
| Logo color (if a technician's shirt back is visible) | derived from brand logo | match RT Olson Plumbing, Heating and Air Conditioning's logo |
| Materials / texture | natural and neutral | copper and brass tones, white PVC and PEX reds/blues, galvanized grays, brushed stainless fixtures, matte sheet-metal ducting |
| Environment-specific atmospherics | regional | varies — see "Setting & Environment" below for Corona |

### Color Treatment Rules

- True-to-life, not pumped up. Service-call scenes are documentary, not Instagram travel content.
- Slight warmth on golden-hour exteriors (white balance ~5800-6200K); neutral white balance for interior service shots (~5000-5500K)
- The client's primary brand color should appear at least once per technician shot (on a work shirt, hat, van wrap, or tool bag). NOT garish — just present.
- No oversaturation. Real copper is muted orange. Real PVC is chalky white. Real ductwork is flat silver.

---

## Mood & Atmosphere

- **Professional and competent**: The viewer should feel they called the right company. No hero-shot smiles or staged enthusiasm.
- **Clean-work pride**: Homeowners let plumbers and HVAC techs into their kitchens, bathrooms, and closets. Imagery should communicate respect for the home — drop cloths down, shoe covers on, tidy tool staging, wiped-down fixtures.
- **Authentic**: Real residential and light-commercial properties in Corona and surrounding areas. Real fittings, real gauges, real water heaters and condensers.
- **Reassuring**: Even emergency scenes (a shutoff valve being closed, a burst pipe being cut out) should read as "help has arrived and it's under control," never chaos or disaster.

---

## **Technician in Uniform — Required in every people-shot**

Every image that depicts a person must show a technician in branded company workwear. This is non-negotiable for visual consistency and trust signaling.

### Uniform specifications
- **Top**: Work shirt or polo in the client's primary brand color (`#0d1b3e`). For darker brand colors (navy, deep red, charcoal), use that color directly. For lighter brand colors, render as a darker navy or charcoal work shirt with the brand color visible as logo embroidery, accent stripe, or branded cap.
- **Bottom**: Neutral work pants (charcoal, dark navy, or khaki). Subordinate to the top.
- **Branding**: RT Olson Plumbing, Heating and Air Conditioning or RT Olson Plumbing, Heating and Air Conditioning embroidered on chest or back.
- **PPE**: Safety glasses when cutting, soldering, or working overhead; gloves for drain, sewer, and gas work; knee pads for under-sink and floor-level work; respirator only where genuinely appropriate (crawlspace, attic insulation). Shoe covers visible in finished-interior scenes.
- **Footwear**: Sturdy work boots, never sneakers.

### Technician positioning
- **Faces**: Generally NOT shown clearly. Photograph from behind, side angle, or with face partially shadowed under a cap brim. This avoids generating recognizable faces and lets the image library represent any team member.
- **Hands and arms**: Fully visible is fine. Show competent technique — torch angled correctly on a copper joint, two wrenches opposing on a supply line, a manifold gauge being read, a multimeter probing a capacitor.
- **Action**: Mid-task, not posed. The technician should be doing the job, not standing for a portrait.

### Per-service technician + equipment context (REQUIRED — match the service)

The technician's workwear stays the same; their PPE and tools shift per service. Every image should be unmistakably "this is a  call," not generic.

| Service | Technician context |
|---------|---------------------|
| Emergency plumbing | Technician arriving with a tool bag or closing a main shutoff valve, calm and in control. For 24/7 brands only: dusk arrival with van lights on. |
| Burst / leaking pipe repair | Technician cutting out a damaged pipe section or pressing a new fitting; wet demarcation on drywall visible but contained, towels and bucket staged. Show the fix, not flooding. |
| Drain cleaning | Technician feeding a drum auger or hydro-jetter line into a cleanout, gloves on, protective mat under the machine. |
| Sewer line repair | Technician at an open cleanout with a sewer camera reel and monitor, or a trenchless rig staged over a neat excavation pit. Daylight. |
| Water heater repair | Technician diagnosing a tank unit — multimeter on the thermostat, anode rod inspection, gas control valve check. Garage or utility-closet setting. |
| Water heater installation | Technician fitting copper connections or securing seismic straps on a new tank or wall-hung tankless unit; old unit staged for haul-away. |
| Leak detection | Technician with acoustic listening equipment or a thermal camera against a wall or floor, focused and methodical. |
| Slab leak repair | Technician marking a floor with detection equipment, or a clean rerouted line through an access opening; protected work area. |
| Whole-house repiping | Runs of new PEX (red/blue) or copper through open stud bays, technician crimping or soldering; organized material staging. |
| Gas line services | Technician with an electronic gas sniffer at a fitting or pressure-testing a line with a gauge manometer. Serious and methodical. NEVER show flames, active leaks, or distress. |
| Sump pumps | Technician lowering a new pump into a clean sump basin or wiring a battery-backup controller; basement setting, work light bright. |
| Water softeners / filtration | Technician plumbing in a softener tank or under-sink RO system; bypass valve and media tanks visible, tidy loops of tubing. |
| Toilet / faucet / fixture | Technician setting a toilet on a fresh wax ring or seating a new faucet; towel-lined countertop, tidy tool roll. |
| Garbage disposal | Technician under a sink cabinet with a headlamp, mounting ring and disposal unit in hand; knee pad and drop cloth visible. |
| Furnace repair | Technician at an open furnace cabinet — multimeter on the control board, inspecting the flame sensor or igniter; work light angled in. |
| Furnace installation | New furnace being set and sheet-metal plenum fitted; foil tape, level, and tin snips staged; clean mechanical room. |
| Heat pumps | Technician commissioning an outdoor heat pump unit — manifold gauges connected, tablet or meter in hand; tidy line-set work. |
| AC repair | Technician at a condenser with gauges hooked to service ports, or checking a capacitor; sunny exterior side-yard setting. |
| AC installation | New condenser being set on a level pad, line set brazed or flared; vacuum pump and micron gauge staged. Recovery machine visible for changeouts. |
| Ductless mini-splits | Technician mounting an indoor wall cassette or flaring line-set connections at the outdoor unit; drill, level, and line-hide channel staged. |
| Ductwork | Technician sealing joints with mastic or hanging insulated flex duct in an attic; headlamp beam, foil surfaces catching light. |
| Indoor air quality | Technician installing a media filter cabinet, UV lamp, or bypass humidifier at the air handler; clean filter held next to a loaded one for contrast. |

---

## Setting & Environment (Corona / CA)

- **Primary setting**: Corona and surrounding CA residential and light-commercial properties
- **Local housing stock cues**: Other cities served: Riverside, Anaheim, Santa Ana, Fullerton, Ontario. — these details should appear in backgrounds and environmental context, NOT as the subject. They quietly anchor "this service call happened in Corona."
- **Regional weather / season**: Regional climate cues per primary city; adapt exterior shots to match. — affects exterior shots especially. Match the client's real region: stucco and tile-roof homes with dry golden light for inland Southern California clients, evergreens and overcast diffusion for Pacific Northwest clients. Adapt per client.
- **Time of day**: Bright daytime for standard service calls; golden hour for finished-install beauty shots; dusk arrival shots ONLY for brands whose hours are actually 24/7.

### Specifically AVOID
- **Tropical or non-regional vegetation**. Match the client's actual region.
- **Wrong housing styles**. Don't show a New England colonial for a Southern California client.
- **Recognizable faces**. Backs, side angles, shadowed-brim shots only.
- **Brand competitors in the frame**. No visible national-franchise plumbing or HVAC trucks or branding.
- **AI-obvious artifacts**: distorted text on tool labels, melted hand geometry, impossible pipe routing, gauges with nonsense dials, extra fingers. If a generated image shows any of these, regenerate.
- **Stock-photo enthusiasm**: no thumbs-up, no smiling-at-camera, no chest-out hero poses.
- **Overly clean / staged scenes**: a real service call has a deployed tool bag, a drop cloth, staged fittings — organized, not chaotic. Sterile spaces look fake; messy ones look unprofessional.
- **Unsafe practices**: no torch work without protection near combustibles, no ungloved sewage contact, no missing safety glasses while cutting, no ladders on uneven ground. Safety violations destroy trust.
- **Children, pets, vulnerable people**. Service imagery should feel adult and professional.
- **Disaster or distress scenes**: no rooms underwater, no geysering pipes, no flames, no visible gas clouds, no panicked homeowners. Emergency services show the professional response and the fixed result, not the catastrophe. Gas-line imagery in particular must never dramatize a leak.

---

## Composition Rules

1. **Rule of thirds**: Place the focal point (technician, tool, the workpiece) at the intersection of thirds
2. **Leading lines**: Use pipe runs, line sets, duct trunks, hallway sightlines, and driveway edges to guide the eye
3. **Foreground interest**: A tool roll, a fitting bag, a manifold gauge in foreground gives depth
4. **Layered depth**: Foreground (subject), middle (equipment / materials / context), background (the home / mechanical space)
5. **Horizon placement**: Interior: usually irrelevant. Exterior: place on lower third to emphasize the property or upper third to emphasize the work in progress.
6. **Negative space**: Allow breathing room. Don't cram every inch. The LEFT THIRD of hero-aspect shots should be compositionally calmer so headline text can overlay cleanly.

---

## Image Categories Needed (per client launch)

This list drives the image generation plan. Skill 3 (initial scaffold) generates the hero. Skill 4 (blog routine) generates blog hero + inline images per post. Service and area images are filled in over time.

### Brand-level
- [ ] Homepage hero — **DEFAULT: branded small-fleet scene.** A matched fleet of 3-5 company service vans (and/or utility-bed pickups typical of the trade) in one identical livery built from the client's brand colors (primary color panel/wrap + accent stripe), staged in front of a regional residential property, golden-hour light, editorial-photography look. Livery rules: one small stylized brand mark/wordmark per vehicle only — NO phone numbers, NO website URLs, NO license/certification numbers, NO other readable text (AI-rendered text artifacts fail review). Composition: fleet in the center/right two-thirds; LEFT THIRD calm (open sky/street) for headline overlay. Alternative if the operator prefers: golden-hour finished-install scene with technician + single branded van.
- [ ] Logo placement test image (no actual logo — narrative shot with brand color on technician workwear)
- [ ] OG / social-share card (1200×630) — usually a crop or variant of the hero

### Service landing pages (one image per selected service)
- [ ] water-heater-repair — see Per-Service table above
- [ ] drain-cleaning
- [ ] ac-repair
- [ ] furnace-repair
- [ ] (continue for each of Emergency Plumbing, Leak Detection, Drain Cleaning, Water Heater Repair, Water Heater Installation and Replacement, Toilet, Faucet and Fixture Services, Garbage Disposal Repair and Installation, Water Softeners and Filtration Systems, Air Conditioning Repair, Furnace Repair, Indoor Air Quality Services)

### Service area pages (one image per city served)
- [ ] Corona hero — exterior shot, regional housing stock, evocative of the city
- [ ] Each additional service-area city — same pattern, regional cues per city

### Blog post heroes
- [ ] Generated on-demand by Skill 4 per post, contextually matching the post's topic + the post's primary service tag

### Inline blog images (optional, when budget allows)
- [ ] 1-2 supporting images per blog post, technical detail or process illustration; diagnostic-tool close-ups and before/after fixture pairs work especially well for plumbing topics

---

## How this guide is used

1. **Skill 4 (blog routine)** reads this file before every Nano Banana call. The prompt to Nano Banana includes the relevant service/category context block above PLUS the scene-specific description.
2. **Manual regeneration** (e.g., to refresh a stale image) follows the same path — read this guide, generate with consistent style.
3. **Updating the guide** (e.g., the client provides updated brand colors, or you want to shift the lighting policy): edit this file in `clients//image-style-guide.md`, then re-run image generation for any pages where consistency matters. Existing images can stay or be regenerated based on cost vs benefit.

---

## Style guide version

This guide is generated from `templates/plumbing/image-style-guide.template.md` v1.1 (2026-07-11: added Standing Brand Rules — real vehicle logos, single declared uniform color, harvest-first). When the canonical template updates, existing clients keep their pinned version unless explicitly regenerated. Bump the version + add a changelog entry when changing structural rules (e.g., adding new mandatory PPE conventions).
