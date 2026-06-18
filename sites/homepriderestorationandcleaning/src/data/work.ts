import type { BeforeAfterPair } from "~/components/ui/BeforeAfterSection.astro";

/*
 * Home Pride Restoration and Cleaning — "Our Work" before/after pairs.
 *
 * Service-matched to Home Pride's actual offerings:
 *   Mitigation/restoration -> water / fire / mold / sewage / storm
 *   Cleaning               -> carpet
 * No remodel/renovation pairs (Home Pride does mitigation + cleaning, not GC/remodeling).
 *
 * Images are AI-generated matched pairs (same room before vs. restored),
 * committed at public/images/before-after/.
 */
export const workPairs: BeforeAfterPair[] = [
  {
    label: "Water Damage Restoration",
    beforeSrc: "/images/before-after/water-before.png",
    beforeAlt: "Residential room with standing water and saturated flooring before water damage restoration",
    afterSrc: "/images/before-after/water-after.png",
    afterAlt: "The same room fully dried, cleaned, and restored after professional water damage restoration",
  },
  {
    label: "Fire & Smoke Damage Restoration",
    beforeSrc: "/images/before-after/fire-before.png",
    beforeAlt: "Room with charred walls and heavy soot and smoke damage before fire restoration",
    afterSrc: "/images/before-after/fire-after.png",
    afterAlt: "The same room rebuilt, cleaned, and repainted after fire and smoke damage restoration",
  },
  {
    label: "Mold Removal & Remediation",
    beforeSrc: "/images/before-after/mold-before.png",
    beforeAlt: "Wall and surfaces with visible mold growth before professional mold remediation",
    afterSrc: "/images/before-after/mold-after.png",
    afterAlt: "The same area cleaned, treated, and restored mold-free after remediation",
  },
  {
    label: "Sewage Cleanup",
    beforeSrc: "/images/before-after/sewage-before.png",
    beforeAlt: "Finished basement flooded by a large sewage backup with contaminated water and debris before cleanup",
    afterSrc: "/images/before-after/sewage-after.png",
    afterAlt: "The same basement cleaned, sanitized, repaired, and dried after professional sewage cleanup",
  },
  {
    label: "Storm Damage Repair",
    beforeSrc: "/images/before-after/storm-before.png",
    beforeAlt: "Room with a collapsed storm-damaged ceiling and debris before repair",
    afterSrc: "/images/before-after/storm-after.png",
    afterAlt: "The same room fully rebuilt and restored after storm damage repair",
  },
  {
    label: "Carpet Cleaning",
    beforeSrc: "/images/before-after/carpet-before.png",
    beforeAlt: "Living room carpet with heavy traffic stains and ground-in dirt before cleaning",
    afterSrc: "/images/before-after/carpet-after.png",
    afterAlt: "The same carpet cleaned fresh and uniform after professional carpet cleaning",
  },
];
