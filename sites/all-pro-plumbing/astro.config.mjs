import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";
import sitemap from "@astrojs/sitemap";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// ---------------------------------------------------------------------------
// Per-URL <lastmod>: report each page's real content date instead of stamping
// every URL with the build timestamp. We walk src/content/**/*.md at config
// time, pull published_at (falling back to generated_at) from frontmatter via
// a simple regex (dependency-free), and key the date by the page's rendered
// URL path. Non-content pages (e.g. /emergency/) fall back to the build date.
// ---------------------------------------------------------------------------
const CONTENT_DIR = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "src",
  "content",
);
const BUILD_DATE = new Date();

function contentLastmodMap() {
  const map = new Map();
  // collection dir -> derived URL path for a given file slug
  const collections = {
    blog: (slug) => `/blog/${slug}/`,
    services: (slug) => `/services/${slug}/`,
    serviceAreas: (slug) => `/service-areas/${slug}/`,
    // locations files are named {area}__{service}.md
    locations: (slug) => {
      const [area, service] = slug.split("__");
      return area && service ? `/service-areas/${area}/${service}/` : null;
    },
    legal: (slug) => `/${slug}/`,
    pages: (slug) =>
      slug === "home" ? "/" : slug === "blog-index" ? "/blog/" : `/${slug}/`,
  };
  for (const [dir, toPath] of Object.entries(collections)) {
    const abs = path.join(CONTENT_DIR, dir);
    if (!fs.existsSync(abs)) continue;
    for (const file of fs.readdirSync(abs)) {
      if (!file.endsWith(".md")) continue;
      const urlPath = toPath(file.replace(/\.md$/, ""));
      if (!urlPath) continue;
      const raw = fs.readFileSync(path.join(abs, file), "utf8");
      const m =
        raw.match(/^published_at:\s*["']?([0-9][^"'\n]*)["']?\s*$/m) ||
        raw.match(/^generated_at:\s*["']?([0-9][^"'\n]*)["']?\s*$/m);
      if (!m) continue;
      const d = new Date(m[1]);
      if (!Number.isNaN(d.getTime())) map.set(urlPath, d);
    }
  }
  return map;
}

const LASTMOD_BY_PATH = contentLastmodMap();

export default defineConfig({
  site: "https://allproplumbingheatingandair.com",
  output: "static",
  trailingSlash: "always",
  integrations: [
    tailwind({ applyBaseStyles: false }),
    sitemap({
      // Exclude noindex Google Ads landing pages (/lp/) from the sitemap.
      // They are intentionally noindex,nofollow; listing them creates conflicting
      // signals ("Submitted URL marked noindex" in GSC) and wastes crawl budget.
      filter: (page) => !page.includes("/404") && !page.includes("/lp/"),
      changefreq: "weekly",
      serialize(item) {
        if (item.url.endsWith("/")) {
          item.priority = item.url === "https://allproplumbingheatingandair.com/" ? 1.0 : 0.7;
        }
        const urlPath = new URL(item.url).pathname;
        item.lastmod = (LASTMOD_BY_PATH.get(urlPath) ?? BUILD_DATE).toISOString();
        return item;
      },
    }),
  ],
  build: { format: "directory" },
  prefetch: { defaultStrategy: "viewport" },
});
