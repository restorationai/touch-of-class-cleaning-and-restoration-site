/** @type {import('tailwindcss').Config}
 *
 * The Restoration Group brand palette — no logo file on hand (rebrand in
 * progress; text wordmark + TRG monogram used sitewide). Palette is the
 * tasteful navy/red restoration direction approved for the preview build.
 *
 *   primary — crimson RED #c8102e. 600 = 5.88:1 and 700 = 8.14:1 on white —
 *             both pass WCAG AA for text and white-on-red CTAs.
 *   accent  — deep NAVY #1b365d (12.12:1 on white) — monogram tile, secondary
 *             CTAs, trust accents.
 *   dark    — slate neutrals.
 */
export default {
  content: ["./src/**/*.{astro,html,js,ts,md,mdx}"],
  theme: {
    extend: {
      colors: {
        dark: {
          // slate grays
          DEFAULT: "#1e293b",
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
        primary: {
          // TRG crimson
          DEFAULT: "#c8102e",
          50: "#fdf1f3",
          100: "#fbdfe4",
          200: "#f6c9d2",
          300: "#efa0af",
          400: "#e56a81",
          500: "#d63a58",
          600: "#c8102e", // 5.88:1 on white — AA for normal text + white-on-red CTAs
          700: "#a00d26", // 8.14:1 on white — links/eyebrows
          800: "#850c22",
          900: "#6f0e20",
          950: "#3d030e",
        },
        accent: {
          // btn-accent renders WHITE text on this color — keep >= 4.5:1 contrast
          // with white (WCAG AA). #1b365d = 12.12:1 (TRG navy).
          DEFAULT: "#1b365d",
          400: "#3b5a8a", // lighter navy — icons/decoration
          600: "#1b365d",
          700: "#142a4a",
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
