import { defineCollection, z } from "astro:content";

const seoFields = z.object({
  title: z.string(),
  h1: z.string(),
  meta_description: z.string(),
  primary_keyword: z.string(),
  secondary_keywords: z.array(z.string()).default([]),
  search_intent: z.string().optional(),
  canonical_url: z.string().url().optional(),
});

const imageFields = z.object({
  hero: z.string().optional(),
  og: z.string().optional(),
  inline: z.array(z.string()).default([]),
});

const planFields = z.object({
  plan_hash: z.string().optional(),
  archetype: z.string(),
  priority: z.number().default(0),
  generated_at: z.string().optional(),
  manual_override: z.boolean().default(false),
});

const internalLinks = z.array(z.string()).default([]);

const faqItem = z.object({
  question: z.string(),
  answer: z.string(),
});

const breadcrumb = z.array(z.object({ name: z.string(), url: z.string().optional() }));

const pages = defineCollection({
  type: "content",
  schema: seoFields.merge(imageFields).merge(planFields).extend({
    internal_links: internalLinks,
    breadcrumb: breadcrumb.optional(),
    faq: z.array(faqItem).default([]),
  }),
});

const services = defineCollection({
  type: "content",
  schema: seoFields.merge(imageFields).merge(planFields).extend({
    service_slug: z.string(),
    service_display: z.string(),
    internal_links: internalLinks,
    breadcrumb: breadcrumb.optional(),
    faq: z.array(faqItem).default([]),
  }),
});

const serviceAreas = defineCollection({
  type: "content",
  schema: seoFields.merge(imageFields).merge(planFields).extend({
    area_slug: z.string(),
    city: z.string(),
    state: z.string(),
    primary: z.boolean().default(false),
    internal_links: internalLinks,
    breadcrumb: breadcrumb.optional(),
    faq: z.array(faqItem).default([]),
  }),
});

const locations = defineCollection({
  type: "content",
  schema: seoFields.merge(imageFields).merge(planFields).extend({
    area_slug: z.string(),
    service_slug: z.string(),
    city: z.string(),
    state: z.string(),
    service_display: z.string(),
    internal_links: internalLinks,
    breadcrumb: breadcrumb.optional(),
    faq: z.array(faqItem).default([]),
    content_guardrails: z.enum(["sensitive"]).optional(),
  }),
});

const blog = defineCollection({
  type: "content",
  schema: seoFields.merge(imageFields).merge(planFields).extend({
    published_at: z.string(),
    updated_at: z.string().optional(),
    services: z.array(z.string()).default([]),
    internal_links: internalLinks,
    breadcrumb: breadcrumb.optional(),
    faq: z.array(faqItem).default([]),
    youtube_id: z.string().optional(),
    video_transcript: z.string().optional().default(""),
  }),
});

const legal = defineCollection({
  type: "content",
  schema: seoFields.merge(imageFields).merge(planFields).extend({
    ref: z.enum(["privacy", "terms", "accessibility"]),
    internal_links: internalLinks,
    breadcrumb: breadcrumb.optional(),
  }),
});

export const collections = { pages, services, serviceAreas, locations, blog, legal };
