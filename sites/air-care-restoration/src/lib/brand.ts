// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "air-care-restoration",
  displayName: "Air Care Restoration",
  shortName: "Air Care Restoration",
  legalName: "Air Care Restoration",
  domain: "aircarerestoration.com",
  canonicalUrl: "https://aircarerestoration.com",
  phone: "(325) 339-8723",
  phoneRaw: "+13253398723",
  // Sitewide call-tracking display number (DNI — see BaseLayout).
  // Schema/NAP keep the canonical number above.
  trackingPhone: "(325) 666-5949",
  trackingPhoneRaw: "+13256665949",
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
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  // Sarha 2026-08-21: company license and personal license kept SEPARATE —
  // RCO1798 is the company (Texas Mold Remediation Company), MRC2262 is
  // Sarha Boyd personally (Texas Mold Remediation Contractor). Never blob
  // credentials into one string; never imply the EPA cert is a firm cert
  // (she holds EPA Certified Renovator personally; firm cert pending).
  licenseNumbers: ["RCO1798", "MRC2262"] as string[],
  licenseAuthority: "Texas Department of Licensing and Regulation",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://www.tdlr.texas.gov/LicenseSearch/",
  licenseType: "Texas Mold Remediation Company RCO1798 | Sarha Boyd — Texas Mold Remediation Contractor MRC2262",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC CERTIFIED FIRM", "BBB ACCREDITED BUSINESS", "IICRC WRT (WATER)", "IICRC FSRT (FIRE & SMOKE)", "IICRC OCT (ODOR)", "IICRC TCST (TRAUMA & CRIME SCENE)", "IICRC HST (HEALTH & SAFETY)", "EPA CERTIFIED RENOVATOR — LEAD RRP (SARHA BOYD)"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.yelp.com/biz/RjvrqMiPOqSCv-PxuabE1w", "https://www.bbb.org/us/tx/abilene/profile/flood-emergency/air-care-restoration-llc-0795-48105", "https://www.facebook.com/aircarerestorationtx/"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "5.0",
  gbpReviewCount: "15",
  gbpReviews: [
    { author: "Clark", rating: 5, text: "Superb response time to water damage in Abilene, and professional industry knowledge. Professional prompt service and helped out with insurance guidance, and recommendations for remediation for a fire damaged home.", when: "August 2026" },
    { author: "Rentl", rating: 5, text: "I cannot recommend Air Care Restoration enough! As a landlord, dealing with property emergencies is always stressful, but they have responded quickly to water leaks at two of my rental properties and handled everything flawlessly. Their team was fast, incredibly communicative, and went above and…", when: "August 2026" },
    { author: "Kiki", rating: 5, text: "I had an outstanding experience with Air Care Restoration in Abilene, TX After dealing with breathing issues, I called them out to inspect my home for mold. They arrived right on time for our scheduled appointment and conducted a thorough inspection of all water sources in the house. They located…", when: "August 2026" },
    { author: "Jody", rating: 5, text: "Air Care Restoration was professional prompt and kind. A storm caused significant damage to my brand new business. Insurance was very slow, Air Care Restoration was not. I will definitely use them in the future should I need too. Thank you!", when: "August 2026" },
    { author: "Missy", rating: 5, text: "I am writing to provide professional feedback regarding my recent experience with Air Care Restoration. On August 11, I spoke with the owner, Sarha, who provided a detailed overview of her credentials and the company's capabilities. Her thoroughness in addressing my specific needs was a deciding…", when: "August 2026" },
    { author: "Bayli", rating: 5, text: "I had an amazing experience with Air Care Restoration! From the moment I called, the team was professional, friendly, and quick to respond. They explained everything clearly, arrived on time, and treated my home with care and respect. Their attention to detail and quality of work exceeded my…", when: "August 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Abilene, TX.",
  ctaLabel: "24/7 Emergency Line",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  tradeNoun: "restoration",
  specialistPhrase: "Damage Restoration Specialists",
  announcementSuffix: "24/7 Emergency Response",
  homeAboutBlurb: "Air Care Restoration serves Abilene and the surrounding TX area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
