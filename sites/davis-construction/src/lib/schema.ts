// JSON-LD schema renderer. Reads schema-stub names from page frontmatter,
// hydrates them with brand + page context, returns one JSON-LD object per stub.
// Skill 3 substitutes the actual schema stubs at scaffold time; this file is
// the runtime view that Astro renders.

import { brand, entityId } from "./brand";

export type PageSchemaContext = {
  archetype: string;
  url: string;
  title: string;
  meta_description: string;
  hero_image_url?: string;
  faq?: { question: string; answer: string }[];
  breadcrumb?: { name: string; url?: string }[];
  service_display?: string;
  city?: string;
  state?: string;
  post_published_at?: string;
  post_updated_at?: string;
  primary_service_display?: string;
  youtube_id?: string;
  video_transcript?: string;
  // City×service page extras (competitor-teardown schema upgrades)
  dispatch_sentence?: string;
  date_modified?: string;
};

const safe = (v: unknown) => (v == null || v === "" ? undefined : v);

// 24/7 gate — same brand.hours regex as the Header announcement bar. Only 24/7
// restoration brands get the EmergencyService typing; scheduled-hours trades
// (e.g. construction) stay plain LocalBusiness.
const IS_247 = /24\s*[\/x-]?\s*7|24 ?hours/i.test(String(brand.hours || ""));

function localBusiness(ctx: PageSchemaContext) {
  // City×service pages get the teardown upgrades: EmergencyService typing
  // (24/7 brands only), the page city as areaServed, the quotable dispatch
  // sentence in the description, and dateModified freshness from the page's
  // generated_at frontmatter (fallback: build date).
  const isCityService = ctx.archetype === "service-area-service" && !!ctx.city;
  return {
    "@context": "https://schema.org",
    "@type": isCityService && IS_247 ? ["LocalBusiness", "EmergencyService"] : "LocalBusiness",
    "@id": entityId,
    name: brand.displayName,
    legalName: brand.legalName,
    alternateName: brand.shortName,
    url: brand.canonicalUrl,
    telephone: brand.phoneRaw,
    email: brand.email,
    image: brand.logoUrl,
    logo: brand.logoUrl,
    priceRange: "$$",
    address: {
      "@type": "PostalAddress",
      streetAddress: brand.streetAddress,
      addressLocality: brand.primaryCity,
      addressRegion: brand.primaryState,
      postalCode: brand.postalCode,
      addressCountry: "US",
    },
    geo: {
      "@type": "GeoCoordinates",
      latitude: brand.lat,
      longitude: brand.lng,
    },
    openingHoursSpecification: {
      "@type": "OpeningHoursSpecification",
      dayOfWeek: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
      opens: "00:00",
      closes: "23:59",
    },
    sameAs: brand.sameAsUrls,
    foundingDate: brand.foundedYear,
    // AggregateRating — values come straight from the live Google Business Profile,
    // synced into brand.ts by scripts/sync_brand_reviews.py (never hand-edited; we
    // publish REAL ratings only). Emitted ONLY when both gbpRatingValue and
    // gbpReviewCount are present — sites without a GBP rating get no rating markup.
    aggregateRating: safe(brand.gbpRatingValue) && safe(brand.gbpReviewCount)
      ? {
          "@type": "AggregateRating",
          ratingValue: brand.gbpRatingValue,
          reviewCount: brand.gbpReviewCount,
          bestRating: "5",
          worstRating: "1",
        }
      : undefined,
    ...(isCityService
      ? {
          areaServed: { "@type": "City", name: ctx.city },
          // The description is EXACTLY the quotable dispatch sentence so the
          // schema repeats the on-page claim verbatim (see ~/lib/dispatch —
          // data-gated, never invented). Deliberately not meta_description:
          // plan-generated meta copy can carry claims the brand data doesn't back.
          description: safe(ctx.dispatch_sentence) ?? safe(ctx.meta_description),
          dateModified: String(ctx.date_modified || new Date().toISOString()).slice(0, 10),
        }
      : {}),
  };
}

