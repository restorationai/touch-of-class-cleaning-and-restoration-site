# Site Plan Report — DISS Restoration

- Template: `restoration` v0.3.0
- Generated: 2026-08-05T05:08:05.790165+00:00
- Domain: `None`
- Services selected: 13 of 54 catalog entries
- Service areas: 9
- Cross-product enabled: True
- Total URLs: **156**
- Total internal links: 1237 (avg 7.9 per page)

## URLs by archetype

| Archetype | Count |
| --- | --- |
| `service-area-service` | 117 |
| `service-landing` | 13 |
| `service-area` | 9 |
| `blog-post` | 8 |
| `legal` | 3 |
| `home` | 1 |
| `services-hub` | 1 |
| `service-areas-hub` | 1 |
| `blog-index` | 1 |
| `about` | 1 |
| `contact` | 1 |

## Selected services

- `water-damage-restoration` — Water Damage Restoration (core, priority 10)
- `fire-damage-restoration` — Fire Damage Restoration (core, priority 10)
- `mold-remediation` — Mold Remediation (core, priority 10)
- `storm-damage-restoration` — Storm Damage Restoration (core, priority 9)
- `general-contracting` — Renovations, Remodels and General Contracting (core, priority 8)
- `sewage-cleanup` — Sewage Cleanup and Sanitization (core, priority 9)
- `biohazard-cleanup` — Biohazard Cleanup (specialty, priority 8)
- `contents-restoration` — Contents Restoration and Storage (supporting, priority 5)
- `asbestos-abatement` — Asbestos Abatement (specialty, priority 6)
- `emergency-board-up-tarping` — Emergency Board-Up and Tarping (specialty, priority 7)
- `air-duct-cleaning` — Air Duct Cleaning (adjacent, priority 5)
- `carpet-cleaning` — Carpet Cleaning (adjacent, priority 4)
- `post-construction-cleaning` — Post-Construction and Specialty Cleaning (supporting, priority 4)

## Service areas

- `youngstown-oh` — Youngstown, OH *(primary)*
- `warren-oh` — Warren, OH
- `boardman-oh` — Boardman, OH
- `austintown-oh` — Austintown, OH
- `niles-oh` — Niles, OH
- `girard-oh` — Girard, OH
- `struthers-oh` — Struthers, OH
- `canfield-oh` — Canfield, OH
- `hubbard-oh` — Hubbard, OH

## Top 10 priority pages

| URL | Archetype | Priority | Primary keyword |
| --- | --- | --- | --- |
| `/services/fire-damage-restoration/` | `service-landing` | 9.0 | fire damage restoration youngstown |
| `/services/mold-remediation/` | `service-landing` | 9.0 | mold remediation youngstown |
| `/services/water-damage-restoration/` | `service-landing` | 9.0 | water damage restoration youngstown |
| `/services/sewage-cleanup/` | `service-landing` | 8.1 | sewage cleanup and sanitization youngstown |
| `/services/storm-damage-restoration/` | `service-landing` | 8.1 | storm damage restoration youngstown |
| `/service-areas/youngstown-oh/` | `service-area` | 7.2 | restoration services youngstown |
| `/services/biohazard-cleanup/` | `service-landing` | 7.2 | biohazard cleanup youngstown |
| `/services/general-contracting/` | `service-landing` | 7.2 | renovations, remodels and general contracting youngstown |
| `/service-areas/austintown-oh/fire-damage-restoration/` | `service-area-service` | 7.0 | fire damage restoration austintown |
| `/service-areas/austintown-oh/mold-remediation/` | `service-area-service` | 7.0 | mold remediation austintown |

## Validation

All checks passed.

## Next steps

1. Open `content-map.csv` and skim the URL list. Edit titles/keywords inline if needed.
2. Run `plan_site.py validate --slug {slug}` after edits.
3. Hand the plan dir off to Skill 3 (`rank-ai-build-site`) when it exists.
