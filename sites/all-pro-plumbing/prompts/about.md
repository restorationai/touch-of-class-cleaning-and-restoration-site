---
name: about
target_word_count: 500
faq_count: 3
---

Write the body for the **About** page of {brand.display_name}'s website.

# Brand context

- Legal name: {brand.legal_name}
- Display name: {brand.display_name}
- Founded: {brand.founded_year}
- HQ: {brand.primary_city}, {brand.primary_state}
- Phone: {brand.phone}
- Certifications: {brand.certifications}
- Hours: {brand.hours}
- License: {brand.license_type}{brand.license_numbers_suffix}, {brand.license_authority}
- Sister company (optional; empty = none — NEVER invent one): {brand.sister_company}

# What this page covers

This is a trust-building page — visitors land here after seeing a service page or a blog post and want to know who's actually behind the company. Avoid the "we take pride in serving our community" trap entirely.

Cover, in order:
1. Brief origin: when {brand.display_name} started (ONLY if Founded is provided — otherwise skip the timeline entirely), and why a combined plumbing + heating + air focus (one company, one number for the systems that run a house). Don't invent founder names or backstories.
2. What we do every day: not a service list (we have separate pages for that) but the *texture* of the work — morning dispatch boards, no-cool calls in triple-digit heat, water heaters that quit on a Sunday, permits and inspections on installs. Availability claims per the brand's Hours only.
3. Credentials — ONLY what the brand context backs. If License data is present, explain what a state contractor license means for the homeowner; if Certifications are listed, explain them (EPA 608 governs refrigerant handling; NATE is an HVAC technician certification). If neither is present, write about workmanship standards, permits, and code compliance in general WITHOUT claiming "licensed" or "certified" status.
4. The service region: {brand.primary_city} and surrounding {brand.primary_state} cities — describe the area honestly.

# Structure

- Opening paragraph (no heading)
- `## What we do`
- `## How we work` (standards, pricing process, permits — truth-gated credentials)
- `## Where we work`

Target: ~{target_word_count} words.

# FAQ — write {faq_count} pairs

Topics: areas served, whether one company really handles both plumbing and HVAC, scheduling/hours, ownership/leadership at a high level (no fabricated names, no unbacked credential claims).

Now generate the JSON.
