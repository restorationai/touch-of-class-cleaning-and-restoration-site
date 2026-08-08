// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "quality-contracting-inc",
  displayName: "Quality Contracting, Inc.",
  shortName: "Quality Contracting, Inc.",
  legalName: "Quality Contracting, Inc.",
  domain: "",
  canonicalUrl: "https://None",
  phone: "(508) 756-8800",
  phoneRaw: "+15087568800",
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
  imagesBase: "https://images.None",
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
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.5",
  gbpReviewCount: "86",
  gbpReviews: [
    { author: "Bryant", rating: 5, text: "Talk about turning a disaster into a small inconvenience. First Ice dam ever. nightmare. One phone call and Quality took care of it. They told me what to do. Sent a team over that day to start remediation. I could never have handled all of this without them. Everyone who came to the house was…", when: "July 2026" },
    { author: "Frankie", rating: 5, text: "I highly recommend Quality Contracting, Inc!!!. They are an amazing team that calmly helped me through a very stressful time for me. I was very fortunate to have Johana as the project manager during the initial mitigation process. I admire her leadership in a traditionally male-dominant field!! She…", when: "June 2026" },
    { author: "Paul", rating: 5, text: "Excellent communication throughout the process. Resources were timely, polite, friendly and experienced.", when: "June 2026" },
    { author: "Bill", rating: 5, text: "The project manager kept me informed as the work progressed. They did excellent work cleaning up as they went along. I could not asked for a better contracting company. On a scale of one to ten they get a ten. Again thanks for the great service.", when: "May 2026" },
    { author: "Denise", rating: 4, text: "Our remediation team was several hours late due to a schedule mishap, but thanks to Johana the team stayed and did a great job. She stopped in to check on them every day that they were here. Johana was knowledgeable, professional, and very pleasant to work with. She's very very good at her job.", when: "April 2026" },
    { author: "Stephanie", rating: 5, text: "I had part of my wall replaced this year and they did great service ! Shout out to Derek Pereira I appreciate all the work done !", when: "March 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Auburn, MA.",
  ctaLabel: "24/7 Emergency Line",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
