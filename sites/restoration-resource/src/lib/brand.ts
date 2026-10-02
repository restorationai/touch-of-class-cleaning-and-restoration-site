// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "restoration-resource",
  displayName: "Restoration Resource ",
  shortName: "Restoration Resource ",
  legalName: "Restoration Resource ",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "restorationresource365.com",
  canonicalUrl: "https://restorationresource365.com",
  phone: "+15095281166",
  phoneRaw: "+15095281166",
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
  trackingPhone: "(509) 461-8940",
  trackingPhoneRaw: "+15094618940",
  email: "logan@restorationresource365.com",
  hours: "24/7",
  foundedYear: "2022",
  primaryCity: "Pasco",
  primaryState: "WA",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Pasco",
  addressState: "WA",
  streetAddress: "3003 N Capital Ave Pasco",
  postalCode: "99301",
  lat: "46.2306739",
  lng: "-119.0921",
  placeId: "ChIJK2yX91k7z4YR5GrxBvlpClU",
  googleCid: "",
  imagesBase: "https://images.restorationresource365.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "https://images.restorationresource365.com/brand/logo.png",
  licenseNumbers: ["RESTORL764CE"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://secure.lni.wa.gov/verify/",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC CERTIFIED FIRM", "IICRC WRT (WATER)", "IICRC ASD (STRUCTURAL DRYING)", "IICRC AMRT (MOLD)", "IICRC FSRT (FIRE & SMOKE)"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.facebook.com/RestorationResource", "https://www.instagram.com/restorationresource/", "https://maps.google.com/maps?cid=6127826761275239140", "https://www.yelp.com/biz/restoration-resource-pasco"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "5.0",
  gbpReviewCount: "38",
  gbpReviews: [
    { author: "Raeanne", rating: 5, text: "I had a great experience working with this company, Logan in particular. I needed their services to fulfill a real estate contract obligation in Richland, Wa. They were professional, responsive, and timely throughout the entire process. The work was completed within a short timeframe, which was…", when: "September 2026" },
    { author: "Bobby", rating: 5, text: "Amazing company. Top tier work. Communication is A1. Pricing is transparent and as fair as you’d expect from a contractor. Highly recommend. You won’t be disappointed in your choice", when: "September 2026" },
    { author: "Dorothy", rating: 5, text: "I called Logan when I found mold and he showed up within 39 mins of my call. He started working on my issue right away. He was the only company willing to help me right away because the mold was effecting my allergies bad. Thank you Logan for helping me quickly. I would recommend this company!!", when: "August 2026" },
    { author: "Bill", rating: 5, text: "Excellent service. Prompt and very 8nformstive. Logan was incredibly knowledable. He did not run a test becaude it wasnt needed which shows amazing integrity. Logan also taught me a lot about insurance as well. Plan on using his company again.", when: "August 2026" },
    { author: "Luz", rating: 5, text: "Logan did an excellent job very friendly and professional he did a thorough job and had to even write an inspection letter. Recommend 10/10!!", when: "July 2026" },
    { author: "Dallin", rating: 5, text: "Logan was amazing. He came out, did an in depth assessment and shared his professional opinion. He exemplifies what it means to be a business owner and is passionate about what he does. If we ever find Mold in our house again there’s no question of who to call.", when: "May 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Pasco, WA.",
  // optional custom insurance positioning line (Hero renders only when set)
  insuranceTrustLine: "",
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
  homeAboutBlurb: "Restoration Resource  serves Pasco and the surrounding WA area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
