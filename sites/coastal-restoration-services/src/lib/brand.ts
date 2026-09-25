// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "coastal-restoration-services",
  displayName: "Coastal Restoration Services Inc",
  shortName: "Coastal Restoration Services Inc",
  legalName: "Coastal Restoration Services Inc",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "callcrs.com",
  canonicalUrl: "https://callcrs.com",
  phone: "(805) 345-7440",
  phoneRaw: "+18053457440",
  hideMobileHeaderCall: false,
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "(805) 590-9385",
  trackingPhoneRaw: "+18055909385",
  email: "tony@callcrs.com",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Santa Maria",
  primaryState: "CA",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Santa Maria",
  addressState: "CA",
  streetAddress: "217 E Fesler St",
  postalCode: "93454",
  lat: "34.9531295",
  lng: "-120.435857",
  placeId: "ChIJgb6Gdhxh4wYRjbzm6ELYT38",
  googleCid: "",
  imagesBase: "https://images.callcrs.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-VHZE6NYBPE",
  clarityProjectId: "",
  logoUrl: "/images/logo.webp",
  licenseNumbers: ["11245226"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: ["IICRC Certified Firm", "WRT (Water Damage Restoration Technician)", "ASD (Applied Structural Drying)"] as string[],
  trustBadges: [] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://facebook.com/JustCallCRS", "https://www.instagram.com/coastalrestorationca/", "https://maps.google.com/maps?cid=9173788747863866509", "https://www.yelp.com/biz/coastal-restoration-services-inc-santa-maria", "https://www.bbb.org/us/ca/santa-maria/profile/fire-water-damage-restoration/coastal-restoration-services-inc-1236-92090387", "https://www.angi.com/companylist/us/ca/santa-maria/coastal-restoration-services-inc-reviews-1.htm", "https://www.bing.com/maps?ss=ypid.YN63B35A1F1F185968"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "5.0",
  gbpReviewCount: "29",
  gbpReviews: [
    { author: "George", rating: 5, text: "Yes i highly recommend. Coastal rushed to the scene on the weekend and promptly provided valued feedback. We were able to move forward with our situation forthwith. Very satisfied with outcome.", when: "July 2026" },
    { author: "Al", rating: 5, text: "We were very satisfied with the work they did. You would never know that we had a mold problem or that the lower 2 feet of our walls surrounding the refrigerator were replaced.", when: "July 2026" },
    { author: "Alejandra", rating: 5, text: "Speedy work and very well done. Flexible with scheduling days and left very happy with the service. Recommend.", when: "July 2026" },
    { author: "Alejandro", rating: 5, text: "I was moving my washer when the water line snapped off the wall. Did not expect it to flood the way it did, it got bad pretty fast. First thing I thought about was mold, so I called CRS right away. I was pretty stressed when the owner Tony showed up but he immediately put me at ease. Walked me…", when: "July 2026" },
    { author: "John", rating: 5, text: "Tony and his crew did a fantastic and quick job to repair the first floor water damage of our condo! Great work at a very reasonable price!!", when: "July 2026" },
    { author: "Jesus", rating: 5, text: "Gave them a call and they came out right away! The crew was professional, courteous, and respectful. We would highly recommend them to anyone in the area.", when: "July 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Santa Maria, CA.",
  ctaLabel: "24/7 Emergency Line",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  // vertical gates layout too: restoration is call-first, so the homepage
  // hero renders NO estimate form there (Santino 2026-09-11).
  vertical: "restoration",
  tradeNoun: "restoration",
  specialistPhrase: "Damage Restoration Specialists",
  announcementSuffix: "24/7 Emergency Response",
  homeAboutBlurb: "Coastal Restoration Services Inc serves Santa Maria and the surrounding CA area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
