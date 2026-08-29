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
  // Sitewide call-tracking display number (DNI — see BaseLayout).
  // Schema/NAP keep the canonical number above.
  trackingPhone: "(385) 438-3364",
  trackingPhoneRaw: "+13854383364",
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
  // Operator-confirmed "licensed & insured" attestation (plan-input.json
  // brand.licensed_insured_attested) — gates the TrustStrip badge when no
  // license number is on file yet.
  licensedInsuredAttested: false,
  certifications: ["IICRC Certified"] as string[],
  trustBadges: [] as string[],
  sameAsUrls: ["https://maps.google.com/maps?cid=6708102771096353237", "https://www.yelp.com/biz/home-pride-restoration-and-cleaning-saratoga-springs", "https://www.facebook.com/Homepride247/", "https://www.bing.com/maps?ss=ypid.YN9C857D065FF121E9"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "5.0",
  gbpReviewCount: "36",
  gbpReviews: [
    { author: "B", rating: 5, text: "He did an amazing job! My stairs were so bad and they looked brand new when he got done!", when: "August 2026" },
    { author: "Kristina", rating: 5, text: "Curt was soooo amazing! Fast and efficient! Very sweet and kind! Would use again if we weren’t moving out of state!!!!!", when: "August 2026" },
    { author: "Joe", rating: 5, text: "I called Home Pride Restoration and Cleaning after a burst pipe and was impressed by how quickly they responded. The team was professional, efficient, and very thorough—everything from emergency water extraction to carpet water extraction was handled smoothly. I appreciate the fast service and will…", when: "July 2026" },
    { author: "Amy", rating: 5, text: "I was nervous at first, but the staff made me feel comfortable. They arrived quickly for emergency water removal and had the water out of my home in no time. I really appreciated their fast response and professional service.", when: "July 2026" },
    { author: "Shannon", rating: 5, text: "I’ve hired Curt multiple times for carpet cleaning and once for a couch cleaning and he does a great job every time! Affordable, friendly, reliable. 10/10 recommend!", when: "June 2026" },
    { author: "Ben", rating: 5, text: "Curt was fast, responsive, and handled everything to restore our rental unit back to move-in ready condition at a fair price. Carpet cleaning, drywall repair, paint matching, trash removal, fixture repair etc. Thank you!", when: "June 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Saratoga Springs, UT.",
  ctaLabel: "24/7 Emergency Hotline",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
