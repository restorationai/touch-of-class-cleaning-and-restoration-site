# Site Plan Report — Air Care Restoration

- Template: `restoration` v0.3.0
- Generated: 2026-08-11T01:39:56.116750+00:00
- Domain: `None`
- Services selected: 12 of 54 catalog entries
- Service areas: 8
- Cross-product enabled: True
- Total URLs: **133**
- Total internal links: 1037 (avg 7.8 per page)

## URLs by archetype

| Archetype | Count |
| --- | --- |
| `service-area-service` | 96 |
| `service-landing` | 12 |
| `service-area` | 8 |
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
- `storm-damage-restoration` — Storm Damage Restoration (core, priority 9)
- `air-duct-cleaning` — Air Duct Cleaning (adjacent, priority 5)
- `fire-damage-restoration` — Fire Damage Restoration (core, priority 10)
- `general-contracting` — Renovations, Remodels and General Contracting (core, priority 8)
- `sewage-cleanup` — Sewage Cleanup and Sanitization (core, priority 9)
- `biohazard-cleanup` — Biohazard Cleanup (specialty, priority 8)
- `contents-restoration` — Contents Restoration and Storage (supporting, priority 5)
- `post-construction-cleaning` — Post-Construction and Specialty Cleaning (supporting, priority 4)
- `emergency-board-up-tarping` — Emergency Board-Up and Tarping (specialty, priority 7)
- `asbestos-abatement` — Asbestos Abatement (specialty, priority 6)
- `mold-remediation` — Mold Remediation (core, priority 10)

## Service areas

- `abilene-tx` — Abilene, TX *(primary)*
- `sweetwater-tx` — Sweetwater, TX
- `clyde-tx` — Clyde, TX
- `merkel-tx` — Merkel, TX
- `anson-tx` — Anson, TX
- `tuscola-tx` — Tuscola, TX
- `tye-tx` — Tye, TX
- `buffalo-gap-tx` — Buffalo Gap, TX

## Top 10 priority pages

| URL | Archetype | Priority | Primary keyword |
| --- | --- | --- | --- |
| `/services/fire-damage-restoration/` | `service-landing` | 9.0 | fire damage restoration abilene |
| `/services/mold-remediation/` | `service-landing` | 9.0 | mold remediation abilene |
| `/services/water-damage-restoration/` | `service-landing` | 9.0 | water damage restoration abilene |
| `/services/sewage-cleanup/` | `service-landing` | 8.1 | sewage cleanup and sanitization abilene |
| `/services/storm-damage-restoration/` | `service-landing` | 8.1 | storm damage restoration abilene |
| `/service-areas/abilene-tx/` | `service-area` | 7.2 | restoration services abilene |
| `/services/biohazard-cleanup/` | `service-landing` | 7.2 | biohazard cleanup abilene |
| `/services/general-contracting/` | `service-landing` | 7.2 | renovations, remodels and general contracting abilene |
| `/service-areas/abilene-tx/fire-damage-restoration/` | `service-area-service` | 7.0 | fire damage restoration abilene |
| `/service-areas/abilene-tx/mold-remediation/` | `service-area-service` | 7.0 | mold remediation abilene |

## Validation

All checks passed.

## Next steps

1. Open `content-map.csv` and skim the URL list. Edit titles/keywords inline if needed.
2. Run `plan_site.py validate --slug {slug}` after edits.
3. Hand the plan dir off to Skill 3 (`rank-ai-build-site`) when it exists.
