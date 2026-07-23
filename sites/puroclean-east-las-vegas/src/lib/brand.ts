// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "puroclean-east-las-vegas",
  displayName: "PuroClean of East Las Vegas",
  shortName: "Puroclean",
  legalName: "PuroClean of East Las Vegas",
  domain: "purocleaneastlasvegas.com",
  canonicalUrl: "https://purocleaneastlasvegas.com",
  phone: "+17025513040",
  phoneRaw: "+117025513040",
  email: "eastlasvegas@puroclean.com",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Las Vegas",
  primaryState: "NV",
  streetAddress: "2777 N Lamb Blvd",
  postalCode: "89115",
  lat: "36.2153",
  lng: "-115.0867",
  placeId: "ChIJWRNeaVbDyIAR429H1EKyxas",
  googleCid: "",
  imagesBase: "https://images.purocleaneastlasvegas.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "https://images.purocleaneastlasvegas.com/brand/logo.png",
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
  tagline: "24/7 restoration services in Las Vegas, NV.",
  ctaLabel: "24/7 Emergency Line",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
