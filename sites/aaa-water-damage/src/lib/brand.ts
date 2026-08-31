// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "aaa-water-damage",
  displayName: "AAA Water Damage Restoration & Carpet Care",
  shortName: "AAA Water Damage",
  legalName: "AAA Flood Service LLC",
  domain: "aaawaterdamagehawaii.com",
  canonicalUrl: "https://aaawaterdamagehawaii.com",
  phone: "(808) 349-3407",
  phoneRaw: "+18083493407",
  // Sitewide call-tracking display number (DNI — see BaseLayout).
  // Schema/NAP keep the canonical number above.
  trackingPhone: "(808) 431-7518",
  trackingPhoneRaw: "+18084317518",
  email: "",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Honolulu",
  primaryState: "HI",
  streetAddress: "",
  postalCode: "96825",
  lat: "",
  lng: "",
  placeId: "ChIJD0yxLYptAHwRja-0yOuatzE",
  googleCid: "3582502366071795597",
  imagesBase: "https://images.aaawaterdamagehawaii.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-YESCZ9R462",
  clarityProjectId: "",
  logoUrl: "/images/logo.webp", // preview: switch to images.{domain} at production cutover
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: [] as string[],
  // "25+ Years in Business" — operator-attested by Santino (owner's nephew),
  // 2026-07-09. No specific founding year on file; foundedYear stays empty.
  trustBadges: ["Locally Owned", "25+ Years in Business", "24/7 Emergency Service"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.google.com/maps?cid=3582502366071795597", "https://www.facebook.com/26flood", "https://www.yelp.com/biz/aaa-water-damage-restoration-and-carpet-care-honolulu"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 water damage restoration & carpet care across Oahu.",
  ctaLabel: "24/7 Emergency Hotline",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
