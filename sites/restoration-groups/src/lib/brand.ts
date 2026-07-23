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
  phone: "(908) 970-8533",
  phoneRaw: "+19089708533",
  email: "office@restorationgroups.com",
  hours: "24/7",
  foundedYear: "2021",
  primaryCity: "Fair Lawn",
  primaryState: "NJ",
  streetAddress: "8 Harlow Crescent",
  postalCode: "07410",
  lat: "40.9403",
  lng: "-74.1318",
  placeId: "ChIJWYxcvlr6wokRi9KZOyNx400",
  googleCid: "5612453956771500683",
  imagesBase: "https://images.restorationgroups.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "",
  licenseNumbers: ["NJ HIC 13VH05488600"] as string[],
  licenseAuthority: "NJ Division of Consumer Affairs",
  licenseLookupUrl: "https://newjersey.mylicense.com/verification/",
  licenseType: "NJ Licensed Home Improvement Contractor",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC Certified Firm #210213"] as string[],
  trustBadges: ["500+ Google Reviews", "IICRC Certified Firm #210213", "NJ Licensed Home Improvement Contractor", "24/7 Emergency Response"] as string[],
  // Real job photos pulled from the client's existing sites
  // (restorationgroups.com + therestorationgroup.com), EXIF/GPS stripped.
  jobPhotos: [
    "/images/work/job-1.webp",
    "/images/work/job-2.webp",
    "/images/work/job-3.webp",
    "/images/work/job-4.webp",
    "/images/work/job-5.webp",
    "/images/work/job-6.webp",
  ] as string[],
  sameAsUrls: ["https://www.google.com/maps?cid=5612453956771500683", "http://facebook.com/EliteRestorationGroups", "https://www.instagram.com/eliterestorationgroup/"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 water, fire & mold damage restoration across New Jersey.",
  ctaLabel: "24/7 Emergency Line",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
