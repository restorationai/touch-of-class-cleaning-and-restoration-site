# ProBrite Gen: Image Style Guide

This guide is consulted by every image-generation call (Skill 4 blog hero images, future image regenerations). The goal: a viewer scrolling through the site should feel like one professional photographer documented one company on one continuous job.

ProBrite Gen serves the Houston, TX metro across two adjacent verticals — restoration (water, mold, sewage) and plumbing-installation (water heater, water softener). Image style should feel cohesive across both.

---

## Brand colors

- **Primary blue**: `#1E5AD4` — calls-to-action, link accents, primary buttons
- **Navy**: `#0D1B3E` — headers, hero overlays, footer
- **Accent orange**: `#F97316` — emphasis, conversion buttons (phone CTA)

When generated images include uniformed workers, branded equipment, or graphical elements, lean on the primary blue + navy combination. Reserve orange for small graphic accents only — never as the dominant color in a hero image.

---

## Photography style (canonical, shared with all Rank AI restoration clients)

Full reference: see `clients/narestco/image-style-guide.md`. Same canonical photographic conventions apply — Sony A7 IV equivalent, 24-70mm focal range, natural overcast or golden-hour lighting, environmental wide shots for heroes, medium shots for workers-in-action.

**Climate adjustment for Houston:** narestco is Pacific Northwest (drizzle, overcast). Houston is humid subtropical (bright sun, occasional storms, lush green vegetation). When generating outdoor shots:

- Lighting: warmer, slightly higher contrast vs the PNW look
- Vegetation: live oaks, magnolias, palmettos (NOT firs or cedars)
- Architecture: brick, stucco, brick-veneer over wood frame (typical Texas single-family — NOT craftsman cedar siding)
- Skies: bright with cumulus, occasionally thunderhead-tinged

---

## Worker-in-uniform requirements (when applicable)

Same as narestco's spec:

- Always show workers in branded uniform if a person is in the shot
- Uniform: navy or blue work shirt, dark pants, work boots
- Hard hat when on a damaged jobsite; no hard hat when in a residential install
- Workers should be MID-TASK (drying with industrial fan, installing a heater, holding a moisture meter) — never posed/static
- Faces obscured or at angle (privacy + future-proofing the asset library)
- Equipment visible should be IICRC-grade where relevant

For plumbing-installation services (water heater, water softener), workers should NOT wear hard hats. Use a tool belt + work gloves + light branded shirt. The setting is a clean utility room or garage, NOT a damaged jobsite.

---

## Subject matter by service vertical

| Service | Hero subject | Allowed inline subjects |
| --- | --- | --- |
| water-damage-restoration | Worker drying flooded room with industrial fans + dehumidifier | Moisture meter on baseboard; air mover row; wet vacuum extraction |
| mold-remediation | Worker in PPE inspecting wall cavity with flashlight | Containment zip-wall; HEPA-filtered air scrubber; mold sample sealed in bag |
| sewage-backup-cleanup | Worker in chest waders + respirator with industrial pump | (handle delicately — never show actual sewage, focus on cleanup equipment) |
| water-heater-installation | Two technicians installing tankless or tank water heater in a utility room | Pipe-cutter close-up; flux + soldering iron; flue venting; expansion tank |
| water-softener-installation | Technician programming a whole-house softener control head | Salt-fill, brine tank, bypass valve, water-quality test |

---

## Composition + color grading

- Hero images: 2:1 horizontal (1920×960 minimum for blog heroes, 1200×630 for OG)
- Inline images: 4:3 horizontal
- Color grading: slight desaturation, lifted shadows, neutral white balance — DON'T grade toward the brand-blue tint. Brand color shows up through the worker's uniform + branded equipment in-frame, not via a digital grade.

---

## Hard rules

- Real-looking only. No cartoonish or illustrated styles.
- No stock-photo "happy people pointing at a clipboard" tropes.
- No before/after split-screens in heroes.
- Always WebP output (PNG → WebP conversion in `image_utils.py` at upload time).
- Per-WebP file size cap: 200KB for blog heroes (probritegen pages already have a page-weight problem — keep new assets disciplined).
