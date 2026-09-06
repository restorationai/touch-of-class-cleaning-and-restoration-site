// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "arch-enviornmental-group-llc",
  displayName: "Arch Enviornmental Group LLC",
  shortName: "Arch Enviornmental Group LLC",
  legalName: "Arch Enviornmental Group LLC",
  domain: "archenviroservice.com",
  canonicalUrl: "https://archenviroservice.com",
  phone: "(559) 296-2088",
  phoneRaw: "+15592962088",
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "(559) 254-4763",
  trackingPhoneRaw: "+15592544763",
  email: "info@archenviroservice.com",
  hours: "24/7",
  foundedYear: "2026",
  primaryCity: "Kingsburg",
  primaryState: "CA",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Kingsburg",
  addressState: "CA",
  streetAddress: "2453 16th Ave",
  postalCode: "93631",
  lat: "36.5138398",
  lng: "-119.5538929",
  placeId: "ChIJw9aO0Idq82sRNFXGkfL6roA",
  googleCid: "",
  imagesBase: "https://images.archenviroservice.com",
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
  certifications: ["CERTIFIED ASBESTOS CONSULTANT - LEAD INSPECTOR ASSESSOR - NIOSH 582 MICROSCOPIST"] as string[],
  trustBadges: ["Licensed & Insured", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://homeguide.com/ca/hanford/water-damage-restoration/arch-enviornmental-group-llc-h6MfKMIQ8"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "5.0",
  gbpReviewCount: "30",
  gbpReviews: [
    { author: "Austin", rating: 5, text: "Mike Luna is the guy to go to if you need fast, professional, or even education about testing. Mike patiently explained how pricing could vary depending on our specific needs. If you aren’t sure about the process, Arch environmental will make sure you have the right tools to make the right…", when: "July 2026" },
    { author: "Hani", rating: 5, text: "My experience with Mike (the owner) was completely not what I expected. Having dealt with a couple environmental company executives for our buisness in the area, I was expecting to be met with a driver form, but he was and still has been so amazing and helpful. Constant follow ups and…", when: "July 2026" },
    { author: "Carlos", rating: 5, text: "Arch Environmental is a great, reliable company! Their process is smooth, and they thoroughly explain every procedure from start to finish, with efficient scheduling and quick results. Highly recommend!", when: "July 2026" },
    { author: "Anthony", rating: 5, text: "I’ve worked with Rob and Mike from Arch Environmental on quite a few asbestos and lead testing jobs, including clearances. Rob knows his stuff and is always thorough with his testing and inspections. Mike is also great to work with and is always easy to get ahold of. They’ve always been…", when: "July 2026" },
    { author: "Jack", rating: 5, text: "I have use Arch environmental for testing for lead as asbestos also Mold clearances. My experience has always been fast service and great communication.Definitely recommend Mike Luna and his team.", when: "July 2026" },
    { author: "Neri", rating: 5, text: "Would definitely give a five star review! I've worked with Arch Environmental, through the company I work for. My experience with Arch Environmental working with Mike Luna has always been pleasant, professional and great communication and service.", when: "July 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "Independent environmental testing and inspections in Kingsburg, CA.",
  ctaLabel: "Schedule an Inspection",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  tradeNoun: "environmental testing",
  specialistPhrase: "Environmental Testing & Inspection Specialists",
  announcementSuffix: "Independent, Lab-Verified Testing",
  homeAboutBlurb: "Arch Enviornmental Group LLC provides independent environmental testing and inspections for homes and businesses across Kingsburg and the surrounding CA area. From mold and air quality testing to asbestos, lead, and water testing, every assessment is backed by accredited laboratory analysis and a clear written report. Because we don't perform the remediation ourselves, our findings are unbiased: we have no incentive to find problems that aren't there.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
