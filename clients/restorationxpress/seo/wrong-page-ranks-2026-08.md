# Wrong-page ranks — restorationxpress — 2026-08
Property: sc-domain:restorationxpress.com | window: last 28d | filter: pos 5-30, impressions >= 20

| query | imp | pos | ranking page | expected page | kind |
|---|---|---|---|---|---|
| fire damage restoration process | 121 | 19.2 | /blog/fire-damage-restoration-process/ | (unserved area: process) | AREA_DEMAND |
| home mold testing | 74 | 24.6 | /blog/how-to-test-for-mold/ | (unserved area: testing) | AREA_DEMAND |
| fire remediation process | 53 | 18.6 | /blog/fire-damage-restoration-process/ | (unserved area: fire process) | AREA_DEMAND |
| smoke damage restoration process | 53 | 20.5 | /blog/fire-damage-restoration-process/ | (unserved area: process) | AREA_DEMAND |
| test my house for mold | 25 | 25.8 | /blog/how-to-test-for-mold/ | (unserved area: my test) | AREA_DEMAND |

## Unserved-area demand (ring-expansion candidates)

| area tokens | queries | impressions |
|---|---|---|
| (unserved area: process) | 2 | 174 |
| (unserved area: testing) | 1 | 74 |
| (unserved area: fire process) | 1 | 53 |
| (unserved area: my test) | 1 | 25 |

WRONG_PAGE = money page exists; strengthen internal links/anchors toward it.
BUILD_GAP = no money page; content-queue candidate.
AREA_DEMAND = real impressions from a town outside the configured ring; consider adding it to the service areas.
