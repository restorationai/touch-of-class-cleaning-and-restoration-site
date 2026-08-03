// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "reign-restoration",
  displayName: "Reign Restoration",
  shortName: "Reign Restoration",
  legalName: "Reign Restoration",
  domain: "",
  canonicalUrl: "https://None",
  phone: "(214) 304-0621",
  phoneRaw: "+12143040621",
  email: "jerrott@reign-restoration.com",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Royse City",
  primaryState: "TX",
  streetAddress: "6691 TX- 276 STE C",
  postalCode: "75189",
  lat: "32.9761045",
  lng: "-96.331334",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.None",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.png", // real logo from branding bucket (CO-1785771354136/brand); switch to images.{domain}/brand/logo.png at production cutover once the domain + R2 bucket exist
  licenseNumbers: ["MRC2276"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://www.tdlr.texas.gov/LicenseSearch/",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: ["IICRC WRT (WATER)", "IICRC CERTIFIED FIRM", "IICRC AMRT (MOLD)", "IICRC FSRT (FIRE & SMOKE)"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Royse City, TX.",
  ctaLabel: "24/7 Emergency Line",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  tradeNoun: "restoration",
  specialistPhrase: "Damage Restoration Specialists",
  announcementSuffix: "24/7 Emergency Response",
  homeAboutBlurb: "Reign Restoration serves Royse City and the surrounding TX area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
