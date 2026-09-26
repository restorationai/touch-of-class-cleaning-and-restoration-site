// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "prorestoration",
  displayName: "ProRestoration Services",
  shortName: "ProRestoration",
  legalName: "ProRestoration Services Inc.",
  // Registered DBA / trade name — filled by rename_site_sync.py the moment
  // the state approves the client's DBA filing (empty until then). When set,
  // the footer carries the "[legal] doing business as [DBA]" line and schema
  // declares it as the business name, so Google/BrightLocal find the new
  // name corroborated on the site before and during the GBP rename.
  dbaName: "",
  domain: "prorestorationca.com",
  canonicalUrl: "https://prorestorationca.com",
  phone: "(661) 393-9306",
  phoneRaw: "+16613939306",
  hideMobileHeaderCall: false,
  // Sitewide call-tracking number (2026-08-24). When BOTH fields are set,
  // a tiny inline script in BaseLayout swaps every visible phone mention
  // and tel: link to this number AFTER the page renders. The HTML source,
  // the JSON-LD in schema.ts, and anything crawlers/citation-checkers read
  // keep the canonical NAP number above — humans dial the tracked line,
  // Google sees consistent NAP. Empty = feature off (default at scaffold;
  // filled by the call-tracking provisioning step).
  trackingPhone: "(661) 438-0258",
  trackingPhoneRaw: "+16614380258",
  email: "",
  hours: "24/7",
  foundedYear: "",
  primaryCity: "Bakersfield",
  primaryState: "CA",
  // primaryCity/primaryState = the #1 MARKETING city (headlines, coverage
  // copy). addressCity/addressState = where the business PHYSICALLY is.
  // They are usually the same and often diverge (DISS: Farrell PA office,
  // Youngstown OH target) — only the address pair may go in a PostalAddress.
  addressCity: "Bakersfield",
  addressState: "CA",
  streetAddress: "3556 Bowman Ct Suite B",
  postalCode: "93308",
  lat: "35.392",
  lng: "-119.09",
  placeId: "ChIJH_3NClVC6oAR3mxvd5xofrQ",
  googleCid: "13005947795120549086",
  imagesBase: "https://images.prorestorationca.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "G-LQE0DXHG08",
  clarityProjectId: "",
  logoUrl: "https://images.prorestorationca.com/brand/logo.png",
  licenseNumbers: ["960566"] as string[],
  licenseAuthority: "Contractors State License Board (CSLB), State of California",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: true as boolean,
  certifications: ["IICRC Certified", "EPA Lead-Safe Certified Firm", "BBB Accredited"] as string[],
  trustBadges: [] as string[],
  jobPhotos: ["https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipMTPJheP1ZRACl9CtTu9AJnHntUzAsm-8PTWpCp.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipO3fH2DWkiTVtDCuGBHzRoufqdx00espLd2Ao_P.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipOyXAybBMKYPVN2pOClJFsoPvXnlYwVGaTXlycD.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipMXOTn_bP9dZrXhqH_qanCRN98GpuQFVLrm8Bi9.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipMq9HViRQxomIpQGadn-J1bcC6sxX3XYebDpDLl.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipNO7mvccwXvWMGERzpqVXDmL5_RGabS1WILYe_a.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipNPwIAkBxmo6eigMkPx-MsctOSQa_6j8SMG-Trp.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipNKwqONuVxVB_nZxN90Gtmp_d6QpKwoYUssu-QA.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipMRryRK00zV-vMQ61f0Kl12Q8HD3-WpgFaQ3T1R.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipPa0DSRmvQPjJRBR0YgRrM2Weo_QXy_lFerhOIz.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipMy6tuyXz8882xKi6iECA4r8I94oR-FcAKzhuEa.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipPx4rlc4ZYeE-JeFsEGdGh4NphnIrbLuGSX52Th.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipNvaOP8UBH_Jzrf00YBhHZaJLBsXL_AcXkmu7i3.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipN7eHyPhukzuuZo7zLdujioeqtGZEG30XJFrJr_.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipN7EVmpLxdla2Q_qtqGaqs4A_XwLofvyVPpHykC.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipNLqRCQUCZ52U5aQPp_mX3Tw6wb-PYKg5HjHLly.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipOT8nBjqwKmhukNYo76qwlOMKV1Z2h2wZlF273z.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipN85zzY6pYZ6YtRW57kTVcyyNP2c-2Fmxipgd0N.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipMB4h6p2U4KxRn-BWFZzq-r0SmFLypzGgpQDOcE.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipOBiB4GL1hHOwAlbJUO03sKOtpKRdN1m4Z55pcs.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipOm9HSCrQh0g5pUYJ3b1gOhFjkXGbgEIwfG61Ml.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipMuewsA98uRBBZtz89WHRVVA2ZbuBcRfHISkz3S.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipMrEMG4XeoTg8WFQ8VPMpXEfCy8wMBiJvb1UBsN.jpg", "https://nyscciinkhlutvqkgyvq.supabase.co/storage/v1/object/public/branding/CO-1779551010975/job-photos/posted/gbp-AF1QipMBgvxF91ojQAwYsZ2putnjwvCWkNHCQ42zVl85.jpg"] as string[],
  sameAsUrls: ["https://www.google.com/maps?cid=13005947795120549086", "https://www.facebook.com/prorestorationservices", "https://www.yelp.com/biz/prorestoration-services-bakersfield-3", "https://www.homeadvisor.com/rated.ProRestorationServices.16241626.html", "https://www.bing.com/maps?ss=ypid.YN415B85C2894CF025"] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "4.8",
  gbpReviewCount: "115",
  gbpReviews: [
    { author: "Angela", rating: 5, text: "Our house flood on Christmas Eve, I called them first thing the morning after Christmas and they showed up within 2 hours and got to work. It took several days to get things cleaned up and dried out. Jack (the owner) stopped by everyday to make sure things were being taken care of. They did a great…", when: "September 2026" },
    { author: "David", rating: 5, text: "Great service, great communication", when: "September 2026" },
    { author: "Francisca", rating: 5, text: "Due to being a homeowners insurance claim, Pro Restoration responded as quickly as they could. Once everything was approved, this team did their best to offer a great price with just as much attention to detail at getting the job completed.", when: "September 2026" },
    { author: "Carol", rating: 4, text: "Showed up on time & great service & very friendly. I would certainly used them again", when: "September 2026" },
    { author: "Kim", rating: 5, text: "Noticed a leak at 6:00 pm on a Friday. ProRestoration came out immediately and stayed until well after midnight to make sure all the damaged drywall was removed. They were professional and courteous.", when: "September 2026" },
    { author: "Aubrey", rating: 5, text: "Was in contact with Jack, he was able to answer all my questions regarding restoration. Very pleased with his service! such a great company to work with. Thank you Jack!", when: "June 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "24/7 restoration services in Bakersfield, CA.",
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
  homeAboutBlurb: "ProRestoration Services serves Bakersfield and the surrounding CA area with professional damage restoration for homes and businesses. From the first emergency call to the final walkthrough, our team manages the entire recovery — and we answer the phone 24/7, so help is on the way the moment something goes wrong.",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
