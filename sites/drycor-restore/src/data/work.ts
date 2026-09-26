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
    beforeAlt: "Flooded living room with standing water across the tile floor before restoration",
    afterSrc: "/images/before-after/water-after.webp",
    afterAlt: "Same living room dried out with clean tile floor and furniture after restoration",
  },
  {
    label: "Fire & Smoke Restoration",
    beforeSrc: "/images/before-after/fire-before.webp",
    beforeAlt: "Kitchen with heavy char and soot damage above the range before restoration",
    afterSrc: "/images/before-after/fire-after.webp",
    afterAlt: "Same kitchen fully rebuilt with new cabinets and range after fire damage",
  },
  {
    label: "Mold Remediation",
    beforeSrc: "/images/before-after/mold-before.webp",
    beforeAlt: "Bedroom wall and corner covered in heavy mold before remediation",
    afterSrc: "/images/before-after/mold-after.webp",
    afterAlt: "Same bedroom wall clean and freshly painted after mold remediation",
  },
  {
    label: "Sewage Cleanup",
    beforeSrc: "/images/before-after/sewage-before.webp",
    beforeAlt: "Laundry room with contaminated water and staining from a sewage backup before cleanup",
    afterSrc: "/images/before-after/sewage-after.webp",
    afterAlt: "Same laundry room sanitized, dry and spotless after cleanup",
  },
  {
    label: "Storm Damage Restoration",
    beforeSrc: "/images/before-after/storm-before.webp",
    beforeAlt: "Living room with collapsed ceiling, broken window and hurricane debris before repair",
    afterSrc: "/images/before-after/storm-after.webp",
    afterAlt: "Same living room with rebuilt ceiling and new window after storm damage restoration",
  }
];
