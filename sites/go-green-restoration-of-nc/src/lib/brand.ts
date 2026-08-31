// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "go-green-restoration-of-nc",
  displayName: "Go Green Restoration of NC",
  shortName: "Go Green Restoration",
  legalName: "Go Green Restoration of NC",
  domain: "gogreenrestorationofnc.com",
  canonicalUrl: "https://gogreenrestorationofnc.com",
  phone: "(919) 906-5473",
  phoneRaw: "+19199065473",
  // Sitewide call-tracking display number (DNI — see BaseLayout).
  // Schema/NAP keep the canonical number above.
  trackingPhone: "(919) 925-4635",
  trackingPhoneRaw: "+19199254635",
  email: "gogreenrestorationofnc@gmail.com",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Middlesex",
  primaryState: "NC",
  streetAddress: "10805 w. NC Hwy 97 ",
  postalCode: "27557",
  lat: "35.7888369",
  lng: "-78.2039124",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.None",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-FB7ZB4MR6V",
  clarityProjectId: "",
  // local file until the client's domain + R2 bucket exist; switch to
  // images.{domain}/brand/logo.png at production cutover
  logoUrl: "/images/logo.png",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: [] as string[],
  trustBadges: [] as string[],
  // Real job photos for the "Recent Work" gallery, curated from the client's
  // own uploads (branding/{cid}/job-photos) via the photo-manifest.json triage:
  // quality>=55, junk categories (unusable/graphic/logo/document) and flags
  // (screenshot/duplicate/blurry) excluded, ranked best-first. See ops-journal
  // 2026-08-09 — the raw newest-first supabase feed led with a black-screen
  // screenshot + a plain green-circle graphic, so this list is curated.
  jobPhotos: [
    "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1784905385326/job-photos/posted/gbp-AF1QipOhdTDQmKo9WpY345XanRSLxFP4kyjCZBolowDY.jpg",
    "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1784905385326/job-photos/fb-11.jpg",
    "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1784905385326/job-photos/fb-10.jpg",
    "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1784905385326/job-photos/fb-22.jpg",
    "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1784905385326/job-photos/fb-5.jpg",
    "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1784905385326/job-photos/posted/gbp-AF1QipPpuk8I5lPU4zV-bUk4hibXtzL_GNKogR_w-6nb.jpg",
    "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1784905385326/job-photos/fb-23.jpg",
    "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1784905385326/job-photos/fb-32.jpg",
    "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1784905385326/job-photos/fb-8.jpg",
    "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1784905385326/job-photos/posted/gbp-AF1QipNQs2xyRb6PFeIpZjRVuCngBdxF9NcJVK9x9d6t.jpg",
    "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1784905385326/job-photos/fb-14.jpg",
    "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1784905385326/job-photos/fb-49.jpg",
  ] as string[],
  sameAsUrls: ["https://maps.google.com/maps?cid=2026903256792048016", "https://www.bbb.org/us/nc/middlesex/profile/restoration-companies/go-green-restoration-of-nc-0593-90323300", "https://www.angi.com/companylist/us/nc/emit/go-green-restoration-of-nc-reviews-163326768.htm", "https://www.facebook.com/gogreenrestorationsofnc/", "https://pro.porch.com/wendell-nc/mold-removal-specialists/go-green-restoration-of-nc/pp", "https://homeguide.com/nc/wilson/water-damage-restoration/go-green-restoration-of-nc-J3JJ01_O8"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Middlesex, NC.",
  ctaLabel: "24/7 Emergency Line",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
