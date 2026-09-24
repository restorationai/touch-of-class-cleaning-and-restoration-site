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
  // A2P/SMS-registration legal entity. When set, the estimate forms render
  // the carrier-compliant consent checkbox naming this entity (exact wording
  // matters to reviewers — do not paraphrase). Empty = generic consent only.
  smsConsentEntity: "",
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
  addressCity: "Abilene",
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
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "5.0",
  gbpReviewCount: "22",
  gbpReviews: [
    { author: "Callie", rating: 5, text: "Very efficient, very nice, great to work with.", when: "September 2026" },
    { author: "Adam", rating: 5, text: "Sarha with Air Care Restoration is a life savor. Our toilet overflowed causing sewage to flood our bathroom, hallway, and one of the bedrooms. Air Care Restoration answered our call, questions, and showed up in less than 45 minutes on a Friday night. This was our first time experiencing water…", when: "September 2026" },
    { author: "Craig", rating: 5, text: "Sarha genuinely cares about her customers and the quality of work is second to none!", when: "September 2026" },
    { author: "Untamablephoenix", rating: 5, text: "Sarha Boyd the owner of Air Care Restoration helped me so very much after I lost my mom. Sarha came promptly, was friendly, compassionate, and understanding. I can't thank Sarah enough for all that she did to help me and my family during such a horrific heartbreaking loss. She is an amazing person…", when: "September 2026" },
    { author: "Alonzo", rating: 5, text: "⭐⭐⭐⭐⭐ One of the best companies I’ve had the opportunity to come across. From start to finish, their team was professional, caring, responsive, and truly committed to providing the best service possible. They went above and beyond to make sure everything was handled properly, and their attention to…", when: "September 2026" },
    { author: "David", rating: 5, text: "Extremely professional crew, showed up quickly, answered all my questions and took care of business. would highly recommend to anyone! Thank you Sarha for everything!", when: "September 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
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
