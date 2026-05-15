# Rank AI — Astro Starter Design Contract

**Audience:** Whoever is designing/redesigning `rank-ai/templates/astro-starter/`. Today that's Google Antigravity. Tomorrow it might be someone else. The contract is what you must honor; everything else is yours to design however you want.

---

## What this is

`rank-ai/templates/astro-starter/` is a token-based Astro 5 template that gets cloned and substituted per client by `rank-ai/scripts/build_site.py scaffold`. After scaffold, content is generated into Astro content collections by `build_site.py render` and the site builds + deploys automatically via Cloudflare Pages.

Your job is to make the starter **look great** — visual design, components, layouts, micro-interactions, typography rhythm. Don't worry about how the data flows in; that part already works.

## Two surfaces

```
STRUCTURAL SURFACE — do not change shape           DESIGN SURFACE — design freely
────────────────────────────────────               ────────────────────────────────
src/content/config.ts (schema definitions)         src/components/*.astro
src/lib/brand.ts (token names + shape)             src/layouts/*.astro
src/lib/schema.ts (JSON-LD renderer signature)     src/pages/*.astro
src/components/Schema.astro (JSON-LD output)       src/styles/*.css
prompts/* (content generation prompts)             tailwind.config.mjs
                                                   public/*.svg, public/*.png
                                                   astro.config.mjs (within Astro conventions)
```

If you touch anything on the left, you'll break the rendering pipeline. If you touch anything on the right, you're doing your job.

## What the rest of the system expects from your starter

The build pipeline runs in this order:

1. `build_site.py scaffold` copies your starter to `rank-ai/sites/{slug}/` and substitutes `{{TOKENS}}` (see Token list below).
2. It generates one markdown file per planned URL in `src/content/{collection}/{slug}.md` with a strict frontmatter schema (see Frontmatter shape below).
3. `build_site.py render` calls Claude Sonnet 4.6 for each page to populate `body_markdown` + `faq` fields, preserving the frontmatter your scaffold wrote.
4. `npm run build` runs on Cloudflare Pages whenever the GitHub repo gets a push to `main` or `staging`.

For all of this to work, your starter must:

- Define exactly the **6 content collections** with exactly the **field names** documented below.
- Use exactly the **route patterns** documented below.
- Reference the **brand tokens** by their exact names — substitution is a literal string replace.
- Render JSON-LD via `src/components/Schema.astro` with the same `schema_stubs` prop interface.

That's the whole contract. Within those constraints, design however you want.

---

## Token list (in `src/lib/brand.ts`)

These tokens are substituted at scaffold time. You can reference them in your Astro components via `import { brand } from "~/lib/brand"` — they're exposed as a typed const. **Token names are LITERAL string match.** If you rename `{{BRAND_PHONE}}` to `{{BRAND_PHONE_NUMBER}}`, the substitution silently fails and you get the literal `{{BRAND_PHONE_NUMBER}}` text in the built site.

