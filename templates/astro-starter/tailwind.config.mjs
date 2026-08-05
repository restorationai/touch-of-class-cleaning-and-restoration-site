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
          DEFAULT: "{{BRAND_DARK_COLOR}}",
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
          DEFAULT: "{{BRAND_PRIMARY_COLOR}}",
          50: "{{BRAND_PRIMARY_50}}",
          100: "{{BRAND_PRIMARY_100}}",
          200: "{{BRAND_PRIMARY_200}}",
          300: "{{BRAND_PRIMARY_300}}",
          400: "{{BRAND_PRIMARY_400}}",
          500: "{{BRAND_PRIMARY_500}}",
          // 600/700 are the DARKENED rungs — brand-tinted TEXT on a white or
          // light surface (Hero's outline button, ProcessSection icons). They
          // are NOT the button fill; that is `cta` below.
          600: "{{BRAND_PRIMARY_CTA}}",
          700: "{{BRAND_PRIMARY_DARK}}",
          800: "{{BRAND_PRIMARY_800}}",
          900: "{{BRAND_PRIMARY_900}}",
          950: "{{BRAND_PRIMARY_950}}",
        },
        /* cta — the SOLID-FILL pair: `bg-cta` is every call-to-action's
           background and `text-cta-fg` is the label that sits on it. They are
           resolved TOGETHER in build_site.resolve_tokens so the pair always
           clears WCAG AA, which lets the fill stay the client's REAL brand hex
           instead of a darkened derivative. A dark brand gets hex + white; a
           light brand (gold, lime, sky) gets hex + a near-black label. Reign,
           2026-08-05: "Action to call on the website need to match golds as
           the logo" — the fill is the logo gold now, the label moved instead. */
        cta: {
          DEFAULT: "{{BRAND_CTA_FILL}}",
          hover: "{{BRAND_CTA_HOVER}}",
          fg: "{{BRAND_CTA_FG}}",
        },
        accent: {
          // Same pair rule as cta — btn-accent renders text-accent-fg on this.
          DEFAULT: "{{BRAND_ACCENT_COLOR}}",
          fg: "{{BRAND_ACCENT_FG}}",
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
        sans: ["{{BRAND_FONT_SANS}}", "system-ui", "sans-serif"],
        display: ["{{BRAND_FONT_DISPLAY}}", "system-ui", "sans-serif"],
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
