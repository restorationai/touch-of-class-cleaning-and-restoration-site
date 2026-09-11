// Rob 2026-09-11 (SERVPRO franchise conflict): mitigation services stay
// PUBLISHED and indexable, but never appear in navigation, footers, hubs,
// homepage grids, or internal-link modules. Same policy as the Emergency
// nav suppression.
export const SUPPRESSED_SERVICE_SLUGS = new Set([
  "water-damage-restoration",
  "mold-remediation",
  "storm-damage-restoration",
]);
export const visibleServices = <T extends { slug: string }>(entries: T[]): T[] =>
  entries.filter((e) => !SUPPRESSED_SERVICE_SLUGS.has(e.slug));
