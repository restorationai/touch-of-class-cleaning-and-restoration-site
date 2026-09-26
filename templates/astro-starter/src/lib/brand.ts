// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "{{BRAND_SLUG}}",
  displayName: "{{BRAND_DISPLAY_NAME}}",
  shortName: "{{BRAND_SHORT_NAME}}",
  legalName: "{{BRAND_LEGAL_NAME}}",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "{{BRAND_DBA_NAME}}",
  domain: "{{BRAND_DOMAIN}}",
  canonicalUrl: "{{BRAND_CANONICAL_URL}}",
  phone: "{{BRAND_PHONE}}",
  phoneRaw: "{{BRAND_PHONE_RAW}}",
  hideMobileHeaderCall: {{BRAND_HIDE_MOBILE_HEADER_CALL}},
  // A2P/SMS-registration legal entity. When set, the estimate forms render
  // the carrier-compliant consent checkbox naming this entity (exact wording
  // matters to reviewers — do not paraphrase). Empty = generic consent only.
  smsConsentEntity: "{{BRAND_SMS_CONSENT_ENTITY}}",
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "",
  trackingPhoneRaw: "",
  email: "{{BRAND_EMAIL}}",
  hours: "{{BRAND_HOURS}}",
  foundedYear: "{{BRAND_FOUNDED_YEAR}}",
  primaryCity: "{{BRAND_PRIMARY_CITY}}",
  primaryState: "{{BRAND_PRIMARY_STATE}}",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "{{BRAND_ADDRESS_CITY}}",
  addressState: "{{BRAND_ADDRESS_STATE}}",
  streetAddress: "{{BRAND_STREET_ADDRESS}}",
  postalCode: "{{BRAND_POSTAL_CODE}}",
  lat: "{{BRAND_LAT}}",
  lng: "{{BRAND_LNG}}",
  placeId: "{{BRAND_PLACE_ID}}",
  googleCid: "{{BRAND_GOOGLE_CID}}",
  imagesBase: "{{BRAND_IMAGES_BASE}}",
  googleMapsApiKey: "{{BRAND_GOOGLE_MAPS_API_KEY}}",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "{{BRAND_GA4_MEASUREMENT_ID}}",
  clarityProjectId: "{{BRAND_CLARITY_PROJECT_ID}}",
  logoUrl: "{{BRAND_LOGO_URL}}",
  licenseNumbers: {{BRAND_LICENSE_NUMBERS_JSON}} as string[],
  licenseAuthority: "{{BRAND_LICENSE_AUTHORITY}}",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "{{BRAND_LICENSE_LOOKUP_URL}}",
  licenseType: "{{BRAND_LICENSE_TYPE}}",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: {{BRAND_LICENSED_INSURED_ATTESTED_JSON}} as boolean,
  certifications: {{BRAND_CERTIFICATIONS_JSON}} as string[],
  trustBadges: {{BRAND_TRUST_BADGES_JSON}} as string[],
  jobPhotos: {{BRAND_JOB_PHOTOS_JSON}} as string[],
  sameAsUrls: {{BRAND_SAME_AS_URLS_JSON}} as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "{{BRAND_GBP_RATING_VALUE}}",
  gbpReviewCount: "{{BRAND_GBP_REVIEW_COUNT}}",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "{{BRAND_TAGLINE}}",
  // optional custom insurance positioning line (Hero renders only when set)
  insuranceTrustLine: "{{BRAND_INSURANCE_TRUST_LINE}}",
  ctaLabel: "{{BRAND_CTA_LABEL}}",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  // vertical gates layout too: restoration is call-first, so the homepage
  // hero renders NO estimate form there (Santino 2026-09-11).
  vertical: "{{BRAND_VERTICAL}}",
  tradeNoun: "{{BRAND_TRADE_NOUN}}",
  specialistPhrase: "{{BRAND_SPECIALIST_PHRASE}}",
  announcementSuffix: "{{BRAND_ANNOUNCEMENT_SUFFIX}}",
  homeAboutBlurb: "{{BRAND_HOME_ABOUT_BLURB}}",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
