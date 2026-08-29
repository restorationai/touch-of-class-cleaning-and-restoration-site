// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "davis-construction",
  displayName: "Davis Construction Contractors",
  shortName: "Davis Construction Contractors",
  legalName: "Davis Construction Inc.",
  domain: "davisconstructioncontractors.com",
  canonicalUrl: "https://davisconstructioncontractors.com",
  phone: "(256) 771-0326",
  phoneRaw: "+12567710326",
  // Sitewide call-tracking display number (DNI — see BaseLayout).
  // Schema/NAP keep the canonical number above.
  trackingPhone: "(256) 257-0752",
  trackingPhoneRaw: "+12562570752",
  email: "davisheath09@gmail.com",
  hours: "Monday–Friday, 8:00 AM – 5:00 PM",
  foundedYear: "2008",
  primaryCity: "Madison",
  primaryState: "AL",
  streetAddress: "",
  postalCode: "",
  lat: "",
  lng: "",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.davisconstructioncontractors.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set by scripts/analytics_set.py / create_ga4.py; no-op if empty
  ga4MeasurementId: "G-BRL1Q2KTGV",
  clarityProjectId: "xdoje59wr1",
  logoUrl: "/images/logo.webp",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation (plan-input.json
  // brand.licensed_insured_attested) — gates the TrustStrip badge when no
  // license number is on file yet.
  licensedInsuredAttested: false,
  certifications: [] as string[],
  // Operator-attested 2026-07-04 (Santino): family business (two brothers),
  // licensed & insured — license number pending; add it to licenseNumbers when
  // received so footer/llms.txt can cite it.
  trustBadges: ["Family-Owned & Operated", "Licensed & Insured", "Locally Owned", "Since 2008"] as string[],
  sameAsUrls: ["https://pro.porch.com/huntsville-al/remodeling-contractors/davis-remodeling-164537953/pp", "https://homeguide.com/al/madison/water-damage-restoration/davis-construction-contractors-IqEW3eGSB"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  // Empty for this client: no GBP profile row yet, so no AggregateRating is
  // published and the ReviewsStrip renders nothing.
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "Construction and restoration services in Madison, AL.",
  ctaLabel: "Call Today — Free Estimates",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
