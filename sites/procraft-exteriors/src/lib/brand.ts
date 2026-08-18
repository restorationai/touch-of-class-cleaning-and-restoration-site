// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "procraft-exteriors",
  displayName: "ProCraft Exteriors ",
  shortName: "ProCraft Exteriors ",
  legalName: "ProCraft Exteriors ",
  domain: "procraft-exteriors.invalid",
  canonicalUrl: "https://procraft-exteriors.invalid",
  phone: "(314) 965-2353",
  phoneRaw: "+13149652353",
  email: "info@procraftexteriors.com",
  hours: "24/7",
  foundedYear: "2005",
  primaryCity: "Chesterfield",
  primaryState: "MO",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Chesterfield",
  addressState: "MO",
  streetAddress: "744 Spirit of St Louis Blvd ",
  postalCode: "63005",
  lat: "38.6581764",
  lng: "-90.5680617",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.procraft-exteriors.invalid",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "https://images.procraft-exteriors.invalid/brand/logo.png",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: [] as string[],
  trustBadges: ["Licensed & Insured", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.yelp.com/biz/procraft-exteriors-chesterfield-2", "https://www.bbb.org/us/mo/chesterfield/profile/construction-services/procraft-exteriors-inc-0734-310353511", "https://nextdoor.com/pages/procraft-exteriors-chesterfield-mo/", "https://pro.porch.com/chesterfield-mo/roofers/procraft-exteriors-164614069/pp"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Chesterfield, MO.",
  ctaLabel: "24/7 Emergency Line",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  tradeNoun: "restoration",
  specialistPhrase: "Damage Restoration Specialists",
  announcementSuffix: "24/7 Emergency Response",
  homeAboutBlurb: "ProCraft Exteriors  serves Chesterfield and the surrounding MO area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
