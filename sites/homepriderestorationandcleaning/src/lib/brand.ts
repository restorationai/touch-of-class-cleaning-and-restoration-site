// Brand config — hydrated at scaffold time by build_site.py from
// plan-input.json and the client record. All {{TOKENS}} are replaced
// by the scaffold step; this file should not be hand-edited after that.

export const brand = {
  slug: "homepriderestorationandcleaning",
  displayName: "Home Pride Restoration and Cleaning",
  shortName: "Home Pride Restoration and Cleaning",
  legalName: "Home Pride Restoration and Cleaning",
  domain: "homepriderestorationandcleaning.com",
  canonicalUrl: "https://homepriderestorationandcleaning.com",
  phone: "(801) 995-2437",
  phoneRaw: "+18019952437",
  email: "homepriderestorationut@gmail.com",
  hours: "24/7",
  foundedYear: "1997",
  primaryCity: "Saratoga Springs",
  primaryState: "UT",
  streetAddress: "",
  postalCode: "",
  lat: "",
  lng: "",
  placeId: "",
  googleCid: "",
  imagesBase: "https://images.homepriderestorationandcleaning.com",
  googleMapsApiKey: "AIzaSyDrYnSuDu-hFvKHEcQCjwb-zsMebInPneU",
  logoUrl: "https://images.homepriderestorationandcleaning.com/brand/logo.png",
  licenseNumbers: ["RC-25-0737"] as string[],
  licenseAuthority: "",
  licenseType: "",
  certifications: ["IICRC Certified"] as string[],
  sameAsUrls: [] as string[],
  gbpRatingValue: "",
  gbpReviewCount: "",
  tagline: "24/7 restoration services in Saratoga Springs, UT.",
  ctaLabel: "24/7 Emergency Hotline",
} as const;

export const entityId = `${brand.canonicalUrl}/#identity`;
