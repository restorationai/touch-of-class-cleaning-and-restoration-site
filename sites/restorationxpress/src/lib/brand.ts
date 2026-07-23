// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "restorationxpress",
  displayName: "RestorationXpress ",
  shortName: "RestorationXpress",
  legalName: "RestorationXpress ",
  domain: "",
  canonicalUrl: "https://None",
  phone: "(954) 964-6471",
  phoneRaw: "+19549646471",
  email: "issac@restorationxpress.com",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Davie",
  primaryState: "FL",
  streetAddress: "4700 SW 51 ST SUIT 205 DAVIE FL33314 ",
  postalCode: "33314",
  lat: "26.0628665",
  lng: "-80.2331038",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.None",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "https://images.None/brand/logo.png",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: [] as string[],
  trustBadges: [] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Davie, FL.",
  ctaLabel: "24/7 Emergency Line",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
