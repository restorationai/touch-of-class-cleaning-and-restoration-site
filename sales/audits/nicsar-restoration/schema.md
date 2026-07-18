# Schema.org Audit — nicsar-restoration.com
**Date:** 2026-07-12
**Site:** Water/fire/storm damage restoration — Nicsar Restoration Contractors Inc., Hoffman Estates IL
**Pages audited:** 36 (homepage + 35 crawled)

---

## 1. Existing Schema Detection

### Format
All schema is delivered via a single **Yoast SEO @graph JSON-LD block** per page (`application/ld+json`). No Microdata or RDFa is present in JSON-LD — however, the Reviews page contains **partial Microdata** for `schema.org/Rating` injected by the Elementor rating widget (three `reviewRating` nodes with no parent `Review` or `AggregateRating` wrapper — orphaned and not parseable by Google).

### Schema types present site-wide

| Type | Pages | Notes |
|------|-------|-------|
| WebSite | All 36 | With SearchAction potentialAction |
| WebPage | All 36 | Standard Yoast output |
| Organization | All 36 | Severely incomplete (see validation below) |
| BreadcrumbList | All 36 | Functional on interior pages; broken on homepage |
| ImageObject | 34/36 | Missing on reviews and contact pages (no primary image) |

### Schema types NOT present anywhere
- LocalBusiness / HomeAndConstructionBusiness / EmergencyService
- Service
- FAQPage
- Review / AggregateRating
- Person
- VideoObject
- Event / JobPosting

---

## 2. Validation Results

### Block: WebPage (all pages)
| Check | Result |
|-------|--------|
| @context = "https://schema.org" | PASS |
| @type valid | PASS |
| url absolute | PASS |
| name present | PASS |
| datePublished ISO 8601 | PASS |
| dateModified ISO 8601 | PASS |
| description present | FAIL — 14 fire-damage city pages have no description in schema (mirrors missing meta description) |

**Critical content error:** `fire-damage-restoration-barrington-hills-il/` has `"name": "Fire Damage Restoration Lemont, IL - Nicsar Restoration"` in both its `<title>` and WebPage schema `name` property. The page URL says Barrington Hills but the content is a copy-paste of the Lemont page. The WebPage schema `url` is correct but `name` contradicts it — Google will see a mismatch between canonical URL and schema name.

### Block: BreadcrumbList
| Check | Result |
|-------|--------|
| Homepage ListItem position 1 has `item` URL | FAIL — homepage breadcrumb omits `"item"` on position 1. Google requires `item` on all but the last ListItem. Yoast omits it on the current page (position 1 on homepage = current page), which is actually acceptable per Yoast's behavior, but it means the homepage has a single-item breadcrumb with no linked URL, providing zero breadcrumb rich result value. |
| Interior pages ListItem final position has no `item` | PASS — correct per spec (last item = current page, item URL optional) |
| All other positions have `item` | PASS |

### Block: Organization
| Check | Result |
|-------|--------|
| @context | PASS (inherited from @graph) |
| @type | FAIL — typed as generic `Organization`, not `LocalBusiness` or more specific subtype |
| name | PASS — "Nicsar Restoration" |
| url | PASS |
| logo | PASS (ImageObject with width/height) |
| telephone | FAIL — MISSING |
| address (PostalAddress) | FAIL — MISSING |
| areaServed | FAIL — MISSING |
| openingHoursSpecification | FAIL — MISSING (24/7 emergency service not declared) |
| sameAs | FAIL — MISSING (no Google Maps, Yelp, Facebook, etc.) |
| geo (GeoCoordinates) | FAIL — MISSING |
| priceRange | MISSING (recommended for local) |
| hasOfferCatalog | MISSING |

**Score: 2/9 required/recommended properties present.** This is the single largest schema gap on the site.

### Block: WebSite
| Check | Result |
|-------|--------|
| SearchAction potentialAction | PASS |
| name | PASS |
| url | PASS |

