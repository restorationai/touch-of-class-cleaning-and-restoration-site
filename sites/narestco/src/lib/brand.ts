// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "narestco",
  displayName: "National Restoration Construction",
  shortName: "NARESTCO",
  legalName: "National Restoration Construction LLC",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "narestco.com",
  canonicalUrl: "https://narestco.com",
  phone: "(206) 883-0333",
  phoneRaw: "+12068830333",
  hideMobileHeaderCall: false,
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "(206) 737-0916",
  trackingPhoneRaw: "+12067370916",
  email: "info@narestco.com",
  hours: "24/7",
  foundedYear: "2004",
  primaryCity: "Federal Way",
  primaryState: "WA",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Federal Way",
  addressState: "WA",
  streetAddress: "1530 S Dash Point Rd",
  postalCode: "98003",
  lat: "47.337",
  lng: "-122.314",
  placeId: "ChIJ8URpSkf_UaURDg_hVb9wMrQ",
  googleCid: "12984564642744438542",
  imagesBase: "https://images.narestco.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-5N8L5D4Z3C",
  clarityProjectId: "xdoigoc8of",
  logoUrl: "https://images.narestco.com/brand/logo.png",
  licenseNumbers: ["NATIORC792M6"] as string[],
  licenseAuthority: "WA State Department of Labor & Industries",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://secure.lni.wa.gov/verify/",
  licenseType: "General Contractor Certificate of Registration",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: ["IICRC Certified", "BBB Accredited", "Lead-Safe Certified Firm", "EPA Certified", "ANSI Certified"] as string[],
  trustBadges: [] as string[],
  jobPhotos: ["https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipPEjDIjv4bW_TyEbkuF2wWzHLkj2HGXHKuY_Pp7.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipPnrhGdTek6fmIPO0fGM7twuMyqCfsXMmEQ5xsE.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipPjBjTW5b7cLtsNPPzmH-pBkR_5vQ7DQGF8nCAv.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipMPcftazJM4P16fDzoxERPoPEGoCYhvbxWs_t8o.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipOtB2WpaKJFczXQ-UeJeVKLKAKGvN2gu-TRWWNx.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipPIGx3KvAp9eXqhxb_C9ydwnT-vHOzBZHm4FxaZ.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipNWlOwwXXwxJAm3WnT-ipY1sO-1c93MskMQjevS.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipMUmNMsVgargkHOUdkAJLMy2Pi6_dGE9anSBy-1.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipOT7u_ynheByXhjMxP9k3Ai0IoYz4Ho5FzkqsL2.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipMPNlGzhqAjQTejl9v2dTTTbiDsen9Dz3SP-mOv.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipO_TL4ODwIojlGnmtZ2L7Dm-_Q7-p6Q0FBR7Zfn.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipOESvqiHosCjRlemnmtBtMkZDtZ3ZaTiFFhDoxy.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipNkO3byS03s3nTlz57xHcF_Ugiwy5jsW48CcWZM.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipOZ5Sn2VN5ye8UwFq15SNFpH_SNsKiF_hzAI1tB.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipPqCnb3jnvWwA2KovMOczqOpZ2uL4rhHxMBZl-C.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipOTMgfRxTjqIl1xIOX2_WWkRytlTvrlmh7wXzGr.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipMGPX8Fq7vzLfszA_OIGQ7DabYCP2iJKUrASU9-.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipNnTfi0SAHwnEtvgY1ME6voTNthcPidEPDUKzIG.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipOk72fw78mW014OPQRlQLXn9pR246DHy0isdjAp.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipMJz3NHxcFfd5K33UQQDWtmNrjXor2OrpiQUMIr.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipP52gNDKgm6SmBYIaUr60zJEpk_jzhx966YBwoR.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipMTqNMy95RRfX2n185yStdt2FDrKYJd1eygV1ZC.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipO84Z3A_OoABvCt2wcYlhLt-GPxrmtwF4HD_ZEq.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1771290587387/job-photos/posted/gbp-AF1QipPRNqBFvbiXmvPha18bawfSwQZJOXdUPC3nWhqd.jpg"] as string[],
  sameAsUrls: ["https://www.google.com/maps?cid=12984564642744438542", "https://www.facebook.com/narestco", "https://www.instagram.com/narestco", "https://www.tiktok.com/@narestco", "https://twitter.com/narestco", "https://www.yelp.com/biz/national-restoration-construction-federal-way-3", "https://www.bbb.org/us/wa/federal-way/profile/fire-water-damage-restoration/national-restoration-construction-llc-1296-1000167537", "https://www.angi.com/companylist/us/wa/federal-way/national-restoration-construction-llc-reviews-1.htm", "https://www.homeadvisor.com/rated.NationalRestoration.118159482.html", "https://www.thumbtack.com/wa/federal-way/water-damage/national-restoration-construction/service/515297469726908420", "https://www.bing.com/maps?ss=ypid.YN5DEE2A36AED87F3B", "https://www.houzz.com/professionals/environmental-services-and-restoration/national-restoration-construction-pfvwus-pf~819253451", "https://homeguide.com/wa/federal-way/water-damage-restoration/national-restoration-construction-A8aisT6gf"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "",
  gbpReviewCount: "",
  gbpReviews: [] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Federal Way, WA.",
  ctaLabel: "24/7 Emergency Line",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  // vertical gates layout too: restoration is call-first, so the homepage
  // hero renders NO estimate form there (Santino 2026-09-11).
  vertical: "restoration",
  tradeNoun: "restoration",
  specialistPhrase: "Damage Restoration Specialists",
  announcementSuffix: "24/7 Emergency Response",
  homeAboutBlurb: "National Restoration Construction serves Federal Way and the surrounding WA area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
