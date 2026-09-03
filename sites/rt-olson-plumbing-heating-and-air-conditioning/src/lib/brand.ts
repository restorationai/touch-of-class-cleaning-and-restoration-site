// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "rt-olson-plumbing-heating-and-air-conditioning",
  displayName: "RT Olson Plumbing, Heating and Air Conditioning",
  shortName: "RT Olson Plumbing, Heating and Air Conditioning",
  legalName: "RT Olson Plumbing, Heating and Air Conditioning",
  domain: "rtolsonplumbing.com",
  canonicalUrl: "https://rtolsonplumbing.com",
  phone: "(951) 344-5596",
  phoneRaw: "+19513445596",
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "",
  trackingPhoneRaw: "",
  email: "office@rtoplumbing.com",
  hours: "24/7",
  foundedYear: "2014",
  primaryCity: "Corona",
  primaryState: "CA",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Corona",
  addressState: "CA",
  streetAddress: "9064 Pulsar Ct. Suite J",
  postalCode: "92883",
  lat: "33.8752945",
  lng: "-117.566444",
  placeId: "ChIJrwzUDFa23IARkhGQxTSJGY8",
  googleCid: "",
  imagesBase: "https://images.rtolsonplumbing.com",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-D2RXDRWJ8D",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: ["997337"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: [] as string[],
  trustBadges: ["Licensed & Insured", "24/7 Emergency Service", "Locally Owned & Operated"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: ["https://www.yelp.com/biz/rt-olson-plumbing-heating-and-air-conditioning-corona-4", "https://www.bbb.org/us/ca/corona/profile/plumber/rt-olson-plumbing-heating-and-air-conditioning-1126-850038253", "https://www.angi.com/companylist/us/ca/corona/rt-olson-plumbing%2C-heating-and-air-conditioning-reviews-8562287.htm", "https://www.facebook.com/rtolsonplumbing/", "https://nextdoor.com/page/rt-olson-plumbing-corona-ca-1", "https://www.yellowpages.com/corona-ca/mip/rt-olson-plumbing-heating-and-air-conditioning-573197261"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "5.0",
  gbpReviewCount: "43",
  gbpReviews: [
    { author: "Dorien", rating: 5, text: "A1 SERVICE, great customer service and answered all my question and finished the job in a timely matter", when: "August 2026" },
    { author: "Franchesca", rating: 5, text: "Bob did an excellent job installing our new toilets and angle stops. Came on time. Quick. Thorough. Reasonably priced. Highly recommend for plumbing needs.", when: "February 2026" },
    { author: "Gifted", rating: 5, text: "Tim did an excellent job installing my thermostat! He was fast, professional, and very kind. He made sure everything was set up correctly and explained what I needed to know. I really appreciated how helpful and patient he was. Great service all around, I would definitely recommend him!", when: "February 2026" },
    { author: "Anne-Marie", rating: 5, text: "Scott and Tim were on time and provided great service. We signed up for the Annual Maintenance program to make sure that everything runs smoothly. We’ve used RT Olson before and have been very pleased with their service.", when: "November 2025" },
    { author: "Celia", rating: 5, text: "RT Olson Plumbing, Heating and Air Conditioning team of Tim,Scott,Tai and Mason did an amazing job for our home with a new comfortable central heat pump installation with new air ducting and attic insulation! We opted in to get an air purification system and a nice pleated 5 inch thick air…", when: "November 2025" },
    { author: "Soraya", rating: 5, text: "We had an amazing experience, Tim was incredibly professional, honest and kind throughout the entire process. He explained everything clearly and made sure we felt comfortable from start to finish. We would absolutely recommend Tim and the company to anyone looking for reliable and top quality…", when: "October 2025" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "Plumbing, heating & air services in Corona, CA.",
  ctaLabel: "24/7 Emergency Line",
  // Vertical trade-identity copy — resolved at scaffold time from
  // templates/{vertical}/vertical-tokens.json (see scripts/verticals.py).
  // Components must use these instead of hardcoding a trade phrase.
  tradeNoun: "plumbing",
  specialistPhrase: "Plumbing, Heating & Air Specialists",
  announcementSuffix: "24/7 Emergency Service",
  homeAboutBlurb: "RT Olson Plumbing, Heating and Air Conditioning serves Corona and the surrounding CA area with full-service plumbing, heating, and air conditioning. From emergency plumbing repairs, drain cleaning, and water heater service to complete AC and furnace installation, our technicians handle it all — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
