# Case studies — real jobs only

## Why this exists

Until 2026-08-04, 318 service-area pages across 19 client sites carried a section
titled **"A recent {City} response"**. Every one of them was written by the content
generator. None of them happened.

They read like this:

> A property manager overseeing a four-unit rental near the Manette Bridge called us
> on a Sunday morning after a tenant reported water coming up through the bathroom
> floor. By the time our crew arrived — under 75 minutes from the call — the subfloor
> in two units was saturated… *(This scenario is representative of the type of work we
> handle; details have been generalized.)*

282 of the 318 carried some version of that disclaimer. 36 carried none at all.

Santino's call, and the standing rule now:

> **We don't add this unless we have actual job stories. If we have to add a
> disclaimer, that defeats the purpose.**

The sections were deleted from every page, and the instruction that produced them was
removed from the generator prompts (`prompts/service-area.md` and the shared
`prompts/_system.md`, which now carries a hard NO FABRICATED EXPERIENCE gate covering
every page type). This document describes the honest path back.

## The rule

**Nothing in a case-studies file may be written by a model.** It is client testimony.
If the client did not tell us the job happened, it does not go on the site. A hedge, a
disclaimer, or "representative scenario" framing does not make an invented story
publishable — needing the disclaimer is the proof it should not be there.

## How it flows

```
clients/{slug}/case-studies.json          <- you edit this (ops-facing)
        |
        |  python3 scripts/case_studies_sync.py --slug {slug}
        v
sites/{slug}/src/data/case-studies.json   <- published entries, ships in the subtree
        |
        |  CaseStudies.astro  (renders ONLY when the city has an entry)
        v
/service-areas/{area_slug}/   ->  "Recent work in {City}"
```

Every client is seeded with an empty list, so the section renders nothing at all until
a real job is added. That mirrors `RecentWork.astro`, which shows crew job photos only
once real photos exist. **An empty section is the correct default, not a gap to fill.**

## Adding a real case study

1. Get the job from the client — Monica's ask, a kickoff call, or an email thread.
   Confirm they are fine with it appearing publicly. If the property is identifiable,
   confirm that too.
2. Photos (optional but far more valuable than text alone) go in the client's branding
   bucket alongside their crew uploads:
   `branding/{company_id}/case-studies/<file>.jpg`
   Public URL form:
   `https://<supabase>/storage/v1/object/public/branding/{company_id}/case-studies/<file>.jpg`
3. Add the entry to `clients/{slug}/case-studies.json`:

```json
{
  "case_studies": [
    {
      "area_slug": "bremerton-wa",
      "service_slug": "water-damage-restoration",
      "title": "Burst supply line, two-story rental",
      "summary": "A second-floor supply line failed overnight and soaked the unit below. We extracted, set drying equipment, and documented moisture readings for the carrier. The tenant moved back in the following week.",
      "performed_on": "2026-07",
      "photos": ["https://.../branding/{company_id}/case-studies/bremerton-supply-line.jpg"],
      "published": true
    }
  ]
}
```

4. Sync and build:

```bash
python3 scripts/case_studies_sync.py --slug {slug}
cd sites/{slug} && npx astro build
```

5. Deploy as normal (`scripts/build_site.py sync-deploy --slug {slug} --branch main|staging`).

### Fields

| Field | Required | Notes |
|---|---|---|
| `title` | yes | Short and factual. No superlatives, no "amazing transformation". |
| `summary` | yes | 2–4 plain sentences: what happened, what we did, the outcome. Only facts the client confirmed. |
| `area_slug` | no | Must match a page in `sites/{slug}/src/content/serviceAreas/`. Omit for a company-wide entry that can appear on any city page. |
| `service_slug` | no | Restricts the entry to one city × service page. |
| `performed_on` | no | `YYYY-MM` or `YYYY-MM-DD`. Renders as "July 2026". |
| `photos` | no | Array of public branding-bucket URLs. The first is used as the card image. |
| `published` | no | `false` stages an entry without rendering it. Defaults to true. |

### What not to write

- No invented specifics — arrival times, dollar figures, drying durations, or claim
  outcomes we did not get from the client.
- No customer names, and no property detail precise enough to identify a household
  without permission.
- No response-time minutes unless the client's brand truth data already supports them
  (`claims_lint.py` governs the same numbers elsewhere on the site).
- No review or testimonial text pasted in as a "case study" — reviews have their own
  pipeline.

## The guard

`scripts/case_studies_sync.py --validate` rejects entries that carry the tells of
generated copy, so this door cannot quietly become the new fabrication vector:

```
$ python3 scripts/case_studies_sync.py --slug narestco --validate
  narestco: REJECTED — 1 problem(s)
      [0] reads like generated copy, not a real job
          (matched /this (scenario|example) is representative/).
          Case studies must be client-supplied.
```

It also checks required fields, that `area_slug` resolves to a real page, and the date
format. Run `--all --validate` to sweep the fleet.

## For Monica

Case studies are the highest-value thing we can ask a client for, and the ask is
concrete enough to answer from a phone: *"Send us one job from the last few months —
what happened, what you did, and two or three photos."* One real job with photos on a
city page outperforms any amount of generated local text, and it is the only version of
this section we are willing to publish.

Until a client sends one, the section does not exist on their site. That is the intended
state, not a backlog item.
