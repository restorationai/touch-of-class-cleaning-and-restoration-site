// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "rachelle-elliston",
  displayName: "Desert Valley Contracting Inc ",
  shortName: "Desert Valley Contracting Inc ",
  legalName: "Desert Valley Contracting Inc",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "Desert Valley Restoration-24/7 Emergency Plumbing, Water and Fire Damage Restoration",
  domain: "desertvalleycontracting.net",
  canonicalUrl: "https://desertvalleycontracting.net",
  phone: "(702) 633-5033",
  phoneRaw: "+17026335033",
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "(725) 500-0975",
  trackingPhoneRaw: "+17255000975",
  email: "relliston@desertvalleyco.com",
  hours: "24/7",
  foundedYear: "2000",
  primaryCity: "North Las Vegas",
  primaryState: "NV",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "North Las Vegas",
  addressState: "NV",
  streetAddress: "3808 N Octagon Rd",
  postalCode: "89030",
  lat: "36.2005191",
  lng: "-115.1214745",
  placeId: "ChIJHe5ukQHCyIARitorWulYy8U",
  googleCid: "",
  imagesBase: "https://images.desertvalleycontracting.net",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: ["0072652-B & B6"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://www.nvcontractorsboard.com/",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC CERTIFIED FIRM", "IICRC AMRT (MOLD)", "OSHA TRAINED", "IICRC FSRT (FIRE & SMOKE)", "IICRC WRT (WATER)", "IICRC ASD (STRUCTURAL DRYING)", "EPA LEAD-SAFE CERTIFIED"] as string[],
  trustBadges: ["IICRC Certified Firm", "Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.instagram.com/desertvalleycontractinginc/", "https://www.facebook.com/DesertValleyContractor/", "https://www.linkedin.com/company/desert-valley-contracting-inc.", "https://maps.google.com/maps?cid=14252583205007514250", "https://www.yelp.com/biz/desert-valley-contracting-north-las-vegas-3", "https://www.bbb.org/us/nv/north-las-vegas/profile/fire-water-damage-restoration/desert-valley-contracting-inc-1086-78265"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.3",
  gbpReviewCount: "95",
  gbpReviews: [
    { author: "M", rating: 5, text: "Juan and his crew were exceptional in everything they did. Very professional, knowledgeable and hard working. Juan always answered all my questions in a very friendly and helpful manner.", when: "July 2026" },
    { author: "Deborah", rating: 5, text: "Very professional. THe crew is amazing", when: "June 2026" },
    { author: "Jeff", rating: 5, text: "Ended up with a leak from the master shower upstairs. Contacted my insurance who recommended DVC. Luanna at DVC sent out Yesenia and Jesus to assess the damage. These two were outstanding! They assessed everything, made an exploratory cut in the ceiling, informed me of everything they were doing…", when: "May 2026" },
    { author: "June", rating: 5, text: "Our master bathroom needed a full upgrade, and this company handled everything from demolition to final fixtures. They installed a walk-in shower, new vanity, and updated tile flooring. The project took about ten days, which was faster than expected. What I appreciated most was their attention to…", when: "May 2026" },
    { author: "Jacob", rating: 5, text: "About a week ago, I unfortunately had a flood in my two-story home while I was out of town. I was extremely stressed not having anyone available to check on my property. I reached out to Desert Valley Contracting through a close friend’s referral, and I’m so glad I did. They responded quickly…", when: "April 2026" },
    { author: "Pamela", rating: 5, text: "My name is Pamela Chavez, and I hired this company to do my bathroom.... they did an amazing job, they made sure to let me know exactly what they are doing, and made sure it was closed off properly.... if you have any leaks, damage, or anything that needs ro be done, call these guys... they were…", when: "March 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in North Las Vegas, NV.",
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
  homeAboutBlurb: "Desert Valley Contracting Inc  serves North Las Vegas and the surrounding NV area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
