// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "flood-fixers",
  displayName: "Flood Fixers",
  shortName: "Flood Fixers",
  legalName: "Flood Fixers",
  domain: "flood-fixers.com",
  canonicalUrl: "https://flood-fixers.com",
  phone: "(855) 204-1124",
  phoneRaw: "+18552041124",
  email: "",
  hours: "24/7 Emergency Service",
  foundedYear: "",
  primaryCity: "San Diego",
  primaryState: "CA",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "San Marcos",
  addressState: "CA",
  streetAddress: "",
  postalCode: "",
  lat: "",
  lng: "",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.flood-fixers.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.webp",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation (plan-input.json
  // brand.licensed_insured_attested) — gates the TrustStrip badge when no
  // license number is on file yet.
  licensedInsuredAttested: true,
  // "EPA Lead-Safe Certified" is also on file (plan-input truth data); the
  // TrustStrip is operator-specced to 4 badges, so only IICRC renders there.
  certifications: ["IICRC Certified"] as string[],
  trustBadges: [] as string[],
  sameAsUrls: ["https://maps.google.com/maps?cid=831059838874778616", "https://www.yelp.com/biz/flood-fixers-san-diego", "https://www.facebook.com/100067690656701/", "https://www.bing.com/maps?ss=ypid.YN98B76BD2E3E0D8A0", "https://www.houzz.com/professionals/environmental-services-and-restoration/flood-fixers-pfvwus-pf~190107846"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  // Empty for this client: no GBP profile row yet, so no AggregateRating is
  // published and the ReviewsStrip renders nothing.
  gbpRatingValue: "5.0",
  gbpReviewCount: "9",
  gbpReviews: [
    { author: "Erik", rating: 5, text: "i'd like to leave a review based upon the exceptional work done in my home. Their services were completed on time, quality assurance after flooring was completed. Thank you", when: "May 2026" },
    { author: "Ian", rating: 5, text: "Courteous and respectful crew with excellent attention to detail.", when: "May 2026" },
    { author: "Nigel", rating: 5, text: "Flood Fixers completely saved my home and my sanity. I experienced an extreme upstairs bathroom leak that could have caused catastrophic damage, but their team responded immediately. They arrived fast, assessed the situation with total professionalism, and went straight to work.The technicians were…", when: "May 2026" },
    { author: "Maryann", rating: 5, text: "Great work by the Flood Fixer team. Highly recommend.", when: "May 2026" },
    { author: "Jeffrey", rating: 5, text: "Absolutely blown away by Flood Fixers! ⭐⭐⭐⭐⭐ They swooped in after our disaster like a team of caffeinated superheroes and brought a level of creative flair I didn’t even know my home needed. The floors? Let’s just say they now have a one-of-a-kind, “you’ll never see this anywhere else” finish. The…", when: "May 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in San Diego, CA.",
  ctaLabel: "24/7 Emergency Hotline",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
