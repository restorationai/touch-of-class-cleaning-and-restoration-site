---
name: service-area
target_word_count: 700
faq_count: 4
---

Write the body for the **{area.city}, {area.state}** service-area page on {brand.display_name}'s website.

# Page focus

- City: **{area.city}, {area.state}**
- This is the canonical city-level overview page. The {area.city} × {service} combo pages link back here.
- Primary keyword: `{page.primary_keyword}`

# CRITICAL: LOCAL CONTEXT — required references

This is a LOCATION page. It must read like it was written for someone living in or coming to {area.city}, not a template. **All of the following are required in the body:**

- **At least 3 named neighborhoods from this list**: {area.neighborhoods}
- **At least 2 named landmarks from this list**: {area.landmarks}
- **At least 2 ZIP codes from this list**: {area.zip_codes}
- **A neighborhood-specific paragraph** that references the area's restoration characteristics from this context: {area.local_notes}
- **If the neighborhood / landmark / ZIP lists above are empty**: do NOT refuse and do NOT invent specifics. Write at the city level (city, county, state routes only if provided in context) and skip the named-local requirements — empty local context is an accepted degraded mode for freshly onboarded clients. Never fabricate a neighborhood, landmark, or ZIP.

# CRITICAL: NO FABRICATED EXPERIENCE

**Never invent a customer, a job, or a past project.** This is an absolute rule, not a style preference.

Specifically forbidden, in the body AND in the FAQ:

- Any "a recent {area.city} response" / "a homeowner called us" / "a property manager contacted us" story.
- Any specific past job: what we found, how fast we arrived, how long it took, what the carrier paid.
- Any job counts, project counts, years-in-{area.city}, or "we've handled X homes here" figures.
- Any named or described customer, tenant, adjuster, or property — real, composite, or hypothetical.
- Any testimonial, quote, or review text.

**A disclaimer does not launder an invented story.** Do not write one and then hedge it with
"this scenario is representative", "details have been generalized", or similar. If the job did not
happen, it does not go on the page — hedged or not.

Real case studies are supplied separately as structured data by the client
(`clients/{slug}/case-studies.json`) and are rendered by the page template, never written by this
prompt. Your job is to be useful about the CITY, not to imply a track record we cannot evidence.

Write shorter rather than padding. A 550-word page of true, locally specific content beats an
800-word page carrying one invented anecdote.

# CRITICAL: UNIQUENESS

This page MUST satisfy all of:

1. Open with a paragraph that names what {brand.display_name} does specifically for {area.city} property owners — not generic "we serve this area."
2. Include a paragraph about why {area.city} sees the restoration emergencies it does — climate, housing stock, water table, code differences, regional factors.
3. List the services we provide in {area.city} (the planner will link them) — short paragraphs per service category that are FRAMED LOCALLY (e.g., "Water damage in {area.city} often involves [local pattern]").
4. Ground the page in verifiable local specifics — housing stock and construction era, soil and drainage behavior, climate and storm patterns, water table, local code or permitting notes, and real geography (routes, distances). These are facts about the CITY, which we can stand behind.
5. Describe realistic travel/coverage from {brand.primary_city} HQ to {area.city} (routes, distance). Per the CLAIMS TRUTH TABLE: no minute promises unless the brand block provides them, and no after-hours implication unless Hours say 24/7.

# Brand context (use naturally)

- Company: {brand.display_name}
- HQ: {brand.primary_city}, {brand.primary_state}
- Phone: {brand.phone}
- Hours: {brand.hours}
- Founded: {brand.founded_year}

# Structure

- Opening paragraph (~80 words) — name what we do for {area.city} property owners, fast.
- `## Restoration emergencies common in {area.city}` — local pattern (climate, housing stock, water, etc.)
- `## Services we provide in {area.city}` — short paragraphs per major service category, framed locally
- `## Coverage and how fast we can get there` — specific neighborhoods or routes; minute figures ONLY if the brand block provides them
- Closing CTA paragraph (no heading)

Target: ~{target_word_count} words.

# FAQ — write {faq_count} pairs

All FAQs must reference {area.city} or a named neighborhood from the list. Topics:
- Reaching a specific {area.city} neighborhood (no minute promises unless the brand block provides them)
- Services we offer locally
- {area.city}-specific factors (HOA rules, code, climate, housing stock)
- Coordination with {area.city} property managers or insurance carriers

# Output

Return ONLY valid JSON, no prose before or after, no code fences. Schema:

```json
{
  "body_markdown": "...",
  "faq": [
    {"question": "...", "answer": "..."},
    ...
  ]
}
```

JSON rules: escape internal double quotes as `\"`. No code fences. No prose around the JSON.