| Token | Type | Example value |
| --- | --- | --- |
| `{{BRAND_SLUG}}` | string | `narestco` |
| `{{BRAND_DISPLAY_NAME}}` | string | `National Restoration Construction` |
| `{{BRAND_SHORT_NAME}}` | string | `NARESTCO` |
| `{{BRAND_LEGAL_NAME}}` | string | `National Restoration Construction LLC` |
| `{{BRAND_DOMAIN}}` | string | `narestco.com` |
| `{{BRAND_CANONICAL_URL}}` | string | `https://narestco.com` |
| `{{BRAND_PHONE}}` | string | `(206) 883-0333` (display form) |
| `{{BRAND_PHONE_RAW}}` | string | `+12068830333` (for `tel:` href) |
| `{{BRAND_EMAIL}}` | string | `info@narestco.com` |
| `{{BRAND_HOURS}}` | string | `24/7` |
| `{{BRAND_FOUNDED_YEAR}}` | string | `2004` |
| `{{BRAND_PRIMARY_CITY}}` | string | `Federal Way` |
| `{{BRAND_PRIMARY_STATE}}` | string | `WA` |
| `{{BRAND_STREET_ADDRESS}}` | string | `1530 S Dash Point Rd` |
| `{{BRAND_POSTAL_CODE}}` | string | `98003` |
| `{{BRAND_LAT}}` | string | `47.337` |
| `{{BRAND_LNG}}` | string | `-122.314` |
| `{{BRAND_PLACE_ID}}` | string | Google Place ID |
| `{{BRAND_GOOGLE_CID}}` | string | Google CID |
| `{{BRAND_LICENSE_AUTHORITY}}` | string | `WA State Department of Labor & Industries` |
| `{{BRAND_LICENSE_TYPE}}` | string | `General Contractor Certificate of Registration` |
| `{{BRAND_LICENSE_NUMBERS_JSON}}` | **JSON array literal** | `["NATIORC792M6"]` — NOTE: unquoted, raw JS literal |
| `{{BRAND_CERTIFICATIONS_JSON}}` | **JSON array literal** | `["IICRC Certified", "BBB Accredited", ...]` |
| `{{BRAND_SAME_AS_URLS_JSON}}` | **JSON array literal** | `["https://www.facebook.com/...", ...]` |
| `{{BRAND_GBP_RATING_VALUE}}` | string | `5.0` |
| `{{BRAND_GBP_REVIEW_COUNT}}` | string | `31` |
| `{{BRAND_TAGLINE}}` | string | `24/7 restoration services...` |
| `{{BRAND_PRIMARY_COLOR}}` | hex string | `#0d1b3e` |
| `{{BRAND_PRIMARY_DARK}}` | hex string | `#1e5ad4` |
| `{{BRAND_PRIMARY_LIGHT}}` | hex string | `#bdd0ff` |
| `{{BRAND_ACCENT_COLOR}}` | hex string | `#f97316` |
| `{{BRAND_FONT_SANS}}` | string | `Inter` |
| `{{BRAND_FONT_DISPLAY}}` | string | `Inter` |
| `{{BRAND_LOGO_URL}}` | URL | `https://images.narestco.com/brand/logo.png` |
| `{{BRAND_INITIALS}}` | string | `NR` |
| `{{BRAND_IMAGES_BASE}}` | URL | `https://images.narestco.com` |
| `{{BRAND_GOOGLE_MAPS_API_KEY}}` | string | Google Maps Embed API key. Empty string when not configured — the `GoogleMap` component must handle empty gracefully (falls back to a "View on Google Maps" link). |

**Important:** the three `*_JSON` tokens are substituted as **raw JS literals without surrounding quotes**. In `brand.ts`, write them like this:

```ts
licenseNumbers: {{BRAND_LICENSE_NUMBERS_JSON}} as string[],
```

After substitution becomes:

```ts
licenseNumbers: ["NATIORC792M6"] as string[],
```

All other tokens are simple string substitutions — wrap them in `"..."` if you want a string value.

If you need a new token, add it to:
1. `src/lib/brand.ts` (add the field)
2. `rank-ai/scripts/build_site.py` (`resolve_tokens()` function — add the key + default)
3. This contract doc (so future you remembers)

The `BRAND_*_JSON` tokens that need special handling are the only ones that aren't plain string replaces; otherwise it's all literal replace.

There are also four computed tokens you should use in `public/llms.txt`:

| Token | Source |
| --- | --- |
| `{{LLMS_SERVICES_INDEX}}` | Markdown list of selected services with URLs |
| `{{LLMS_SERVICE_AREAS_INDEX}}` | Markdown list of selected areas with URLs |
| `{{LLMS_CERTIFICATIONS}}` | Comma-separated certification names |
| `{{LLMS_SERVICE_RADIUS}}` | Human-readable service area description |

---

## Content collections (in `src/content/config.ts`)

There are **exactly 6 collections** and your starter must define all of them with at least these fields. Renaming fields breaks the LLM-rendered content stored in `rank-ai/sites/*/src/content/`. Adding optional fields is fine. Adding required fields breaks all existing rendered content.

### `pages` — fixed pages

