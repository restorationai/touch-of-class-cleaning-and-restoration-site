// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "homelyft-restoration-ms",
  displayName: "HomeLyft Restoration MS",
  shortName: "HomeLyft Restoration MS",
  legalName: "HomeLyft Restoration MS",
  domain: "",
  canonicalUrl: "https://None",
  phone: "+12282845200",
  phoneRaw: "+112282845200",
  email: "info@homelyft.net",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Gulfport",
  primaryState: "MS",
  streetAddress: "1311 SPRING Street",
  postalCode: "39507",
  lat: "",
  lng: "",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.None",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "https://images.None/brand/logo.png",
  licenseNumbers: ["RO 2728"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: ["IICRC Certified Firm", "IICRC WRT (Water)", "IICRC ASD (Structural Drying)", "EPA Lead-Safe Certified", "IICRC FSRT (Fire & Smoke)", "IICRC AMRT (Mold)", "OSHA Trained", "FORTIFIED Roofing (MS Windstorm) Certified"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Gulfport, MS.",
  ctaLabel: "24/7 Emergency Line",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  tradeNoun: "restoration",
  specialistPhrase: "Damage Restoration Specialists",
  announcementSuffix: "24/7 Emergency Response",
  homeAboutBlurb: "HomeLyft Restoration MS serves Gulfport and the surrounding MS area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
