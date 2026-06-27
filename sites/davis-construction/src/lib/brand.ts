// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "davis-construction",
  displayName: "Davis Construction Contractors",
  shortName: "Davis Construction Contractors",
  legalName: "Davis Construction Inc.",
  domain: "davisconstructioncontractors.com",
  canonicalUrl: "https://davisconstructioncontractors.com",
  phone: "(256) 771-0326",
  phoneRaw: "+12567710326",
  email: "davisheath09@gmail.com",
  hours: "Monday–Friday, 8:00 AM – 5:00 PM",
  foundedYear: "2008",
  primaryCity: "Madison",
  primaryState: "AL",
  streetAddress: "",
  postalCode: "",
  lat: "",
  lng: "",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.davisconstructioncontractors.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set by scripts/analytics_set.py / create_ga4.py; no-op if empty
  ga4MeasurementId: "G-BRL1Q2KTGV",
  clarityProjectId: "xdoje59wr1",
  logoUrl: "/images/logo.webp",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  licenseType: "",
  certifications: [] as string[],
  sameAsUrls: [] as string[],
  gbpRatingValue: "",
  gbpReviewCount: "",
  tagline: "Construction and restoration services in Madison, AL.",
  ctaLabel: "24/7 Emergency Hotline",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
