# Emergency-plumber intent — the ads playbook restoration names can't touch

**Why this file exists (Santino 2026-09-10):** the panicking homeowner's first
search is plumbing-shaped, not restoration-shaped. A restoration company's GBP
NAME can't say "emergency plumber" (real-world-name policy, licensing, caller
mismatch) — but ADS can say what names can't. This is the standing reference
for building emergency-intent campaigns for any water/fire client.

## The demand (Google Keyword Planner, verified vs native API 2026-09-10)

| Term | US /mo | WA /mo | notes |
|---|---|---|---|
| plumber near me | 823,000 | 18,100 | mostly routine-plumbing intent — bid carefully |
| emergency plumber near me | 110,000 | 2,900 | THE panic moment |
| emergency plumber / emergency plumbing | 60,500 | 1,300 | same |
| water heater leaking | 14,800 | 590 | flooding adjacent, high fit |
| 24 hour plumber | 8,100 | 320 | panic |
| water leak repair | 2,900 | 90 | mixed intent |
| slab leak repair | 2,400 | 40 | detection + damage fit |
| ceiling leaking | 1,600 | 50 | pure damage moment |
| burst pipe repair | 1,300 | 30 | pure damage moment |

WA emergency-plumber family (~4,500/mo) is ~3x "water damage restoration"
(1,600/mo). CPCs run $75-138 — the market already prices this as the most
valuable minute in home services.

## Campaign recipe (restoration client, NO plumbing license)

- **Keywords:** emergency plumber (+near me), 24 hour plumber, burst pipe,
  ceiling leaking, water heater leaking/flooded, slab leak. PHRASE/EXACT only —
  never let the ads_manager helper default to BROAD.
- **Negatives (critical):** drain cleaning, clog/clogged, toilet, faucet,
  install, water heater replacement/installation, sewer line, repipe, hydro
  jet, garbage disposal, "plumber salary/jobs/school". We stop the DAMAGE; we
  do not snake drains. Wasted plumbing-repair clicks at $90 kill the campaign.
- **Ad copy angle:** honest pivot at the moment of panic — "Pipe burst? First
  stop the damage." / "Water everywhere? We dry it out before it becomes mold."
  / "Plumber fixes the pipe. We fix everything the water ruined." Never claim
  to BE a plumber; claim the half of the emergency we own. Landing page =
  emergency/burst-pipe page, tracked number, click-to-call.
- **Schedule/geo:** 24/7 (panic ignores business hours), tight radius around
  real service capacity, phone-first bidding (call conversions).
- **Pair with content:** the same terms get organic emergency pages ("Burst
  pipe: who to call first — plumber or restoration?") — fleet GSC already
  shows clients surfacing for "24 hour plumbers near me" unprompted.

## When the client HAS a plumbing license (RT Olson class)

Everything above PLUS: "Plumber" GBP category, plumber LSA vertical (LSA
requires the license doc per category), and the name terms become legitimately
available ("... - Emergency Plumber & Water Damage"). A restoration company
hiring ONE licensed plumber unlocks this whole pool permanently — often the
cheapest growth lever on this page.

## Known landmines

- LSA plumber category demands the plumbing license during verification —
  never enroll an unlicensed client there.
- Google Ads policy already burned us once on "suicide cleanup services"
  (HEALTH_IN_PERSONALIZED_ADS) — emergency terms are fine, death/trauma terms
  are not.
- geo_lookup in ads_manager once resolved wrong-state city IDs — verify geo
  target constants are in the client's actual state before launch.