Files: `pages/home.md`, `pages/about.md`, `pages/contact.md`, `pages/services.md` (services hub), `pages/service-areas.md` (areas hub), `pages/blog-index.md`

Route: `home` is rendered by `src/pages/index.astro`; `blog-index` by `src/pages/blog/index.astro`; the rest by `src/pages/[fixed].astro` (which filters out home + blog-index).

Frontmatter fields (your schema must accept all of these):

```ts
{
  archetype: string,        // e.g., "home", "about", "services-hub"
  title: string,            // <title> tag content
  h1: string,               // <h1> on the page, usually shorter than title
  meta_description: string, // meta description + OG description
  primary_keyword: string,
  secondary_keywords: string[],
  search_intent?: string,
  priority: number,
  hero?: string,            // URL to a hero image (on the R2 bucket)
  og?: string,              // URL to OG image (defaults to hero if absent)
  inline?: string[],        // URLs to inline content images
  plan_hash?: string,
  generated_at?: string,
  manual_override: boolean,
  internal_links: string[], // List of URL paths to render in InternalLinks
  breadcrumb?: { name: string, url?: string }[],
  faq: { question: string, answer: string }[],
}
```

### `services` — service landing pages

Files: `services/{service_slug}.md`
Route: `src/pages/services/[slug].astro` using `getStaticPaths` from `service_slug` frontmatter.

Fields: all of `pages` plus:
```ts
{
  service_slug: string,     // matches the URL slug
  service_display: string,  // e.g., "Water Damage Restoration"
}
```

### `serviceAreas` — city pages

Files: `serviceAreas/{area_slug}.md`
Route: `src/pages/service-areas/[area].astro`

Fields: all of `pages` plus:
```ts
{
  area_slug: string,        // e.g., "federal-way-wa"
  city: string,             // e.g., "Federal Way"
  state: string,            // e.g., "WA"
  primary: boolean,         // true for the brand's HQ city
}
```

### `locations` — city × service cross-product (the bulk of pages, ~180 of 229)

Files: `locations/{area_slug}__{service_slug}.md` (double underscore in filename)
Route: `src/pages/service-areas/[area]/[service].astro` using `getStaticPaths` from `area_slug` + `service_slug` frontmatter.

Fields: all of `pages` plus:
```ts
{
  area_slug: string,
  service_slug: string,
  city: string,
  state: string,
  service_display: string,
  content_guardrails?: "sensitive",  // present on biohazard/crime/hoarding/meth-lab pages — apply muted styling
}
```

### `blog` — blog posts

