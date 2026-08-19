# Wrong-page ranks — all-pro-plumbing — 2026-08
Property: sc-domain:allproplumbingheatingandair.com | window: last 28d | filter: pos 5-30, impressions >= 20

| query | imp | pos | ranking page | expected page | kind |
|---|---|---|---|---|---|
| trenchless sewer line | 99 | 24.2 | /blog/trenchless-sewer-repair-explained/ | (unserved area: trenchless) | AREA_DEMAND |
| all pro plumbing | 74 | 22.5 | / | (unserved area: all) | AREA_DEMAND |
| trenchless pipe bursting water line | 40 | 26.7 | /blog/trenchless-sewer-repair-explained/ | (unserved area: bursting pipe trenchless water) | AREA_DEMAND |

## Unserved-area demand (ring-expansion candidates)

| area tokens | queries | impressions |
|---|---|---|
| (unserved area: trenchless) | 1 | 99 |
| (unserved area: all) | 1 | 74 |
| (unserved area: bursting pipe trenchless water) | 1 | 40 |

WRONG_PAGE = money page exists; strengthen internal links/anchors toward it.
BUILD_GAP = no money page; content-queue candidate.
AREA_DEMAND = real impressions from a town outside the configured ring; consider adding it to the service areas.
