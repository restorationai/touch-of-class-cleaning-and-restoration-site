// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "life-savers-restoration-llc",
  displayName: "Life Savers Restoration LLC",
  shortName: "Life Savers Restoration LLC",
  legalName: "Life Savers Restoration LLC",
  domain: "lifesaversrestorationvegas.com",
  canonicalUrl: "https://lifesaversrestorationvegas.com",
  phone: "(702) 845-1325",
  phoneRaw: "+17028451325",
  // Sitewide call-tracking display number (DNI — see BaseLayout).
  // Schema/NAP keep the canonical number above.
  trackingPhone: "(702) 930-8647",
  trackingPhoneRaw: "+17029308647",
  email: "info@lifesaversrestoration.com",
  hours: "24/7",
  foundedYear: "2019",
  primaryCity: "Henderson",
  primaryState: "NV",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Henderson",
  addressState: "NV",
  streetAddress: "7685 Commercial Way Ste G",
  postalCode: "89011",
  lat: "36.0319602",
  lng: "-114.9822716",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.lifesaversrestorationvegas.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-EGE48LYQVZ",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: ["0091001"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://www.nvcontractorsboard.com/",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC CERTIFIED FIRM", "IICRC WRT (WATER)", "IICRC ASD (STRUCTURAL DRYING)", "IICRC AMRT (MOLD)", "IICRC FSRT (FIRE & SMOKE)", "EPA LEAD-SAFE CERTIFIED", "OSHA TRAINED"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.facebook.com/LifeSaversResto/", "https://www.yellowpagesdirectory.com/Henderson-NV/Life+Savers+Restoration+LLC/75688", "https://maps.google.com/maps?cid=10061689300988421569", "https://www.bbb.org/us/nv/henderson/profile/fire-water-damage-restoration/life-savers-restoration-llc-1086-90068182", "https://homeguide.com/nv/henderson/water-damage-restoration/life-savers-restoration-llc-UlP_1GhU4"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.8",
  gbpReviewCount: "246",
  gbpReviews: [
    { author: "Marcia", rating: 5, text: "I highly recommend Rudy and Life Savers Restoration! I had sudden water damage emergency at my townhome while living out of town, and Rudy came through on very short notice after being recommended by a friend. He kept me informed every step of the way, did an excellent job, and took the time to…", when: "July 2026" },
    { author: "Martin", rating: 5, text: "The Life Savers team took care of our water damage and was done quickly, with as little disruption as possible. The team was professional. Rudy helped us through the process with the insurance company from start to finish.", when: "June 2026" },
    { author: "Cindy", rating: 5, text: "Rudy was very helpful and informative. Made this process less stressful and was always available to answer any questions. His team was professional and very informative. Thank you all for making this process easier to navigate through, we appreciate you all.", when: "May 2026" },
    { author: "Shelley", rating: 5, text: "We had a sewer line break and had sewage backed up in two bathrooms. Before we could fix the main line we had to get rid of the black water business. Called Life Savers and they went out to look at, quote , and do the clean up the same day! Very impressed! Very professional! If I ever need…", when: "May 2026" },
    { author: "Larosha", rating: 5, text: "I highly recommend Life Savers, LLC! Their team is caring, dependable, and truly committed to providing outstanding service. From the very beginning, they have shown professionalism, kindness, and genuine compassion. It’s rare to find a company that consistently goes the extra mile, but Life…", when: "May 2026" },
    { author: "Roy", rating: 5, text: "Had a water valve failure. Life Savers were prompt and cleaned up the mess so that restoration could begin. Great service. Great people. Would not hesitate to recommend or use again (hopefully I won't need them)", when: "March 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Henderson, NV.",
  ctaLabel: "24/7 Emergency Line",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  tradeNoun: "restoration",
  specialistPhrase: "Damage Restoration Specialists",
  announcementSuffix: "24/7 Emergency Response",
  homeAboutBlurb: "Life Savers Restoration LLC serves Henderson and the surrounding NV area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
