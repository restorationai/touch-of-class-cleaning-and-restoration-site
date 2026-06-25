import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  site: "https://rankai.restorationai.io",
  output: "static",
  trailingSlash: "ignore",
  integrations: [tailwind({ applyBaseStyles: false }), sitemap()],
  build: { format: "directory" },
  prefetch: { defaultStrategy: "viewport" },
});