Files: `blog/{slug}.md` — filename IS the URL slug (Astro auto-derives — do NOT add a `slug` field, it's reserved).
Route: `src/pages/blog/[slug].astro` using `entry.slug` (filename-derived).

Fields: all of `pages` plus:
```ts
{
  published_at: string,     // ISO date
  updated_at?: string,
  services: string[],       // service slugs this post relates to
}
```

### `legal` — privacy/terms/accessibility

Files: `legal/{ref}.md` where `ref ∈ {"privacy", "terms", "accessibility"}`
Route: `src/pages/[legal].astro`

Fields: all of `pages` plus:
```ts
{
  ref: "privacy" | "terms" | "accessibility",
}
```

---

## Routes — exact URL patterns

These URL patterns are baked into the plan generator (Skill 2) and the sitemap. Don't change them.

| URL pattern | Astro route file | Collection |
| --- | --- | --- |
| `/` | `src/pages/index.astro` | `pages` (entry slug `home`) |
| `/about/` | `src/pages/[fixed].astro` | `pages` (entry slug `about`) |
| `/contact/` | `src/pages/[fixed].astro` | `pages` (entry slug `contact`) |
| `/services/` | `src/pages/[fixed].astro` | `pages` (entry slug `services`) |
| `/services/{service-slug}/` | `src/pages/services/[slug].astro` | `services` |
| `/service-areas/` | `src/pages/[fixed].astro` | `pages` (entry slug `service-areas`) |
| `/service-areas/{area-slug}/` | `src/pages/service-areas/[area].astro` | `serviceAreas` |
| `/service-areas/{area-slug}/{service-slug}/` | `src/pages/service-areas/[area]/[service].astro` | `locations` |
| `/blog/` | `src/pages/blog/index.astro` | (consumes `blog` + `pages.blog-index`) |
| `/blog/{post-slug}/` | `src/pages/blog/[slug].astro` | `blog` |
| `/privacy/` | `src/pages/[legal].astro` | `legal` (ref `privacy`) |
| `/terms/` | `src/pages/[legal].astro` | `legal` (ref `terms`) |
| `/accessibility/` | `src/pages/[legal].astro` | `legal` (ref `accessibility`) |
| `/404` | `src/pages/404.astro` | none |

Trailing slashes on all URLs. The Astro config has `trailingSlash: "always"`.

`[fixed].astro` must filter `home` and `blog-index` out of its `getStaticPaths` (they have their own dedicated route files).

`getStaticPaths` runs in an isolated module-scope context in Astro 5 — variables defined in the Astro frontmatter ARE NOT visible inside it. Inline any helpers it needs.

---

## JSON-LD schema injection

`src/components/Schema.astro` accepts:

```ts
type Props = {
  stubs: string[];                        // list of schema names
  ctx: PageSchemaContext;                 // context to render with
};
```

The stubs the planner emits are: `organization`, `website`, `local-business`, `service`, `blog-posting`, `faq`, `breadcrumb-list`. The resolver is in `src/lib/schema.ts` — its function signatures must stay stable.

Don't change:
- `src/lib/schema.ts`'s `renderSchema(stubs, ctx)` signature
- `src/components/Schema.astro`'s `Props` shape
- The `<script type="application/ld+json">` output (search engines depend on it)

DO change anything else about how the schema visually appears (which means: nothing, since JSON-LD is metadata).

---

## What the rendered content looks like in the wild

Pull any file from `rank-ai/sites/narestco/src/content/` to see real content the LLM produced. Example: `locations/federal-way-wa__water-damage-restoration.md` has the full Federal Way × water-damage page with:

- `body_markdown`: ~5500 chars of markdown with 3-4 `##` subsections
- `faq`: 5-6 `{question, answer}` pairs, each answer 2-4 sentences

When designing layouts, **render against this real content**, not lorem ipsum. The content has its own rhythm (the FAQ section is dense; the body has shifting subheadings; the breadcrumb is always present except on home).

---

## Per-archetype design considerations

Things to remember as you design each route:

- **Home**: full-bleed hero with brand image, then services strip, then content, FAQ, CTA, footer.
- **Service landings**: hero with service-specific framing, then long-form body with H2 subsections, then FAQ + related areas + CTA.
- **City × service (the 180-page bulk)**: same shape as service landings but the H1 says "{Service} in {City}." This is the SEO money page — make it feel locally specific, not just a template.
- **Sensitive guardrail pages** (4 services: biohazard, crime-scene, hoarding, meth-lab decon): if `data.content_guardrails === "sensitive"`, use a quieter visual tone — muted accents, less urgency-red CTA, more "discreet professional" feel. The LLM-rendered content already softens; the layout should match.
- **Blog index**: card grid of posts, no FAQ, no internal-links section.
- **Blog post**: article layout, narrow max-width for readability, FAQ + related at bottom.
- **Legal**: narrow column, dense prose, no FAQ, no internal-links.
- **404**: graceful, big "404" number, back-to-home CTA.
- **Inverted footer or matching footer**: probritegen uses an inverted (white background) footer against the dark site. Worth replicating if you go dark.

### Required component: `<GoogleMap>` on every location and city × service page

Read this carefully. **The current starter already includes `src/components/GoogleMap.astro` and references it from the two route files** (`service-areas/[area].astro` and `service-areas/[area]/[service].astro`). You may redesign its visual treatment — section heading, container styling, map height, surrounding spacing — but the component must:

1. Take `city: string`, `state: string`, optional `service?: string`, optional `heading?: string`, optional `height?: number` props.
2. Render a `<section>` with the same logical structure (eyebrow + heading + map container).
3. Use the Google Maps Embed API iframe pattern below when `brand.googleMapsApiKey` is set.
4. Render a graceful fallback (a "View on Google Maps" link) when the key is empty — many client deployments will start without a key.
5. Set the section heading text:
   - Service-area page (no service prop): *"Serving {City Name} and Surrounding Neighborhoods"*
   - City × service page: *"{Service Name} in {City Name}: Service Coverage Map"*
   - Overridable via the `heading` prop.

Iframe spec (when key is present):

```html
<iframe
  src="https://www.google.com/maps/embed/v1/place?key={key}&q={City},{State}&zoom=11"
  width="100%"
  height="400"
  style="border:0; display:block;"
  allowfullscreen
  loading="lazy"
  referrerpolicy="no-referrer-when-downgrade"
  title="Map of {City}, {State}"
></iframe>
```

Why this is locked: Google rewards location pages that have an embedded Map (it's a signal of genuine local relevance), and the planner explicitly counts on this component being present on every service-area and service-area-service page. Removing it weakens local SEO ranking signals on ~190 of the 229 pages.

### Content differentiation requirements

`rank-ai/docs/content-differentiation.md` is a separate document that defines content-quality rules enforced by the prompts. As a designer, you should know that the rendered content on every location and city × service page is **required** to include:

- 2-3 named neighborhoods or landmarks from that area
- At least 1 ZIP code from that area
- A neighborhood-specific paragraph about local restoration patterns
- A local-tip paragraph

Design accordingly — give those content elements room. The neighborhood paragraph should feel like a deliberate section, not a wedged-in paragraph. The local tip is best as a callout (boxed quote-style block, or a sidebar treatment). You can lean into that visual moment.

---

## Things that already work — don't break them

- The build outputs 230 static HTML files for a fully-configured client (229 plan URLs + 404). Verify your design keeps building all 230.
- Astro auto-generates the sitemap from the routes via `@astrojs/sitemap`. The sitemap respects `<lastmod>` based on the page's content date if you don't filter pages out.
- `public/llms.txt`, `public/ai.txt`, `public/robots.txt` are token-substituted at scaffold. Their formats are conventional — feel free to redesign visually only the content that humans see (none).
- `public/favicon.svg` uses `{{BRAND_INITIALS}}` and `{{BRAND_PRIMARY_COLOR}}` tokens. Redesign the SVG mark however you want, but keep those two tokens or update `resolve_tokens()` to not emit them.

---

## When you (Antigravity) think you're done

A successful redesign:

1. `cd rank-ai/sites/narestco && rm -rf node_modules .astro dist && npm install && npm run build` returns successfully.
2. The build produces 230 pages (run `find dist -name "*.html" | wc -l`).
3. Spot-check `dist/index.html`, `dist/service-areas/federal-way-wa/water-damage-restoration/index.html`, and `dist/blog/{any-blog-post}/index.html` — they should show real content from the markdown files.
4. JSON-LD `<script type="application/ld+json">` blocks render on every page.
5. The footer NAP (name, address, phone) is correctly substituted from tokens.
6. Sitemap at `dist/sitemap-0.xml` lists 229 URLs.
7. **The site looks great** — that's the only criterion you uniquely bring. Don't ship a redesign you wouldn't be proud to show a client.

When all those are true, the handoff back to Claude Code is: "Antigravity is done. Sync the new starter into all existing per-client sites." Claude Code will preserve rendered content and only update the design files.

---

## Out of scope for the design pass

- Don't touch `rank-ai/scripts/*` (Python orchestration).
- Don't touch `rank-ai/templates/restoration/` (planning template — that's a different layer).
- Don't touch `rank-ai/clients/*.json` (client records — these are owned by the onboarding pipeline).
- Don't change the Anthropic prompt templates in `prompts/` — that's content quality, separate concern.
- Don't change content collection field names (breaks every existing rendered page).

---

*Contract version: 1.0. Last updated 2026-05-14. Bump version + add a changelog entry when the structural surface changes.*
