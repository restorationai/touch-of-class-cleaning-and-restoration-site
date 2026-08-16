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
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC CERTIFIED FIRM", "OSHA TRAINED", "IICRC WRT (WATER)", "IICRC FSRT (FIRE & SMOKE)", "EPA LEAD-SAFE CERTIFIED", "MRC2262-RCO1798-TCST-HST-OCT"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.yelp.com/biz/RjvrqMiPOqSCv-PxuabE1w", "https://www.bbb.org/us/tx/abilene/profile/flood-emergency/air-care-restoration-llc-0795-48105", "https://www.facebook.com/aircarerestorationtx/"] as string[],
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
  tradeNoun: "restoration",
  specialistPhrase: "Damage Restoration Specialists",
  announcementSuffix: "24/7 Emergency Response",
  homeAboutBlurb: "Air Care Restoration serves Abilene and the surrounding TX area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
