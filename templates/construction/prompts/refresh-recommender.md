# Refresh Recommender (Rank AI System 4 Layer 2) — Construction Vertical

**Inherits the full methodology from `templates/restoration/prompts/refresh-recommender.md`.** Read that file first — all steps, action classifications, dedup logic, state schema, and report format are identical. This file documents only construction-vertical differences.

---

## Construction-specific differences

### Money page definition (Step Pre-flight, Step 2)

Construction money pages include one additional archetype vs restoration:

- `home`
- `contact`
- `services-hub`
- `service-landing`
- `service-area`
- `gallery` — project portfolio pages are high-conversion for construction; treat as money pages for refresh priority

### Refresh priority signals for construction content

Construction content ages differently from restoration content:

**Refresh signals that matter more in construction:**
- **Cost/pricing posts** — construction material and labor costs shift with lumber prices, supply chain, and inflation. Any cost guide post older than 12 months should be flagged `stale_12mo` regardless of other signals. Add a note: "Construction pricing posts decay faster than general content — update cost figures annually."
- **Product/material posts** — posts about specific products (e.g., "Trex vs TimberTech") should be checked if the products have had major updates. Flag if post is > 18 months old.
- **Gallery/portfolio pages** — if gallery hasn't been updated in 6+ months, flag as `aging` with action `refresh` (add new project photos). Fresh project photos are a strong trust signal.

**Refresh signals that matter less in construction:**
- Emergency response timelines (not applicable)
- Insurance claim procedures (not applicable unless client has a restoration vertical too)

### Action selection notes

Same four actions as restoration (`refresh`, `audit_then_decide`, `request_indexing` [v2], `fix_canonical` [v2]).

For construction-specific context in `reasoning` fields:
- Gallery pages: "Project portfolio not updated in {N} months — new project photos improve buyer trust and provide fresh content signals."
- Cost guides: "Construction cost data from {year} — material and labor prices have likely shifted. Update cost ranges and date."
- Service pages: standard restoration reasoning applies unchanged.

---

## Everything else

Follow `templates/restoration/prompts/refresh-recommender.md` exactly:
- Pre-flight (slug, client record, Layer 1 candidates file, content queue, url-plan)
- Skip logic (fresh URLs, already-handled by System 2)
- Action classification per URL
- Refresh queue write at `clients/{slug}/refresh-queue.json`
- Markdown report
- Client record update (`refresh.last_run_at`)
