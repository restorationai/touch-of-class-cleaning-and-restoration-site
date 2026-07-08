---
name: service-area
target_word_count: 800
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

# CRITICAL: UNIQUENESS

This page MUST satisfy all of:

1. Open with a paragraph that names what {brand.display_name} does specifically for {area.city} property owners — not generic "we serve this area."
2. Include a paragraph about why {area.city} sees the restoration emergencies it does — climate, housing stock, water table, code differences, regional factors.
3. List the services we provide in {area.city} (the planner will link them) — short paragraphs per service category that are FRAMED LOCALLY (e.g., "Water damage in {area.city} often involves [local pattern]").
4. Include a brief illustrative customer scenario for {area.city} — e.g., "*A property manager in [neighborhood] called us after [specific scenario]; we [response].*" Clearly framed as representative, not attributed to a real named person. These will be replaced with real testimonials over time.
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
- `## A recent {area.city} response` — illustrative scenario (1 paragraph)
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
