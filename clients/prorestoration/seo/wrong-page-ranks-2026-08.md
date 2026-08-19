# Wrong-page ranks — prorestoration — 2026-08
Property: sc-domain:prorestorationca.com | window: last 28d | filter: pos 5-30, impressions >= 20

| query | imp | pos | ranking page | expected page | kind |
|---|---|---|---|---|---|
| water damage restoration near me | 4028 | 28.2 | / | /services/water-damage-restoration/ | WRONG_PAGE |
| water restoration near me | 1828 | 28.3 | / | /services/water-damage-restoration/ | WRONG_PAGE |
| water damage restoration services near me | 1563 | 18.0 | / | /services/water-damage-restoration/ | WRONG_PAGE |
| water restoration company | 1267 | 26.7 | / | /services/water-damage-restoration/ | WRONG_PAGE |
| water restoration company near me | 843 | 27.6 | / | /services/water-damage-restoration/ | WRONG_PAGE |
| fire damage restoration process | 43 | 27.4 | /blog/fire-damage-restoration-process/ | (unserved area: process) | AREA_DEMAND |
| professional water damage restoration services | 37 | 25.1 | / | /services/water-damage-restoration/ | WRONG_PAGE |
| water restoration pros | 31 | 17.7 | / | (unserved area: pros) | AREA_DEMAND |
| damage restoration companies | 21 | 17.7 | / | /services/water-damage-restoration/ | WRONG_PAGE |

## Unserved-area demand (ring-expansion candidates)

| area tokens | queries | impressions |
|---|---|---|
| (unserved area: process) | 1 | 43 |
| (unserved area: pros) | 1 | 31 |

WRONG_PAGE = money page exists; strengthen internal links/anchors toward it.
BUILD_GAP = no money page; content-queue candidate.
AREA_DEMAND = real impressions from a town outside the configured ring; consider adding it to the service areas.
