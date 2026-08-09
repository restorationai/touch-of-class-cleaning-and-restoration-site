// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "crew-restoration-construction",
  displayName: "Crew Restoration & Construction",
  shortName: "Crew",
  legalName: "Crew Restoration & Construction",
  domain: "crew3r.com",
  canonicalUrl: "https://crew3r.com",
  phone: "(605) 965-2727",
  phoneRaw: "+16059652727",
  email: "estimates@crewthatcares.com",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Sioux Falls",
  primaryState: "SD",
  streetAddress: "3503 South Norton Avenue",
  postalCode: "57110",
  lat: "43.5476008",
  lng: "-96.7293629",
  placeId: "ChIJ62IxEgm2jocRJj94-dsO6Nw",
  googleCid: "",
  imagesBase: "https://images.None",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: ["3814"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC"] as string[],
  trustBadges: ["Locally Trusted for 50+ Years", "Highly Trained, Certified Technicians", "24 Hour Emergency Service", "One Stop Shop From Start To Finish"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.8",
  gbpReviewCount: "488",
  gbpReviews: [
    { author: "Chelsey", rating: 5, text: "We made an appointment with Victor from Crew to inspect our basement for possible mold. He arrived promptly, thoroughly examined the area, and took the time to explain his findings in detail. After his inspection, he reassured us that the only work needed was to remove a few baseboards and that…", when: "July 2026" },
    { author: "Chris", rating: 5, text: "Vic runs a stellar promo tent with swag for days", when: "July 2026" },
    { author: "Jason", rating: 5, text: "Great bunch!! Well organized and everything was as it should be. Thanks.", when: "July 2026" },
    { author: "Nick", rating: 5, text: "Had a great experience with Victor and learned way more about how the whole restoration process works & feel much more confident!", when: "July 2026" },
    { author: "Billy", rating: 5, text: "Very helpful with questions I had!", when: "July 2026" },
    { author: "Brendon", rating: 5, text: "Crew is very sweaty and cool dude", when: "July 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Sioux Falls, SD.",
  ctaLabel: "24/7 Emergency Line",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
