// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "flood-fixers",
  displayName: "Flood Fixers",
  shortName: "Flood Fixers",
  legalName: "Flood Fixers",
  domain: "flood-fixers.com",
  canonicalUrl: "https://flood-fixers.com",
  phone: "(855) 204-1124",
  phoneRaw: "+18552041124",
  email: "",
  hours: "24/7 Emergency Service",
  foundedYear: "",
  primaryCity: "San Diego",
  primaryState: "CA",
  streetAddress: "",
  postalCode: "",
  lat: "",
  lng: "",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.flood-fixers.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.webp",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation (plan-input.json
  // brand.licensed_insured_attested) — gates the TrustStrip badge when no
  // license number is on file yet.
  licensedInsuredAttested: true,
  // "EPA Lead-Safe Certified" is also on file (plan-input truth data); the
  // TrustStrip is operator-specced to 4 badges, so only IICRC renders there.
  certifications: ["IICRC Certified"] as string[],
  trustBadges: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  // Empty for this client: no GBP profile row yet, so no AggregateRating is
  // published and the ReviewsStrip renders nothing.
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in San Diego, CA.",
  ctaLabel: "24/7 Emergency Hotline",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
