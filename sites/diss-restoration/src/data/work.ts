import type { BeforeAfterPair } from "~/components/ui/BeforeAfterSection.astro";

/*
 * Per-client "Our Work" before/after pairs for BeforeAfterSection.
 *
 * Ships EMPTY in the template — the homepage section self-hides until pairs
 * are populated. POLICY (Santino 2026-09-18): populate EVERY client with
 * Davis/Home Pride-style generated showcase imagery at build time — do not
 * wait for real client photos (that stance left the section invisible
 * fleet-wide). Generate before/after pairs (nano banana; before first, then
 * edit the same scene to the after so geometry matches) into
 * `public/images/before-after/`.
 *
 * SERVICE-MATCHED still applies: only pairs for services the client sells
 * and publicly advertises (never suppressed lanes — TDI/SERVPRO case).
 *   - Restoration/mitigation -> water / fire / mold / sewage / storm
 *   - Cleaning               -> carpet / upholstery / tile & grout
 *   - Remodel/renovation     -> ONLY if the client does GC / remodeling
 */
export const workPairs: BeforeAfterPair[] = [
  {
    label: "Water Damage Restoration",
    beforeSrc: "/images/before-after/water-before.png",
    beforeAlt: "Flooded living room with standing water before restoration",
    afterSrc: "/images/before-after/water-after.png",
    afterAlt: "Same living room fully dried and restored",
  },
  {
    label: "Fire & Smoke Restoration",
    beforeSrc: "/images/before-after/fire-before.png",
    beforeAlt: "Kitchen with soot and smoke damage before restoration",
    afterSrc: "/images/before-after/fire-after.png",
    afterAlt: "Same kitchen fully cleaned and restored after fire damage",
  },
  {
    label: "Mold Remediation",
    beforeSrc: "/images/before-after/mold-before.png",
    beforeAlt: "Bathroom wall with spreading mold before remediation",
    afterSrc: "/images/before-after/mold-after.png",
    afterAlt: "Same bathroom wall clean and repainted after mold remediation",
  },
  {
    label: "Sewage Cleanup",
    beforeSrc: "/images/before-after/sewage-before.png",
    beforeAlt: "Basement floor after a sewage backup before cleanup",
    afterSrc: "/images/before-after/sewage-after.png",
    afterAlt: "Same basement floor disinfected and dry after cleanup",
  }
];
