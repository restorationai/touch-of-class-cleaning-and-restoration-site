// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "mcc-restoration",
  displayName: "MCC Restoration and Contracting Services",
  shortName: "MCC Restoration",
  legalName: "MCC Restoration and Contracting Services",
  domain: "mccrestoration.com",
  canonicalUrl: "https://mccrestoration.com",
  phone: "(682) 772-9123",
  phoneRaw: "+16827729123",
  // Sitewide call-tracking display number (DNI — see BaseLayout).
  // Schema/NAP keep the canonical number above.
  trackingPhone: "(682) 281-4632",
  trackingPhoneRaw: "+16822814632",
  email: "",
  hours: "",
  foundedYear: "",
  primaryCity: "Duncanville",
  primaryState: "TX",
  streetAddress: "",
  postalCode: "",
  lat: "",
  lng: "",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.mccrestoration.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-G4M427GZWR",
  clarityProjectId: "",
  logoUrl: "/images/logo.webp", // clients/mcc-restoration/Logo.png (chrome MCC + green/blue lockup). Local file for preview; move to images.mccrestoration.com/brand/logo.webp at production cutover once the zone + R2 bucket exist.
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: [] as string[],
  trustBadges: [] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.facebook.com/masterscarpetcleaningtx/", "https://homeguide.com/tx/duncanville/water-damage-restoration/mcc-restoration-and-contracting-services-aysz69Oct"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "Restoration and contracting services in Duncanville, TX.", // no 24/7 — hours not attested by client
  ctaLabel: "Call For Emergency Service",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
