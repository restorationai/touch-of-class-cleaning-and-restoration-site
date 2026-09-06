// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "drycor-restore",
  displayName: "DRYCOR RESTORE",
  shortName: "DRYCOR RESTORE",
  legalName: "DRYCOR RESTORE",
  domain: "drycor.com",
  canonicalUrl: "https://drycor.com",
  phone: "(813) 829-1091",
  phoneRaw: "+18138291091",
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "",
  trackingPhoneRaw: "",
  email: "team@drycor.com",
  hours: "24/7",
  foundedYear: "2005",
  primaryCity: "Thonotosassa",
  primaryState: "FL",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Thonotosassa",
  addressState: "FL",
  streetAddress: "10798 Florence Ave",
  postalCode: "33592",
  lat: "28.0655281",
  lng: "-82.294789",
  placeId: "ChIJ--4aNxtJuIURz7eqWifJBM4",
  googleCid: "14845211442582042575",
  imagesBase: "https://images.drycor.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: ["CBC1253966"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://www.myfloridalicense.com/wl11.asp",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC CERTIFIED FIRM", "IICRC WRT (WATER)", "EPA LEAD-SAFE CERTIFIED", "OSHA TRAINED", "NAERMC-(MOLD)"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.bing.com/maps?ss=ypid.YND295ED88552C26BD", "https://homeguide.com/fl/tampa/water-damage-restoration/drycor-restore-B7Lx1MPyy"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "5.0",
  gbpReviewCount: "22",
  gbpReviews: [
    { author: "Bobbie", rating: 5, text: "I can’t say enough wonderful things about Drycor Company! When a pipe broke in my home and caused water and mold problems, they responded so quickly and were there when I needed them most. Their promptness, professionalism, and genuine concern made a very stressful situation so much easier to…", when: "August 2026" },
    { author: "Shane", rating: 5, text: "A company with a long track record! Willow is great to deal with and really cares. No one wants to use the service but can not mess around with having mold in Florida", when: "July 2026" },
    { author: "Cora", rating: 5, text: "We have been working on our mold problem in our home for about a week with them and we are so grateful that we didn’t go with another “cheaper” company (it’s only cheaper because they aren’t doing the work right). If you are beginning your mold remediation experience you’ll learn quickly that a lot…", when: "July 2026" },
    { author: "Mark", rating: 5, text: "The Showalter Construction and Restoration Team as well as DryCor Restore have been a Great Help and Excellent Experience. From Initial assessment, Insurance navigation, Expert Advice, Execution of Restore have been spot on ! The Crew of Victor, Victor, Damen and Garrett are the best, Hard working…", when: "June 2026" },
    { author: "Cindy", rating: 5, text: "I highly recommend Drycor Restore, and Showalter Construction and Restoration. I had a plumbing issue that allowed water to run unseen throughout the house for months, damaging all of my floors, and leaving mold in my bathroom and bedroom. The slab had to be dried throughout, sealed, and new floors…", when: "May 2026" },
    { author: "Josh", rating: 5, text: "After our rental property in Land O' Lakes flooded in winter 2025 (sewage drain clog), we needed more than just cleanup. We needed a strategic partner. Drycor Restore delivered exactly that. Robert arrived first, incredibly knowledgeable, calm, and walked us through every step. He guided us on…", when: "May 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Thonotosassa, FL.",
  ctaLabel: "24/7 Emergency Line",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  tradeNoun: "restoration",
  specialistPhrase: "Damage Restoration Specialists",
  announcementSuffix: "24/7 Emergency Response",
  homeAboutBlurb: "DRYCOR RESTORE serves Thonotosassa and the surrounding FL area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
