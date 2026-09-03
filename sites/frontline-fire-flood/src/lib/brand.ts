// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "frontline-fire-flood",
  displayName: "Frontline Fire & Flood",
  shortName: "Frontline Fire & Flood",
  legalName: "Frontline Fire & Flood",
  domain: "frontlinefireflood.com",
  canonicalUrl: "https://frontlinefireflood.com",
  phone: "+12532000503",
  phoneRaw: "+112532000503",
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "",
  trackingPhoneRaw: "",
  email: "service@frontlinefireflood.com",
  hours: "24/7",
  foundedYear: "2014",
  primaryCity: "Lakewood",
  primaryState: "WA",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Lakewood",
  addressState: "WA",
  streetAddress: "9520 Front St",
  postalCode: "98499",
  lat: "47.1717649",
  lng: "-122.518458",
  placeId: "ChIJK-c9495UkFQRpJu9uz3VE20",
  googleCid: "",
  imagesBase: "https://images.frontlinefireflood.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: ["CCFRONTFF761CB"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://secure.lni.wa.gov/verify/",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC CERTIFIED FIRM", "IICRC AMRT (MOLD)", "IICRC WRT (WATER)", "IICRC FSRT (FIRE & SMOKE)", "IICRC ASD (STRUCTURAL DRYING)", "EPA LEAD-SAFE CERTIFIED", "OSHA TRAINED"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://frontlinefireflood.com/meet-the-team/"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.9",
  gbpReviewCount: "133",
  gbpReviews: [
    { author: "Samuel", rating: 5, text: "Darius was very helpful and informative through the entire process. Very easy to work with. Highly recommended!", when: "September 2026" },
    { author: "Alivia", rating: 5, text: "Frontline went above and beyond when I had a major flood at one of my properties! Their team responded incredibly fast and took care of the problem before the damage could get any worse. Jamal was absolutely amazing—kind, courteous, and extremely professional. He worked quickly to get all the water…", when: "August 2026" },
    { author: "Jaleel", rating: 5, text: "I had a great experience with Frontline Fire and Flood when we discovered mold in our home. It was the basement spare bedroom to be exact. From the beginning, they were professional, knowledgeable, and made us feel like we were in good hands. They did an excellent job addressing the mold issue and…", when: "August 2026" },
    { author: "Rochelle", rating: 5, text: "I had a great experience with Frontline Fire and Flood. From start to finish, the team was professional, responsive, and respectful of our home. The work was handled carefully, and it was clear that they genuinely cared about getting everything done right. Jamal was especially great to work with…", when: "August 2026" },
    { author: "Danyel", rating: 5, text: "Frontline did a great job addressing water damage to our home. Jamal was the onsite lead and was professional and thorough. He and Darius clearly and promptly answered my many questions as I interviewed a handful of vendors, providing all the documentation about their business and certifications I…", when: "August 2026" },
    { author: "Jonathan", rating: 5, text: "Very professional team, small heater caught fire in our home. Their team came out the next day and were quick to remediate our house. Their reconstruction team was very helpful and made it a very swift process. Shoutout Frontline", when: "August 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Lakewood, WA.",
  ctaLabel: "24/7 Emergency Line",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  tradeNoun: "restoration",
  specialistPhrase: "Damage Restoration Specialists",
  announcementSuffix: "24/7 Emergency Response",
  homeAboutBlurb: "Frontline Fire & Flood serves Lakewood and the surrounding WA area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
