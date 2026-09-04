# Environmental Testing & Solutions Industry Template

Vertical template for ENVIRONMENTAL TESTING companies: mold inspection/testing,
indoor air quality, asbestos/lead/radon/water testing, clearance testing
(post-remediation verification), environmental site assessments, compliance
consulting, and remediation oversight. Consumed by the `rank-ai-plan-site`
skill (Skill 2) and resolved per-client via `scripts/verticals.py`
(`resolve_template(slug, ...)` — never hardcode this path in pipeline code).

Seeded 2026-09-04 from `templates/restoration/` (the canonical structure),
following the adaptation pattern `templates/plumbing/` established for second
verticals (services.json note style, tiers, linking-rules sister_company_policy).
Pilot client: Arch Environmental Group (Kingsburg, CA).

## The independence rule (this vertical's core positioning)

Environmental testing companies are INDEPENDENT TESTERS. Their credibility
comes from NOT being the remediation contractor: they don't profit from
finding problems, and their reports are contractor-neutral. Every asset in
this template encodes that:

- Copy must NEVER call the client a restoration/remediation company or imply
  they perform cleanup, abatement, or repairs themselves — unless the client's
  own record explicitly says so.
- Remediation referrals are `linking-rules.json` `sister_company_policy`
  territory: only a disclosed `brand.sister_company` may be referenced, with
  an explicit independence-preservation disclosure in the same passage. When
  the field is absent, content ends at the testing scope plus neutral advice
  to hire a qualified, unaffiliated contractor.
- No 24/7 defaults: testing is appointment-shaped work. Only sewage
  contamination assessment and post-flood mold assessment carry
  local_emergency intent.
- Health-claims guardrail: cite EPA/CDC/state guidance calmly; never diagnose,
  never fear-monger.

## What's in here

```
environmental/
├── template.json            top-level descriptor + version
├── services.json            canonical 16-service catalog (core/specialty/adjacent)
├── seed-keywords.txt        shared seed list for System 1
├── seed-blog-topics.json    ranked seed blog backlog (~16 topics to start)
├── keyword-variants.json    customer-language phrasing variants per service
├── vertical-tokens.json     trade-identity copy tokens (build_site resolve_tokens)
├── linking-rules.json       internal-link graph rules + sister_company_policy
├── image-style-guide.template.md  per-client image guide template
├── prompts/                 System 1-4 agent prompts (env-vertical adapted)
├── archetypes/              one JSON per page-type the planner instantiates
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
│   └── legal.json
└── schema/                  Schema.org JSON-LD stubs filled in at build time
    ├── local-business.json  (ProfessionalService + HomeInspector — no env subtype exists)
    ├── service.json
    ├── blog-posting.json
    └── faq.json
```

## Versioning

Each generated plan stamps `template_version` (from `template.json`). Bumping
that version is a deliberate act — plans built against older versions stay
valid against the older shape, and Skill 3 builds against the version the plan
was generated with.

## Adding a new service

1. Append an entry to `services.json` with a unique slug. Respect the
   independence rule: testing/assessment/oversight services only, never
   remediation, unless a specific client genuinely offers it (per-client
   services_selected, not the canonical catalog).
2. (Optional) Add a corresponding seed topic to `seed-blog-topics.json` and a
   variants entry to `keyword-variants.json`.
3. (Optional) Add per-service secondary keyword templates if `service-landing`
   archetype's `secondary_keywords_ref` needs new lookup keys.
4. Add an inspector-context row to the per-service table in
   `image-style-guide.template.md`.

No archetype edits required for typical service additions.

## Adding a new archetype

1. Drop a new JSON file in `archetypes/`.
2. Add it to `template.json`'s `supported_archetypes`.
3. Add a `from:` rule to `linking-rules.json` for how other pages link to it
   and (if it appears in some pages' outbound rules) update those entries.
4. If it carries new schema, add the stub to `schema/`.
