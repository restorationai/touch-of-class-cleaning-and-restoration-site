import type { BeforeAfterPair } from "~/components/ui/BeforeAfterSection.astro";

/*
 * ACS Enterprise "Our Work" pairs — one per core service line (Santino
 * 2026-09-19: water, air duct, junk removal, carpet — a total of four).
 * carpet-before.png is a REAL job photo from Alfredo's GBP; the after is an
 * edit of that same photo. The other pairs are generated before->same-scene
 * edits (nano banana) per the fleet showcase policy.
 */
export const workPairs: BeforeAfterPair[] = [
  {
    label: "Water Damage Restoration",
    beforeSrc: "/images/before-after/water-before.webp",
    beforeAlt: "Flooded living room with standing water before restoration",
    afterSrc: "/images/before-after/water-after.webp",
    afterAlt: "Same living room fully dried and restored",
  },
  {
    label: "Air Duct Cleaning",
    beforeSrc: "/images/before-after/duct-before.webp",
    beforeAlt: "HVAC duct interior caked with dust and debris before cleaning",
    afterSrc: "/images/before-after/duct-after.webp",
    afterAlt: "Same duct interior spotless after professional cleaning",
  },
  {
    label: "Junk & Debris Removal",
    beforeSrc: "/images/before-after/junk-before.webp",
    beforeAlt: "Garage packed with junk and debris before removal",
    afterSrc: "/images/before-after/junk-after.webp",
    afterAlt: "Same garage cleared and swept clean after junk removal",
  },
  {
    label: "Carpet Cleaning",
    beforeSrc: "/images/before-after/carpet-before.webp",
    beforeAlt: "Heavily soiled carpet on an ACS Enterprise job before cleaning",
    afterSrc: "/images/before-after/carpet-after.webp",
    afterAlt: "Same carpet restored to like-new condition after cleaning",
  },
];
