# Ops Journal — frontline-fire-flood

## 2026-09-03 14:10 UTC — client ops sync
- Customer-list checklist completed: Customer list for the review campaign

## 2026-09-18 — PENDING: About Us team photo (Jared, 2026-09-15 call) — punted to Santino
Jared uploaded individual team headshots to Client Hub and asked to assemble a
team photo for the About Us page, with two corrections: (1) one tech appears 3×
in the raw media library — include him once; (2) one tech wore a NAVY polo, not
royal blue — match the rest.

Machine-work already done, so this is a placement/layout decision only:
- **The headshot set is 13 distinct people, one per person.** photo-manifest.json
  assets crew:1789508896241 … 1789509019953 (team-slot ≥78). The client's "3
  photos of one guy" were already collapsed by triage — verified no two of the
  13 are the same person (face review + the two women + distinct men). So the
  "include him once" constraint is satisfied by using this set as-is.
- **Navy-polo tech = crew:1789508954676-5aab5213** ("Heavyset male in navy
  Frontline polo"), shirt RGB ~(22,33,60) vs everyone else ~(2,50,145).
  Corrected royal-blue version saved:
  `harvested/team-headshot-5aab5213-royal.jpg` (deterministic PIL recolor,
  connected-component shirt mask; Nike swoosh + Frontline patch + backdrop
  preserved).
- **Proof montage** (4-5-4 grid, all 13, recolored tech blended in):
  `reports/team-photo-montage-proof.jpg`.

**Blocker (why punted):** there is no team-member display on the site to drop a
grid into. team.webp lives only in the HOMEPAGE About section (index.astro),
rendered `object-cover aspect-video lg:aspect-square` — a square desktop crop
chops ~230px off each side of the montage and cuts off the edge people; the
/about/ page ([fixed].astro) shows no team photo at all. Shipping the grid needs
either a new "Meet the Team" section or a crop-behavior change to AboutSection —
a design call on a LIVE homepage that Jared scoped to Santino ("text Santino to
assemble"). The current homepage photo is a good REAL group shot, so nothing is
broken in the meantime.
