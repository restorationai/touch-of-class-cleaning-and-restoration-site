---
name: home
target_word_count: 700
faq_count: 5
---

Write the body for the **home page** of {brand.display_name}'s website.

# Page focus

- Primary search keyword: `{page.primary_keyword}`
- This is the most visible page on the site. It's a homeowner's first impression.

# Brand context (use naturally)

- Company: {brand.display_name} ({brand.legal_name})
- Phone: {brand.phone}
- HQ: {brand.primary_city}, {brand.primary_state}
- Founded: {brand.founded_year}
- Certifications: {brand.certifications}
- License: {brand.license_type}{brand.license_numbers_suffix}, {brand.license_authority}
- Tagline: {brand.tagline}

# What this page needs to do

1. Open with a short lead (strictly 1 concise paragraph maximum) that names what {brand.display_name} actually does — water, fire, mold, storm, biohazard, reconstruction — in language a stressed homeowner skims. Avoid corporate openers and lengthy histories. Readability is priority.
2. Establish trust quickly: years in business, certifications, insurance billing, 24/7 response.
3. Give a brief breakdown of the main service categories (3-4 services with one sentence each).
4. Anchor service area: {brand.primary_city} and surrounding {brand.primary_state} cities. Mention 2-3 nearby cities by name if obvious from context.
5. Close with a soft CTA acknowledging that anyone reading this is probably in the middle of an emergency.

# Structure

- Opening lead paragraph (no `##` heading)
- `## Services we handle` — 3-4 service sub-bullets or short paragraphs
- `## Why homeowners and property managers call us` — trust signals woven through
- `## Service area` — geographic coverage
- Closing CTA paragraph (no `##` heading)

Target: ~{target_word_count} words of body content.

# FAQ — write {faq_count} pairs

Topics for the home-page FAQ: response time, insurance billing, what to do while waiting, certifications, free estimates, after-hours coverage. Answers 2-4 sentences each.

Now generate the JSON.
