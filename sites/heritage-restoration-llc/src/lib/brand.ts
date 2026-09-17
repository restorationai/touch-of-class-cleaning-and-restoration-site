// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "heritage-restoration-llc",
  displayName: "Heritage Restoration LLC",
  shortName: "Heritage Restoration LLC",
  legalName: "Heritage Restoration LLC",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "Heritage Restoration - 24/7 Emergency Plumbing, Water and Fire Damage Restoration",
  domain: "heritagermn.com",
  canonicalUrl: "https://heritagermn.com",
  phone: "(320) 733-8868",
  phoneRaw: "+13207338868",
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "(320) 431-2606",
  trackingPhoneRaw: "+13204312606",
  email: "support@heritagermn.com",
  hours: "24/7",
  foundedYear: "2023",
  primaryCity: "Little Falls",
  primaryState: "MN",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Little Falls",
  addressState: "MN",
  streetAddress: "10984 Harvest Road",
  postalCode: "56345",
  lat: "45.9763545",
  lng: "-94.3625024",
  placeId: "ChIJlRLa-3KCHy8RUE-lOQD16VU",
  googleCid: "",
  imagesBase: "https://images.heritagermn.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: ["BC807677"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC WRT (WATER)", "IICRC FSRT (FIRE & SMOKE)", "IICRC ASD (STRUCTURAL DRYING)", "EPA LEAD-SAFE CERTIFIED", "IICRC AMRT (MOLD)"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://facebook.com/heritagermn", "https://maps.google.com/maps?cid=6190748544113397584", "https://www.yelp.com/biz/heritage-restoration-little-falls", "https://www.bbb.org/us/mn/little-falls/profile/residential-general-contractor/heritage-restoration-llc-0704-1000067972", "https://www.homeadvisor.com/rated.greensourceinc.156583960.html"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Little Falls, MN.",
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
  homeAboutBlurb: "Heritage Restoration LLC serves Little Falls and the surrounding MN area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
