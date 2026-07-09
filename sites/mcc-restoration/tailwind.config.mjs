/** @type {import('tailwindcss').Config}
 *
 * MCC Restoration brand palette — sampled from clients/mcc-restoration/Logo.png
 * (2026-07 rebrand: chrome MCC lettering, green+blue construction-scaffold house
 * motif, green/blue swoosh underline).
 *
 *   primary — MCC logo BLUE (#0a5eb6 sampled). 600 = 6.38:1 and 700 = 8.78:1 on
 *             white — both pass WCAG AA for text and white-on-blue CTAs.
 *   accent  — MCC logo GREEN. The literal logo green (#8bbb4e) is only 2.25:1 on
 *             white, so accent.DEFAULT (btn-accent renders WHITE text on it) is
 *             the AA-checked deep green #4f7d21 (4.90:1); the true logo green
 *             lives at accent-400 for icons/decorative use only.
 *   dark    — steel/slate neutrals to match the chrome lettering.
 */
export default {
  content: ["./src/**/*.{astro,html,js,ts,md,mdx}"],
  theme: {
    extend: {
      colors: {
        dark: {
          // steel/slate grays (Tailwind slate) — matches the chrome MCC lettering
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
          // MCC logo blue (#0a5eb6 sampled from Logo.png swoosh + scaffold motif)
          DEFAULT: "#0a5eb6",
          50: "#eef7fd",
          100: "#d8ecfa",
          200: "#b5daf4",
          300: "#83c0eb",
          400: "#49a0de",
          500: "#1f7ecb",
          600: "#0a5eb6", // 6.38:1 on white — AA for normal text + white-on-blue CTAs
          700: "#084a90", // 8.78:1 on white — AAA-adjacent, used for links/eyebrows
          800: "#0a3e75",
          900: "#0d3560",
          950: "#08203d",
        },
        accent: {
          // btn-accent renders WHITE text on this color — keep >= 4.5:1 contrast
          // with white (WCAG AA). #4f7d21 = 4.90:1 (deepened MCC logo green).
          DEFAULT: "#4f7d21",
          400: "#8bbb4e", // true MCC logo green — icons/decoration only, NOT text-on-white
          600: "#4f7d21",
          700: "#3f651a",
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
