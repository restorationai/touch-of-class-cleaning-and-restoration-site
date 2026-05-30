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
  logoUrl: "/images/logo.webp",
  licenseNumbers: ["NATIORC792M6"] as string[],
  licenseAuthority: "WA State Department of Labor & Industries",
  licenseType: "General Contractor Certificate of Registration",
  certifications: ["IICRC Certified", "BBB Accredited", "Lead-Safe Certified Firm", "EPA Certified", "ANSI Certified"] as string[],
  sameAsUrls: ["https://www.google.com/maps?cid=12984564642744438542", "https://www.facebook.com/narestco", "https://www.instagram.com/narestco", "https://www.tiktok.com/@narestco", "https://twitter.com/narestco"] as string[],
  gbpRatingValue: "",
  gbpReviewCount: "",
  tagline: "24/7 restoration services in Federal Way, WA.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
