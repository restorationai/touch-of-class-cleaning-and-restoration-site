// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "flood-fixers",
  displayName: "Flood Fixers",
  shortName: "Flood Fixers",
  legalName: "Flood Fixers",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "flood-fixers.com",
  canonicalUrl: "https://flood-fixers.com",
  phone: "(855) 204-1124",
  phoneRaw: "+18552041124",
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
  trackingPhone: "(858) 371-5656",
  trackingPhoneRaw: "+18583715656",
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
  lat: "33.1434",
  lng: "-117.1661",
  placeId: "ChIJJ3gQpF913IAR-Hs5M4WEiAs",
  googleCid: "",
  imagesBase: "https://images.flood-fixers.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-BPB9R60M10",
  clarityProjectId: "",
  logoUrl: "/images/logo.webp", // brand/logo.png missing from R2 (404); pinned to local file
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC Certified", "EPA Lead-Safe Certified"] as string[],
  trustBadges: [] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://maps.google.com/maps?cid=831059838874778616", "https://www.yelp.com/biz/flood-fixers-san-diego", "https://www.facebook.com/100067690656701/", "https://www.bing.com/maps?ss=ypid.YN98B76BD2E3E0D8A0"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
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
  homeAboutBlurb: "Flood Fixers serves San Diego and the surrounding CA area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
