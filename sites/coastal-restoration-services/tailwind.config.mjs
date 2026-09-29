/** @type {import('tailwindcss').Config}
 *
 * Canonical Rank AI starter palette — matches the narestco visual reference.
 * Tokens substituted at scaffold time from plan-input.json via build_site.py.
 *
 *   dark    — primary background surface (charcoal/near-black)
 *   primary — CTA color (red by default; override via BRAND_PRIMARY_* tokens)
 *   accent  — brighter highlight for urgent elements
 */
export default {
  content: ["./src/**/*.{astro,html,js,ts,md,mdx}"],
  theme: {
    extend: {
      colors: {
        dark: {
          DEFAULT: "#14144a",
          50: "#f3f3fc",
          100: "#e3e3f7",
          200: "#c3c3ef",
          300: "#8f8fe1",
          400: "#4a4ace",
          500: "#2b2ba1",
          600: "#212178",
          700: "#181858",
          800: "#111140",
          900: "#0c0c2c",
          950: "#08081c",
        },
        primary: {
          DEFAULT: "#14144a",
          50: "#f3f3fc",
          100: "#dfdff6",
          200: "#bfbfee",
          300: "#8f8fe1",
          400: "#6262d5",
          500: "#3636c9",
          // 600/700 are the DARKENED rungs — brand-tinted TEXT on a white or
          // light surface (Hero's outline button, ProcessSection icons). They
          // are NOT the button fill; that is `cta` below.
          600: "#14144a",
          700: "#0b0b2a",
          800: "#060618",
          900: "#020208",
          950: "#020208",
        },
        /* cta — the SOLID-FILL pair: `bg-cta` is every call-to-action's
           background and `text-cta-fg` is the label that sits on it. They are
           resolved TOGETHER in build_site.resolve_tokens so the pair always
           clears WCAG AA, which lets the fill stay the client's REAL brand hex
           instead of a darkened derivative. A dark brand gets hex + white; a
           light brand (gold, lime, sky) gets hex + a near-black label. Reign,
           2026-08-05: "Action to call on the website need to match golds as
           the logo" — the fill is the logo gold now, the label moved instead. */
        gold: {
          DEFAULT: "#e6ac1a",
          50: "#fdfaf1",
          100: "#fbf2da",
          200: "#f7e4b5",
          300: "#f1d07e",
          400: "#ebbc47",
          500: "#e6ac19",
          600: "#af8213",
          700: "#8f6a10",
          800: "#73560d",
          900: "#57410a",
          950: "#332606",
        },
        cta: {
          DEFAULT: "#14144a",
          hover: "#0b0b2a",
          fg: "#ffffff",
        },
        accent: {
          DEFAULT: "#8f6a10",
          fg: "#ffffff",
        },
        muted: {
          DEFAULT: "#4b5563",
        },
        /* navy — deep blue-black surface used by Footer (text-navy-900 on the
           inverted white footer), GoogleMap/InternalLinks sections, and the
           interior page-route backgrounds. Was referenced by components but
           never defined, so Tailwind dropped every navy-* class and the white
           footer rendered white-on-white text (audit: color-contrast). */
        navy: {
          DEFAULT: "#0f172a",
          50: "#f8fafc",
          100: "#f1f5f9",
          200: "#e2e8f0",
          300: "#cbd5e1",
          400: "#94a3b8",
          500: "#64748b",
          600: "#475569",
          700: "#334155",
          800: "#1e293b",
          900: "#0f172a",
          950: "#020617",
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
