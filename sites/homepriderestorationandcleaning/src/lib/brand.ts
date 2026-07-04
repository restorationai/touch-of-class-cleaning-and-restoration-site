// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "homepriderestorationandcleaning",
  displayName: "Home Pride Restoration and Cleaning",
  shortName: "Home Pride Restoration and Cleaning",
  legalName: "Home Pride Restoration and Cleaning",
  domain: "homepriderestorationandcleaning.com",
  canonicalUrl: "https://homepriderestorationandcleaning.com",
  phone: "(801) 995-2437",
  phoneRaw: "+18019952437",
  email: "homepriderestorationut@gmail.com",
  hours: "24/7",
  foundedYear: "1997",
  primaryCity: "Saratoga Springs",
  primaryState: "UT",
  streetAddress: "",
  postalCode: "",
  lat: "",
  lng: "",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.homepriderestorationandcleaning.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set by scripts/analytics_set.py / create_ga4.py; no-op if empty
  ga4MeasurementId: "G-6X1L63FBE5",
  clarityProjectId: "xdojyl8enb",
  logoUrl: "https://images.homepriderestorationandcleaning.com/brand/logo.png",
  licenseNumbers: ["RC-25-0737"] as string[],
  licenseAuthority: "",
  licenseType: "",
  certifications: ["IICRC Certified"] as string[],
  trustBadges: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "5.0",
  gbpReviewCount: "30",
  gbpReviews: [
    { author: "Ben", rating: 5, text: "Curt was fast, responsive, and handled everything to restore our rental unit back to move-in ready condition at a fair price. Carpet cleaning, drywall repair, paint matching, trash removal, fixture repair etc. Thank you!", when: "June 2026" },
    { author: "Melissa", rating: 5, text: "Arrived on time and got the hazard waste removed. Thank you", when: "June 2026" },
    { author: "James", rating: 5, text: "Home Pride Restoration and Cleaning was incredibly fast and responsive when my pipe burst. The crew was professional, efficient, and did a thorough job with the water damage restoration and drying. I especially appreciated the emergency water extraction and the careful cleanup of the carpet. Highly…", when: "May 2026" },
    { author: "Linda", rating: 5, text: "The entire experience with Home Pride was very positive. Communication was prompt and they even touched base with me the morning of the appointment. I asked them to clean an area rug, a large off-white couch, and my dining chairs which have upholstered seats. All were looking pretty dirty. I'm…", when: "May 2026" },
    { author: "Rita", rating: 5, text: "Curt and Kim are fantastic, fast and very thorough @", when: "May 2026" },
    { author: "Megan", rating: 5, text: "They are quick, professional, affordable, and super friendly! They answered all my questions and my carpets look great. I would use them again!", when: "May 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Saratoga Springs, UT.",
  ctaLabel: "24/7 Emergency Hotline",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
