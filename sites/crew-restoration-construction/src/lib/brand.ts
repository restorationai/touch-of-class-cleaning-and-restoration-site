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
  // Sitewide call-tracking display number (DNI — see BaseLayout).
  // Schema/NAP keep the canonical number above.
  trackingPhone: "(605) 656-5940",
  trackingPhoneRaw: "+16056565940",
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
  imagesBase: "https://images.crew3r.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-GCKPEW6C00",
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
  sameAsUrls: ["https://maps.google.com/maps?cid=15917989220887052070", "https://www.yelp.com/biz/crew-construction-and-restoration-sioux-falls", "https://www.bbb.org/us/sd/sioux-falls/profile/fire-water-damage-restoration/crew-construction-restoration-0714-300168398", "https://www.facebook.com/CrewSiouxFalls/", "https://www.bing.com/maps?ss=ypid.YN841719F0A3CAB26F"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.8",
  gbpReviewCount: "501",
  gbpReviews: [
    { author: "Ryan", rating: 5, text: "Bryson, did a great job at cleaning up our sewage back up!", when: "August 2026" },
    { author: "Rylie", rating: 5, text: "loren and jason did an amazing job on the deck at the cabin. I would highly recommend for their expertise", when: "August 2026" },
    { author: "Andrea", rating: 5, text: "We enlisted the help of Crew Inc. for an after-hours water emergency. Their team was quick to respond and friendly throughout the process despite it being an unexpected job for them. Brandon & Trey put us at ease about the situation and what comes next. We are grateful we called them!", when: "August 2026" },
    { author: "John", rating: 5, text: "Brandy was amazing helping us curate a beautiful renovation. Her communication was on point and style gave our house a much needed boost. If you’re ever in need of construction or a style boost to your real estate, you can’t beat the quality you’ll get with Brandy.", when: "August 2026" },
    { author: "Ryan", rating: 5, text: "Zach is great at communicating, works hard and great restoration services", when: "August 2026" },
    { author: "Jay", rating: 5, text: "Brandon was amazing to work with. He made the whole process seamless. AMAZING WORK!", when: "August 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Sioux Falls, SD.",
  ctaLabel: "24/7 Emergency Line",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
