# Wrong-page ranks — restoration-groups — 2026-08
Property: sc-domain:therestorationgroup.com | window: last 28d | filter: pos 5-30, impressions >= 20

| query | imp | pos | ranking page | expected page | kind |
|---|---|---|---|---|---|
| fire restoration company | 133 | 17.9 | / | /services/fire-damage-restoration/ | WRONG_PAGE |
| fire damage restoration near me | 131 | 25.3 | / | /services/fire-damage-restoration/ | WRONG_PAGE |
| commercial restoration service | 120 | 6.3 | / | /services/commercial-restoration/ | WRONG_PAGE |
| damage restoration service | 115 | 14.8 | / | /services/water-damage-restoration/ | WRONG_PAGE |
| restoration group | 108 | 6.6 | / | (unserved area: group) | AREA_DEMAND |
| fire damage restoration process | 108 | 27.5 | /blog/fire-damage-restoration-process/ | (unserved area: process) | AREA_DEMAND |
| fire damage restoration nj | 74 | 28.2 | / | /services/fire-damage-restoration/ | WRONG_PAGE |
| commercial water damage restoration new jersey | 35 | 28.9 | / | (unserved area: jersey new) | AREA_DEMAND |
| fire remediation process | 35 | 26.3 | /blog/fire-damage-restoration-process/ | (unserved area: fire process) | AREA_DEMAND |
| commercial storm damage restoration new jersey | 32 | 26.5 | / | (unserved area: jersey new) | AREA_DEMAND |
| fire and water damage restoration new jersey | 31 | 17.7 | / | (unserved area: fire jersey new) | AREA_DEMAND |
| fire and water damage restoration in new jersey | 28 | 15.4 | / | (unserved area: fire jersey new) | AREA_DEMAND |
| damage restoration | 22 | 14.7 | / | /services/water-damage-restoration/ | WRONG_PAGE |
| damage restoration services | 22 | 19.6 | / | /services/water-damage-restoration/ | WRONG_PAGE |
| fire damage restoration company new jersey | 22 | 17.5 | / | (unserved area: jersey new) | AREA_DEMAND |
| commercial restoration insurance claims contractor | 21 | 11.3 | / | (unserved area: claims contractor insurance) | AREA_DEMAND |
| commercial restoration company | 20 | 22.5 | / | /services/commercial-restoration/ | WRONG_PAGE |
| fire damage restoration new providence | 20 | 26.7 | / | (unserved area: new providence) | AREA_DEMAND |

## Unserved-area demand (ring-expansion candidates)

| area tokens | queries | impressions |
|---|---|---|
| (unserved area: group) | 1 | 108 |
| (unserved area: process) | 1 | 108 |
| (unserved area: jersey new) | 3 | 89 |
| (unserved area: fire jersey new) | 2 | 59 |
| (unserved area: fire process) | 1 | 35 |
| (unserved area: claims contractor insurance) | 1 | 21 |
| (unserved area: new providence) | 1 | 20 |

WRONG_PAGE = money page exists; strengthen internal links/anchors toward it.
BUILD_GAP = no money page; content-queue candidate.
AREA_DEMAND = real impressions from a town outside the configured ring; consider adding it to the service areas.
