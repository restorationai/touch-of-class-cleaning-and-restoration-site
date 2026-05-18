import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

// Astro v6 content collections for ProBrite Gen. Today this only includes
// the `blog` collection — System 2 (content-writer) writes markdown posts
// here. The existing service pages remain individual .astro files under
// src/pages/ and are NOT migrated into content collections.

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

const blog = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/blog" }),
  schema: seoFields.merge(imageFields).merge(planFields).extend({
    published_at: z.string(),
    updated_at: z.string().optional(),
    services: z.array(z.string()).default([]),
    internal_links: internalLinks,
    breadcrumb: breadcrumb.optional(),
    faq: z.array(faqItem).default([]),
  }),
});

export const collections = { blog };
