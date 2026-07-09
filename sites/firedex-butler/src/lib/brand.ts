// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "firedex-butler",
  displayName: "FireDEX Butler",
  shortName: "FireDEX",
  legalName: "FireDEX Butler, Inc.",
  domain: "firedex.net",
  canonicalUrl: "https://firedex.net",
  phone: "(724) 452-7400",
  phoneRaw: "+17244527400",
  email: "mail@firedex.net",
  hours: "24/7",
  foundedYear: "1981",
  primaryCity: "Cranberry Township",
  primaryState: "PA",
  streetAddress: "9133 Marshall Rd",
  postalCode: "16066",
  lat: "",
  lng: "",
  placeId: "ChIJ4zqdqGF9NIgR0zyEf6VVd80",
  googleCid: "14805396469301132499",
  imagesBase: "https://images.firedex.net",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "",
  licenseNumbers: ["PA001913"] as string[],
  licenseAuthority: "Pennsylvania Attorney General — Home Improvement Contractor Registration",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: [] as string[],
  trustBadges: [] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.google.com/maps?cid=14805396469301132499"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "Water • Fire • Storm Restoration — 24/7 emergency response across Cranberry Township, Butler County and the Pittsburgh North suburbs since 1981.",
  ctaLabel: "24/7 Emergency Hotline",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
