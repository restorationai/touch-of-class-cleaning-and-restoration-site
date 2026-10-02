---
name: legal
target_word_count: 500
faq_count: 0
---

Write the body for a **legal** page for {brand.display_name}: specifically the **{legal_ref}** page.

# Brand context

- Legal name: {brand.legal_name}
- Address: {brand.street_address}, {brand.primary_city}, {brand.primary_state} {brand.postal_code}
- Email: {brand.email}
- Phone: {brand.phone}
- Domain: {brand.domain}

# Page

Based on `{legal_ref}`, write:

- **privacy** — A standard privacy policy covering: information we collect (contact form submissions, basic analytics), how we use it (responding to inquiries, scheduling estimates, insurance documentation), how we share it (only with the visitor's authorization to coordinate with insurance carriers; we don't sell data), retention period, visitor rights, and contact info for privacy questions. Reference common standards (CCPA if California residents may visit; GDPR is unlikely to apply to a US-only restoration contractor but mention if appropriate). Keep it readable, not legalese-heavy.

- **terms** — Terms of service covering: service area limitations, that estimates are not binding contracts until signed, payment terms and accepted methods, liability scope (we are licensed contractors operating within {brand.primary_state} state regulations), insurance coordination, scope of work clarifications, dispute resolution. Mention that signed work-authorization forms govern the actual service relationship.

- **accessibility** — A short accessibility statement: we aim to meet WCAG 2.1 AA, the site is built to be screen-reader compatible, contact info for accessibility issues, commitment to address reported issues within a reasonable window.

Target: ~{target_word_count} words.

# Structure

Use `##` subheadings naturally. Format as readable prose with clear sections. NOT a numbered list of clauses.

# FAQ

Return an empty FAQ array.

Now generate the JSON.
