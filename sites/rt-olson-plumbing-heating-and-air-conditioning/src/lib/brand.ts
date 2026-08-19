// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "rt-olson-plumbing-heating-and-air-conditioning",
  displayName: "RT Olson Plumbing, Heating and Air Conditioning",
  shortName: "RT Olson Plumbing, Heating and Air Conditioning",
  legalName: "RT Olson Plumbing, Heating and Air Conditioning",
  domain: "rtolsonplumbing.com",
  canonicalUrl: "https://rtolsonplumbing.com",
  phone: "(951) 344-5596",
  phoneRaw: "+19513445596",
  email: "office@rtoplumbing.com",
  hours: "24/7",
  foundedYear: "2014",
  primaryCity: "Corona",
  primaryState: "CA",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Corona",
  addressState: "CA",
  streetAddress: "9064 Pulsar Ct. Suite J",
  postalCode: "92883",
  lat: "33.8752945",
  lng: "-117.566444",
  placeId: "ChIJEXHd9pfR3IARQ_LumANTVG8",
  googleCid: "",
  imagesBase: "https://images.rtolsonplumbing.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: ["997337"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: [] as string[],
  trustBadges: ["Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "Plumbing, heating & air services in Corona, CA.",
  ctaLabel: "24/7 Emergency Line",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  tradeNoun: "plumbing",
  specialistPhrase: "Plumbing, Heating & Air Specialists",
  announcementSuffix: "24/7 Emergency Service",
  homeAboutBlurb: "RT Olson Plumbing, Heating and Air Conditioning serves Corona and the surrounding CA area with full-service plumbing, heating, and air conditioning. From emergency plumbing repairs, drain cleaning, and water heater service to complete AC and furnace installation, our technicians handle it all — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
