# TDI Builders: Image Style Guide

This guide is consulted by every image-generation call (Skill 3 launch images, Skill 4 blog hero images, future image regenerations). The goal: a viewer scrolling through the site should feel like one professional photographer documented one company on one continuous project. No stylistic drift from page to page.

The values below are auto-populated from `plan-input.json` at planning time. Per-client brand colors come from the client's logo / brand identity — NOT from the canonical starter palette. The structural conventions (camera, lens, lighting, composition) are construction-vertical canonical and shared across all Rank AI clients.
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
| Wide environment | 24-28mm | Hero shots, full-property exteriors, framing going up on a jobsite, finished remodel reveals |
| Medium service | 35-50mm | Crew members performing tasks, tools in action, mid-range jobsite documentation |
| Close-up detail | 60-70mm | Joinery, tile work, fastener patterns, finish carpentry, material texture shots |
| Portrait / team | 50-70mm | Crew members, faces obscured (back, side angle, hard hat shadow) |

---

## Exposure Settings

### Exterior Scenes
- **Aperture**: f/4 to f/5.6 — full scene in sharp focus from foreground (crew member, materials) to background (the property, surrounding neighborhood)
- **ISO**: 100-400

### Interior Build / Remodel Scenes (most common)
- **Aperture**: f/2.8 to f/4 — slight subject isolation while keeping context legible
- **ISO**: 400-1600 — interiors mid-remodel often have mixed light; clean noise acceptable

### Detail / Close-up
- **Aperture**: f/2.8 — shallow depth of field to isolate joinery, tile layouts, level readings, cabinet hardware, fresh paint lines
- **ISO**: 100-400

### General
- Shutter speed fast enough to freeze action (1/250+ for crew movement)
- No motion blur except intentional sawdust in a shaft of light or a nail gun mid-cycle

---

## Lighting

- **Exterior primary**: Golden hour natural light (first 2 hours after sunrise, last 2 hours before sunset) for finished-project shots, and bright mid-morning daylight for active-jobsite framing shots
- **Interior primary**: Natural daylight through window openings plus clean work-light fill — what you'd actually see on a well-run remodel in progress. NOT overly warm or staged.
- **Finished-space lighting**: Bright, airy, welcoming. Completed kitchens, baths, and decks should feel like the homeowner's reward — warm and lived-in, not sterile showroom.
- **Avoid**: Direct overhead noon sun for portraits, harsh flash, heavy HDR, oversaturated processing
- **Daytime only**: Construction is daytime work. No night scenes, no dusk "arrival" urgency shots — this vertical sells planning and craftsmanship, not rapid response.

---

## Color Palette

Per-client brand colors take priority. The values below are substituted from `plan-input.json`'s `brand` block.

