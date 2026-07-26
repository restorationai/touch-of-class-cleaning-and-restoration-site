// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "crew-restoration-construction",
  displayName: "Crew Restoration & Construction",
  shortName: "Crew",
  legalName: "Crew Restoration & Construction",
  domain: "",
  canonicalUrl: "https://None",
  phone: "(605) 965-2727",
  phoneRaw: "+16059652727",
  email: "estimates@crewthatcares.com",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Sioux Falls",
  primaryState: "SD",
  streetAddress: "3503 South Norton Avenue",
  postalCode: "57110",
  lat: "43.5476008",
  lng: "-96.7293629",
  placeId: "ChIJ62IxEgm2jocRJj94-dsO6Nw",
  googleCid: "",
  imagesBase: "https://images.None",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: ["3814"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC"] as string[],
  trustBadges: ["IICRC Certified", "Licensed & Insured", "24/7 Emergency Response", "Locally Owned Since 2015"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Sioux Falls, SD.",
  ctaLabel: "24/7 Emergency Line",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
