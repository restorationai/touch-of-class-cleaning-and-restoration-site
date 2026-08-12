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
  sameAsUrls: ["https://www.google.com/maps?cid=12984564642744438542", "https://www.facebook.com/narestco", "https://www.instagram.com/narestco", "https://www.tiktok.com/@narestco", "https://twitter.com/narestco", "https://www.yelp.com/biz/national-restoration-construction-federal-way-3", "https://www.bbb.org/us/wa/federal-way/profile/fire-water-damage-restoration/national-restoration-construction-llc-1296-1000167537", "https://www.angi.com/companylist/us/wa/federal-way/national-restoration-construction-llc-reviews-1.htm", "https://www.homeadvisor.com/rated.NationalRestoration.118159482.html", "https://www.thumbtack.com/wa/federal-way/water-damage/national-restoration-construction/service/515297469726908420", "https://www.bing.com/maps?ss=ypid.YN5DEE2A36AED87F3B", "https://www.houzz.com/professionals/environmental-services-and-restoration/national-restoration-construction-pfvwus-pf~819253451", "https://homeguide.com/wa/federal-way/water-damage-restoration/national-restoration-construction-A8aisT6gf"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.9",
  gbpReviewCount: "57",
  gbpReviews: [
    { author: "Tatyana", rating: 5, text: "So glad they were able to come out same day as I called to check my home for mold. Everything was explained simple and easy to understand", when: "July 2026" },
    { author: "Wesley", rating: 5, text: "These fellas came in when we had a water leak from a major big box store install. They came in as a third party. It did take some time, but they got everything fixed.And they went out of the way to make sure that we got what we needed.The way we needed it.", when: "July 2026" },
    { author: "Doneen", rating: 5, text: "Very pleased with the service. They explained each step clearly. They answered any questions we had. They were on time and cleaned up each day any mess they had created working.", when: "July 2026" },
    { author: "Sherry", rating: 5, text: "Jose is such a great pleasure to work with to remediate water damage to our property caused by sprinkler malfunction. He is very experienced in working with the insurance company. He is efficient in managing teams and timelines to complete remediation and restoration project milestones. He was very…", when: "July 2026" },
    { author: "Bhave", rating: 5, text: "My friend had a water leak and Jose and his team did such a fantastic job start to finish. My friend was so happy . Thorough professionals . Highly recommend", when: "June 2026" },
    { author: "Tuong", rating: 5, text: "We’re very happy with the results! We worked with Jose and Niki, and the team was incredibly responsive throughout the entire process. They kept us informed every step of the way by sending pictures and communicating what was completed as they went. They replaced the flooring for the whole place…", when: "June 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Federal Way, WA.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
