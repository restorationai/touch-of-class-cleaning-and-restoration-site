// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "dry1-out-restoration-and-construction",
  displayName: "Dry1 Out Restoration and Construction",
  shortName: "Dry1",
  legalName: "Dry1 Out Restoration and Construction",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "dry1out.com",
  canonicalUrl: "https://dry1out.com",
  phone: "(760) 576-1987",
  phoneRaw: "+17605761987",
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
  trackingPhone: "(760) 278-6497",
  trackingPhoneRaw: "+17602786497",
  email: "Jason@dry1out.com",
  hours: "24/7",
  foundedYear: "2026",
  primaryCity: "Vista",
  primaryState: "CA",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Vista",
  addressState: "CA",
  streetAddress: "1235 activity dr ",
  postalCode: "82081",
  lat: "",
  lng: "",
  placeId: "ChIJh3y1Q-iumqsRn1E-rGgHmcU",
  googleCid: "",
  imagesBase: "https://images.dry1out.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: ["#993442"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC Certified Firm", "IICRC WRT (Water)", "IICRC ASD (Structural Drying)", "IICRC AMRT (Mold)", "IICRC FSRT (Fire & Smoke)"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://maps.google.com/maps?cid=14238419843056292255"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "5.0",
  gbpReviewCount: "21",
  gbpReviews: [
    { author: "Doug", rating: 5, text: "As good as it gets… fast, friendly put my mind to ease…", when: "September 2026" },
    { author: "Iris", rating: 5, text: "I had a great experience with Dry1Out after a fire damaged my home. The entire situation was overwhelming, but their team made the process much easier from the moment they arrived. They were professional, responsive, and compassionate. They explained what needed to be done, helped me understand the…", when: "September 2026" },
    { author: "Christopher", rating: 5, text: "I've had the pleasure of working with the team at Dry 1 Out, and their professionalism stands out every step of the way. They're responsive, reliable, and thorough in everything they do. You can tell they hold themselves to a high standard and genuinely care about doing quality work. It's been a…", when: "September 2026" },
    { author: "Yowan", rating: 5, text: "Excellent service after a small kitchen fire. Highly recommend.", when: "September 2026" },
    { author: "Sumit", rating: 5, text: "The crew was here super fast after our water heater exploded. They really know their stuff about water extraction and getting things dried out properly. Huge relief.", when: "September 2026" },
    { author: "Christopher", rating: 5, text: "Dry1Out Flood and Fire did an amazing job handling a water damage project at one of my rental properties in Carlsbad, California. They were professional, responsive, and did excellent-quality work from start to finish. I highly recommend Dry1Out Flood and Fire to anyone needing water damage…", when: "September 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Vista, CA.",
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
  homeAboutBlurb: "Dry1 Out Restoration and Construction serves Vista and the surrounding CA area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
