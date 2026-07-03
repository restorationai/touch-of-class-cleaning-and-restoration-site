// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "flood-fixers",
  displayName: "Flood Fixers",
  shortName: "Flood Fixers",
  legalName: "Flood Fixers",
  domain: "flood-fixers.com",
  canonicalUrl: "https://flood-fixers.com",
  phone: "(855) 204-1124",
  phoneRaw: "+18552041124",
  email: "",
  hours: "24/7 Emergency Service",
  foundedYear: "",
  primaryCity: "San Diego",
  primaryState: "CA",
  streetAddress: "",
  postalCode: "",
  lat: "",
  lng: "",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.flood-fixers.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.webp",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  licenseType: "",
  certifications: [] as string[],
  trustBadges: [] as string[],
  sameAsUrls: [] as string[],
  gbpRatingValue: "",
  gbpReviewCount: "",
  tagline: "24/7 restoration services in San Diego, CA.",
  ctaLabel: "24/7 Emergency Hotline",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
