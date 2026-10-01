// Dispatch-claim helpers — the one quotable sentence AI answer engines can cite
// for "who serves {city}?" queries (competitor teardown: Robinson Restoration
// wins out-of-city citations with exactly this pattern). Every claim here is
// data-gated on brand.ts fields (hours, certifications, primaryCity) — nothing
// invents a capability the client doesn't actually have.
import { brand } from "./brand";

// Same 24/7 gate the Header announcement bar uses (brand.hours is the source
// of truth; scheduled-hours trades like construction never make emergency claims).
export const is247 = /24\s*[\/x-]?\s*7|24 ?hours/i.test(String(brand.hours || ""));

// Only claim IICRC when the brand actually holds the certification.
const hasIicrc = (brand.certifications || []).some((c) => /iicrc/i.test(String(c)));

// "technicians" for 24/7 restoration brands, "crews" for scheduled trades.
export const crewLabel = `${hasIicrc ? "IICRC-certified " : ""}${is247 ? "technicians" : "crews"}`;

export function isHqCity(city: string): boolean {
  return String(city).trim().toLowerCase() === String(brand.primaryCity).trim().toLowerCase();
}

// The dispatch sentence — repeated verbatim on-page (DispatchCallout) and in
// the LocalBusiness schema description so engines see one consistent claim.
// The 60-minute figure matches the emergency-page standard claim.
export function dispatchSentence(city: string): string {
  const hq = isHqCity(city);
  if (is247) {
    return hq
      ? `Our ${crewLabel} are headquartered right here in ${city} and are typically on-site within 60 minutes of your call.`
      : `Our ${crewLabel} are dispatched from our ${brand.primaryCity}, ${brand.primaryState} headquarters and are typically on-site in ${city} within 60 minutes of your call.`;
  }
  return hq
    ? `Our ${crewLabel} are headquartered right here in ${city} and take on projects across the surrounding area.`
    : `Our ${crewLabel} are dispatched from our ${brand.primaryCity}, ${brand.primaryState} headquarters and respond quickly to projects across ${city}.`;
}

// Deterministic review rotation: stable per city (same snippet every build for
// a given page) while different cities surface different GBP review snippets.
export function cityHash(city: string): number {
  let h = 0;
  const s = String(city);
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}
