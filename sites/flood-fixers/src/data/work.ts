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
    label: "Reconstruction & Rebuild",
    beforeSrc: "/images/before-after/reconstruction-before.webp",
    beforeAlt: "Room gutted to the studs before reconstruction",
    afterSrc: "/images/before-after/reconstruction-after.webp",
    afterAlt: "Same room fully rebuilt and finished after reconstruction",
  }
];
