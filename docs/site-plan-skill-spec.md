# Rank AI — Site Plan Skill Spec (`rank-ai-plan-site`)

**Last updated:** 2026-05-10
**Implementation:** `rank-ai/scripts/plan_site.py`
**Skill wrapper:** `~/.claude/skills/rank-ai-plan-site/SKILL.md` (interactive)
**Position in pipeline:** Skill 2 of 4. Runs *after* `rank-ai-onboard` (client record exists, R2 bucket bound) and *before* `rank-ai-build-site` (Skill 3).

---

## Purpose

Turn a freshly-onboarded restoration-industry client into a deterministic site plan: every URL the new site will have, the page-type and SEO metadata for each, the internal-link graph, and a content map CSV that drives content generation downstream.

Skill 1 (`onboard`) produced infrastructure. Skill 2 produces the *blueprint* the build skill (3) and blog routine (4) consume. Once this skill finishes, Skill 3 has no creative decisions left to make about IA, keywords, or page taxonomy — it just renders the plan into Astro routes and queues content generation.

## Why a separate skill (not part of build)

1. **Plan is reviewable.** A CSV + a small JSON spec is easy for a human to skim and edit before any HTML is written. Spotting a missing service area at the plan stage costs minutes; spotting it after the build costs a rerun.
2. **Plan is reusable.** The same blueprint can be re-applied to regenerate sections without rebuilding the whole site (e.g., add 5 new service-area pages later).
3. **Plan is the source of truth.** Skill 3, Skill 4, and any future Skill 5 (rewrite / refresh) all read from the same plan record, so the system stays coherent.
4. **Restoration templates change rarely.** Decoupling planning from building means the template library evolves on its own cadence and gets versioned without churning build code.

## Contract

### Inputs

| Field              | Required | Type      | Source                                                                                  |
| ------------------ | -------- | --------- | --------------------------------------------------------------------------------------- |
| `slug`             | yes      | string    | Existing client record at `rank-ai/clients/{slug}.json`                                 |
| `template`         | yes      | enum      | `restoration` (only one for now; future verticals plug in here)                         |
| `services`         | yes      | string[]  | Service slugs the client offers, from the template's service catalog                    |
| `service_areas`    | yes      | object[]  | List of `{city, state, county?, lat?, lng?, primary?}` — primary = headquarters city    |
| `brand`            | yes      | object    | `{phone, email, hours, founded_year, license_numbers[], certifications[]}`              |
| `competitor_urls`  | no       | string[]  | Optional — fed to DataForSEO for SERP intelligence                                      |
| `keyword_strategy` | no       | enum      | `aggressive` \| `conservative` \| `manual`; default `conservative`                      |
| `cross_product`    | no       | bool      | Generate `/service-areas/{city}/{service}/` cross-product pages. Default true.          |
| `blog_seed_count`  | no       | int       | How many seed blog posts to plan up front. Default 12.                                  |
| `dry_run`          | no       | bool      | Print plan to stdout, do not write artifacts                                            |

The skill wrapper (interactive) asks the user for these one by one and writes the resolved input set to `rank-ai/clients/{slug}/plan-input.json` for reproducibility.

### Outputs

Everything lives under `rank-ai/clients/{slug}/plan/`:

```
plan/
├── plan-input.json        # frozen copy of inputs (audit trail)
├── url-plan.json          # machine-readable plan; Skill 3 reads this
├── content-map.csv        # human-reviewable + Skill 4's blog queue source
├── internal-links.json    # link graph for the entire site
├── schema-stubs.json      # per-URL Schema.org JSON-LD templates (filled at build)
└── plan-report.md         # human summary: # pages by type, top keywords, gaps
```

### Side effects

- DataForSEO API calls (keyword volumes, SERP analysis, local intent classification) — billable per call but cheap at this scale.
- Writes to local repo only. No Cloudflare or external state mutation.
- Updates the client record's `plan` block: `{ template, generated_at, url_count, status: "planned" }`.

### Idempotency

