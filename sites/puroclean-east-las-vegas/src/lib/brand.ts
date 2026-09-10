// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "puroclean-east-las-vegas",
  displayName: "PuroClean of East Las Vegas",
  shortName: "Puroclean",
  legalName: "PuroClean of East Las Vegas",
  domain: "purocleaneastlasvegas.com",
  canonicalUrl: "https://purocleaneastlasvegas.com",
  phone: "+17025513040",
  phoneRaw: "+17025513040",
  // LP-only display pair (replaced by a dedicated ads tracking number when provisioned)
  adsTrackingPhone: "(702) 551-3040",
  adsTrackingPhoneRaw: "+17025513040",
  // Sitewide call-tracking display number (DNI — see BaseLayout).
  // Schema/NAP keep the canonical number above.
  trackingPhone: "(725) 500-0996",
  trackingPhoneRaw: "+17255000996",
  email: "eastlasvegas@puroclean.com",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Las Vegas",
  primaryState: "NV",
  streetAddress: "2777 N Lamb Blvd",
  postalCode: "89115",
  lat: "36.2153",
  lng: "-115.0867",
  placeId: "ChIJWRNeaVbDyIAR429H1EKyxas",
  googleCid: "",
  imagesBase: "https://images.purocleaneastlasvegas.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-M4N5NVD0WN",
  clarityProjectId: "",
  logoUrl: "/images/logo.png", // real PuroClean franchise mark from branding bucket (CO-1784594708149/brand); switch to images.purocleaneastlasvegas.com/brand/logo.png once the images R2 custom domain resolves (it currently has no DNS)
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: [] as string[],
  trustBadges: [] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.facebook.com/PuroCleanofEastLasVegas/", "https://maps.google.com/maps?cid=12377495150996713443", "https://www.yelp.com/biz/puroclean-las-vegas-3"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.9",
  gbpReviewCount: "20",
  gbpReviews: [
    { author: "Kim", rating: 5, text: "Our experience was great! They responded quickly, they were respectful of the property, and very friendly! Unfortunately we lived in a rental and the homeowner chose not to use PuroClean. I felt the estimate was reasonable that was given.", when: "September 2026" },
    { author: "Leilani", rating: 5, text: "We had a great experience with PuroClean of East Las Vegas. They responded quickly to our leak and provided excellent, professional service from start to finish. The team was knowledgeable, courteous, and took the time to make sure everything was handled properly. They made a stressful situation…", when: "August 2026" },
    { author: "Tracy", rating: 5, text: "Lino was amazing, walking us step by step through the whole process", when: "June 2026" },
    { author: "Johanna", rating: 5, text: "Lino came out after a leak in my home. I cannot express how wonderful he was. At every step of the way he was knowledgable and reassuring. The process went much more smoothly than I expected. They have an extensive understanding of how to best manage these types of disasters that can happen. I am…", when: "May 2026" },
    { author: "Andrea", rating: 5, text: "Lino was absolutely exceptional! He has the highest level of integrity and work ethic. He handled a very delicate emotional situation with empathy and sincerity and he handled the clean up of my home with professionalism, care and attention to detail. I could not have asked for a better person to…", when: "May 2026" },
    { author: "Christina", rating: 5, text: "Awesome service!!! Very professional and very knowledgeable! 10 out of 10 would recommend!", when: "March 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Las Vegas, NV.",
  ctaLabel: "24/7 Emergency Line",
  // Google Ads click-to-call conversion (biohazard-division PPC launch
  // 2026-09-08). The LP layouts load gtag + fire on tel: clicks when set.
  gadsId: "AW-18217052718",
  gadsCallConversionLabel: "AW-18217052718/YvXxCIn2s_EcEK7UyO5D",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
