// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "{{BRAND_SLUG}}",
  displayName: "{{BRAND_DISPLAY_NAME}}",
  shortName: "{{BRAND_SHORT_NAME}}",
  legalName: "{{BRAND_LEGAL_NAME}}",
  domain: "{{BRAND_DOMAIN}}",
  canonicalUrl: "{{BRAND_CANONICAL_URL}}",
  phone: "{{BRAND_PHONE}}",
  phoneRaw: "{{BRAND_PHONE_RAW}}",
  email: "{{BRAND_EMAIL}}",
  hours: "{{BRAND_HOURS}}",
  foundedYear: "{{BRAND_FOUNDED_YEAR}}",
  primaryCity: "{{BRAND_PRIMARY_CITY}}",
  primaryState: "{{BRAND_PRIMARY_STATE}}",
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
  licenseType: "{{BRAND_LICENSE_TYPE}}",
  certifications: {{BRAND_CERTIFICATIONS_JSON}} as string[],
  sameAsUrls: {{BRAND_SAME_AS_URLS_JSON}} as string[],
  gbpRatingValue: "{{BRAND_GBP_RATING_VALUE}}",
  gbpReviewCount: "{{BRAND_GBP_REVIEW_COUNT}}",
  tagline: "{{BRAND_TAGLINE}}",
  ctaLabel: "{{BRAND_CTA_LABEL}}",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
