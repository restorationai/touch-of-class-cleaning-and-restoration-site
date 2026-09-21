import type { BeforeAfterPair } from "~/components/ui/BeforeAfterSection.astro";

/*
 * Per-client "Our Work" before/after pairs for BeforeAfterSection.
 *
 * Ships EMPTY in the template — the homepage section self-hides until a client
 * has real, service-matched pairs. Populate per client with images committed to
 * `public/images/before-after/{slug}-before.png` / `-after.png`.
 *
 * SERVICE-DRIVEN RULE: only add a pair for a service the client actually offers.
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
    afterAlt: "Same living room with new flooring and repaired walls after restoration",
  },
  {
    label: "Fire & Smoke Restoration",
    beforeSrc: "/images/before-after/fire-before.png",
    beforeAlt: "Living room with severe fire damage and charred walls before restoration",
    afterSrc: "/images/before-after/fire-after.png",
    afterAlt: "Same living room fully rebuilt and restored after fire damage",
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
  },
  {
    label: "Storm Damage Restoration",
    beforeSrc: "/images/before-after/storm-before.png",
    beforeAlt: "Bedroom with collapsed ceiling and storm debris before repair",
    afterSrc: "/images/before-after/storm-after.png",
    afterAlt: "Same bedroom with rebuilt ceiling after storm damage restoration",
  }
];
