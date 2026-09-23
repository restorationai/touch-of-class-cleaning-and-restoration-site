// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "firedex-butler",
  displayName: "FireDEX Butler",
  shortName: "FireDEX",
  legalName: "FireDEX Butler, Inc.",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "firedex.net",
  canonicalUrl: "https://firedex.net",
  phone: "(724) 452-7400",
  phoneRaw: "+17244527400",
  hideMobileHeaderCall: false,
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "(724) 623-2137",
  trackingPhoneRaw: "+17246232137",
  email: "mail@firedex.net",
  hours: "24/7",
  foundedYear: "1981",
  primaryCity: "Cranberry Township",
  primaryState: "PA",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Cranberry Township",
  addressState: "PA",
  streetAddress: "9133 Marshall Rd",
  postalCode: "16066",
  lat: "40.7099",
  lng: "-80.1061",
  placeId: "ChIJ4zqdqGF9NIgR0zyEf6VVd80",
  googleCid: "14805396469301132499",
  imagesBase: "https://images.firedex.net",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-65LP4WBQWM",
  clarityProjectId: "",
  logoUrl: "",
  licenseNumbers: ["PA001913"] as string[],
  licenseAuthority: "Pennsylvania Attorney General — Home Improvement Contractor Registration",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://hicsearch.attorneygeneral.gov/",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: [] as string[],
  trustBadges: [] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.google.com/maps?cid=14805396469301132499", "https://www.linkedin.com/in/cathi-olinger-82523515", "https://www.homeadvisor.com/rated.FiredexofButlerInc.22614897.html"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "Water • Fire • Storm Restoration — 24/7 emergency response across Cranberry Township, Butler County and the Pittsburgh North suburbs since 1981.",
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
  homeAboutBlurb: "FireDEX Butler serves Cranberry Township and the surrounding PA area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
