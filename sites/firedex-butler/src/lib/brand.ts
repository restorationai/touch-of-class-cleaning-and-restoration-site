// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "firedex-butler",
  displayName: "FireDEX Butler",
  shortName: "FireDEX",
  legalName: "FireDEX Butler, Inc.",
  domain: "firedex.net",
  canonicalUrl: "https://firedex.net",
  phone: "(724) 452-7400",
  phoneRaw: "+17244527400",
  // Sitewide call-tracking display number (DNI — see BaseLayout).
  // Schema/NAP keep the canonical number above.
  trackingPhone: "(724) 623-2137",
  trackingPhoneRaw: "+17246232137",
  email: "mail@firedex.net",
  hours: "24/7",
  foundedYear: "1981",
  primaryCity: "Cranberry Township",
  primaryState: "PA",
  streetAddress: "9133 Marshall Rd",
  postalCode: "16066",
  lat: "",
  lng: "",
  placeId: "ChIJ4zqdqGF9NIgR0zyEf6VVd80",
  googleCid: "14805396469301132499",
  imagesBase: "https://images.firedex.net",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-65LP4WBQWM",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: ["PA001913"] as string[],
  licenseAuthority: "Pennsylvania Attorney General — Home Improvement Contractor Registration",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: [] as string[],
  trustBadges: [] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.google.com/maps?cid=14805396469301132499", "https://www.yelp.com/biz/firedex-butler-cranberry-twp", "https://www.bbb.org/us/pa/cranberry-twp/profile/building-restoration/firedex-of-butler-inc-0141-12002805", "https://www.homeadvisor.com/rated.FiredexofButlerInc.22614897.html", "https://www.houzz.com/professionals/general-contractors/firedex-of-butler-inc-pfvwus-pf~26200651", "https://www.yellowpages.com/cranberry-township-pa/mip/firedex-of-butler-inc-7424511"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "3.7",
  gbpReviewCount: "13",
  gbpReviews: [
    { author: "Sue", rating: 5, text: "I had a great experience with FireDEX. They were great to work with. Quick to get me a quote and to schedule the repairs. The job they did turned out fantastic and I would call them again if the need arises. Hands Down Solid 5 Star!!", when: "August 2025" },
    { author: "Jim", rating: 5, text: "Good company, their work speaks for itself,their team of professionals are friendly and knowledgeable.", when: "September 2023" },
    { author: "Matt", rating: 5, text: "FireDex of Butler has always been there when I needed them. From restoration to construction, they have professionally performed several jobs for me. I would highly recommend this company for their service, expertise, and value.", when: "April 2020" },
    { author: "Michael", rating: 5, text: "Big stone job underway when the mason crew discovered one of the biggest components of the job - our chimney - was decayed and structurally to weak to support the additional weight of stone veneer. Time is money and our stone masons needed to keep working. Fire Dex of Butler came in and…", when: "April 2019" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "Water • Fire • Storm Restoration — 24/7 emergency response across Cranberry Township, Butler County and the Pittsburgh North suburbs since 1981.",
  ctaLabel: "24/7 Emergency Hotline",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
