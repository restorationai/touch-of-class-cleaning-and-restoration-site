---
name: service-area-service
target_word_count: 850
faq_count: 5
---

Write the body for a city × service combo page on **{brand.display_name}**'s website. THIS PAGE IS ONE OF ~180 SIMILAR-SHAPE PAGES ON THE SITE. Google penalizes near-duplicate cross-product pages. Your job is to make this page meaningfully different from the other 179.

# Page focus

- Service: **{service.display_name}**
- City: **{area.city}, {area.state}**
- Primary keyword: `{page.primary_keyword}`
- Secondary keywords: {page.secondary_keywords}
- Search intent: `{page.search_intent}`
- Target word count: ~{target_word_count} words of body (excluding FAQ)

# CRITICAL: LOCAL CONTEXT — use these (do not invent substitutes)

This {area.city} page must reference SPECIFIC LOCAL DETAILS. Use the following research-backed local context. **At least 2 of the named neighborhoods or landmarks must appear in the body. At least 1 ZIP code from the list must appear in the body or FAQs.**

- **Named neighborhoods in {area.city}**: {area.neighborhoods}
- **Named landmarks in {area.city}**: {area.landmarks}
- **ZIP codes covering {area.city}**: {area.zip_codes}
- **Local restoration context**: {area.local_notes}

Do not list these mechanically. Weave them naturally into context where they make sense:
- A burst pipe in *the Capitol Hill area* sounds local; *"we serve Capitol Hill"* sounds like a list.
- Pre-1950 housing in *Magnolia and Queen Anne* is a real Seattle pattern; mentioning it shows local awareness.

# CRITICAL: UNIQUENESS

This page MUST satisfy all of:

1. **Unique opening paragraph** that references BOTH {service.display_name} AND a specific local condition in {area.city}. Do NOT open with a sentence that would also fit on a different city's page for the same service.
2. **Local problems specific to {area.city}** — climate, soil, building stock, codes, utilities. Reference at least one specific factor.
3. **FAQ items that combine the service AND {area.city}**. At least 60% of FAQ questions must reference the city, a {area.city} neighborhood, or a {area.city}-specific consideration. Generic "How fast?" / "Do you bill insurance?" questions are NOT allowed unless framed locally (e.g., "How fast can you reach Capitol Hill from your HQ?").
4. **A local tip** — one paragraph that mentions something only someone working in {area.city} would know. See examples below.
5. **A service-specific process angle** — what's different about doing {service.short_or_display_name|lower} in {area.city} vs anywhere else (older homes, HOA rules, regulatory specifics, climate factors).

# Brand context (use naturally, do not list)

- Company: {brand.display_name}
- Phone: {brand.phone}
- HQ: {brand.primary_city}, {brand.primary_state}
- Founded: {brand.founded_year}
- Certifications: {brand.certifications}
- Hours: {brand.hours}
- License: {brand.license_type}{brand.license_numbers_suffix}, {brand.license_authority}

# Structure

- Opening paragraph (~80 words) — local + service-specific hook. NO subheading.
- 3-4 `##` subsections, chosen from this menu (pick the ones that match this service + city combo):
  - "Why {area.city} Properties See {service.short_or_display_name|lower} Issues" — local pattern, climate / housing stock / utilities
  - "Our {service.display_name} Process in {area.city}" — concrete steps, calibrated to local conditions
  - "Reaching {area.city} from {brand.primary_city}" — specific routes or neighborhoods; minute figures ONLY if the brand block provides response-time data, and no after-hours implication unless Hours say 24/7
  - "{area.city} Insurance & HOA Coordination" — local claim patterns, HOA requirements if known
  - "Equipment & Methods We Use for {service.short_or_display_name}" — only if technical detail matters for this service
- A short `## Local note` (or similarly framed) with the local-tip paragraph
- Closing CTA paragraph (no heading) — references the service AND {area.city} specifically

{sensitive_block}

# FAQ — write {faq_count} pairs

Mix:
- 2-3 questions that specifically mention {area.city} or a named {area.city} neighborhood
- 1-2 service-specific technical questions (process, equipment, timeline, materials)
- 1 question about cost / insurance with a {area.city} angle if natural

EXAMPLES OF GOOD QUESTIONS (adapt to this combo):
- "How quickly can you reach the [neighborhood] area for a [service] emergency?"
- "Does [city]'s [code/ordinance/HOA pattern] affect [service] work in [city]?"
- "What's typical for [service] in [city]'s [housing-stock pattern] homes?"
- "Are [neighborhood] homes more prone to [service-related issue]?"

EXAMPLES OF BAD QUESTIONS (DO NOT USE):
- "How fast can you respond?" (no city context)
- "Do you bill insurance?" (no city context, generic)
- "How much does [service] cost?" (no city context)

# Examples of LOCAL TIPS (adapt to this combo — invent if needed but plausible)

- *"In Seattle's Magnolia and Queen Anne neighborhoods, pre-1950 plaster walls absorb water differently than modern drywall — extraction is faster, but full drying takes 50% longer because plaster releases moisture slowly."*
- *"Federal Way's Lakeland and Twin Lakes neighborhoods often have shared driveway easements that complicate emergency vehicle staging — we call ahead to coordinate access on those addresses."*
- *"Bellevue HOA developments built after 2005 typically require third-party air clearance testing post-mold remediation; we coordinate the test with an independent industrial hygienist before closing out the job."*

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

Critical JSON rules:
- All string values must escape internal double quotes as `\"`. If you write `"we," "us," or "our"`, escape as `\"we,\" \"us,\" or \"our\"`.
- No code fences (no ```json ... ``` wrapping).
- No prose commentary before or after the JSON.
