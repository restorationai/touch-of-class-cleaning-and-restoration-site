// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "bionic-emergency-services-llc",
  displayName: "BIONIC Emergency Services LLC",
  shortName: "BIONIC",
  legalName: "BIONIC Emergency Services LLC",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "bionic24365.com",
  canonicalUrl: "https://bionic24365.com",
  phone: "(713) 338-2424",
  phoneRaw: "+17133382424",
  hideMobileHeaderCall: false,
  // A2P/SMS-registration legal entity. When set, the estimate forms render
  // the carrier-compliant consent checkbox naming this entity (exact wording
  // matters to reviewers — do not paraphrase). Empty = generic consent only.
  smsConsentEntity: "",
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "(346) 249-5322",
  trackingPhoneRaw: "+13462495322",
  email: "shane@bionic24365.com",
  hours: "24/7",
  foundedYear: "2011",
  primaryCity: "Houston",
  primaryState: "TX",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Houston",
  addressState: "TX",
  streetAddress: "14300 Northwest Freeway, Suite A9",
  postalCode: "77040",
  lat: "29.863982",
  lng: "-95.53306",
  placeId: "ChIJDy5x1I7PQIYRe-CvUTGxj3g",
  googleCid: "",
  imagesBase: "https://images.bionic24365.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.jpg",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC WRT (Water)", "IICRC ASD (Structural Drying)"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.angi.com/companylist/us/tx/houston/bionic-emergency-services-llc-reviews-1.htm", "https://www.homeadvisor.com/rated.BIONICEmergencyServices.25215285.html"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.9",
  gbpReviewCount: "154",
  gbpReviews: [
    { author: "Jasmine", rating: 5, text: "Very professional and proficient.", when: "August 2026" },
    { author: "Jim", rating: 5, text: "They were very through and did a beautiful job! I highly recommend their services!", when: "August 2026" },
    { author: "Eric", rating: 5, text: "Shane is the man! Extremely professional and does outstanding work. High recommended service provider 👍🏼", when: "August 2026" },
    { author: "Kat", rating: 5, text: "Jesus and everyone else were wonderful. Great company!!", when: "August 2026" },
    { author: "Adam", rating: 5, text: "Great experience they were attentive to detail and explained everything throughout the process of getting our house back to the way it was before the pipe busted", when: "August 2026" },
    { author: "Marcus", rating: 5, text: "I was out of town when one of our pipes began to leak. My wife was home and had to deal with the whole mess by herself. Our Bionic Project Supervisor, Tristan Rodriguez made the process easy to understand and walked my wife through the whole process to where she was comfortable. He explained…", when: "May 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Houston, TX.",
  // optional custom insurance positioning line (Hero renders only when set)
  insuranceTrustLine: "",
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
  homeAboutBlurb: "BIONIC Emergency Services LLC serves Houston and the surrounding TX area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
