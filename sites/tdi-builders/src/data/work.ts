import type { BeforeAfterPair } from "~/components/ui/BeforeAfterSection.astro";

/*
 * TDI "Our Work" before/after pairs (Davis-pattern showcase imagery,
 * Santino 2026-09-18). Construction/remodel scenes ONLY on purpose:
 * TDI's water/fire/mold services are suppressed during the SERVPRO
 * contract conflict, so showcase imagery stays on the GC lanes they
 * actively sell — kitchen, bath, whole-home, addition, garage, new build.
 */
export const workPairs: BeforeAfterPair[] = [
  {
    label: "Kitchen Remodel",
    beforeSrc: "/images/before-after/kitchen-before.webp",
    beforeAlt: "Dated kitchen with worn oak cabinets and laminate counters before remodel",
    afterSrc: "/images/before-after/kitchen-after.webp",
    afterAlt: "Finished modern kitchen remodel with white shaker cabinets and quartz counters",
  },
  {
    label: "Bathroom Renovation",
    beforeSrc: "/images/before-after/bathroom-before.webp",
    beforeAlt: "Dated bathroom with worn vanity and stained shower doors before renovation",
    afterSrc: "/images/before-after/bathroom-after.webp",
    afterAlt: "Renovated bathroom with floating walnut vanity and frameless walk-in shower",
  },
  {
    label: "Whole-Home Remodeling",
    beforeSrc: "/images/before-after/remodel-before.webp",
    beforeAlt: "Dated living room with wood paneling and worn carpet before remodel",
    afterSrc: "/images/before-after/remodel-after.webp",
    afterAlt: "Bright remodeled living room with oak floors and stone fireplace",
  },
  {
    label: "Room Addition",
    beforeSrc: "/images/before-after/addition-before.webp",
    beforeAlt: "Room addition framing in progress on a single-story home",
    afterSrc: "/images/before-after/addition-after.webp",
    afterAlt: "Completed room addition matching the original home with new patio",
  },
  {
    label: "Garage Construction",
    beforeSrc: "/images/before-after/garage-before.webp",
    beforeAlt: "Detached two-car garage framed on a fresh concrete slab",
    afterSrc: "/images/before-after/garage-after.webp",
    afterAlt: "Finished detached two-car garage with stucco walls and new driveway",
  },
  {
    label: "New Construction",
    beforeSrc: "/images/before-after/newbuild-before.webp",
    beforeAlt: "New custom home fully framed with house wrap during construction",
    afterSrc: "/images/before-after/newbuild-after.webp",
    afterAlt: "Completed two-story custom home with landscaped front yard",
  },
];
