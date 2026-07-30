// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "coastal-restoration-services",
  displayName: "Coastal Restoration Services Inc",
  shortName: "Coastal Restoration Services Inc",
  legalName: "Coastal Restoration Services Inc",
  domain: "",
  canonicalUrl: "https://None",
  phone: "(805) 345-7440",
  phoneRaw: "+18053457440",
  email: "tony@callcrs.com",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Vandenberg Village",
  primaryState: "CA",
  streetAddress: "217 E Fesler St",
  postalCode: "93454",
  lat: "34.9531295",
  lng: "-120.435857",
  placeId: "ChIJgb6Gdhxh4wYRjbzm6ELYT38",
  googleCid: "",
  imagesBase: "https://images.None",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
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
  tagline: "24/7 restoration services in Vandenberg Village, CA.",
  ctaLabel: "24/7 Emergency Line",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
