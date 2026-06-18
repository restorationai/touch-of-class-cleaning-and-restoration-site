import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  site: "https://homepriderestorationandcleaning.com",
  output: "static",
  trailingSlash: "always",
  integrations: [
    tailwind({ applyBaseStyles: false }),
    sitemap({
      filter: (page) => !page.includes("/404"),
      changefreq: "weekly",
      lastmod: new Date(),
      serialize(item) {
        if (item.url.endsWith("/")) {
          item.priority = item.url === "https://homepriderestorationandcleaning.com/" ? 1.0 : 0.7;
        }
        return item;
      },
    }),
  ],
  build: { format: "directory" },
  prefetch: { defaultStrategy: "viewport" },
});
