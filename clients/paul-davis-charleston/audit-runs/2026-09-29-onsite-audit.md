# Onsite Audit - Paul Davis Restoration of Charleston - 2026-09-29

**Live origin audited:** none (pre-flight blocked)
**Site verdict:** not computed
**URLs audited:** 0
**Prior audit:** first audit (no prior `onsite-audit.json`; the 2026-09-24 and 2026-09-28 runs were also blocked at pre-flight)

## Status: BLOCKED at pre-flight (third consecutive day)

No Lighthouse or on-page calls were made, so there was no DataForSEO spend. No state file was written and the client record was not changed, so nothing downstream will read a fake result.

### Blockers (unchanged since 2026-09-24)

1. **Client status is `onboarding`, not `active`.** The audit requires `status == "active"`. (`build_status` is `pushed_main`, which is fine.)
2. **Nothing is live to audit.**
   - `domain` is `null` and there is no `apex_cutover.completed_at`, so the apex origin cannot be used.
   - `https://staging.rankai-paul-davis-charleston.pages.dev/` returned HTTP 000 (connection failed) on 2026-09-29.
   - `https://rankai-paul-davis-charleston.pages.dev/` also returned HTTP 000.
   - Control: `https://staging.rankai-tdi-builders.pages.dev/` returned 200 with `x-robots-tag: noindex` from the same runner, so the runner network is fine.
   - `build.last_pushed_main_at` is 2026-09-23T00:48Z (repo `restorationai/paul-davis-charleston-site`), but the Cloudflare Pages project still appears not to exist.

### URL set that will be audited once unblocked (Mode B, from url-plan.json)

| Slot | Archetype | Path |
| --- | --- | --- |
| 1 | home | `/` |
| 2 | services-hub | `/services/` |
| 3 | service-landing | `/services/water-damage-restoration/` |
| 3 | service-landing | `/services/fire-damage-restoration/` |
| 4 | service-area | `/service-areas/mount-pleasant-sc/` (fallback: no `primary: true` entry and no `business.address.city`) |
| 5 | contact | `/contact/` |

## Recommended next actions (priority order)

1. Create the Cloudflare Pages project `rankai-paul-davis-charleston`, connect it to `restorationai/paul-davis-charleston-site`, and deploy the `staging` branch. Then confirm that `https://staging.rankai-paul-davis-charleston.pages.dev/` returns 200.
2. When the client leaves onboarding, set `status` to `active` in `clients/paul-davis-charleston.json`.
3. Add `domain` and `business.address` to the client record. The address lets slot 4 use a Charleston area page instead of the fallback.
4. Pause this client in the audit scheduler until item 1 is done. This is the third blocked run in six days and each one adds noise without adding data.
5. Re-run the onsite audit once items 1 and 2 are done. It will be the client's first real audit, with no regression comparison.

## Notes / caveats

- Re-checked later on 2026-09-29 (second invocation today): still blocked. `status` is still `onboarding` and `domain` is still `null`. Both Pages origins still return HTTP 000, and the tdi-builders control still returns 200. No DataForSEO calls were made and no state file was written.
- Re-checked again at 2026-09-29T18:17Z (third invocation today): same result. `status` is `onboarding`, `domain` is `null`, both Pages origins return HTTP 000, and the tdi-builders control returns 200. No DataForSEO calls and no state file. The scheduler is re-dispatching this client several times a day, which makes recommendation 4 more urgent.
- Re-checked again at 2026-09-29T18:55Z (fourth invocation today): same result. `status` is `onboarding`, `domain` is `null`, both Pages origins return HTTP 000, and the tdi-builders control returns 200. No DataForSEO calls and no state file.

- Once the audit runs, Lighthouse will be desktop-only through the DataForSEO wrapper. Expect mobile performance scores to be 10-20 points lower.
- A staging audit will leave SEO out of the verdict because of the Pages noindex header. SEO stays inconclusive until apex cutover.
