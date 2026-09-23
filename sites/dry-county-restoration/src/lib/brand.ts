// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "dry-county-restoration",
  displayName: "Dry County Restoration",
  shortName: "Dry County Restoration",
  legalName: "Dry County Restoration",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "drycountyrestoration.com",
  canonicalUrl: "https://drycountyrestoration.com",
  phone: "(951) 667-9910",
  phoneRaw: "+19516679910",
  hideMobileHeaderCall: false,
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "(951) 629-3771",
  trackingPhoneRaw: "+19516293771",
  email: "info@drycountyrestoration.com",
  hours: "24/7",
  foundedYear: "2020",
  primaryCity: "Corona",
  primaryState: "CA",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Corona",
  addressState: "CA",
  streetAddress: "9064 Pulsar Ct. Suit I ",
  postalCode: "92883",
  lat: "33.8752945",
  lng: "-117.566444",
  placeId: "ChIJBQyutfy53IARKDqQsaEwmyQ",
  googleCid: "",
  imagesBase: "https://images.drycountyrestoration.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-211581WVBQ",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: ["1083555"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC CERTIFIED FIRM", "IICRC WRT (WATER)", "IICRC ASD (STRUCTURAL DRYING)", "IICRC AMRT (MOLD)", "OSHA TRAINED"] as string[],
  trustBadges: ["Licensed & Insured", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://maps.google.com/maps?cid=2637755477782444584"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "5.0",
  gbpReviewCount: "80",
  gbpReviews: [
    { author: "Heather", rating: 5, text: "Everyone at Dry County was great to work with! They came out quickly and were very responsive and easy to communicate with throughout the process. Every single person who showed up at the house to do a job was intelligent, competent, and respectful. They came when they said they would, did what…", when: "September 2026" },
    { author: "Rachel", rating: 5, text: "They were very helpful and knowledgeable!", when: "September 2026" },
    { author: "Efren", rating: 5, text: "The crew was knowledgeable & thorough. And customer friendly.", when: "September 2026" },
    { author: "Jenny", rating: 5, text: "Everyone at Dry County have been so helpful and communicative. They helped make a difficult situation much more bareable. From beginning to end, everyone involved have been amazing.", when: "September 2026" },
    { author: "Darla", rating: 5, text: "These guys helped me out with drying up the water that flooded my house. They were here when they said they would be. It was a great experience.", when: "September 2026" },
    { author: "Jo", rating: 5, text: "They did a great job and cleaned up afterwards. Very happy with the job.", when: "August 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Corona, CA.",
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
  homeAboutBlurb: "Dry County Restoration serves Corona and the surrounding CA area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
