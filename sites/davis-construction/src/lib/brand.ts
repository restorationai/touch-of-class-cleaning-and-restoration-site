// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "davis-construction",
  displayName: "Davis Construction Contractors",
  shortName: "Davis Construction Contractors",
  legalName: "Davis Construction Inc.",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "davisconstructioncontractors.com",
  canonicalUrl: "https://davisconstructioncontractors.com",
  phone: "(256) 771-0326",
  phoneRaw: "+12567710326",
  hideMobileHeaderCall: false,
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "(256) 257-0752",
  trackingPhoneRaw: "+12562570752",
  email: "davisheath09@gmail.com",
  hours: "Monday–Friday, 8:00 AM – 5:00 PM",
  foundedYear: "2008",
  primaryCity: "Madison",
  primaryState: "AL",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Madison",
  addressState: "AL",
  streetAddress: "",
  postalCode: "",
  lat: "34.77368",
  lng: "-86.56751",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.davisconstructioncontractors.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-BRL1Q2KTGV",
  clarityProjectId: "xdoje59wr1",
  logoUrl: "https://images.davisconstructioncontractors.com/brand/logo.png",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: [] as string[],
  trustBadges: [] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://davisconstructioncontractors.com/about/"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "Construction and remodeling services in Madison, AL.",
  ctaLabel: "Call for a Free Estimate",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  // vertical gates layout too: restoration is call-first, so the homepage
  // hero renders NO estimate form there (Santino 2026-09-11).
  vertical: "construction",
  tradeNoun: "construction",
  specialistPhrase: "Construction & Remodeling Specialists",
  announcementSuffix: "Free Estimates",
  homeAboutBlurb: "Davis Construction Contractors serves Madison and the surrounding AL area with full-service construction and remodeling. From new construction and additions to roofing, siding, decks, and painting, our team manages every project from the first estimate to the final walkthrough.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
