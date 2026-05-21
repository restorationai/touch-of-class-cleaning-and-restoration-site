/** @type {import('tailwindcss').Config}
 *
 * Design tokens derived from the restoration-vertical visual template
 * (see rank-ai/docs/build-site-skill-spec.md). Three colors:
 *   navy    — primary background, the dominant brand surface
 *   primary — saturated blue for CTAs, hovers, links
 *   accent  — orange highlight; sparingly applied to emergency CTAs / accents
 *
 * Per-client overrides happen at scaffold time via brand tokens; the default
 * palette below is the canonical restoration-industry look.
 */
export default {
  content: ["./src/**/*.{astro,html,js,ts,md,mdx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: "#0d1b3e",
          50: "#f5f7fb",
          100: "#e6eaf3",
          900: "#0d1b3e",
        },
        primary: {
          DEFAULT: "#1e5ad4",
          50: "#eff4ff",
          200: "#bdd0ff",
        },
        accent: {
          DEFAULT: "#f97316",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Inter", "system-ui", "sans-serif"],
      },
      maxWidth: {
        content: "72ch",
        wide: "1400px",
      },
      letterSpacing: {
        widest: "0.25em",
      },
    },
  },
  plugins: [],
};
