# Restoration Industry Template

Stub directory for the `rank-ai-plan-site` skill (Skill 2). The full design is in
`rank-ai/docs/site-plan-skill-spec.md`.

## What's in here

```
restoration/
├── template.json            top-level descriptor + version
├── services.json            canonical 12-service catalog
├── seed-blog-topics.json    ranked seed blog backlog (~15 topics to start)
├── linking-rules.json       internal-link graph rules consumed by Pass 3
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
    ├── local-business.json
    ├── service.json
    ├── blog-posting.json
    └── faq.json
```

## Status

Stubs only. No script consumes these yet — `rank-ai/scripts/plan_site.py` will
be written next, and the file shapes here are what it expects to read. If a
shape needs to change after implementation, update the spec doc + every
archetype together so the planner doesn't break silently.

## Versioning

Each generated plan stamps `template_version` (from `template.json`). Bumping
that version is a deliberate act — plans built against older versions stay
valid against the older shape, and Skill 3 builds against the version the plan
was generated with.

## Adding a new service

1. Append an entry to `services.json` with a unique slug.
2. (Optional) Add a corresponding seed topic to `seed-blog-topics.json`.
3. (Optional) Add per-service secondary keyword templates if `service-landing`
   archetype's `secondary_keywords_ref` needs new lookup keys.

No archetype edits required for typical service additions.

## Adding a new archetype

1. Drop a new JSON file in `archetypes/`.
2. Add it to `template.json`'s `supported_archetypes`.
3. Add a `from:` rule to `linking-rules.json` for how other pages link to it
   and (if it appears in some pages' outbound rules) update those entries.
4. If it carries new schema, add the stub to `schema/`.