Re-running with the same inputs is a no-op on output files (sha256-compared first, only rewritten if changed). Re-running with new inputs overwrites — previous artifacts are saved as `*.{timestamp}.bak` in the same directory.

## State machine (client-level)

The client record gains a `plan_status` field that progresses:

```
(no plan)  →  planning  →  planned  →  built  →  live
```

- `planning` — script is mid-execution (set on entry, cleared on success).
- `planned` — artifacts on disk, ready for Skill 3 review.
- `built` — Skill 3 has rendered Astro routes; the plan is the source-of-truth still.
- `live` — site deployed.

This skill only writes `planning` and `planned`.

## Subcommands

| Subcommand   | Purpose                                                                                | Notes                                                          |
| ------------ | -------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `generate`   | Produce all plan artifacts from inputs                                                 | Main entry point. Idempotent.                                  |
| `expand`     | Add new service-areas or services to an existing plan without regenerating from scratch | Read-modify-write. Preserves existing URLs.                    |
| `validate`   | Lint an existing plan: dead internal links, missing keywords, schema gaps              | Pre-flight before Skill 3.                                     |
| `diff`       | Show what would change if a new input set were applied                                 | Dry-run for `expand` / `generate --force`.                     |
| `report`     | Regenerate `plan-report.md` from current artifacts                                     | Useful after manual CSV edits.                                 |

## How the plan is generated (algorithm)

Given inputs, the pipeline runs in four passes:

### Pass 1 — IA expansion

The template (`restoration`) defines a parametric IA: a set of *page archetypes*, each with a path pattern and the variables that drive it. The script enumerates the cartesian-product instantiations:

```
Archetype: ServiceLandingPage
  pattern: /services/{service.slug}/
  driver:  one per `services[]`

Archetype: ServiceAreaPage
  pattern: /service-areas/{area.slug}/
  driver:  one per `service_areas[]`

Archetype: ServiceAreaServicePage   (the SEO gold; produced only if cross_product=true)
  pattern: /service-areas/{area.slug}/{service.slug}/
  driver:  one per (service × service_area) pair

Archetype: BlogSeedPost
  pattern: /blog/{post.slug}/
  driver:  N posts pulled from template.seed_blog_topics, top-N by template ranking
```

Plus the fixed-singleton pages (Home, About, Contact, Privacy, Terms, Sitemap, 404, Blog index, Services hub, Service-areas hub). The script outputs a flat list of all URLs with their archetype tag.

### Pass 2 — Keyword + intent enrichment

For each URL, the script attaches:

- **Primary keyword** — derived from the archetype template's keyword formula. Examples:
  - `ServiceLandingPage` → `"{service.display_name}"` (e.g., "water damage restoration")
  - `ServiceAreaServicePage` → `"{service.display_name} {area.city}"` (e.g., "water damage restoration Phoenix")
