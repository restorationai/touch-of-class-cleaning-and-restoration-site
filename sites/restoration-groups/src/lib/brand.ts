// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "restoration-groups",
  displayName: "The Restoration Group",
  shortName: "The Restoration Group",
  legalName: "The Restoration Group",
  domain: "therestorationgroup.com",
  canonicalUrl: "https://therestorationgroup.com",
  phone: "(855) 650-7422",
  phoneRaw: "+18556507422",
  email: "",
  hours: "24/7",
  foundedYear: "2021",
  primaryCity: "Kenilworth",
  primaryState: "NJ",
  streetAddress: "500 S 31st St",
  postalCode: "07033",
  lat: "40.6749",
  lng: "-74.2957",
  placeId: "ChIJfZMnExzVxiIRkevldLILJW8",
  googleCid: "8008820373441604497",
  imagesBase: "https://images.therestorationgroup.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "",
  licenseNumbers: [] as string[],
  licenseAuthority: "NJ Division of Consumer Affairs",
  licenseType: "NJ Licensed Home Improvement Contractor",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC Certified Firm #210213"] as string[],
  trustBadges: ["IICRC Certified Firm #210213", "NJ Licensed Home Improvement Contractor", "24/7 Emergency Response", "Serving NJ Since 2021"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.google.com/maps?cid=8008820373441604497"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 water, fire & mold damage restoration across New Jersey.",
  ctaLabel: "24/7 Emergency Hotline",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
