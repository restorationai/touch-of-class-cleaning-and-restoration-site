# Onsite Audit Agent (Rank AI System 3) — Construction Vertical

**Inherits the full methodology from `templates/restoration/prompts/onsite-audit.md`.** Read that file first — all steps, scoring thresholds, regression detection, state schema, and report format are identical. This file documents only construction-vertical differences.

---

## Construction-specific differences

### Money page archetypes (Step 1, Mode B URL selection)

Construction sites have one additional high-value archetype not present in restoration:

| Slot | Archetype | Notes |
|---|---|---|
| 1 | `home` | Homepage |
| 2 | `services-hub` | All services overview |
| 3 | `service-landing` | Top revenue service (e.g., remodeling or decks) |
| 4 | `service-landing` | Second top service |
| 5 | `gallery` | Project portfolio — critical trust signal for construction buyers |
| 6 | `contact` | Conversion page |

If `gallery` archetype is not in `url-plan.json`, substitute the next highest-traffic service-landing page.

### Schema types to check (Step 4, on-page audit)

For construction clients, flag missing or incorrect schema:
- Primary: `HomeAndConstructionBusiness` or `GeneralContractor` (both valid; prefer `GeneralContractor` if the client does general contracting)
- Secondary: `LocalBusiness` with appropriate `@type`
- `hasOfferCatalog` listing service types
- `areaServed` with service city names
- `review` / `aggregateRating` if reviews are present

Flag as an amber issue if the schema uses only generic `LocalBusiness` without a construction-specific subtype.

### Gallery page audit notes

The gallery / project portfolio page is uniquely important for construction clients — buyers make hire/no-hire decisions based on past work. Flag these issues specifically for gallery pages:

- Missing `ImageObject` schema on project photos
- Alt text that doesn't describe the project (e.g., alt="image1.jpg" instead of alt="Deck addition on brick ranch home in Madison AL")
- Slow image loading on gallery (LCP > 3s is common and almost always from unoptimized project photos)
- No project descriptions / captions (missed keyword opportunity)

### Staging noindex caveat

Same as restoration: if `live_origin_source == staging` and `x-robots-tag: noindex` is detected, exclude SEO scores from the verdict. Log the caveat clearly.

---

## Everything else

Follow `templates/restoration/prompts/onsite-audit.md` exactly:
- Pre-flight steps (client record validation, live origin determination, URL list)
- Lighthouse scan via `mcp__dataforseo__on_page_lighthouse` (mobile strategy, `full_data: true`)
- On-page audit via `mcp__dataforseo__on_page_instant_pages`
- Per-URL verdicts and site-level rollup
- Regression detection vs prior `onsite-audit.json`
- State file write at `clients/{slug}/onsite-audit.json`
- Markdown report at `clients/{slug}/audit-runs/{YYYY-MM-DD}-onsite-audit.md`
- Client record update (`audit.last_audit_at`, `audit.last_audit_verdict`, `audit.last_audit_report_path`)
