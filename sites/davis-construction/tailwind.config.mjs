/** @type {import('tailwindcss').Config}
 *
 * Davis Construction Contractors brand palette:
 *   dark    — primary background surface (charcoal/near-black)
 *   primary — Davis red for CTAs, hovers, links
 *   accent  — brighter red for urgent highlights
 */
export default {
  content: ["./src/**/*.{astro,html,js,ts,md,mdx}"],
  theme: {
    extend: {
      colors: {
        dark: {
          DEFAULT: "#111827", // gray-900
          50: "#f9fafb",
          100: "#f3f4f6",
          200: "#e5e7eb",
          300: "#d1d5db",
          400: "#9ca3af",
          500: "#6b7280",
          600: "#4b5563",
          700: "#374151",
          800: "#1f2937",
          900: "#111827",
          950: "#030712",
        },
        primary: {
          DEFAULT: "#dc2626", // Davis Red (matches logo)
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
          // #dc2626 (was #ef4444): keeps the urgent red but meets WCAG AA 4.5:1
          // with white button text (audit: color-contrast)
          DEFAULT: "#dc2626",
        },
        muted: {
          DEFAULT: "#4b5563",
        },
        /* navy — deep blue-black surface used by Footer (text-navy-900 on the
           inverted white footer), GoogleMap/InternalLinks sections, and interior
           page-route backgrounds. Was referenced by components but never defined,
           so Tailwind dropped every navy-* class and the white footer rendered
           white-on-white text (audit: color-contrast). */
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