| Role | Source | Value for this client |
|------|--------|----------------------|
| Primary brand color (uniforms, vehicle, signage glimpsed in shots) | `#0080C4` | **#0080C4** |
| Accent (jobsite signage, CTAs that appear in promo shots) | `#0080C4` | **#0080C4** |
| Logo color (if a crew member's shirt back is visible) | derived from brand logo | match TDI Builders's logo |
| Materials / texture | natural and neutral | warm lumber tones, cool concrete grays, real drywall whites, natural stone and tile textures |
| Environment-specific atmospherics | regional | varies — see "Setting & Environment" below for Sacramento |

### Color Treatment Rules

- True-to-life, not pumped up. Jobsite scenes are documentary, not Instagram travel content.
- Slight warmth on golden-hour exteriors (white balance ~5800-6200K); neutral white balance for interior build shots (~5000-5500K)
- The client's primary brand color should appear at least once per crew shot (on a work shirt, hat, vehicle wrap, or jobsite sign). NOT garish — just present.
- No oversaturation. Real framing lumber is muted tan. Real concrete is flat gray. Real primer is chalky white.

---

## Mood & Atmosphere

- **Professional and competent**: The viewer should feel they hired the right builder. No hero-shot smiles or staged enthusiasm.
- **Craftsmanship and care**: Homeowners are making a big investment. Imagery should communicate precision — clean cuts, square corners, tidy jobsites, protected floors.
- **Authentic**: Real residential and commercial properties in Sacramento and surrounding areas. Real materials. Real framing, real tile work, real finish carpentry.
- **Optimistic**: Construction is about what's being created. Before/during/after progressions, framing rising against a blue sky, a finished kitchen catching the morning light.

---

## **Crew Member in Uniform — Required in every people-shot**

Every image that depicts a person must show a crew member in branded company workwear. This is non-negotiable for visual consistency and trust signaling.

### Uniform specifications
- **Top**: Work shirt or polo in the client's primary brand color (`#0080C4`). For darker brand colors (navy, deep red, charcoal), use that color directly. For lighter brand colors, render as a darker navy or charcoal work shirt with the brand color visible as logo embroidery, accent stripe, or branded hat.
- **Bottom**: Neutral work pants (charcoal, dark navy, or khaki). Subordinate to the top.
- **Branding**: TDI Builders or TDI Builders embroidered on chest or back.
- **PPE**: Hard hat on active framing/roofing/demolition scenes, safety glasses when cutting, gloves for material handling, ear protection near loud tools. Finish-work scenes (painting, trim, cabinet install) can be hard-hat-free.
- **Footwear**: Sturdy work boots, never sneakers.

### Crew positioning
- **Faces**: Generally NOT shown clearly. Photograph from behind, side angle, or with face partially in shadow under a hard hat brim or cap. This avoids generating recognizable faces and lets the image library represent any team member.
- **Hands and arms**: Fully visible is fine. Show competent technique — reading a tape measure, checking a level, running a circular saw with proper grip, rolling paint with even pressure.
- **Action**: Mid-task, not posed. The crew member should be doing the job, not standing for a portrait.

### Per-service crew + equipment context (REQUIRED — match the service)

The crew member's workwear stays the same; their PPE and tools shift per service. Every image should be unmistakably "this is a  job," not generic.

| Service | Crew context |
|---------|---------------|
| Home remodeling | Crew member mid-build on a kitchen, bath, or living-area remodel. Cabinets staged, floor protection down, tool belt on. |
| Kitchen remodeling | Crew member setting cabinets, templating countertops, or installing a tile backsplash. New appliances boxed in background. |
| Bathroom remodeling | Crew member setting wall tile, installing a vanity, or waterproofing a shower pan. Tile spacers and layout lines visible. |
| New home construction | Crew member on a framing deck — nail gun, framing square, engineered lumber. Blue sky behind the rising structure. |
| General contracting / renovations | Crew member reviewing plans on site, marking layout lines, or coordinating material staging. Clipboard-and-tape-measure vibe. |
| Room additions / home additions | New framing tied into an existing house — the seam between old siding and new sheathing visible. Crew member at the junction. |
| Roofing | Crew member on a roof installing shingles or metal panels, harness and fall protection visible, ladder staged. Daytime, dry conditions. |
| Siding and gutters | Crew member installing lap siding or hanging gutter runs, scaffolding or ladder visible, siding stack on sawhorses. |
| Decks, pergolas and fences | Crew member setting deck boards, checking post plumb, or driving fence pickets. Fresh lumber, string lines, post-hole tools. |
| Painting and trim | Crew member cutting in a clean line, rolling a wall, or nailing crown molding. Drop cloths, taped edges, tidy staging. |
| Garage / ADU construction | Small-structure framing or finished exterior; concrete slab, framed walls, or completed unit with clean lines. |
| Basement finishing | Crew member framing interior walls or hanging drywall in a basement, work lights bright, insulation visible. |
| Windows and doors | Crew member setting a window into a framed opening — shims, level held to the frame, flashing tape visible. |
| Drywall and interior finishing | Crew member hanging board, taping seams, or sanding with a pole sander. Fine white dust in a shaft of window light. |
| Flooring installation | Crew member laying hardwood, laminate, or tile — kneepads, spacers, flooring nailer or trowel in use. |
| Concrete and flatwork | Crew member screeding or floating fresh concrete, forms staked, wheelbarrow or pump line in scene. |
| Commercial construction | Crew member in a scaled-up scene — steel studs, suspended ceiling grid, tenant-improvement buildout. Hard hats and vests. |
| Exterior remodeling | Crew member on porch, facade, or trim work — the house visibly mid-transformation, materials staged neatly. |
| Water damage restoration (repair/rebuild) | Crew member REBUILDING after a leak — replacing drywall, installing new flooring, repainting a repaired ceiling. Show the repair, not standing water or extraction gear. |
| Storm damage restoration (repair/rebuild) | Crew member replacing damaged shingles or siding on a dry, calm day. Show the repair in progress and the restored result — never an active storm or night tarping. |
| Mold remediation (during renovation) | Crew member in N95 respirator and gloves removing affected drywall behind clean poly sheeting, then the rebuilt, repainted space. Clinical and controlled, not alarming. |

---

## Setting & Environment (Sacramento / CA)

- **Primary setting**: Sacramento and surrounding CA residential and commercial properties
- **Local housing stock cues**: Other cities served: Roseville, Elk Grove, Folsom, Modesto, Rocklin. — these details should appear in backgrounds and environmental context, NOT as the subject. They quietly anchor "this was built in Sacramento."
- **Regional weather / season**: Regional climate cues per primary city; adapt exterior shots to match. — affects exterior shots especially. Match the client's real region: valley oak canopies and golden summer light for Central Valley clients, evergreens and cedar tones for Pacific Northwest clients. Adapt per client.
- **Time of day**: Bright daytime for active jobsites; golden hour reserved for finished-project beauty shots.

### Specifically AVOID
- **Tropical or non-regional vegetation**. Match the client's actual region.
- **Wrong housing styles**. Don't show a Texas ranch home for a Seattle client.
- **Recognizable faces**. Backs, side angles, shadowed-brim shots only.
- **Brand competitors in the frame**. No visible national-builder or franchise-contractor trucks or branding.
- **AI-obvious artifacts**: distorted text on tool labels, melted hand geometry, impossible tool shapes, extra fingers, physically wrong framing (studs that don't land on plates). If a generated image shows any of these, regenerate.
- **Stock-photo enthusiasm**: no thumbs-up, no smiling-at-camera, no chest-out hero poses.
- **Overly clean / staged jobsites**: a real active site has sawdust, staged materials, deployed tools — but organized, not chaotic. Sterile spaces look fake; messy sites look unprofessional.
- **Unsafe practices**: no missing fall protection on roofs, no bare feet, no crew members under suspended loads, no ladders on uneven ground. Safety violations destroy trust.
- **Children, pets, vulnerable people**. Jobsite imagery should feel adult and professional.
- **Disaster or distress scenes**: no flooding, no fire, no night-crisis framing, no storm-in-progress. Damage-repair services show the repair and the finished result, not the catastrophe.

---

## Composition Rules

1. **Rule of thirds**: Place the focal point (crew member, tool, the workpiece) at the intersection of thirds
2. **Leading lines**: Use joists, stud bays, deck boards, rooflines, hallway sightlines to guide the eye
3. **Foreground interest**: A tape measure, a stack of lumber, a paint tray in foreground gives depth
4. **Layered depth**: Foreground (subject), middle (materials / tools / context), background (the property / structure)
5. **Horizon placement**: Interior: usually irrelevant. Exterior: place on lower third to emphasize the structure or upper third to emphasize the work in progress.
6. **Negative space**: Allow breathing room. Don't cram every inch. The LEFT THIRD of hero-aspect shots should be compositionally calmer so headline text can overlay cleanly.

---

## Image Categories Needed (per client launch)

This list drives the image generation plan. Skill 3 (initial scaffold) generates the hero. Skill 4 (blog routine) generates blog hero + inline images per post. Service and area images are filled in over time.

### Brand-level
- [ ] Homepage hero — **DEFAULT: branded small-fleet scene.** A matched fleet of 3-5 company vehicles (pickup trucks, box trucks, and/or cargo vans typical of the trade) in one identical livery built from the client's brand colors (primary color panel/wrap + accent stripe), staged in front of a finished or in-progress project matching the client's region, golden-hour light, editorial-photography look. Livery rules: one small stylized brand mark/wordmark per vehicle only — NO phone numbers, NO website URLs, NO license/certification numbers, NO other readable text (AI-rendered text artifacts fail review). Composition: fleet in the center/right two-thirds; LEFT THIRD calm (open sky/street) for headline overlay. Alternative if the operator prefers: golden-hour finished project with crew member + single branded truck.
- [ ] Logo placement test image (no actual logo — narrative shot with brand color on crew workwear)
- [ ] OG / social-share card (1200×630) — usually a crop or variant of the hero

### Service landing pages (one image per selected service)
- [ ] home-remodeling — see Per-Service table above
- [ ] roofing
- [ ] decks-pergolas-fences
- [ ] new-construction
- [ ] (continue for each of Commercial Construction and Tenant Improvements, Renovations, Remodels and General Contracting, New Home Construction, Fire and Smoke Damage Rebuilding, Water Damage Restoration, Storm Damage Restoration, Mold Remediation, Home Remodeling, Kitchen Remodeling, Bathroom Remodeling, Garage Construction, Room Additions and Home Additions, 24/7 Emergency Water Cleanup, Basement Sewage Cleanup, Bathroom Remodeler, Carpet & Upholstery Cleaning, Carpet Water Extraction, General Contractor, Post-Construction & Specialty Cleaning)

### Service area pages (one image per city served)
- [ ] Sacramento hero — exterior shot, regional housing stock, evocative of the city
- [ ] Each additional service-area city — same pattern, regional cues per city

### Blog post heroes
- [ ] Generated on-demand by Skill 4 per post, contextually matching the post's topic + the post's primary service tag

### Inline blog images (optional, when budget allows)
- [ ] 1-2 supporting images per blog post, technical detail or process illustration; before/after pairs work especially well for remodel topics

---

## How this guide is used

1. **Skill 4 (blog routine)** reads this file before every Nano Banana call. The prompt to Nano Banana includes the relevant service/category context block above PLUS the scene-specific description.
2. **Manual regeneration** (e.g., to refresh a stale image) follows the same path — read this guide, generate with consistent style.
3. **Updating the guide** (e.g., the client provides updated brand colors, or you want to shift the lighting policy): edit this file in `clients//image-style-guide.md`, then re-run image generation for any pages where consistency matters. Existing images can stay or be regenerated based on cost vs benefit.

---

## Style guide version

This guide is generated from `templates/construction/image-style-guide.template.md` v1.1 (2026-07-11: added Standing Brand Rules — real vehicle logos, single declared uniform color, harvest-first). When the canonical template updates, existing clients keep their pinned version unless explicitly regenerated. Bump the version + add a changelog entry when changing structural rules (e.g., adding new mandatory PPE conventions).
