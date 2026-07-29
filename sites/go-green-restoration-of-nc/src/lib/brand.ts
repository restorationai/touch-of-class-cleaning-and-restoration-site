// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "go-green-restoration-of-nc",
  displayName: "Go Green Restoration of NC",
  shortName: "Go Green Restoration of NC",
  legalName: "Go Green Restoration of NC",
  domain: "",
  canonicalUrl: "https://None",
  phone: "(919) 906-5473",
  phoneRaw: "+19199065473",
  email: "gogreenrestorationofnc@gmail.com",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Middlesex",
  primaryState: "NC",
  streetAddress: "10805 w. NC Hwy 97 ",
  postalCode: "27557",
  lat: "35.7888369",
  lng: "-78.2039124",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.None",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "https://images.None/brand/logo.png",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: [] as string[],
  trustBadges: [] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Middlesex, NC.",
  ctaLabel: "24/7 Emergency Line",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
