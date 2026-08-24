// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "tdi-builders",
  displayName: "TDI Builders, Inc.",
  shortName: "TDI Builders, Inc.",
  legalName: "TDI Builders, Inc.",
  domain: "tdiusa.com",
  canonicalUrl: "https://tdiusa.com",
  phone: "(877) 688-0866",
  phoneRaw: "+18776880866",
  email: "",
  hours: "24/7",
  foundedYear: "1985",
  primaryCity: "Sacramento",
  primaryState: "CA",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Sacramento",
  addressState: "CA",
  streetAddress: "701 Del Paso Rd",
  postalCode: "95834",
  lat: "38.6446",
  lng: "-121.5058",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.tdiusa.com",
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
  licensedInsuredAttested: true as boolean,
  certifications: ["LICENSED & INSURED", "COMMERCIAL, INDUSTRIAL & RESIDENTIAL", "40+ YEARS OF CONSTRUCTION & REBUILDING EXPERIENCE"] as string[],
  trustBadges: ["Commercial, Industrial & Residential", "Licensed & Insured", "40+ Years of Construction Experience", "Insurance Rebuilds Handled Direct"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "Construction and remodeling services in Sacramento, CA.",
  ctaLabel: "Call for a Free Estimate",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  tradeNoun: "construction",
  specialistPhrase: "Construction & Remodeling Specialists",
  announcementSuffix: "Free Estimates",
  homeAboutBlurb: "TDI Builders, Inc. serves Sacramento and the surrounding CA area with full-service construction and remodeling. From new construction and additions to roofing, siding, decks, and painting, our team manages every project from the first estimate to the final walkthrough.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
