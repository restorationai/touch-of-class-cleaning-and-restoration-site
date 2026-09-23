// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "homepriderestorationandcleaning",
  displayName: "Home Pride Restoration and Cleaning",
  shortName: "Home Pride Restoration and Cleaning",
  legalName: "Home Pride Restoration and Cleaning",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "homepriderestorationandcleaning.com",
  canonicalUrl: "https://homepriderestorationandcleaning.com",
  phone: "(801) 995-2437",
  phoneRaw: "+18019952437",
  hideMobileHeaderCall: false,
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "(385) 438-3364",
  trackingPhoneRaw: "+13854383364",
  email: "homepriderestorationut@gmail.com",
  hours: "24/7",
  foundedYear: "1997",
  primaryCity: "Saratoga Springs",
  primaryState: "UT",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Saratoga Springs",
  addressState: "UT",
  streetAddress: "78 W Wildflower Dr",
  postalCode: "84045",
  lat: "40.31172",
  lng: "-111.89406",
  placeId: "ChIJGzr1iePDLCsR1fkC5O33F10",
  googleCid: "6708102771096353237",
  imagesBase: "https://images.homepriderestorationandcleaning.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-6X1L63FBE5",
  clarityProjectId: "xdojyl8enb",
  logoUrl: "/images/logo.png",
  licenseNumbers: ["RC-25-0737"] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://secure.utah.gov/llv/search/index.html",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: ["IICRC Certified"] as string[],
  trustBadges: [] as string[],
  jobPhotos: ["https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipPS3R_C5yx9wUnci1K0TkBy-UXo951gstBJBsE1.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipOfO9KUXGQn3yOvYv3dW79jmUXzveZgsW86pG35.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipMdli4M3U0k_wKR2-SQRLxsvf_XlhVPQ7nNvvvJ.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipP9zQplpO3jW29vHPcQzghJLtTvwfvdmq_EGzHh.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipPcQwvcSi_0r8xSJce179adGKw_6xwujuSrY52J.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipNqJUE1ImQT4QUKj_5U4D_QiUmbnWNjZRDiJPOl.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipMPAQoR0CW-laohE06GmKua3k6qVDJwOSUT0o4Y.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipOLFhME4fy2kAFH_ijSF7BCgDy48s2pZJLF6n8b.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipMkmBIH1Gdp-6vWyO07KsNJz1rzSlLUrAdW1oc2.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipPqyPkduS4wEahsrCISOdF88KQkQGI3AjxAOaDC.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipNyAO7WM0n28AF45GFUw-_0BE61qdYcLNwgUmWO.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipMBnNTYLWLebkDIqpMRK06x7dWqz0Hb4fTIfYJb.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipOXhw5Bajc-NqaTFqPSW-SYdyvrgn3o9V-rI3q4.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipNk7nf97wGwBbwLZ1hmgM81KZUrLLp4aho1AykH.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipPoh6MJ1dr0EIVcNrq-xJxOGfU2Q6_3UsJRwKn_.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipOafWfmhU7QtUG45i72nyuRa54zcggk3I5kfhWf.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipPsB4HutRZ2eCplQ5XuY_zx-TaEC7BbseRMoZOS.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipPW9k0VIEmym8LgNxBhkU0J7FkHXHJTb1jn09MP.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipNRtq6HJuOXL2nqqiU43eYzqspisyrd-hLYipSR.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipOz_5yd1bNIc1zu-fCxzLWtD4tEyUzhh439GN5t.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipPPA2J267IBwjAS7KiiK2OZxJEp8YjXnGLnuPhI.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipMyCmi-9Iisc7nzBHJCKcGxVWttwX6g_Oq4pgn5.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipM7Wr9UwJRfXL2-r-TZ5a1A-WWRgS5sCNnMpu_3.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1780333664867/job-photos/posted/gbp-AF1QipNoZDmW-w-Tqnqb9b_Rx8ekLf9V0UbuK8Fq8xrU.jpg"] as string[],
  sameAsUrls: ["https://maps.google.com/maps?cid=6708102771096353237", "https://www.yelp.com/biz/home-pride-restoration-and-cleaning-saratoga-springs", "https://www.facebook.com/Homepride247/", "https://www.bing.com/maps?ss=ypid.YN9C857D065FF121E9"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "5.0",
  gbpReviewCount: "36",
  gbpReviews: [
    { author: "B", rating: 5, text: "He did an amazing job! My stairs were so bad and they looked brand new when he got done!", when: "August 2026" },
    { author: "Kristina", rating: 5, text: "Curt was soooo amazing! Fast and efficient! Very sweet and kind! Would use again if we weren’t moving out of state!!!!!", when: "August 2026" },
    { author: "Joe", rating: 5, text: "I called Home Pride Restoration and Cleaning after a burst pipe and was impressed by how quickly they responded. The team was professional, efficient, and very thorough—everything from emergency water extraction to carpet water extraction was handled smoothly. I appreciate the fast service and will…", when: "July 2026" },
    { author: "Amy", rating: 5, text: "I was nervous at first, but the staff made me feel comfortable. They arrived quickly for emergency water removal and had the water out of my home in no time. I really appreciated their fast response and professional service.", when: "July 2026" },
    { author: "Shannon", rating: 5, text: "I’ve hired Curt multiple times for carpet cleaning and once for a couch cleaning and he does a great job every time! Affordable, friendly, reliable. 10/10 recommend!", when: "June 2026" },
    { author: "Ben", rating: 5, text: "Curt was fast, responsive, and handled everything to restore our rental unit back to move-in ready condition at a fair price. Carpet cleaning, drywall repair, paint matching, trash removal, fixture repair etc. Thank you!", when: "June 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Saratoga Springs, UT.",
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
  homeAboutBlurb: "Home Pride Restoration and Cleaning serves Saratoga Springs and the surrounding UT area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
