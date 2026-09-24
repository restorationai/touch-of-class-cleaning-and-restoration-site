// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "flood-solutions-inc",
  displayName: "Flood Solutions inc",
  shortName: "Flood Solutions inc",
  legalName: "Flood Solutions inc",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "floodsolutionsinc.com",
  canonicalUrl: "https://floodsolutionsinc.com",
  phone: "(586) 580-0197",
  phoneRaw: "+15865800197",
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
  trackingPhone: "(586) 331-6706",
  trackingPhoneRaw: "+15863316706",
  email: "",
  hours: "24/7",
  foundedYear: "1996",
  primaryCity: "Macomb",
  primaryState: "MI",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Ira",
  addressState: "MI",
  streetAddress: "10153 Marine City Highway",
  postalCode: "48023",
  lat: "",
  lng: "",
  placeId: "ChIJF_GiDO_gJIgR1VZPHRihQr4",
  googleCid: "",
  imagesBase: "https://images.floodsolutionsinc.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.webp",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: [] as string[],
  trustBadges: ["Licensed & Insured", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.4",
  gbpReviewCount: "35",
  gbpReviews: [
    { author: "Lisa", rating: 4, text: "Staff that visited my home for Mold Restoration process were respectful in every aspect to include my need for less as possible demolition. Both (Will & Stephanie) shared procedures that would be taken, monitored progression daily & ensured I was pleased with the services provided.", when: "July 2026" },
    { author: "Craig", rating: 5, text: "Did great job in clean up and sanitation", when: "July 2026" },
    { author: "Angela", rating: 5, text: "I have utilized Flood and Fire solutions twice for my home. I would highly recommend them and will always use them for any needs in the future if I unfortunately have the need. Crew worked very hard, efficiently, and professionally. Luis and his crew were very impressive and take pride in what they…", when: "February 2026" },
    { author: "Sandy", rating: 5, text: "Louis was very knowledgeable and helpful with the process. Would definitely recommend Flood and Fire solutions.", when: "December 2025" },
    { author: "Chuck", rating: 5, text: "Very knowledgeable and friendly employees. I had a flooded crawl space that I couldn't take care of myself. But Louis and his crew talked me through the whole process and then finished the job quickly and thoroughly.", when: "October 2025" },
    { author: "Danielle", rating: 5, text: "Such a great experience this team was so helpful. Got my basement cleaned up and made sure there was no damage to the walls or anything else. They handled everything so fast.", when: "October 2025" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Macomb, MI.",
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
  homeAboutBlurb: "Flood Solutions inc serves Macomb and the surrounding MI area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
