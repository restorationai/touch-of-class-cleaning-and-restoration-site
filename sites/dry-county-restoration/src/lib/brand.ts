// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "dry-county-restoration",
  displayName: "Dry County Restoration",
  shortName: "Dry County Restoration",
  legalName: "Dry County Restoration",
  domain: "",
  canonicalUrl: "https://None",
  phone: "(951) 667-9910",
  phoneRaw: "+19516679910",
  email: "stephen@drycountyrestoration.com",
  hours: "24/7",
  foundedYear: "2020",
  primaryCity: "Corona",
  primaryState: "CA",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Corona",
  addressState: "CA",
  streetAddress: "9064 Pulsar Ct. Suit I ",
  postalCode: "92883",
  lat: "33.8752945",
  lng: "-117.566444",
  placeId: "ChIJBQyutfy53IARKDqQsaEwmyQ",
  googleCid: "",
  imagesBase: "https://images.None",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "https://images.None/brand/logo.png",
  licenseNumbers: ["1083555"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC CERTIFIED FIRM", "IICRC WRT (WATER)", "IICRC ASD (STRUCTURAL DRYING)", "IICRC AMRT (MOLD)", "OSHA TRAINED"] as string[],
  trustBadges: ["Licensed & Insured", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Corona, CA.",
  ctaLabel: "24/7 Emergency Line",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  tradeNoun: "restoration",
  specialistPhrase: "Damage Restoration Specialists",
  announcementSuffix: "24/7 Emergency Response",
  homeAboutBlurb: "Dry County Restoration serves Corona and the surrounding CA area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