### Partial Microdata on reviews.html — Orphaned Rating widgets
Three Elementor rating widgets output:
```html
<div itemtype="https://schema.org/Rating" itemscope itemprop="reviewRating">
  <meta itemprop="worstRating" content="0">
  <meta itemprop="bestRating" content="5">
  <div itemprop="ratingValue" content="5">
```
These are `reviewRating` properties with no parent `Review` itemscope. Google cannot parse them. `worstRating` of `0` is also incorrect — schema.org specifies worst/best as the scale boundaries; 0 is non-standard (should be `1`). These are ignored by rich result parsers but exist in the DOM.

---

## 3. Present vs. Missing — Site-Wide Assessment

### Present (partial credit only)
- WebSite + SearchAction — functional but low SEO value alone
- WebPage — standard, satisfies basic structured data presence
- BreadcrumbList — functional on 35/36 pages; eligible for breadcrumb rich results
- Organization (stub) — name and logo only; insufficient for local signals

### Missing (high-priority gaps)

**CRITICAL — No LocalBusiness schema anywhere on the site.**
This is the most impactful gap. For a restoration SAB, Google uses LocalBusiness (or its subtypes `HomeAndConstructionBusiness`, `EmergencyService`) to power Knowledge Panel data, Local Pack signals, and AI answer entity disambiguation. The site has none.

**HIGH — No Service schema on any of the 28 city/service pages.**
Every water-damage, fire-damage, and storm-damage city page is a rich opportunity for `Service` with `areaServed`, `provider`, and `serviceType`. All 28 pages currently output only generic WebPage.

**HIGH — No FAQPage schema despite on-page FAQ content.**
All service pages (both Hoffman Estates hub pages and city pages) contain a "Frequently Asked Questions" section with 5 Q&A pairs marked up in `<strong>` question / `<p>` answer format. Zero FAQPage schema is implemented.

Note on FAQPage restriction: Google restricted FAQPage rich results to government and healthcare sites in August 2023. Adding FAQPage will NOT produce Google FAQ rich result snippets for this commercial site. However, FAQPage markup is strongly recommended for AI/LLM citation engines (ChatGPT, Perplexity, Google AI Overviews) which actively consume it. Implement for GEO (Generative Engine Optimization) value.

**MEDIUM — No AggregateRating or Review schema on reviews page.**
The reviews page contains three on-page testimonials with names (Michael R., Sarah L., David M.) and star ratings (all 5/5). These are not third-party Google reviews — they are site-owned testimonials. `AggregateRating` requires a minimum count and should only be used if reviews are genuinely present on-page. These three testimonials could support `Review` markup with `author`, `reviewBody`, `reviewRating`, and `datePublished` (if dates are available — none are visible in the HTML). Implement as `Review` items only; do not add `AggregateRating` without a real aggregate count.

**LOW — No sameAs links on Organization.**
No social profiles (Facebook, Instagram, Yelp, Houzz) are linked from the site HTML at all — not even in the footer. The Google Maps embed confirms the business exists at place_id `ChIJFYgRLp2pD4gRJhtgSstaDN4`. This should be in `sameAs`.

