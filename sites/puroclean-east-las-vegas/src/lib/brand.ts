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
  phoneRaw: "+117025513040",
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
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "https://images.purocleaneastlasvegas.com/brand/logo.png",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: [] as string[],
  trustBadges: [] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.8",
  gbpReviewCount: "17",
  gbpReviews: [
    { author: "Tracy", rating: 5, text: "Lino was amazing, walking us step by step through the whole process", when: "June 2026" },
    { author: "Johanna", rating: 5, text: "Lino came out after a leak in my home. I cannot express how wonderful he was. At every step of the way he was knowledgable and reassuring. The process went much more smoothly than I expected. They have an extensive understanding of how to best manage these types of disasters that can happen. I am…", when: "May 2026" },
    { author: "Andrea", rating: 5, text: "Lino was absolutely exceptional! He has the highest level of integrity and work ethic. He handled a very delicate emotional situation with empathy and sincerity and he handled the clean up of my home with professionalism, care and attention to detail. I could not have asked for a better person to…", when: "May 2026" },
    { author: "Christina", rating: 5, text: "Awesome service!!! Very professional and very knowledgeable! 10 out of 10 would recommend!", when: "March 2026" },
    { author: "Patrick", rating: 5, text: "I hired Our clean to biohazard my trailer after a squatter was living in it while I storage. Lino was amazing. Super friendly, efficient, and thorough. He made the process easy. Would definitely recommend them.", when: "March 2026" },
    { author: "Royi", rating: 5, text: "Very responsive and honest. I had a leak and called the in the afternoon and received immediate response.", when: "November 2024" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Las Vegas, NV.",
  ctaLabel: "24/7 Emergency Line",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
