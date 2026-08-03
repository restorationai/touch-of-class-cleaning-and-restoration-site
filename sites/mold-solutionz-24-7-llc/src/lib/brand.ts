// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "mold-solutionz-24-7-llc",
  displayName: "Mold Solutionz 24/7",
  shortName: "Mold Solutionz",
  legalName: "Mold Solutionz 24/7 LLC",
  domain: "",
  canonicalUrl: "https://None",
  phone: "(714) 409-4758",
  phoneRaw: "+17144094758",
  email: "moldsolutionz247@gmail.com",
  hours: "24/7",
  foundedYear: "2017",
  primaryCity: "Cerritos",
  primaryState: "CA",
  streetAddress: "18869 Jeffrey Avenue",
  postalCode: "90703",
  lat: "33.8644291",
  lng: "-118.0539323",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.None",
  googleMapsApiKey: "",
  // Analytics — set post-scaffold (scripts/analytics_set.py / create_ga4.py); no-op if empty
  ga4MeasurementId: "",
  clarityProjectId: "",
  logoUrl: "/images/logo.png",
  licenseNumbers: [] as string[],
  licenseAuthority: "",
  // State license-verification page — the footer links the license number here.
  licenseLookupUrl: "",
  licenseType: "",
  // Operator-confirmed "licensed & insured" attestation from plan-input.json —
  // lets the TrustStrip show the badge before a license number is on file.
  licensedInsuredAttested: false as boolean,
  certifications: ["IICRC WRT #70145645"] as string[],
  trustBadges: ["IICRC Certified", "MICRO Certified", "Serving Greater LA & Orange County Since 2017"] as string[],
  jobPhotos: [] as string[],
  sameAsUrls: [] as string[],
  // GBP rating fields — synced from the live Google Business Profile by
  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).
  gbpRatingValue: "5.0",
  gbpReviewCount: "62",
  gbpReviews: [
    { author: "Yolanda", rating: 5, text: "Andrea was wonderful to work with throughout our mold inspection. From the very beginning, she made us feel supported and reassured during a stressful situation. Her service was prompt, efficient, and professional. What really stood out was her availability. Andrea is always just a text or phone…", when: "July 2026" },
    { author: "Karla", rating: 5, text: "Andrea did an outstanding job! From the moment she arrived, she was professional, friendly, and extremely knowledgeable. She took the time to explain everything clearly, answered all of my questions, and made sure I understood the process every step of the way. Her attention to detail and…", when: "July 2026" },
    { author: "Monique", rating: 5, text: "I cannot recommend Mold Solutions 24/7 enough. Before reaching out to Andrea, I had been getting sick and couldn’t figure out why. I started noticing a little bit of mold in my home, and while searching for answers, I came across Andrea’s Instagram. What immediately stood out to me was how…", when: "June 2026" },
    { author: "Craig", rating: 5, text: "If you’re looking for a straightforward, Mold remediation company who does what they say when they say they’re gonna do it you’ve come to the right place. They are conscientious and work very hard to meet your needs to ensure a great outcome. Totally satisfied. Would not go anywhere else!!", when: "May 2026" },
    { author: "Peter", rating: 5, text: "The team did a great job with our remediation project. Professional service and great communication, both the on site team and project manager. I was impressed and would definitely recommend.", when: "May 2026" },
    { author: "Ahmed", rating: 5, text: "I hired a mold remediation company but observed some red flags and had concerns they didn’t do a thorough job. So I hired Mold Solutionz 24/7 to have a little peace of mind. The tester. Andrea, showed up to do testing within the time window provided. Andrea was very friendly and patient with me to…", when: "May 2026" },
  ] as { author: string; rating: number; text: string; when: string }[],
  tagline: "Got mold? We have the solution.",
  ctaLabel: "Talk to a Mold Specialist",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
