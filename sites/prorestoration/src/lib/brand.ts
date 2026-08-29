// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "prorestoration",
  displayName: "ProRestoration Services",
  shortName: "ProRestoration",
  legalName: "ProRestoration Services Inc.",
  domain: "prorestorationca.com",
  canonicalUrl: "https://prorestorationca.com",
  phone: "(661) 393-9306",
  phoneRaw: "+16613939306",
  // Sitewide call-tracking display number (DNI — see BaseLayout).
  // Schema/NAP keep the canonical number above.
  trackingPhone: "(661) 438-0258",
  trackingPhoneRaw: "+16614380258",
  email: "",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Bakersfield",
  primaryState: "CA",
  streetAddress: "3556 Bowman Ct Suite B",
  postalCode: "93308",
  lat: "",
  lng: "",
  placeId: "ChIJH_3NClVC6oAR3mxvd5xofrQ",
  googleCid: "13005947795120549086",
  imagesBase: "https://images.prorestorationca.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.svg", // preview: switch to images.prorestorationca.com/brand/... at production cutover
  licenseNumbers: ["960566"] as string[],
  licenseAuthority: "Contractors State License Board (CSLB), State of California",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC Certified", "EPA Lead-Safe Certified Firm", "BBB Accredited"] as string[],
  trustBadges: [] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.google.com/maps?cid=13005947795120549086", "https://www.yelp.com/biz/prorestoration-services-bakersfield-3", "https://www.homeadvisor.com/rated.ProRestorationServices.16241626.html", "https://www.facebook.com/prorestorationservices/"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.8",
  gbpReviewCount: "105",
  gbpReviews: [
    { author: "Luis", rating: 5, text: "Friendly, knowledgeable and reliable person", when: "July 2026" },
    { author: "Aubrey", rating: 5, text: "Was in contact with Jack, he was able to answer all my questions regarding restoration. Very pleased with his service! such a great company to work with. Thank you Jack!", when: "June 2026" },
    { author: "Pedro", rating: 5, text: "I am writing to express my sincere gratitude for the exceptional service your team has provided. I have been a customer since the beginning of 2023, when I first found your company through a Google search following water damage in my home. I was very happy with the service and the quick turnaround…", when: "June 2026" },
    { author: "Emily", rating: 5, text: "Wonderful staff. Understanding and helpful. We appreciate your team!", when: "May 2026" },
    { author: "Sheila", rating: 5, text: "Carlos just put up the drywall in my kitchen after water damage. He did a very good job. He covered everything and blocked off the kitchen when he did some sanding. I’m very happy with the job he did. The first guys that came to remove the damaged drywall were terrible. They didn’t cover my stove…", when: "May 2026" },
    { author: "Ed", rating: 5, text: "Fantastic Work. Great People. Highly recommend.", when: "April 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Bakersfield, CA.",
  ctaLabel: "24/7 Emergency Hotline",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
