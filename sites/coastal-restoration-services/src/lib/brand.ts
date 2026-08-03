// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "coastal-restoration-services",
  displayName: "Coastal Restoration Services Inc",
  shortName: "Coastal Restoration Services Inc",
  legalName: "Coastal Restoration Services Inc",
  domain: "",
  canonicalUrl: "https://None",
  phone: "(805) 345-7440",
  phoneRaw: "+18053457440",
  email: "tony@callcrs.com",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Santa Maria",
  primaryState: "CA",
  streetAddress: "217 E Fesler St",
  postalCode: "93454",
  lat: "34.9531295",
  lng: "-120.435857",
  placeId: "ChIJgb6Gdhxh4wYRjbzm6ELYT38",
  googleCid: "",
  imagesBase: "https://images.None",
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
  licensedInsuredAttested: false as boolean,
  certifications: [] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "5.0",
  gbpReviewCount: "29",
  gbpReviews: [
    { author: "George", rating: 5, text: "Yes i highly recommend. Coastal rushed to the scene on the weekend and promptly provided valued feedback. We were able to move forward with our situation forthwith. Very satisfied with outcome.", when: "July 2026" },
    { author: "Al", rating: 5, text: "We were very satisfied with the work they did. You would never know that we had a mold problem or that the lower 2 feet of our walls surrounding the refrigerator were replaced.", when: "July 2026" },
    { author: "Alejandra", rating: 5, text: "Speedy work and very well done. Flexible with scheduling days and left very happy with the service. Recommend.", when: "July 2026" },
    { author: "Alejandro", rating: 5, text: "I was moving my washer when the water line snapped off the wall. Did not expect it to flood the way it did, it got bad pretty fast. First thing I thought about was mold, so I called CRS right away. I was pretty stressed when the owner Tony showed up but he immediately put me at ease. Walked me…", when: "July 2026" },
    { author: "John", rating: 5, text: "Tony and his crew did a fantastic and quick job to repair the first floor water damage of our condo! Great work at a very reasonable price!!", when: "July 2026" },
    { author: "Jesus", rating: 5, text: "Gave them a call and they came out right away! The crew was professional, courteous, and respectful. We would highly recommend them to anyone in the area.", when: "July 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Vandenberg Village, CA.",
  ctaLabel: "24/7 Emergency Line",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
