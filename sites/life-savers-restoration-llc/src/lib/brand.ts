// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "life-savers-restoration-llc",
  displayName: "Life Savers Restoration LLC",
  shortName: "Life Savers Restoration LLC",
  legalName: "Life Savers Restoration LLC",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "lifesaversrestorationvegas.com",
  canonicalUrl: "https://lifesaversrestorationvegas.com",
  phone: "(702) 845-1325",
  phoneRaw: "+17028451325",
  hideMobileHeaderCall: false,
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "(702) 930-8647",
  trackingPhoneRaw: "+17029308647",
  email: "info@lifesaversrestoration.com",
  hours: "24/7",
  foundedYear: "2019",
  primaryCity: "Henderson",
  primaryState: "NV",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Henderson",
  addressState: "NV",
  streetAddress: "7685 Commercial Way Ste G",
  postalCode: "89011",
  lat: "36.0319602",
  lng: "-114.9822716",
  placeId: "ChIJSxyUH2zVyIARwWXDMRxNoos",
  googleCid: "",
  imagesBase: "https://images.lifesaversrestorationvegas.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-EGE48LYQVZ",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: ["0091001"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://www.nvcontractorsboard.com/",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC CERTIFIED FIRM", "IICRC WRT (WATER)", "IICRC ASD (STRUCTURAL DRYING)", "IICRC AMRT (MOLD)", "IICRC FSRT (FIRE & SMOKE)", "EPA LEAD-SAFE CERTIFIED", "OSHA TRAINED"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://maps.google.com/maps?cid=10061689300988421569", "https://www.bbb.org/us/nv/henderson/profile/fire-water-damage-restoration/life-savers-restoration-llc-1086-90068182", "https://homeguide.com/nv/henderson/water-damage-restoration/life-savers-restoration-llc-UlP_1GhU4"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Henderson, NV.",
  ctaLabel: "24/7 Emergency Line",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  // vertical gates layout too: restoration is call-first, so the homepage
  // hero renders NO estimate form there (Santino 2026-09-11).
  vertical: "restoration",
  tradeNoun: "restoration",
  specialistPhrase: "Damage Restoration Specialists",
  announcementSuffix: "24/7 Emergency Response",
  homeAboutBlurb: "Life Savers Restoration LLC serves Henderson and the surrounding NV area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
