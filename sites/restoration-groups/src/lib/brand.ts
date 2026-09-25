// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "restoration-groups",
  displayName: "The Restoration Group",
  shortName: "The Restoration Group",
  legalName: "The Restoration Group",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "therestorationgroup.com",
  canonicalUrl: "https://therestorationgroup.com",
  phone: "(855) 650-7422",
  phoneRaw: "+18556507422",
  hideMobileHeaderCall: false,
  // A2P/SMS-registration legal entity. When set, the estimate forms render
  // the carrier-compliant consent checkbox naming this entity (exact wording
  // matters to reviewers — do not paraphrase). Empty = generic consent only.
  smsConsentEntity: "",
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "(908) 341-9611",
  trackingPhoneRaw: "+19083419611",
  email: "",
  hours: "24/7",
  foundedYear: "2021",
  primaryCity: "Kenilworth",
  primaryState: "NJ",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Kenilworth",
  addressState: "NJ",
  streetAddress: "500 S 31st St",
  postalCode: "07033",
  lat: "40.6749",
  lng: "-74.2957",
  placeId: "ChIJWYxcvlr6wokRi9KZOyNx400",
  googleCid: "8008820373441604497",
  imagesBase: "https://images.therestorationgroup.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-E4FC6VR918",
  clarityProjectId: "",
  logoUrl: "",
  licenseNumbers: [] as string[],
  licenseAuthority: "NJ Division of Consumer Affairs",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "NJ Licensed Home Improvement Contractor",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC Certified Firm #210213"] as string[],
  trustBadges: ["IICRC Certified Firm #210213", "NJ Licensed Home Improvement Contractor", "24/7 Emergency Response", "Serving NJ Since 2021"] as string[],
  jobPhotos: ["https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipNHvyh5n1_nipgaDhwOBaN0QYaHckW3D6VIEH1w.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipOWBs4M6wHJVxb1e3ngo746QWlqoocvYUde2R31.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipMT7reP5G43TQY7TvIsS7cnWAU0JCPGnJ6525UD.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipOvbRphL-4s4s2HBcHNSAUVJmUE73jUHrqHEFok.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipPzPSzIX5dvZD638-rIwRrEfldtlEourOh-_1sX.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipMOgD-xHr3gRbqOElwFL_XD-E4-UAiLrwaVFXfD.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipPL5EVHdJpU3Spb64wmmfbc02EGGMre4aT9srJT.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipMrmDh0WtXqYlP9kkfRmOS39YTziMN1YUyBKiN3.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipOKahQMSb_AIsG4VND5MWULWT9oPg6p1_jd-s1x.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipN-avWt91U36YGQd5Aak63HDTLZYhev-JZDQURP.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipOQRcPtLjaKR4TAQ2tLuszuAZ7H_O3PameFfmjW.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipM3t8PqpHPqbsIBvzjYkUFTosv4B9qGYghuwtF3.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipOhqRZauq7MaIUhzVAT5skyOS1ZcU__IQPa76iJ.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipO0AYq5poFmN0s-WUISaFChBa2dpXbrvuYzei1-.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipNSjXaF4r5J0GeqFFhqdH3kBmlZBjwVmJbpT2pV.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/trg-fleet-branded.png", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipNeLNoKbRcifiELTsqvkGvb7p-cok0wN6HUJ7Mo.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipOfOghShkNxRtPa1cSJ0f0jpbJqhLP7YeIcBQZA.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipPRez6Qrva30t-9iE-1LM7IpaTjGk7ftvLz9dWU.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipME94K9aDb-A-NWBOW8AN6afN8DXgYJHgtg_Pai.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipNVAgGhcPSXNcnaU_bTQMjhi0QuQR8H3_wIlGzn.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipMnOg28vyvrJA0RZiMhqvmGOZA7Z8oP0DvsVCXG.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipNpy1anxQVP8SiLUlxmRDEzHCEnFS9nLzl9A_6-.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1783527517866/job-photos/posted/gbp-AF1QipNGu2W0h_V6CRl9e1m4Z8jTkUEBEIu67qmgztVk.jpg"] as string[],
  sameAsUrls: ["https://www.google.com/maps?cid=8008820373441604497", "https://maps.google.com/maps?cid=5612453956771500683", "https://www.yelp.com/biz/the-restoration-group-highland-park", "https://www.houzz.com/professionals/general-contractors/north-jersey-restoration-group-pfvwus-pf~1892966983", "https://homeguide.com/nj/paterson/water-damage-restoration/the-restoration-group-vhnT_n48y"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.8",
  gbpReviewCount: "160",
  gbpReviews: [
    { author: "Dessy", rating: 5, text: "(Translated by Google) Excellent work. The staff were responsible, friendly, and above all, very clean. I was very satisfied and I recommend them 100%. (Original) Excelente trabajo.el personal responsables,amables y sobre todo muy limpios para trabajar .quedé satisfecha y lo recomiendo al 💯.", when: "September 2026" },
    { author: "Lisa", rating: 5, text: "They were very professional, and took care of all the water in my ceiling. It was alot of work, but they were very good at what they did.", when: "September 2026" },
    { author: "Peggy", rating: 5, text: "Teams were very prompt and respectful.. company responded quickly and kept in touch", when: "August 2026" },
    { author: "Jw", rating: 5, text: "The folks at TRG were professional, punctual, and pleasant to deal with. They did a great job addressing our issue and performed appropriate follow up to ensure our satisfaction.", when: "August 2026" },
    { author: "F.", rating: 5, text: "Prompt and professional work. Kept in contact thru out the process which was very important to me.", when: "July 2026" },
    { author: "Ryan", rating: 5, text: "Great customer service. I was kept well informed throughout the entire process. I received nothing but respect and sympathy from everyone I dealt with.", when: "July 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 water, fire & mold damage restoration across New Jersey.",
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
  homeAboutBlurb: "The Restoration Group serves Kenilworth and the surrounding NJ area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
