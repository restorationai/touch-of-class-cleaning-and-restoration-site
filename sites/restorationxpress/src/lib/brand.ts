// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "restorationxpress",
  displayName: "RestorationXpress ",
  shortName: "RestorationXpress",
  legalName: "RestorationXpress ",
  domain: "",
  canonicalUrl: "https://None",
  phone: "(954) 964-6471",
  phoneRaw: "+19549646471",
  email: "issac@restorationxpress.com",
  hours: "24/7",
  foundedYear: "2011",
  primaryCity: "Davie",
  primaryState: "FL",
  streetAddress: "4700 SW 51 ST SUIT 205 DAVIE FL33314 ",
  postalCode: "33314",
  lat: "26.0628665",
  lng: "-80.2331038",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.None",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: ["1057"] as string[],
  licenseAuthority: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: [] as string[],
  trustBadges: ["Licensed & Insured", "24/7 Emergency Response", "Serving Broward, Palm Beach & Miami-Dade Since 2011", "Insurance Billing Accepted"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.9",
  gbpReviewCount: "131",
  gbpReviews: [
    { author: "Alexis", rating: 5, text: "I had an emergency, and they responded immediately and professionally. They quickly resolved the issue of water damage caused by a leak from my master bathroom. Communication was excellent because they speak Spanish, which was helpful since my wife is not fluent in the language. Restoration Xpress…", when: "July 2026" },
    { author: "Helia", rating: 5, text: "I had a mold problem in my apartment and the service was excellent. I have a dog so I was worried about the treatment being safe for pets, but everything was completely petfriendly and there were no issues at all. The apartment was left spotless, and the mold is completely gone. Also, my English…", when: "July 2026" },
    { author: "Jonathan", rating: 5, text: "I highly recommend this restoration company! They did an outstanding job repairing and restoring my bathroom. From start to finish, the team was professional, reliable, and courteous. They kept me informed throughout the process, showed up when they said they would, and paid close attention to…", when: "July 2026" },
    { author: "Cheryl", rating: 5, text: "Shadi and Chris were professional, kind, thoughtful and patient under a very difficult circumstance. I appreciate how much they went above and beyond to be certain all was taken care in the correct way.", when: "June 2026" },
    { author: "Shmuel", rating: 5, text: "Shadi and chris did a great job", when: "June 2026" },
    { author: "Lilach", rating: 5, text: "⭐⭐⭐⭐⭐ I cannot say enough good things about Restoration Xpress, Issac, and the entire team. After we experienced water damage in our home, they handled everything from the mitigation process to the reconstruction of our kitchen and the final post-construction cleaning. The entire process was…", when: "June 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Davie, FL.",
  ctaLabel: "24/7 Emergency Line",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
