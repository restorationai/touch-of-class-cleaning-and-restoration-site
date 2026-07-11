/** @type {import('tailwindcss').Config}
 *
 * The Restoration Group brand palette — sampled from the REAL brand assets:
 * logo (therestorationgroup.com wp-content, flat two-color: #1498d5 light blue
 * + black) and the box-truck livery in public/images/team.webp (~#2899bc in
 * overcast shade — same cerulean family). White/light-blue brand.
 *
 *   primary — TRG brand BLUE. The literal logo blue #1498d5 is only 3.24:1 on
 *             white, so it lives at 500 for decorative accents/washes only.
 *             600 = #0f719f (5.41:1) and 700 = #0c5d83 (7.22:1) are the
 *             AA-checked interactive/text shades (same approach as MCC green).
 *   accent  — deep petrol/ink derived from the brand hue. #09435d = 10.65:1
 *             on white — monogram tile, secondary CTAs, trust accents.
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
          // TRG brand blue (logo #1498d5 / truck livery). DEFAULT is the
          // AA-checked 600 because bare text-primary/border-primary is used for
          // links on white (Footer, DispatchCallout) — the literal logo blue
          // fails 4.5:1 there and lives at 500 for decorative use only.
          DEFAULT: "#0f719f",
          50: "#eff9fd",
          100: "#dff2fb",
          200: "#bae4f7",
          300: "#86d1f4",
          400: "#3bb5ed",
          500: "#1498d5", // TRUE logo/truck blue — decorative accents + tints only (3.24:1)
          600: "#0f719f", // 5.41:1 on white — AA for normal text + white-on-blue CTAs
          700: "#0c5d83", // 7.22:1 on white — links/eyebrows
          800: "#0a4967",
          900: "#083a52",
          950: "#052533",
        },
        accent: {
          // btn-accent renders WHITE text on this color — keep >= 4.5:1 contrast
          // with white (WCAG AA). #09435d = 10.65:1 (deep petrol from the brand hue).
          DEFAULT: "#09435d",
          400: "#2a7ba3", // lighter petrol blue — icons/decoration (4.71:1 on white)
          600: "#09435d",
          700: "#073349",
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