- **Secondary keywords** — template-defined supporting terms, e.g. for water damage: `water removal`, `flood cleanup`, `burst pipe repair`, `basement flooding`.
- **Search intent** — pulled from DataForSEO `dataforseo_labs_search_intent` if available; falls back to template-declared intent (mostly `local_commercial` for restoration).
- **Volume + difficulty** — DataForSEO `bulk_keyword_difficulty` + `bulk_traffic_estimation` if API enabled; logged but does NOT remove pages (we don't skip pages on low volume — they exist for topical coverage). The data flows into prioritization for Skill 4's blog queue.

`keyword_strategy = aggressive` enables long-tail variants ("emergency 24/7 water damage cleanup near me Phoenix"); `conservative` stays with template defaults.

### Pass 3 — Internal-link graph

Restoration sites win at SEO through dense, semantic internal linking. The script computes the link graph from a small set of explicit rules in the template:

```
linking_rules:
  - from: Home
    to:   [services_hub, service_areas_hub, all primary ServiceLandingPages, contact]
  - from: ServicesHub
    to:   [all ServiceLandingPages]
  - from: ServiceAreasHub
    to:   [all ServiceAreaPages]
  - from: ServiceLandingPage
    to:   [services_hub, related ServiceAreaServicePages (same service), 3 related ServiceLandingPages, blog posts tagged with this service]
  - from: ServiceAreaPage
    to:   [service_areas_hub, all ServiceAreaServicePages for this area, 2 adjacent ServiceAreaPages (geographic)]
  - from: ServiceAreaServicePage
    to:   [parent ServiceLandingPage, parent ServiceAreaPage, 2 sibling ServiceAreaServicePages (same area), 2 cousin ServiceAreaServicePages (same service, different area)]
  - from: BlogPost
    to:   [related ServiceLandingPage(s) by tag, 3 related blog posts]
```

The graph is materialized in `internal-links.json` as adjacency lists. Skill 3 reads this and injects the links during page render — no per-page authoring needed.

Validation: every link target must exist in `url-plan.json`. The `validate` subcommand re-checks this after manual edits.

### Pass 4 — Schema stubs

For each URL, the script writes a JSON-LD stub with placeholder slots that Skill 3 fills:

```json
{
  "ServiceAreaServicePage": {
    "@context": "https://schema.org",
    "@type": "Service",
    "serviceType": "{service.display_name}",
    "provider": { "@type": "LocalBusiness", "name": "{brand.legal_name}", "@id": "{brand.entity_id}" },
    "areaServed": { "@type": "City", "name": "{area.city}", "addressRegion": "{area.state}" },
    "url": "{full_url}"
  }
}
```

Stubs are emitted per archetype with `{var}` placeholders so the build skill never invents schema — it only substitutes.

## Restoration template — what the catalog contains

The template at `rank-ai/templates/restoration/` holds:

```
restoration/
├── template.json                 # top-level template descriptor
├── services.json                 # canonical service catalog
├── seed-blog-topics.json         # ranked seed topics for first N blog posts
├── archetypes/
│   ├── home.json
│   ├── about.json
│   ├── contact.json
│   ├── services-hub.json
│   ├── service-landing.json
│   ├── service-areas-hub.json
│   ├── service-area.json
│   ├── service-area-service.json
│   ├── blog-index.json
│   ├── blog-post.json
│   └── legal.json                # privacy / terms / accessibility
├── linking-rules.json            # the graph rules from Pass 3
└── schema/
    ├── local-business.json
    ├── service.json
    ├── blog-posting.json
    └── faq.json
```

### Canonical service catalog (`services.json`)

The restoration industry has a stable set of revenue services. The template's catalog locks in:

| Slug                          | Display name                       | Primary intent  | Notes                                                  |
| ----------------------------- | ---------------------------------- | --------------- | ------------------------------------------------------ |
| `water-damage-restoration`    | Water Damage Restoration           | local_emergency | Highest-volume restoration service                     |
| `fire-damage-restoration`     | Fire Damage Restoration            | local_emergency | High-margin, lower-volume                              |
| `mold-remediation`            | Mold Remediation                   | local_health    | Often regulated; certifications matter for trust       |
| `storm-damage-restoration`    | Storm Damage Restoration           | local_emergency | Seasonal; pairs with insurance content                 |
| `smoke-damage-restoration`    | Smoke Damage Restoration           | local_emergency | Usually fire-adjacent; sometimes standalone            |
| `sewage-cleanup`              | Sewage Cleanup & Sanitization      | local_emergency | Biohazard-adjacent                                     |
| `biohazard-cleanup`           | Biohazard & Trauma Cleanup         | local_sensitive | Sensitive content guidelines apply                     |
| `commercial-restoration`      | Commercial Restoration             | local_b2b       | Larger contracts; longer sales cycle                   |
| `reconstruction`              | Reconstruction Services            | local_commercial| Post-restoration rebuild                               |
| `contents-restoration`        | Contents Cleaning & Pack-Out       | local_specialty | Belongings cleaning after damage                       |
| `appliance-leak-cleanup`      | Appliance Leak Cleanup             | local_emergency | Dishwasher/washing-machine specific                    |
| `crawlspace-encapsulation`    | Crawlspace Encapsulation           | local_commercial| Preventative; pairs with mold                          |

The client picks any subset; the IA only generates pages for selected services. Adding new services to the catalog is a JSON edit, not a code change.

### Seed blog topics (`seed-blog-topics.json`)

Ranked list (~80 topics) of evergreen restoration-industry blog post titles, each tagged with the services it relates to. Skill 4's blog routine consumes this as its initial backlog and Skill 2 just plans the first `blog_seed_count` (default 12) into the site's launch state.

Format:

```json
[
  {
    "slug": "what-to-do-after-a-burst-pipe",
    "title_template": "What To Do in the First 24 Hours After a Burst Pipe",
    "services": ["water-damage-restoration"],
    "intent": "informational_emergency",
    "priority": 9
  },
  ...
]
```

`title_template` allows location-aware variants ("...After a Burst Pipe in {primary_city}") if the topic supports it.

## Archetype file format

Every archetype is a JSON file. Example for `service-area-service.json`:

```json
{
  "name": "ServiceAreaServicePage",
  "path_pattern": "/service-areas/{area.slug}/{service.slug}/",
  "title_template": "{service.display_name} in {area.city}, {area.state}",
  "h1_template": "{service.display_name} in {area.city}",
  "meta_description_template": "24/7 {service.display_name|lower} in {area.city}, {area.state}. Licensed, insured, IICRC-certified. Call {brand.phone}.",
  "primary_keyword_template": "{service.display_name|lower} {area.city|lower}",
  "secondary_keywords_template_set": "{service.slug}.local_supporting",
  "search_intent_default": "local_commercial",
  "target_word_count": 900,
  "image_roles": ["hero", "og", "inline-1", "inline-2"],
  "schema_stubs": ["service", "local-business", "faq"],
  "linking_rules_ref": "service-area-service",
  "required_brand_fields": ["phone", "license_numbers"]
}
```

The script needs zero hardcoding — every page-type's behavior is a JSON file plus a substitution engine.

## Substitution engine

A tiny `{var}` resolver with three features:

1. **Dot access** — `{service.display_name}`, `{area.state}`.
2. **Filters** — `{x|lower}`, `{x|title}`, `{x|slug}`. Filterable chain: `{x|lower|slug}`.
3. **Set lookups** — `{service.slug}.local_supporting` reads from a per-service keyword set table.

Anything more (conditionals, loops) is a sign the archetype JSON is doing too much; lift it to code or split archetypes instead.

## Content-map CSV columns

Single CSV row per URL. Columns:

| Column                | Source                                                |
| --------------------- | ----------------------------------------------------- |
| `url_path`            | Pass 1                                                |
| `archetype`           | Pass 1                                                |
| `title`               | Archetype `title_template` substituted                |
| `h1`                  | Archetype `h1_template` substituted                   |
| `meta_description`    | Archetype `meta_description_template` substituted     |
| `primary_keyword`     | Pass 2                                                |
| `secondary_keywords`  | Pass 2 (pipe-delimited)                               |
| `search_intent`       | Pass 2                                                |
| `search_volume`       | Pass 2 (DataForSEO, blank if unavailable)             |
| `difficulty`          | Pass 2 (DataForSEO, blank if unavailable)             |
| `target_word_count`   | Archetype                                             |
| `image_roles`         | Archetype (pipe-delimited)                            |
| `schema_stubs`        | Archetype (pipe-delimited)                            |
| `internal_links_out`  | Pass 3 (pipe-delimited target paths)                  |
| `priority`            | Computed: `archetype_priority × keyword_priority`     |
| `status`              | Always `planned` at this stage                        |

CSV is the deliverable artifact for a human to review before the build skill runs.

## Validation pre-flight

`plan_site.py validate --slug {slug}` runs these checks:

1. Every `internal_links_out` target exists in `url_path` column.
2. No two URLs collide on path after substitution.
3. Every `primary_keyword` is non-empty.
4. Every `schema_stubs` entry resolves to a file in `templates/{template}/schema/`.
5. Every required brand field referenced by any archetype exists in the inputs.
6. Service-area `slug` fields are URL-safe (lowercase, hyphenated, no diacritics).

A `validate` failure stops Skill 3 from running.

## DataForSEO usage

The skill uses DataForSEO MCP tools (already available in the harness):

- `dataforseo_labs_bulk_keyword_difficulty` — one call covering all primary + secondary keywords across the plan.
- `dataforseo_labs_bulk_traffic_estimation` — same batch, for volume.
- `dataforseo_labs_search_intent` — intent classification for ambiguous keywords.
- `serp_organic_live_advanced` — pulled for the top 1–2 primary keywords as competitive intelligence (top-10 URLs feed into `plan-report.md`).
- `business_data_business_listings_search` — used opportunistically to check existing GBP listings in service areas (informs Skill 3's local-schema work later).

All API responses are cached under `rank-ai/clients/{slug}/plan/.cache/` keyed by request hash so re-runs cost nothing.

## Failure modes & recovery

| Failure                                       | Cause                                              | Recovery                                                      |
| --------------------------------------------- | -------------------------------------------------- | ------------------------------------------------------------- |
| `generate` aborts: client record missing      | Onboarding skill not run for this slug             | Run Skill 1 first; rerun                                      |
| `generate` aborts: template not found         | `template=` typo or template dir missing           | Use a valid template name                                     |
| DataForSEO quota / network error              | API down                                           | Skill proceeds with template defaults; CSV's vol/difficulty blank; warning in report |
| Path collision after substitution             | Two service-areas with the same slug               | Edit `plan-input.json` to disambiguate (e.g., `phoenix-az`), rerun |
| Plan validation fails                         | Template or input bug                              | Surfaced in `plan-report.md` and stderr; fix and rerun        |

## Skill wrapper UX (`~/.claude/skills/rank-ai-plan-site/SKILL.md`)

The interactive wrapper:

1. Confirms the slug exists and shows the current `plan_status`.
2. Walks `AskUserQuestion` through: template choice, service multi-select (from `services.json`), service-areas (free-text with `{city}, {state}` parser), brand details (autofill from any prior config if present).
3. Previews the URL list (count by archetype) before generating.
4. Shells out to `python3 rank-ai/scripts/plan_site.py generate ...`.
5. On success, opens `plan-report.md` and the first 30 rows of `content-map.csv` for inline review.
6. Prompts: "Looks right? Run `validate`?" — runs validate, displays any issues.
7. Suggests next step: `/rank-ai-build-site --slug {slug}` (Skill 3, not yet built).

The script does the work; the skill is conversational glue.

## Versioning

The template descriptor has a `version` field. The plan artifacts record `template_version` so future template changes don't silently invalidate older plans. A plan generated against template v1 will not be regenerated against template v2 unless explicitly forced — Skill 3 builds against whatever template version the plan was generated with.

## Out of scope

- HTML/Astro rendering — Skill 3.
- Blog content generation — Skill 4.
- Image generation — Skill 4 (and `rank-ai-image-gen`).
- Sitemap.xml writing — Skill 3.
- Robots.txt — Skill 3.
- Deployment — Skill 3 / Skill 5.

## What this skill bakes in (so later skills don't decide)

By committing to this spec, downstream skills never have to:

- Decide the IA. URLs are fixed at plan time.
- Decide internal-link structure. Graph is fixed at plan time.
- Pick which schema types each page uses. Stubs are fixed at plan time.
- Re-research primary keywords. Plan owns the keyword-to-URL mapping.

This is the same principle as the image hosting decision: one place to change behavior, not N.

---

*Decision rationale: this spec was written before any code so Skill 3 (`rank-ai-build-site`) can be designed against a stable plan format. The CSV + JSON artifact split exists because the CSV is for humans to skim and the JSON is for code to read — same data, different surfaces.*