function organization() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${brand.canonicalUrl}/#organization`,
    name: brand.legalName,
    alternateName: brand.shortName,
    url: brand.canonicalUrl,
    logo: { "@type": "ImageObject", url: brand.logoUrl },
    telephone: brand.phoneRaw,
    email: brand.email,
    foundingDate: brand.foundedYear,
    sameAs: brand.sameAsUrls,
  };
}

function website() {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": `${brand.canonicalUrl}/#website`,
    url: brand.canonicalUrl,
    name: brand.displayName,
    alternateName: brand.shortName,
    description: brand.tagline,
    publisher: { "@id": `${brand.canonicalUrl}/#organization` },
    inLanguage: "en-US",
  };
}

function service(ctx: PageSchemaContext) {
  if (!ctx.service_display) return undefined;
  return {
    "@context": "https://schema.org",
    "@type": "Service",
    serviceType: ctx.service_display,
    name: ctx.city ? `${ctx.service_display} in ${ctx.city}` : ctx.service_display,
    provider: { "@id": entityId },
    areaServed: ctx.city
      ? { "@type": "City", name: ctx.city, addressRegion: ctx.state, addressCountry: "US" }
      : { "@type": "AdministrativeArea", name: brand.primaryState },
    url: `${brand.canonicalUrl}${ctx.url}`,
    description: ctx.meta_description,
  };
}

function blogPosting(ctx: PageSchemaContext) {
  return {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: ctx.title,
    description: ctx.meta_description,
    image: ctx.hero_image_url,
    datePublished: ctx.post_published_at,
    dateModified: ctx.post_updated_at ?? ctx.post_published_at,
    author: { "@type": "Organization", name: brand.displayName, url: brand.canonicalUrl },
    publisher: {
      "@type": "Organization",
      "@id": `${brand.canonicalUrl}/#organization`,
      name: brand.displayName,
      logo: { "@type": "ImageObject", url: brand.logoUrl },
    },
    mainEntityOfPage: { "@type": "WebPage", "@id": `${brand.canonicalUrl}${ctx.url}` },
    articleSection: ctx.primary_service_display,
  };
}

function videoObject(ctx: PageSchemaContext) {
  if (!ctx.youtube_id) return undefined;
  return {
    "@context": "https://schema.org",
    "@type": "VideoObject",
    name: ctx.title,
    description: ctx.meta_description,
    thumbnailUrl: `https://img.youtube.com/vi/${ctx.youtube_id}/maxresdefault.jpg`,
    uploadDate: ctx.post_published_at,
    contentUrl: `https://www.youtube.com/watch?v=${ctx.youtube_id}`,
    embedUrl: `https://www.youtube.com/embed/${ctx.youtube_id}`,
    ...(ctx.video_transcript ? { transcript: ctx.video_transcript } : {}),
    publisher: {
      "@type": "Organization",
      name: brand.displayName,
      logo: { "@type": "ImageObject", url: brand.logoUrl },
    },
  };
}

function faqPage(ctx: PageSchemaContext) {
  if (!ctx.faq || ctx.faq.length === 0) return undefined;
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: ctx.faq.map((q) => ({
      "@type": "Question",
      name: q.question,
      acceptedAnswer: { "@type": "Answer", text: q.answer },
    })),
  };
}

function breadcrumbList(ctx: PageSchemaContext) {
  if (!ctx.breadcrumb || ctx.breadcrumb.length < 2) return undefined;
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: ctx.breadcrumb.map((c, i) => {
      const isLast = i === ctx.breadcrumb!.length - 1;
      const item: any = { "@type": "ListItem", position: i + 1, name: c.name };
      if (!isLast && c.url) item.item = `${brand.canonicalUrl}${c.url}`;
      return item;
    }),
  };
}

const RESOLVERS: Record<string, (ctx: PageSchemaContext) => unknown | undefined> = {
  "local-business": localBusiness,
  organization,
  website,
  service,
  "blog-posting": blogPosting,
  "video-object": videoObject,
  faq: faqPage,
  "breadcrumb-list": breadcrumbList,
  // "aggregate-rating" is embedded inside local-business, not emitted standalone
};

export function renderSchema(stubs: string[], ctx: PageSchemaContext): unknown[] {
  return stubs
    .map((s) => RESOLVERS[s]?.(ctx))
    .filter((x) => x !== undefined && x !== null);
}
