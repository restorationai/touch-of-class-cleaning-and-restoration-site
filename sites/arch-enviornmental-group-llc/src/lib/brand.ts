// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "arch-enviornmental-group-llc",
  displayName: "Arch Enviornmental Group LLC",
  shortName: "Arch Enviornmental Group LLC",
  legalName: "Arch Enviornmental Group LLC",
  domain: "archenviroservice.com",
  canonicalUrl: "https://archenviroservice.com",
  phone: "(559) 296-2088",
  phoneRaw: "+15592962088",
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "(559) 254-4763",
  trackingPhoneRaw: "+15592544763",
  email: "info@archenviroservice.com",
  hours: "24/7",
  foundedYear: "2026",
  primaryCity: "Kingsburg",
  primaryState: "CA",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Kingsburg",
  addressState: "CA",
  streetAddress: "2453 16th Ave",
  postalCode: "93631",
  lat: "36.5138398",
  lng: "-119.5538929",
  placeId: "ChIJw9aO0Idq82sRNFXGkfL6roA",
  googleCid: "",
  imagesBase: "https://images.archenviroservice.com",
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
  certifications: ["CERTIFIED ASBESTOS CONSULTANT - LEAD INSPECTOR ASSESSOR - NIOSH 582 MICROSCOPIST"] as string[],
  trustBadges: ["Licensed & Insured", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "Independent environmental testing and inspections in Kingsburg, CA.",
  ctaLabel: "Schedule an Inspection",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  tradeNoun: "environmental testing",
  specialistPhrase: "Environmental Testing & Inspection Specialists",
  announcementSuffix: "Independent, Lab-Verified Testing",
  homeAboutBlurb: "Arch Enviornmental Group LLC provides independent environmental testing and inspections for homes and businesses across Kingsburg and the surrounding CA area. From mold and air quality testing to asbestos, lead, and water testing, every assessment is backed by accredited laboratory analysis and a clear written report. Because we don't perform the remediation ourselves, our findings are unbiased: we have no incentive to find problems that aren't there.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
