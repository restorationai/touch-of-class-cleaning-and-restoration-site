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
  // Sitewide call-tracking display number (DNI — see BaseLayout).
  // Schema/NAP keep the canonical number above.
  trackingPhone: "(206) 737-0916",
  trackingPhoneRaw: "+12067370916",
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
  gbpRatingValue: "5.0",
  gbpReviewCount: "63",
  gbpReviews: [
    { author: "Julia", rating: 5, text: "Jose and his team were very helpful and did a great job! Super happy with their work!", when: "August 2026" },
    { author: "Benjamin", rating: 5, text: "Had a water emergency on site. These guys showed up the next day and started taking care of business! took a few days to get all the water out/ damage ripped out. Those guys worked hard! Communication with the guys in the office was easy and fast. Overall, very happy. Would recommend.", when: "August 2026" },
    { author: "Ivan", rating: 5, text: "Did a great job! Negotiated with my home insurance for me, was patient and communicated well, and we're overall satisfied with the work", when: "August 2026" },
    { author: "Tate", rating: 5, text: "Jose and crew at National Restoration are exactly the kind of people you want on your side after a disaster in your home. Within hours of our small house fire they had a crew in our house, mitigating damage and starting clean up. After mitigation was complete, they worked diligently and efficiently…", when: "August 2026" },
    { author: "Snehal", rating: 5, text: "It's our third time working with Jose and his team. We keep coming back to him because of his prompt response and fixing things within days. We recently had a plumbing issue at one of our rentals. Jose replied to my text within minutes and scheduled his team for inspection the next day. Our tenants…", when: "August 2026" },
    { author: "Kevin", rating: 5, text: "Super professional and helpful. The crew went out of their way to be helpful. Jose was super informative on the phone.", when: "August 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Federal Way, WA.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
