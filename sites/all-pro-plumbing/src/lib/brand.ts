// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "all-pro-plumbing",
  displayName: "All Pro Plumbing Heating and Air",
  shortName: "All Pro",
  legalName: "All Pro Plumbing Heating and Air",
  domain: "allproplumbingheatingandair.com",
  canonicalUrl: "https://allproplumbingheatingandair.com",
  phone: "(661) 863-9242",
  phoneRaw: "+16618639242",
  email: "info@allproplumbingheatingandair.com",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Bakersfield",
  primaryState: "CA",
  streetAddress: "",
  postalCode: "",
  lat: "",
  lng: "",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.allproplumbingheatingandair.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.webp", // preview: switch to images.allproplumbingheatingandair.com/brand/... at production cutover
  licenseNumbers: [] as string[],
  licenseAuthority: "",
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
  tagline: "24/7 plumbing, heating and air service in Bakersfield, CA.",
  ctaLabel: "24/7 Emergency Hotline",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
