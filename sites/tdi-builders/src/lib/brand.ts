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
  certifications: ["IICRC CERTIFIED TECHNICIANS", "LICENSED & INSURED", "40+ YEARS OF CONSTRUCTION & RESTORATION EXPERIENCE"] as string[],
  trustBadges: ["IICRC Certified Technicians", "Licensed & Insured", "24/7 Emergency Response", "Operator-Led, Not a Franchise"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Sacramento, CA.",
  ctaLabel: "24/7 Emergency Line",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  tradeNoun: "restoration",
  specialistPhrase: "Damage Restoration Specialists",
  announcementSuffix: "24/7 Emergency Response",
  homeAboutBlurb: "TDI Builders, Inc. serves Sacramento and the surrounding CA area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
