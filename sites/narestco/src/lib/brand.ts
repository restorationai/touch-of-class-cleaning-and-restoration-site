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
  licenseLookupUrl: "https://secure.lni.wa.gov/verify/",
  licenseType: "General Contractor Certificate of Registration",
  // Operator-confirmed "licensed & insured" attestation (plan-input.json
  // brand.licensed_insured_attested) — gates the TrustStrip badge when no
  // license number is on file yet.
  licensedInsuredAttested: false,
  certifications: ["IICRC Certified", "BBB Accredited", "Lead-Safe Certified Firm", "EPA Certified", "ANSI Certified"] as string[],
  trustBadges: [] as string[],
  sameAsUrls: ["https://www.google.com/maps?cid=12984564642744438542", "https://www.facebook.com/narestco", "https://www.instagram.com/narestco", "https://www.tiktok.com/@narestco", "https://twitter.com/narestco"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.9",
  gbpReviewCount: "53",
  gbpReviews: [
    { author: "Bhave", rating: 5, text: "My friend had a water leak and Jose and his team did such a fantastic job start to finish. My friend was so happy . Thorough professionals . Highly recommend", when: "June 2026" },
    { author: "Tuong", rating: 5, text: "We’re very happy with the results! We worked with Jose and Niki, and the team was incredibly responsive throughout the entire process. They kept us informed every step of the way by sending pictures and communicating what was completed as they went. They replaced the flooring for the whole place…", when: "June 2026" },
    { author: "Stacey", rating: 5, text: "I hired them for water mitigation services and am quite pleased with their professionalism and work overall. Jose ( and Miguel) took the time to explain everything and made sure i understood what would take place. He's very thorough, honest and really cares about getting the job done right!", when: "June 2026" },
    { author: "Thomas", rating: 5, text: "We worked with Jose and his team to replace the very old hardwood floor and repaint the walls in the dated living room of our first home. From start to finish, they communicated clearly and were patient with all of our concerns and requests, which was exactly what we needed for our first big…", when: "June 2026" },
    { author: "Belinda", rating: 5, text: "Absolutely great! Rescued us, attentive through the entire process. Look no where else.", when: "May 2026" },
    { author: "Gretchen", rating: 5, text: "Jose and his company completed two large projects for us. He was professional, timely, responsive, and knowledgeable. He made sure we understood the process and all the options for repairs. We would highly recommend him for any project you need.", when: "May 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Federal Way, WA.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
