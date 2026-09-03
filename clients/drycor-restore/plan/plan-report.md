# Site Plan Report — DRYCOR RESTORE

- Template: `restoration` v0.3.0
- Generated: 2026-09-03T11:18:11.648103+00:00
- Domain: `None`
- Services selected: 9 of 60 catalog entries
- Service areas: 9
- Cross-product enabled: True
- Total URLs: **106**
- Total internal links: 809 (avg 7.6 per page)

## URLs by archetype

| Archetype | Count |
| --- | --- |
| `service-area-service` | 72 |
| `service-landing` | 9 |
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
- `fire-damage-restoration` — Fire Damage Restoration (core, priority 10)
- `mold-remediation` — Mold Remediation (core, priority 10)
- `contents-restoration-storage` — Contents Restoration & Storage (adjacent, priority 5)
- `general-contracting` — Renovations, Remodels and General Contracting (core, priority 8)
- `storm-damage-restoration` — Storm Damage Restoration (core, priority 9)
- `water-cleanup` — Water Cleanup (core, priority 9)
- `sewage-cleanup` — Sewage Cleanup and Sanitization (core, priority 9)
- `emergency-board-up-tarping` — Emergency Board-Up and Tarping (specialty, priority 7)

## Service areas

- `thonotosasa-fl` — Thonotosasa, FL *(primary)*
- `tampa-fl` — Tampa, FL
- `brandon-fl` — Brandon, FL
- `plant-city-fl` — Plant City, FL
- `temple-terrace-fl` — Temple Terrace, FL
- `lakeland-fl` — Lakeland, FL
- `seffner-fl` — Seffner, FL
- `zephyrhills-fl` — Zephyrhills, FL
- `dover-fl` — Dover, FL

## Top 10 priority pages

| URL | Archetype | Priority | Primary keyword |
| --- | --- | --- | --- |
| `/services/fire-damage-restoration/` | `service-landing` | 9.0 | fire damage restoration thonotosasa |
| `/services/mold-remediation/` | `service-landing` | 9.0 | mold remediation thonotosasa |
| `/services/water-damage-restoration/` | `service-landing` | 9.0 | water damage restoration thonotosasa |
| `/services/sewage-cleanup/` | `service-landing` | 8.1 | sewage cleanup and sanitization thonotosasa |
| `/services/storm-damage-restoration/` | `service-landing` | 8.1 | storm damage restoration thonotosasa |
| `/services/water-cleanup/` | `service-landing` | 8.1 | water cleanup thonotosasa |
| `/services/general-contracting/` | `service-landing` | 7.2 | renovations, remodels and general contracting thonotosasa |
| `/service-areas/brandon-fl/fire-damage-restoration/` | `service-area-service` | 7.0 | fire damage restoration brandon |
| `/service-areas/brandon-fl/mold-remediation/` | `service-area-service` | 7.0 | mold remediation brandon |
| `/service-areas/brandon-fl/water-damage-restoration/` | `service-area-service` | 7.0 | water damage restoration brandon |

## Validation

All checks passed.

## Next steps

1. Open `content-map.csv` and skim the URL list. Edit titles/keywords inline if needed.
2. Run `plan_site.py validate --slug {slug}` after edits.
3. Hand the plan dir off to Skill 3 (`rank-ai-build-site`) when it exists.
