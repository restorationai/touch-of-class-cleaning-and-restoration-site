---
name: service-landing
target_word_count: 950
faq_count: 5
---

Write the body for the **{service.display_name}** canonical service page on {brand.display_name}'s website.

# Page focus

- Service: **{service.display_name}**
- Primary keyword: `{page.primary_keyword}`
- Secondary keywords (use naturally): {page.secondary_keywords}
- This is the location-neutral CANONICAL page for this service. The {service.display_name} × city combo pages link back here.

# CRITICAL: SERVICE-SPECIFIC UNIQUENESS

This page is the deep dive on {service.display_name} specifically. It must be impossible to confuse with any other service page on the site.

**Required:**

1. **Unique opening paragraph** that names a specific problem THIS service solves. Bad: *"We handle [service] for homeowners."* Good: opens with a specific symptom, timeline, or scenario that only matches this service.

2. **SERVICE-SPECIFIC PROCESS STEPS**. The body must include 3-4 concrete steps that are UNIQUE to {service.display_name}. Examples for different services:
   - Water damage: extraction → drying → moisture monitoring → containment for Category 2/3
   - Mold remediation: containment → air sampling → HEPA filtration → clearance testing
   - Fire damage: soot characterization → thermal fogging → ozone treatment → contents pack-out
   - Biohazard: PPE staging → bio-contaminant removal → enzymatic treatment → waste manifest
   - Reconstruction: scope of work → permits → framing → finishing

3. **SERVICE-SPECIFIC COMMON PROBLEMS** — what goes wrong, what gets missed by less-experienced operators, what insurance adjusters look for. Be technical where it matters.

4. **SERVICE-SPECIFIC FAQs**. Every FAQ on this page must be ABOUT THIS SERVICE. Do not write generic restoration FAQs that would fit on any service page.

   GOOD examples for {service.display_name}: (write FAQs that are this specific)
   - Water damage: "How long does structural drying typically take in different categories of water?"
   - Mold: "What level of mold remediation requires IICRC S520-compliant containment?"
   - Fire: "What's the difference between protein soot and synthetic soot, and why does cleanup vary?"
   - Biohazard: "What licenses are required to transport biohazard waste in this state?"

   BAD examples (DO NOT USE these on every service page):
   - "How much does it cost?" (use ONCE per site, on the about/contact page, not on every service)
   - "Do you bill insurance?" (use ONCE per site, on the contact page)
   - "How fast can you respond?" (use ONCE per site, on the home or contact page)

5. **SERVICE-SPECIFIC CTAs**. Bad: "Contact us today." Good: a CTA that names what the visitor is actually trying to do —
   - Water damage: "Schedule your moisture assessment"
   - Mold: "Request an air quality test"
   - Fire: "Begin smoke and soot removal"
   - Biohazard: "Begin discreet biohazard cleanup"
   - Reconstruction: "Get a reconstruction scope of work"

# Brand context (use naturally, do not list)

- Company: {brand.display_name}
- Phone: {brand.phone}
- HQ: {brand.primary_city}, {brand.primary_state}
- Certifications: {brand.certifications}
- License: {brand.license_type}{brand.license_numbers_suffix}

# Structure

- Opening paragraph (~80 words) — service-specific hook, not generic.
- `## What {service.display_name} actually involves` — concrete description of the work, equipment, and timeline. Be specific to THIS service.
- `## Our process` — 4-5 numbered steps SPECIFIC to {service.display_name}. Not a generic "we assess, we work, we clean up" template.
- `## What separates a good [service] response from a bad one` — common technical mistakes, what good operators do differently, what insurance adjusters look for.
- `## Seasonal & regional considerations` — only if relevant for this service (e.g., for water damage: freeze-thaw cycles; for storm damage: peak season; for mold: humidity windows).
- `## Service area` — brief mention of {brand.primary_city} and surrounding cities (the planner links service-area-service pages).
- Closing CTA paragraph (no heading) — service-specific CTA.

Target: ~{target_word_count} words.

{sensitive_block}

# FAQ — write {faq_count} pairs

All FAQs must be SPECIFIC TO {service.display_name}. See the GOOD/BAD examples above. Mix technical depth (process, equipment, timeline) with practical concerns (insurance documentation, what to do while waiting) — but EVERY question must clearly belong on a {service.display_name} page, not just any service page.

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
