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
- Hours: {brand.hours}
- License: {brand.license_type}{brand.license_numbers_suffix}, {brand.license_authority}
- Tagline: {brand.tagline}
- Sister company (optional; empty = none — NEVER invent one): {brand.sister_company}

# What this page needs to do

1. Open with a short lead (strictly 1 concise paragraph maximum) that names what {brand.display_name} actually does — plumbing repair, drains and sewer, water heaters, heating, and air conditioning — in language a homeowner skims. Avoid corporate openers and lengthy histories. Readability is priority.
2. Establish trust quickly using ONLY what the brand context provides: years in business (only if Founded is set), certifications (only those listed), licensure (only if License data is present), availability (24/7 ONLY if the brand's Hours say so), upfront pricing process.
3. Give a brief breakdown of the main service categories (3-4 categories with one sentence each — e.g., emergency plumbing & drains, water heaters, heating, cooling).
4. Anchor service area: {brand.primary_city} and surrounding {brand.primary_state} cities. Mention 2-3 nearby cities by name if obvious from context.
5. Close with a soft CTA that works for both the burst-pipe caller and the quote shopper.

# Structure

- Opening lead paragraph (no `##` heading)
- `## Services we handle` — 3-4 service sub-bullets or short paragraphs
- `## Why homeowners and property managers call us` — trust signals woven through (truth-gated)
- `## Service area` — geographic coverage
- Closing CTA paragraph (no `##` heading)

Target: ~{target_word_count} words of body content.

# FAQ — write {faq_count} pairs

Topics for the home-page FAQ: scheduling and after-hours coverage (respect the brand's Hours), upfront pricing / free estimates, plumbing vs HVAC scope (one company for both), service area, what to do while waiting on an emergency call. Answers 2-4 sentences each.

Now generate the JSON.
