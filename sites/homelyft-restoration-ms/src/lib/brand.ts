// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "homelyft-restoration-ms",
  displayName: "HomeLyft Restoration MS",
  shortName: "HomeLyft Restoration MS",
  legalName: "HomeLyft Restoration MS",
  domain: "",
  canonicalUrl: "https://None",
  phone: "+12282845200",
  phoneRaw: "+112282845200",
  // Sitewide call-tracking display number (DNI — see BaseLayout).
  // Schema/NAP keep the canonical number above.
  trackingPhone: "(228) 900-9718",
  trackingPhoneRaw: "+12289009718",
  email: "info@homelyft.net",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Gulfport",
  primaryState: "MS",
  streetAddress: "1311 SPRING Street",
  postalCode: "39507",
  lat: "",
  lng: "",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.None",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.png", // real logo from branding bucket (CO-1785514205030/brand); switch to images.{domain}/brand/logo.png at production cutover once the domain + R2 bucket exist
  licenseNumbers: ["RO 2728"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: ["IICRC Certified Firm", "IICRC WRT (Water)", "IICRC ASD (Structural Drying)", "EPA Lead-Safe Certified", "IICRC FSRT (Fire & Smoke)", "IICRC AMRT (Mold)", "OSHA Trained", "FORTIFIED Roofing (MS Windstorm) Certified"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.google.com/maps?cid=2198109827142676174", "https://www.yelp.com/biz/homelyft-restoration-gulfport", "https://www.bbb.org/us/ms/gulfport/profile/restoration-companies/homelyft-restoration-0523-235903913", "https://www.facebook.com/p/HomeLyft-Restoration-61560770035871/", "https://pro.porch.com/gulfport-ms/general-contractors/homelyft-restoration/pp", "https://homeguide.com/ms/gulfport/water-damage-restoration/homelyft-restoration-_ZLeDzvnC"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "5.0",
  gbpReviewCount: "51",
  gbpReviews: [
    { author: "Tamera", rating: 5, text: "I highly recommend HomeLyft Restoration. When I first found them online, I was honestly a little nervous because I had never heard of them before. Hiring a company to restore your home after water damage is a big decision, and I wasn’t sure what to expect. I wondered if they would show up when they…", when: "July 2026" },
    { author: "Virginia", rating: 5, text: "We had a major flooding issue at a family home, and Homelyft arrived within 30 minutes of our call, and immediately started the cleanup! They were incredibly knowledgeable, professional, and easy to work with every step of the way, and truly rescued us. We offer our highest recommendation. Thank…", when: "June 2026" },
    { author: "Tyler", rating: 5, text: "Made an appointment and they were we at my house the next day, extremely professional and efficient! They were able to answer any question or concerns i had. Highly recommend this company!", when: "June 2026" },
    { author: "Missy", rating: 5, text: "Josiah was very efficient and the crew was amazing. Good work!", when: "June 2026" },
    { author: "Lindsay", rating: 5, text: "We can’t say enough great things about Homelyft Restoration. As a plumbing company, we encounter water damage situations regularly, and having a trusted, reliable restoration partner is essential. The Homelyft team consistently delivers prompt response times, clear communication, and high-quality…", when: "April 2026" },
    { author: "Laura", rating: 5, text: "HomeLyft did a phenomenal job repairing and restoring a roof leak and the damage it caused. I would definitely recommend this locally owned and family operated company!😃", when: "March 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Gulfport, MS.",
  ctaLabel: "24/7 Emergency Line",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  tradeNoun: "restoration",
  specialistPhrase: "Damage Restoration Specialists",
  announcementSuffix: "24/7 Emergency Response",
  homeAboutBlurb: "HomeLyft Restoration MS serves Gulfport and the surrounding MS area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
