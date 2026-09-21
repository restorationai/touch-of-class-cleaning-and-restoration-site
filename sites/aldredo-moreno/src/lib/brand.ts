// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "aldredo-moreno",
  displayName: "ACS Enterprise ",
  shortName: "ACS Enterprise ",
  legalName: "ACS Enterprise ",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "theacs-enterprises.com",
  canonicalUrl: "https://theacs-enterprises.com",
  phone: "(432) 847-4704",
  phoneRaw: "+14328474704",
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "",
  trackingPhoneRaw: "",
  email: "am@theacsenterprises.com",
  hours: "24/7",
  foundedYear: "2019",
  primaryCity: "Midland",
  primaryState: "TX",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Midland",
  addressState: "TX",
  streetAddress: "3517 ECR 175",
  postalCode: "79706",
  lat: "31.83688",
  lng: "-102.0103767",
  placeId: "ChIJ_8rF3eff-4YRWkbhWgvgu_8",
  googleCid: "18427568639690491482",
  imagesBase: "https://images.theacs-enterprises.com",
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
  certifications: [] as string[],
  trustBadges: ["Licensed & Insured", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "5.0",
  gbpReviewCount: "362",
  gbpReviews: [
    { author: "Pam", rating: 5, text: "Response was wonderful. Working with them was great considering it was a rough day following a flood in my master bathroom and bedroom.", when: "September 2026" },
    { author: "Cami", rating: 5, text: "Mr. Moreno was very kind, easy to communicate with, and quick to complete the job. I would definitely use ASC Enterprise again and recommend them.", when: "September 2026" },
    { author: "Brian", rating: 5, text: "Quick and easy, picked up same day", when: "August 2026" },
    { author: "Kyle", rating: 5, text: "These guys are phenomenal!!! I bought a house recently and it had insulation issues and needed to be removed. The air ducts needed cleaning, as well. I called around to and was given the number for ACS. Alfredo’s guys showed up to work and that they did! They completed the job in a timely manner…", when: "July 2026" },
    { author: "Rosa", rating: 5, text: "Very friendly, punctual nd helpful overall SUPER AWESOME!!! 💯👍", when: "July 2026" },
    { author: "Vivian", rating: 5, text: "Great guys very professional extremely happy with the service", when: "July 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Midland, TX.",
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
  homeAboutBlurb: "ACS Enterprise  serves Midland and the surrounding TX area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
