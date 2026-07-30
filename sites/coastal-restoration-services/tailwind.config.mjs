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
        accent: {
          // btn-accent renders WHITE text on this color — pick an accent that
          // keeps >= 4.5:1 contrast with white (WCAG AA). e.g. #dc2626 or #c2410c.
          DEFAULT: "#8f6a10",
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
