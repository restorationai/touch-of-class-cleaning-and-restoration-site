// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "air-care-restoration",
  displayName: "Air Care Restoration",
  shortName: "Air Care Restoration",
  legalName: "Air Care Restoration",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "aircarerestoration.com",
  canonicalUrl: "https://aircarerestoration.com",
  phone: "(325) 339-8723",
  phoneRaw: "+13253398723",
  hideMobileHeaderCall: false,
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "(325) 896-3836",
  trackingPhoneRaw: "+13258963836",
  email: "info@aircarerestoration.com",
  hours: "24/7",
  foundedYear: "2026",
  primaryCity: "Abilene",
  primaryState: "TX",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "ABILENE",
  addressState: "TX",
  streetAddress: "2241 S 41ST ST SUITE A",
  postalCode: "79602",
  lat: "32.44645",
  lng: "-99.7475905",
  placeId: "ChIJAbX4Kjsyg2IRF9RgElzgJXk",
  googleCid: "",
  imagesBase: "https://images.aircarerestoration.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-FW5QLBCH24",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: ["MRC2262"] as string[],
  licenseAuthority: "Texas Department of Licensing and Regulation",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://www.tdlr.texas.gov/LicenseSearch/",
  licenseType: "Texas Mold Remediation Contractor License",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC CERTIFIED FIRM", "OSHA TRAINED", "IICRC WRT (WATER)", "IICRC FSRT (FIRE & SMOKE)", "EPA LEAD-SAFE CERTIFIED", "MRC2262-RCO1798-TCST-HST-OCT"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.facebook.com/aircarerestorationtx", "https://www.youtube.com/@AirCareRestorationLLC", "https://www.instagram.com/aircarerestoration/", "https://www.tiktok.com/@aircarerestoration", "https://www.linkedin.com/company/air-care-restoration/", "https://maps.google.com/maps?cid=8729630138777523223", "https://www.linkedin.com/in/sarha-boyd-45b165352"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Abilene, TX.",
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
  homeAboutBlurb: "Air Care Restoration serves Abilene and the surrounding TX area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
