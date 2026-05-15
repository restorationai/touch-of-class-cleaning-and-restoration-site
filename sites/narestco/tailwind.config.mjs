/** @type {import('tailwindcss').Config}
 *
 * Design tokens derived from the Narestco brand palette:
 *   dark    — primary background, the dominant brand surface (dark grays/blacks)
 *   primary — deep red for CTAs, hovers, links
 *   accent  — slightly brighter red highlight; applied to emergency CTAs / accents
 */
export default {
  content: ["./src/**/*.{astro,html,js,ts,md,mdx}"],
  theme: {
    extend: {
      colors: {
        dark: {
          DEFAULT: "#111827", // gray-900
          50: "#f9fafb", // gray-50
          100: "#f3f4f6", // gray-100
          200: "#e5e7eb", // gray-200
          300: "#d1d5db", // gray-300
          400: "#9ca3af", // gray-400
          500: "#6b7280", // gray-500
          600: "#4b5563", // gray-600
          700: "#374151", // gray-700
          800: "#1f2937", // gray-800
          900: "#111827", // gray-900
          950: "#030712", // gray-950
        },
        primary: {
          DEFAULT: "#a83227", // Narestco Deep Red
          50: "#fef2f2",
          100: "#fee2e2",
          200: "#fecaca",
          300: "#fca5a5",
          400: "#f87171",
          500: "#ef4444",
          600: "#dc2626",
          700: "#b91c1c",
          800: "#991b1b",
          900: "#7f1d1d",
          950: "#450a0a",
        },
        accent: {
          DEFAULT: "#ef4444", // Brighter red for urgent CTA
        },
        muted: {
          DEFAULT: "#4b5563", // gray-600 for sensitive pages
        }
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
