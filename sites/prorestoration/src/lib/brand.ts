// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "prorestoration",
  displayName: "ProRestoration Services",
  shortName: "ProRestoration",
  legalName: "ProRestoration Services Inc.",
  domain: "prorestorationca.com",
  canonicalUrl: "https://prorestorationca.com",
  phone: "(661) 393-9306",
  phoneRaw: "+16613939306",
  email: "",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Bakersfield",
  primaryState: "CA",
  streetAddress: "3556 Bowman Ct Suite B",
  postalCode: "93308",
  lat: "",
  lng: "",
  placeId: "ChIJH_3NClVC6oAR3mxvd5xofrQ",
  googleCid: "13005947795120549086",
  imagesBase: "https://images.prorestorationca.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.svg", // preview: switch to images.prorestorationca.com/brand/... at production cutover
  licenseNumbers: ["960566"] as string[],
  licenseAuthority: "Contractors State License Board (CSLB), State of California",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC Certified", "EPA Lead-Safe Certified Firm", "BBB Accredited"] as string[],
  trustBadges: [] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.google.com/maps?cid=13005947795120549086"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Bakersfield, CA.",
  ctaLabel: "24/7 Emergency Hotline",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
