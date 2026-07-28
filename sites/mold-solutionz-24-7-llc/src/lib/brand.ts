// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "mold-solutionz-24-7-llc",
  displayName: "Mold Solutionz 24/7",
  shortName: "Mold Solutionz",
  legalName: "Mold Solutionz 24/7 LLC",
  domain: "",
  canonicalUrl: "https://None",
  phone: "(714) 409-4758",
  phoneRaw: "+17144094758",
  email: "moldsolutionz247@gmail.com",
  hours: "24/7",
  foundedYear: "2017",
  primaryCity: "Cerritos",
  primaryState: "CA",
  streetAddress: "18869 Jeffrey Avenue",
  postalCode: "90703",
  lat: "33.8644291",
  lng: "-118.0539323",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.None",
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
  licensedInsuredAttested: false as boolean,
  certifications: ["IICRC WRT #70145645"] as string[],
  trustBadges: ["IICRC Certified", "Serving Greater LA & Orange County Since 2017"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "Got mold? We have the solution.",
  ctaLabel: "Talk to a Mold Specialist",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
