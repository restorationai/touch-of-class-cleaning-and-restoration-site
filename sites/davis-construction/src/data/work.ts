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
// Davis's own pairs, restored after the 09-23 ops-sync sweep emptied them.
export const workPairs: BeforeAfterPair[] = [
  // Renovation pairs first
  {
    label: "Bathroom Renovation",
    beforeSrc: "/images/before-after/bathroom-before.png",
    beforeAlt: "Outdated residential bathroom with worn vanity, aged fixtures, and dated tile before renovation",
    afterSrc: "/images/before-after/bathroom-after.png",
    afterAlt: "Fully renovated modern bathroom with subway tile, floating vanity, LED mirror, and walk-in shower",
  },
  {
    label: "Kitchen Remodel",
    beforeSrc: "/images/before-after/kitchen-before.png",
    beforeAlt: "Dated kitchen with worn oak cabinets, old laminate countertops, and aging appliances before remodel",
    afterSrc: "/images/before-after/kitchen-after.png",
    afterAlt: "Renovated open kitchen with white shaker cabinets, quartz countertops, stainless appliances, and hardwood flooring",
  },
  {
    label: "Construction & Rebuild",
    beforeSrc: "https://storage.googleapis.com/msgsndr/SoaJxwp6MUc7dIBOnzdi/media/693d97eeab25946ca9b33c36.png",
    beforeAlt: "Damaged structure before Davis Construction general contracting rebuild project",
    afterSrc: "https://storage.googleapis.com/msgsndr/SoaJxwp6MUc7dIBOnzdi/media/693d97eeb4f4202a2efedc02.png",
    afterAlt: "Completed construction and rebuild showing finished quality craftsmanship by Davis Construction Contractors",
  },
  // Restoration pairs below
  {
    label: "Water Damage Restoration",
    beforeSrc: "https://storage.googleapis.com/msgsndr/Tx5eKisj3Xluq1SeZKe3/media/697e98141311f66b99469f5f.png",
    beforeAlt: "Interior room with water damage, wet flooring, and standing moisture before restoration",
    afterSrc: "https://storage.googleapis.com/msgsndr/Tx5eKisj3Xluq1SeZKe3/media/697e981b1fd827570a43ac94.png",
    afterAlt: "Same room fully restored with clean dry flooring and repaired walls after water damage remediation",
  },
  {
    label: "Fire & Smoke Damage Restoration",
    beforeSrc: "https://storage.googleapis.com/msgsndr/Tx5eKisj3Xluq1SeZKe3/media/697e9be266e7ca4d0885c947.png",
    beforeAlt: "Room with heavy fire and smoke damage, charred walls and soot-covered surfaces before restoration",
    afterSrc: "https://storage.googleapis.com/msgsndr/Tx5eKisj3Xluq1SeZKe3/media/697e9be266e7ca34a485c946.png",
    afterAlt: "Fully rebuilt and repainted interior after fire and smoke damage restoration",
  },
  {
    label: "Storm Damage Cleanup",
    beforeSrc: "https://storage.googleapis.com/msgsndr/Tx5eKisj3Xluq1SeZKe3/media/697e9ed41311f66d494798c4.png",
    beforeAlt: "Property with storm debris and hazardous conditions before professional cleanup and restoration",
    afterSrc: "https://storage.googleapis.com/msgsndr/Tx5eKisj3Xluq1SeZKe3/media/697e9ed4f7a8776652d24fbc.png",
    afterAlt: "Clean safe restored property after storm damage cleanup and decontamination",
  },
];
