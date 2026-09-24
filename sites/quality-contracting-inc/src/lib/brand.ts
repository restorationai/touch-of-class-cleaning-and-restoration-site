// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "quality-contracting-inc",
  displayName: "Quality Contracting, Inc.",
  shortName: "Quality Contracting, Inc.",
  legalName: "Quality Contracting, Inc.",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "qualitycontracting.us",
  canonicalUrl: "https://qualitycontracting.us",
  phone: "(508) 756-8800",
  phoneRaw: "+15087568800",
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
  trackingPhone: "(508) 355-3039",
  trackingPhoneRaw: "+15083553039",
  email: "info@qualitycontracting.us",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Auburn",
  primaryState: "MA",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Auburn",
  addressState: "MA",
  streetAddress: "211 Southbridge Street",
  postalCode: "01501",
  lat: "42.1945465",
  lng: "-71.8358095",
  placeId: "ChIJ9wuzUNMF5IkR23w7vv0t_Hc",
  googleCid: "",
  imagesBase: "https://images.qualitycontracting.us",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-G8PLTS9XDN",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: [] as string[],
  trustBadges: [] as string[],
  jobPhotos: ["https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1785180744028/job-photos/posted/r1788980315_sms-1785358224564-5c715e96.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1785180744028/job-photos/posted/r1788814538_gbp-AF1QipP_p1uc76KgQ_e_r5cWTb9_xiLVg11kKmv8wix7.jpg"] as string[],
  sameAsUrls: ["https://www.facebook.com/qualcon534/", "https://www.linkedin.com/company/quality-contracting-inc-"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.6",
  gbpReviewCount: "108",
  gbpReviews: [
    { author: "Ellin", rating: 5, text: "Quality did an excellent restoration job when my condo was involved in a fire.", when: "September 2026" },
    { author: "Peggy", rating: 4, text: "Derek was wonderful! We had an insurance claim from water damage. The work was well done.", when: "September 2026" },
    { author: "Mark", rating: 5, text: "Quality Contracting updated our standard tub/shower to a walk in for my elderly father. They came when they said they would, the did everything they said they would and the charged me the reasonable cost that they said they would. Highly recommend.", when: "September 2026" },
    { author: "Jane", rating: 5, text: "I highly recommend Quality Construction! When my condo suffered water damage Matt , Kale and a third person (sorry I don’t remember his name), provided outstanding support and expertise from start to finish.They worked carefully and thoroughly to dry and clean every affected area, while treating my…", when: "September 2026" },
    { author: "Denise", rating: 5, text: "We had extensive flood damage at our home. Quality Contracting did the repairs for us and did an exceptional job", when: "September 2026" },
    { author: "Jeannine", rating: 5, text: "Luis was wonderful! Explained everything and handled the our water leak professionally. Thank you!", when: "September 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Auburn, MA.",
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
  homeAboutBlurb: "Quality Contracting, Inc. serves Auburn and the surrounding MA area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
