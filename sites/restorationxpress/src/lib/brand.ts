// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "restorationxpress",
  displayName: "RestorationXpress ",
  shortName: "RestorationXpress",
  legalName: "RestorationXpress ",
  domain: "restorationxpress.com",
  canonicalUrl: "https://restorationxpress.com",
  phone: "(954) 932-5420",
  phoneRaw: "+19549325420",
  // Sitewide call-tracking display number (DNI — see BaseLayout).
  // Schema/NAP keep the canonical number above.
  trackingPhone: "(561) 621-4582",
  trackingPhoneRaw: "+15616214582",
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
  imagesBase: "https://images.restorationxpress.com",
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
  sameAsUrls: ["https://maps.google.com/maps?cid=16857264021556416183", "https://www.homeadvisor.com/rated.RestorationXpressLLC.85203543.html", "https://www.facebook.com/restorationxpress/", "https://homeguide.com/fl/davie/water-damage-restoration/restorationxpress-_VgGv-Adz"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.9",
  gbpReviewCount: "129",
  gbpReviews: [
    { author: "Piero", rating: 5, text: "Shadi and Chris were very helpful, all the expensive furniture was placed on foam blocks to prevent damage. The place was left dry. Very grateful would recommend.", when: "August 2026" },
    { author: "Jonathan", rating: 5, text: "I highly recommend this restoration company! They did an outstanding job repairing and restoring my bathroom. From start to finish, the team was professional, reliable, and courteous. They kept me informed throughout the process, showed up when they said they would, and paid close attention to…", when: "July 2026" },
    { author: "Cheryl", rating: 5, text: "Shadi and Chris were professional, kind, thoughtful and patient under a very difficult circumstance. I appreciate how much they went above and beyond to be certain all was taken care in the correct way.", when: "June 2026" },
    { author: "Shmuel", rating: 5, text: "Shadi and chris did a great job", when: "June 2026" },
    { author: "Lilach", rating: 5, text: "⭐⭐⭐⭐⭐ I cannot say enough good things about Restoration Xpress, Issac, and the entire team. After we experienced water damage in our home, they handled everything from the mitigation process to the reconstruction of our kitchen and the final post-construction cleaning. The entire process was…", when: "June 2026" },
    { author: "Marilyn", rating: 5, text: "We chose Restoration Express to do our mold remediation. They are such an amazing company. They are so professional not only in their work ethic, but they communicated with me daily. They worked with me as far as pricing. they are extremely fair. they are clean. they removed every spec of mold from…", when: "June 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Davie, FL.",
  ctaLabel: "24/7 Emergency Line",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
