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
    beforeSrc: "/images/before-after/water-before.png",
    beforeAlt: "Flooded living room with standing water before restoration",
    afterSrc: "/images/before-after/water-after.png",
    afterAlt: "Same living room fully dried and restored",
  },
  {
    label: "Air Duct Cleaning",
    beforeSrc: "/images/before-after/duct-before.png",
    beforeAlt: "HVAC duct interior caked with dust and debris before cleaning",
    afterSrc: "/images/before-after/duct-after.png",
    afterAlt: "Same duct interior spotless after professional cleaning",
  },
  {
    label: "Junk & Debris Removal",
    beforeSrc: "/images/before-after/junk-before.png",
    beforeAlt: "Garage packed with junk and debris before removal",
    afterSrc: "/images/before-after/junk-after.png",
    afterAlt: "Same garage cleared and swept clean after junk removal",
  },
  {
    label: "Carpet Cleaning",
    beforeSrc: "/images/before-after/carpet-before.png",
    beforeAlt: "Heavily soiled carpet on an ACS Enterprise job before cleaning",
    afterSrc: "/images/before-after/carpet-after.png",
    afterAlt: "Same carpet restored to like-new condition after cleaning",
  },
];
