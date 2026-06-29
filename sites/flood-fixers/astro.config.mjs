import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  site: "https://flood-fixers.com",
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
      lastmod: new Date(),
      serialize(item) {
        if (item.url.endsWith("/")) {
          item.priority = item.url === "https://flood-fixers.com/" ? 1.0 : 0.7;
        }
        return item;
      },
    }),
  ],
  build: { format: "directory" },
  prefetch: { defaultStrategy: "viewport" },
});
