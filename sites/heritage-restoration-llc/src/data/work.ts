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
    label: "Storm Damage Restoration",
    beforeSrc: "/images/before-after/storm-before.webp",
    beforeAlt: "Bedroom with collapsed ceiling and storm debris before repair",
    afterSrc: "/images/before-after/storm-after.webp",
    afterAlt: "Same bedroom with rebuilt ceiling after storm damage restoration",
  }
];
