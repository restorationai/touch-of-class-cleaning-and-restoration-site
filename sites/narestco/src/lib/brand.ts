// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "narestco",
  displayName: "National Restoration Construction",
  shortName: "NARESTCO",
  legalName: "National Restoration Construction LLC",
  domain: "narestco.com",
  canonicalUrl: "https://narestco.com",
  phone: "(206) 883-0333",
  phoneRaw: "+12068830333",
  // Google Ads click-to-call conversion (LP layouts read these; no-op if empty)
  gadsId: "AW-16824131335",
  gadsCallConversionLabel: "AW-16824131335/lNXeCMeuy74cEIe-r9Y-",
  // Twilio call-tracking number — shows on the /lp/ ad pages ONLY (main site NAP unchanged)
  adsTrackingPhone: "(253) 338-5162",
  adsTrackingPhoneRaw: "+12533385162",
  email: "info@narestco.com",
  hours: "24/7",
  foundedYear: "2004",
  primaryCity: "Federal Way",
  primaryState: "WA",
  streetAddress: "1530 S Dash Point Rd",
  postalCode: "98003",
  lat: "47.337",
  lng: "-122.314",
  placeId: "ChIJ8URpSkf_UaURDg_hVb9wMrQ",
  googleCid: "12984564642744438542",
  imagesBase: "https://images.narestco.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set by scripts/analytics_set.py / create_ga4.py; no-op if empty
  ga4MeasurementId: "G-5N8L5D4Z3C",
  clarityProjectId: "xdoigoc8of",
  logoUrl: "/images/logo.webp",
  licenseNumbers: ["NATIORC792M6"] as string[],
  licenseAuthority: "WA State Department of Labor & Industries",
  licenseType: "General Contractor Certificate of Registration",
  certifications: ["IICRC Certified", "BBB Accredited", "Lead-Safe Certified Firm", "EPA Certified", "ANSI Certified"] as string[],
  trustBadges: [] as string[],
  sameAsUrls: ["https://www.google.com/maps?cid=12984564642744438542", "https://www.facebook.com/narestco", "https://www.instagram.com/narestco", "https://www.tiktok.com/@narestco", "https://twitter.com/narestco"] as string[],
  gbpRatingValue: "4.9",
  gbpReviewCount: "53",
  tagline: "24/7 restoration services in Federal Way, WA.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
