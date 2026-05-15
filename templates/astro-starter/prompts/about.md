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
- License: {brand.license_type}{brand.license_numbers_suffix}, {brand.license_authority}

# What this page covers

This is a trust-building page — visitors land here after seeing a service page or a blog post and want to know who's actually behind the company. Avoid the "we take pride in serving our community" trap entirely.

Cover, in order:
1. Brief origin: when {brand.display_name} started, why restoration as a focus (don't invent specific founder names or backstories unless we have them — keep it honest at a company level).
2. What we do every day: not a service list (we have separate pages for that) but the *texture* of the work — being on call 24/7, working insurance claims, responding to homeowners in the worst moments of their year.
3. Our certifications and what they actually mean: IICRC sets industry standards; EPA Lead-Safe is a federal certification required for pre-1978 homes; ANSI accreditation, etc. Don't just list them.
4. The service region: {brand.primary_city} and surrounding {brand.primary_state} cities — describe the area honestly.

# Structure

- Opening paragraph (no heading)
- `## What we do`
- `## Our certifications and licensure`
- `## Where we work`

Target: ~{target_word_count} words.

# FAQ — write {faq_count} pairs

Topics: how long {brand.display_name} has been in business, locations/areas served, certifications, ownership/leadership at a high level (no fabricated names).

Now generate the JSON.
