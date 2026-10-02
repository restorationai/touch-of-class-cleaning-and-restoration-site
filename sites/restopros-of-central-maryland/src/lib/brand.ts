// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "restopros-of-central-maryland",
  displayName: "RestoPros of Central Maryland",
  shortName: "RestoPros of Central Maryland",
  legalName: "RestoPros of Central Maryland",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "restopros-of-central-maryland.invalid",
  canonicalUrl: "https://restopros-of-central-maryland.invalid",
  phone: "(240) 261-1639",
  phoneRaw: "+12402611639",
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
  trackingPhone: "(240) 617-4402",
  trackingPhoneRaw: "+12406174402",
  email: "drestum@restopros.co",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Baldwin",
  primaryState: "MD",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Baldwin",
  addressState: "MD",
  streetAddress: "2710 Hunting Ridge Ct",
  postalCode: "21013",
  lat: "39.4945894",
  lng: "-76.4701866",
  placeId: "ChIJ64mT9f9M2oMRGaajJtP-T4A",
  googleCid: "",
  imagesBase: "https://images.restopros-of-central-maryland.invalid",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC WRT (WATER)"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.9",
  gbpReviewCount: "28",
  gbpReviews: [
    { author: "Leslie", rating: 5, text: "RestoPros of Central MD is EXCELLENT! Totally professional, reasonably priced, and they don't try to up-sell. Mike was our main contact and was so wonderful to work with - really gave us great advice and peace of mind.", when: "September 2026" },
    { author: "Jram927", rating: 5, text: "Dan and Mike were extremely helpful and supportive in helping with our plumbing leak damage. They were professional and fair and made our emergency feel more manageable and comfortable.", when: "September 2026" },
    { author: "Wendy", rating: 5, text: "The customer service and attention to detail were excellent.", when: "September 2026" },
    { author: "Tyler", rating: 5, text: "Daniel and his team were absolute lifesavers in an emergency. They arrived right on time and immediately got to work, preventing any further damage. Friendly, professional, and fast. And more importantly, very reasonable with the prices. Surely call him for any future need. Highly recommended.", when: "September 2026" },
    { author: "Smart", rating: 5, text: "Best Water Damage services provider in the area. Highly professional and skillful. Dan you are the gem", when: "September 2026" },
    { author: "Oscar", rating: 5, text: "Dan helped me through the process and explained me in detail about all my questions. I highly recommend Restopros.", when: "September 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Baldwin, MD.",
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
  homeAboutBlurb: "RestoPros of Central Maryland serves Baldwin and the surrounding MD area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