**CONTENT BUG (not schema) — fire-damage-restoration-barrington-hills-il/**
Title, H1, meta description, and WebPage schema `name` all reference "Lemont, IL" instead of "Barrington Hills, IL". This is a copy-paste template error that will harm rankings for that page.

---

## 4. Generated JSON-LD — Ready to Paste

### 4a. LocalBusiness — Homepage (`https://nicsar-restoration.com/`)

Add this block to the homepage `<head>`, alongside (not replacing) the existing Yoast block. The `@id` uses a distinct fragment (`#localbusiness`) to avoid colliding with Yoast's `#organization`.

```json
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": ["LocalBusiness", "HomeAndConstructionBusiness", "EmergencyService"],
  "@id": "https://nicsar-restoration.com/#localbusiness",
  "name": "Nicsar Restoration",
  "legalName": "Nicsar Restoration Contractors Inc.",
  "url": "https://nicsar-restoration.com/",
  "logo": "https://nicsar-restoration.com/wp-content/uploads/2021/04/nicsar-restoration-contractors-inc.png",
  "image": "https://nicsar-restoration.com/wp-content/uploads/2025/11/full-restotation-services.jpg",
  "description": "Professional water, fire, storm, and flood damage restoration for residential and commercial properties in Hoffman Estates, IL and the greater Chicagoland area.",
  "telephone": "+1-773-220-6751",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "2400 Hassell Rd Ste 420",
    "addressLocality": "Hoffman Estates",
    "addressRegion": "IL",
    "postalCode": "60169",
    "addressCountry": "US"
  },
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": 42.062,
    "longitude": -88.139
  },
  "hasMap": "https://maps.google.com/?cid=16002847513600803622",
  "sameAs": [
    "https://www.google.com/maps/place/?q=place_id:ChIJFYgRLp2pD4gRJhtgSstaDN4"
  ],
  "openingHoursSpecification": [
    {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday"
      ],
      "opens": "00:00",
      "closes": "23:59"
    }
  ],
  "areaServed": [
    {"@type": "City", "name": "Hoffman Estates", "sameAs": "https://en.wikipedia.org/wiki/Hoffman_Estates,_Illinois"},
    {"@type": "City", "name": "Schaumburg", "sameAs": "https://en.wikipedia.org/wiki/Schaumburg,_Illinois"},
    {"@type": "City", "name": "Barrington", "sameAs": "https://en.wikipedia.org/wiki/Barrington,_Illinois"},
    {"@type": "City", "name": "Downers Grove", "sameAs": "https://en.wikipedia.org/wiki/Downers_Grove,_Illinois"},
    {"@type": "City", "name": "Naperville", "sameAs": "https://en.wikipedia.org/wiki/Naperville,_Illinois"},
    {"@type": "City", "name": "Bolingbrook", "sameAs": "https://en.wikipedia.org/wiki/Bolingbrook,_Illinois"},
    {"@type": "City", "name": "Hinsdale", "sameAs": "https://en.wikipedia.org/wiki/Hinsdale,_Illinois"},
    {"@type": "City", "name": "Burr Ridge", "sameAs": "https://en.wikipedia.org/wiki/Burr_Ridge,_Illinois"},
    {"@type": "City", "name": "Westmont", "sameAs": "https://en.wikipedia.org/wiki/Westmont,_Illinois"},
    {"@type": "City", "name": "Tinley Park", "sameAs": "https://en.wikipedia.org/wiki/Tinley_Park,_Illinois"},
    {"@type": "City", "name": "Orland Park", "sameAs": "https://en.wikipedia.org/wiki/Orland_Park,_Illinois"},
    {"@type": "City", "name": "Mokena", "sameAs": "https://en.wikipedia.org/wiki/Mokena,_Illinois"},
    {"@type": "City", "name": "Homer Glen", "sameAs": "https://en.wikipedia.org/wiki/Homer_Glen,_Illinois"},
    {"@type": "City", "name": "Lemont", "sameAs": "https://en.wikipedia.org/wiki/Lemont,_Illinois"},
    {"@type": "AdministrativeArea", "name": "Chicagoland"}
  ],
  "hasOfferCatalog": {
    "@type": "OfferCatalog",
    "name": "Restoration Services",
    "itemListElement": [
      {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Water Damage Restoration"}},
      {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Fire Damage Restoration"}},
      {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Storm and Flood Restoration"}},
      {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Insurance Claims Assistance"}}
    ]
  },
  "priceRange": "$$"
}
</script>
```

**Implementation note:** Add as a second `<script type="application/ld+json">` block in `<head>`. Do not merge with Yoast's block — Yoast manages its own graph. Google supports multiple LD+JSON blocks per page.

**sameAs to add when available:** Facebook page URL, Yelp business URL, BBB listing URL, Angi/HomeAdvisor profile URL. Add each as an additional string in the `sameAs` array.

---

### 4b. Service + areaServed — City Page Template
**Template for:** `water-damage-restoration-schaumburg-il/`
**Apply the same pattern to all 28 city/service pages**, substituting `[CITY]`, `[STATE]`, `[SERVICE_TYPE]`, `[SERVICE_NAME]`, and `[PAGE_URL]` per page.

```json
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Service",
  "@id": "https://nicsar-restoration.com/water-damage-restoration-schaumburg-il/#service",
  "name": "Water Damage Restoration in Schaumburg, IL",
  "serviceType": "Water Damage Restoration",
  "description": "Professional water damage restoration in Schaumburg, IL for homes and businesses. Fast mitigation and reliable restoration solutions including water removal, structural drying, and full property repair.",
  "url": "https://nicsar-restoration.com/water-damage-restoration-schaumburg-il/",
  "provider": {
    "@type": "LocalBusiness",
    "@id": "https://nicsar-restoration.com/#localbusiness"
  },
  "areaServed": {
    "@type": "City",
    "name": "Schaumburg",
    "containedInPlace": {
      "@type": "State",
      "name": "Illinois"
    },
    "sameAs": "https://en.wikipedia.org/wiki/Schaumburg,_Illinois"
  },
  "availableChannel": {
    "@type": "ServiceChannel",
    "servicePhone": {
      "@type": "ContactPoint",
      "telephone": "+1-773-220-6751",
      "contactType": "customer service",
      "availableLanguage": "English",
      "hoursAvailable": {
        "@type": "OpeningHoursSpecification",
        "dayOfWeek": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
        "opens": "00:00",
        "closes": "23:59"
      }
    }
  },
  "hasOfferCatalog": {
    "@type": "OfferCatalog",
    "name": "Water Damage Restoration Services",
    "itemListElement": [
      {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Emergency Water Extraction"}},
      {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Structural Drying"}},
      {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Moisture Detection and Monitoring"}},
      {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Mold Prevention"}},
      {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Property Repair and Restoration"}}
    ]
  }
}
</script>
```

**Substitution guide for all 28 city pages:**

| Page slug pattern | `serviceType` value | `name` pattern |
|---|---|---|
| `water-damage-restoration-[city]-il` | "Water Damage Restoration" | "Water Damage Restoration in [City], IL" |
| `fire-damage-restoration-[city]-il` | "Fire Damage Restoration" | "Fire Damage Restoration in [City], IL" |
| `storm-and-flood-restoration-hoffman-estates-il` | "Storm and Flood Restoration" | "Storm and Flood Restoration in Hoffman Estates, IL" |
| `insurance-claims-assistance-hoffman-estates-il` | "Insurance Claims Assistance" | "Insurance Claims Assistance in Hoffman Estates, IL" |

For fire-damage pages, update `hasOfferCatalog` items to: Fire Damage Assessment, Smoke and Soot Removal, Odor Elimination, Structural Cleanup, Content Restoration.

---

### 4c. FAQPage — Water Damage City Page Example
**Template for:** `water-damage-restoration-schaumburg-il/` (and all water-damage city pages)

Note: Google will not show FAQ rich results for this commercial site (restricted since August 2023). This markup targets AI/LLM citation engines (Google AI Overviews, Perplexity, ChatGPT) for GEO benefit.

```json
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "@id": "https://nicsar-restoration.com/water-damage-restoration-schaumburg-il/#faq",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "How quickly should water damage restoration begin?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Restoration should start as soon as possible to reduce the risk of structural damage and additional complications. Nicsar Restoration offers 24/7 emergency response for water damage in Schaumburg, IL."
      }
    },
    {
      "@type": "Question",
      "name": "Can water damage affect areas that do not look wet?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes. Moisture can travel beneath floors and inside wall systems, which is why professional inspection and moisture monitoring is important even in areas that appear dry."
      }
    },
    {
      "@type": "Question",
      "name": "Do you restore both residential and commercial properties in Schaumburg?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes. Nicsar Restoration provides water damage restoration for homes, offices, retail locations, and other commercial facilities throughout Schaumburg, IL."
      }
    },
    {
      "@type": "Question",
      "name": "How long does the drying phase usually take?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "The drying timeline depends on moisture levels and material types. Some projects take several days, while others with more extensive damage require additional time. Our team monitors progress throughout the process."
      }
    },
    {
      "@type": "Question",
      "name": "Are repairs included after drying is complete?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes. Once drying is complete, Nicsar Restoration provides full repair and restoration services to return your property to its pre-damage condition."
      }
    }
  ]
}
</script>
```

**Apply the same structure to:**
- All 14 water-damage city pages (update city name in answers where relevant)
- All 14 fire-damage city pages (replace with fire-specific Q&A from their FAQ sections)
- `storm-and-flood-restoration-hoffman-estates-il/` (use: "What should I do first if my property floods during a storm?", "Do you service both homes and commercial buildings?", "How long does the drying process take after a flood?", "Can storm-related structural damage be repaired during restoration?")
- `insurance-claims-assistance-hoffman-estates-il/` (use: "Do you help both homeowners and business owners with insurance claims?", "Can you speak with my insurance adjuster?", "What types of damage can be included in an insurance claim?", "Do I need to be present when the adjuster comes?")

---

## 5. Additional Issues Noted (Non-Schema)

These are outside schema scope but surfaced during the audit:

1. **Homepage has no H1 tag** — confirmed by crawler (h1_count: 0). The hero section uses styled divs rather than a heading element. Critical on-page SEO issue.
2. **All 14 fire-damage city pages missing meta description** — the Yoast WebPage schema `description` field will also be empty on these pages.
3. **Template clone error on fire-damage-restoration-barrington-hills-il/** — title, H1, meta description, and WebPage schema `name` all say "Lemont, IL" instead of "Barrington Hills, IL". Page needs full content correction.
4. **6 images on homepage missing alt text** — signals weak accessibility and reduces image schema signal quality.
5. **No social media profiles linked from site** — limits `sameAs` population and entity disambiguation across the web.

---

## 6. Implementation Priority Order

| Priority | Action | Impact |
|----------|--------|--------|
| 1 — Critical | Add LocalBusiness JSON-LD to homepage | Local Pack signals, Knowledge Panel, entity disambiguation |
| 2 — Critical | Fix homepage H1 (not schema, but foundational) | Core on-page signal |
| 3 — Critical | Fix Barrington Hills page clone error | Prevents ranking for wrong city |
| 4 — High | Add Service schema to all 28 city/service pages | Rich result eligibility, AI citation |
| 5 — High | Add FAQPage schema to all service pages | AI Overview / LLM citation (GEO) |
| 6 — High | Add meta descriptions to all 14 fire-damage pages | CTR + WebPage schema description |
| 7 — Medium | Add Review markup for 3 on-page testimonials (reviews page) | Structured review entity signal |
| 8 — Medium | Add social profile URLs to sameAs once profiles exist | Entity confidence |
| 9 — Low | Fix orphaned Microdata Rating on reviews page (worstRating=0) | Schema hygiene |

---

## Schema Score: 18 / 100

**Scoring rationale:**

| Category | Max | Score | Reason |
|----------|-----|-------|--------|
| LocalBusiness / entity schema | 30 | 0 | Completely absent; Organization stub typed generically with 2/9 properties |
| Service schema on service pages | 20 | 0 | Zero Service schema across all 28 city/service pages |
| BreadcrumbList | 15 | 11 | Present and functional on 35/36 pages; homepage single-item issue |
| WebSite + WebPage | 10 | 8 | Present everywhere; minor description gaps on fire pages |
| FAQPage | 10 | 0 | FAQ content exists on every service page; zero markup |
| Review / AggregateRating | 10 | 0 | On-page testimonials exist; zero markup |
| Technical validity (context, URLs, dates) | 5 | 4 | All LD+JSON is valid JSON; @context correct; one template content mismatch |
| **Total** | **100** | **23** | |

Adjusted down to **18** for the critical Barrington Hills content error (schema name mismatches canonical URL) and the orphaned Microdata on the reviews page that could confuse parsers.

The site's Yoast-generated baseline is technically clean but delivers almost no local or service-level structured data value for a restoration business. Implementing items 1-5 in the priority list above would realistically push the score to 70+.
