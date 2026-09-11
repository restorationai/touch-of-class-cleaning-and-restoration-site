// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "diss-restoration",
  displayName: "DISS Restoration",
  shortName: "DISS Restoration",
  legalName: "DISS Restoration",
  domain: "dissrestoration.com",
  canonicalUrl: "https://dissrestoration.com",
  phone: "(724) 981-1441",
  phoneRaw: "+17249811441",
  trackingPhone: "",
  trackingPhoneRaw: "",
  email: "info@dissrestoration.com",
  hours: "24/7",
  foundedYear: "2021",
  primaryCity: "Youngstown",
  primaryState: "OH",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Farrell",
  addressState: "PA",
  streetAddress: "712 Spearman Avenue",
  postalCode: "16121",
  lat: "41.1035786",
  lng: "-80.6520161",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.dissrestoration.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-QQDEBB808D",
  clarityProjectId: "",
  // local file until the client's domain + R2 bucket exist; switch to
  // images.{domain}/brand/logo.png at production cutover
  logoUrl: "/images/logo.png",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC CERTIFIED FIRM", "IICRC WRT (WATER)", "IICRC FSRT (FIRE & SMOKE)", "IICRC AMRT (MOLD)", "EPA LEAD-SAFE CERTIFIED", "OSHA TRAINED", "IICRC ASD (STRUCTURAL DRYING)"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.facebook.com/DISSRestoration/", "https://maps.google.com/maps?cid=3976360707548162480", "https://www.bbb.org/us/pa/farrell/profile/fire-water-damage-restoration/diss-restoration-0141-10835"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.6",
  gbpReviewCount: "62",
  gbpReviews: [
    { author: "Fe", rating: 5, text: "Awesome company! They were here for pictures in less than an hour after initial call and here to do clean up in my basement within 5 hours.", when: "July 2026" },
    { author: "Jeff", rating: 5, text: "We called DISS Restoration to remediate a flooded basement. They came out within an hour of getting called to assess the situation. Immediate action was then taken to remove the water, tear out carpets, dry the basement and treat the basement for any mold. They used a slew of people for all of…", when: "July 2026" },
    { author: "Greg", rating: 5, text: "Arrived within 90 minutes from initial call. Went in to a basement with 6 to 8 inches of waste from a busted sewer line, smelled worse than septic tank in July. They coordinatedmwith plumbing company to clear path for repair, then they finished cleaning everything up, including disposal of…", when: "June 2026" },
    { author: "Natara", rating: 5, text: "Daniel and his crew were awesome! Very professional, thorough, and efficient. They were also incredibly friendly and were there to answer any questions I had. Highly recommended!", when: "June 2026" },
    { author: "Kyra", rating: 5, text: "Joey, Pat, and Josh. I now have these gentlemen on speed dial. We had a plumbing issue last summer that resulted in a water logged powder room and garage ceiling. DISS was sent via our insurance. When a similar issue happened again, I got in touch with the boys and a team was here inside of 2…", when: "May 2026" },
    { author: "Judy", rating: 5, text: "Joe is so awesome! So easy to talk with! He was so great to do business with! He made us feel comfortable the whole way through.People like him make circumstances that could be difficult to deal with seem easy.. we are happy with the whole experience! Joe made a good impression on us! Bob and Judy…", when: "May 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Youngstown, OH.",
  ctaLabel: "24/7 Emergency Line",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  tradeNoun: "restoration",
  specialistPhrase: "Damage Restoration Specialists",
  announcementSuffix: "24/7 Emergency Response",
  homeAboutBlurb: "DISS Restoration serves Youngstown and the surrounding OH area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
