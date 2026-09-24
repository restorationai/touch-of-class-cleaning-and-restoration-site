// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "homelyft-restoration-ms",
  displayName: "HomeLyft Restoration MS",
  shortName: "HomeLyft Restoration MS",
  legalName: "HomeLyft Restoration MS",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "homelyft.net",
  canonicalUrl: "https://homelyft.net",
  phone: "+12282845200",
  phoneRaw: "+112282845200",
  hideMobileHeaderCall: false,
  // A2P/SMS-registration legal entity. When set, the estimate forms render
  // the carrier-compliant consent checkbox naming this entity (exact wording
  // matters to reviewers — do not paraphrase). Empty = generic consent only.
  smsConsentEntity: "MULTIGLOBAL SERVICES LLC",
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "(228) 900-9718",
  trackingPhoneRaw: "+12289009718",
  email: "info@homelyft.net",
  hours: "24/7",
  foundedYear: "2022",
  primaryCity: "Gulfport",
  primaryState: "MS",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Gulfport",
  addressState: "MS",
  streetAddress: "1311 SPRING Street",
  postalCode: "39507",
  lat: "30.3886736",
  lng: "-89.0586991",
  placeId: "ChIJ5dJT_FQWnIgRzm4i4D1BgR4",
  googleCid: "2198109827142676174",
  imagesBase: "https://images.homelyft.net",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-CY001B6T82",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: ["RO 2728"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: ["IICRC CERTIFIED FIRM", "IICRC WRT (WATER)", "IICRC ASD (STRUCTURAL DRYING)", "EPA LEAD-SAFE CERTIFIED", "IICRC FSRT (FIRE & SMOKE)", "IICRC AMRT (MOLD)", "OSHA TRAINED", "FORTIFIED-BUILDING-ROOFING-MS-WINDSTORM-CERTIFIED"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://maps.google.com/maps?cid=2198109827142676174", "https://www.homelyft.net/"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "5.0",
  gbpReviewCount: "54",
  gbpReviews: [
    { author: "Rachel", rating: 5, text: "Was very helpful and compassionate to our situation. Highly recommend 👌", when: "September 2026" },
    { author: "Lauren", rating: 5, text: "The entire HomeLyft team was very professional and great to work with. They went above and beyond to provide quality customer service and quality construction work.", when: "August 2026" },
    { author: "Emile", rating: 5, text: "We hired this company to mitigate the damage to our home after it sustained water damage from rising water during a torrential rain. They arrived at our home the very next day to start the process of remediating the damage. We truly cannot say enough good things about our experience with them. They…", when: "August 2026" },
    { author: "Tamera", rating: 5, text: "I highly recommend HomeLyft Restoration. When I first found them online, I was honestly a little nervous because I had never heard of them before. Hiring a company to restore your home after water damage is a big decision, and I wasn’t sure what to expect. I wondered if they would show up when they…", when: "July 2026" },
    { author: "Virginia", rating: 5, text: "We had a major flooding issue at a family home, and Homelyft arrived within 30 minutes of our call, and immediately started the cleanup! They were incredibly knowledgeable, professional, and easy to work with every step of the way, and truly rescued us. We offer our highest recommendation. Thank…", when: "June 2026" },
    { author: "Tyler", rating: 5, text: "Made an appointment and they were we at my house the next day, extremely professional and efficient! They were able to answer any question or concerns i had. Highly recommend this company!", when: "June 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Gulfport, MS.",
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
  homeAboutBlurb: "HomeLyft Restoration MS serves Gulfport and the surrounding MS area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
