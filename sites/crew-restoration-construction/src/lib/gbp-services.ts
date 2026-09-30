// Services-we-handle lists (Santino 2026-09-30, GBP <-> site parity). Generated
// from clients/{slug}/gbp-service-map.json by scripts/site_structure.py
// write_page_services(): every GBP service mapped onto a page, in plain
// customer language, deduped; declined / undecided services never list.
// Do not edit ~/data/gbp-services.json by hand.
import data from "~/data/gbp-services.json";

const lists = data as Record<string, string[]>;

export function gbpServicesFor(serviceSlug: string | undefined): string[] {
  return (serviceSlug && Array.isArray(lists[serviceSlug]) && lists[serviceSlug]) || [];
}
