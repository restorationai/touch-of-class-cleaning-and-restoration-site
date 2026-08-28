// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "quality-contracting-inc",
  displayName: "Quality Contracting, Inc.",
  shortName: "Quality Contracting, Inc.",
  legalName: "Quality Contracting, Inc.",
  domain: "",
  canonicalUrl: "https://qualitycontracting.us",
  phone: "(508) 756-8800",
  phoneRaw: "+15087568800",
  // Sitewide call-tracking display number (DNI — see BaseLayout).
  // Schema/NAP keep the canonical number above.
  trackingPhone: "(508) 978-7507",
  trackingPhoneRaw: "+15089787507",
  email: "info@qualitycontracting.us",
  hours: "24/7",
  // Fran 2026-08-05: "We started almost 30 years ago and incorporated in 2001."
  // Using the INCORPORATION year, which is the documented, verifiable one. The
  // ~30-year figure is his recollection and is not something we can evidence,
  // so it does not go on the site as a claim.
  foundedYear: "2001",
  primaryCity: "Auburn",
  primaryState: "MA",
  streetAddress: "211 Southbridge Street",
  postalCode: "01501",
  lat: "42.1945465",
  lng: "-71.8358095",
  placeId: "",
  googleCid: "",
  // No per-client images bucket provisioned — serve the brand hero fallback
  // from the site itself (public/brand/hero.webp)
  imagesBase: "",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo-dark-bg.png",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: [] as string[],
  trustBadges: ["24/7 Emergency Response", "25+ Years of Experience", "Commercial & Residential", "Serving MA, CT & RI"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://maps.google.com/maps?cid=8645835952486055131", "https://www.yelp.com/biz/quality-contracting-auburn", "https://www.bbb.org/us/ma/auburn/profile/fire-water-damage-restoration/quality-contracting-inc-0261-103855", "https://www.angi.com/companylist/us/ma/auburn/quality-contracting-inc-reviews-164220227.htm", "https://www.facebook.com/qualcontracting/", "https://www.houzz.com/professionals/general-contractors/quality-contracting-inc-pfvwus-pf~815837747"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.6",
  gbpReviewCount: "95",
  gbpReviews: [
    { author: "William", rating: 5, text: "Very courteous workers. Kept me informed as the work was progressing", when: "August 2026" },
    { author: "Gail", rating: 5, text: "I have never had such an incredible team as Quality Contracting’s under manager Mike Bonnette following last winter’s ice dam. Each member of the team he put together…from movers, to those securing all entries with plastic, filtering air machine in place to assure the rest of the house had only…", when: "August 2026" },
    { author: "Heather", rating: 5, text: "I am so happy I chose this company to move our belongings to our new home. The whole process was seamless and the guys (Henry’s team) were incredible. They were kind, considerate, careful, and fast! I will tell everyone to use your company. I didn’t mention one of the best parts, your quote was…", when: "August 2026" },
    { author: "Renee", rating: 5, text: "Quality contracting had been top notch to work with so far. We had a roof leak that resulted in water damage to multiple areas within our home. Quality's swift response saved our 100 year old flooring in multiple rooms. Javier, Jose & Luis were always professional and took great care to ensure that…", when: "August 2026" },
    { author: "Erik", rating: 5, text: "I’ve been working with QCI for over 5 years. The always deliver a quality renovation and are easy to work with. Highly recommended.", when: "August 2026" },
    { author: "Gino", rating: 5, text: "I had a major main sewer line back up over the weekend that flooded out my finished cellar and had to get in touch with a hazmat company. I chose Quality Contracting. OMG what a lucky choice I made ! Everyone that I've dealt with from the company have been Wonderful. It all started with Amy in the…", when: "August 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Auburn, MA.",
  ctaLabel: "24/7 Emergency Line",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
