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
    beforeSrc: "/images/before-after/water-before.webp",
    beforeAlt: "Flooded living room with standing water before restoration",
    afterSrc: "/images/before-after/water-after.webp",
    afterAlt: "Same living room with new premium plank flooring and repaired walls after restoration",
  },
  {
    label: "Fire & Smoke Restoration",
    beforeSrc: "/images/before-after/fire-before.webp",
    beforeAlt: "Living room with severe fire damage and charred walls before restoration",
    afterSrc: "/images/before-after/fire-after.webp",
    afterAlt: "Same living room fully rebuilt and restored after fire damage",
  },
  {
    label: "Sewage Cleanup",
    beforeSrc: "/images/before-after/sewage-before.webp",
    beforeAlt: "Basement flooded wall to wall by a sewage backup before cleanup",
    afterSrc: "/images/before-after/sewage-after.webp",
    afterAlt: "Same basement extracted, disinfected and dry after cleanup",
  },
  {
    label: "Emergency Water Cleanup",
    beforeSrc: "/images/before-after/flood-before.webp",
    beforeAlt: "Basement flooded wall to wall before emergency water cleanup",
    afterSrc: "/images/before-after/flood-after.webp",
    afterAlt: "Same basement extracted, dried and repaired after cleanup",
  }
];
