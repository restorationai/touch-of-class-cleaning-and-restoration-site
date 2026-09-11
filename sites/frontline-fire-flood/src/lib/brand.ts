// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "frontline-fire-flood",
  displayName: "Frontline Fire & Flood",
  shortName: "Frontline Fire & Flood",
  legalName: "Frontline Fire & Flood",
  domain: "frontlinefireflood.com",
  canonicalUrl: "https://frontlinefireflood.com",
  phone: "+12532000503",
  phoneRaw: "+112532000503",
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "",
  trackingPhoneRaw: "",
  email: "service@frontlinefireflood.com",
  hours: "24/7",
  foundedYear: "2014",
  primaryCity: "Lakewood",
  primaryState: "WA",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Lakewood",
  addressState: "WA",
  streetAddress: "9520 Front St",
  postalCode: "98499",
  lat: "47.1717649",
  lng: "-122.518458",
  placeId: "ChIJK-c9495UkFQRpJu9uz3VE20",
  googleCid: "",
  imagesBase: "https://images.frontlinefireflood.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: ["CCFRONTFF761CB"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://secure.lni.wa.gov/verify/",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC CERTIFIED FIRM", "IICRC AMRT (MOLD)", "IICRC WRT (WATER)", "IICRC FSRT (FIRE & SMOKE)", "IICRC ASD (STRUCTURAL DRYING)", "EPA LEAD-SAFE CERTIFIED", "OSHA TRAINED"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Lakewood, WA.",
  ctaLabel: "24/7 Emergency Line",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  tradeNoun: "restoration",
  specialistPhrase: "Damage Restoration Specialists",
  announcementSuffix: "24/7 Emergency Response",
  homeAboutBlurb: "Frontline Fire & Flood serves Lakewood and the surrounding WA area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
