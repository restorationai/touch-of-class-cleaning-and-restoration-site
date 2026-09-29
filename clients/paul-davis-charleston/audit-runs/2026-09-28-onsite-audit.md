# Onsite Audit - Paul Davis Restoration of Charleston - 2026-09-28

**Live origin audited:** none (pre-flight blocked)
**Site verdict:** not computed
**URLs audited:** 0
**Prior audit:** first audit (no prior `onsite-audit.json`; the 2026-09-24 run was also blocked at pre-flight)

## Status: BLOCKED at pre-flight (second consecutive run)

No Lighthouse or on-page calls were made, so there was no DataForSEO spend. No state file was written and the client record was not changed, so nothing downstream will read a fake result.

### Blockers (unchanged since 2026-09-24)

1. **Client status is `onboarding`, not `active`.** The audit requires `status == "active"`. (`build_status` is `pushed_main`, which is fine.)
2. **Nothing is live to audit.**
   - `domain` is `null` and there is no `apex_cutover.completed_at`, so the apex origin cannot be used.
   - The fallback staging origin `https://staging.rankai-paul-davis-charleston.pages.dev/` still does not resolve (HTTP 000, connection failed). The production Pages alias `https://rankai-paul-davis-charleston.pages.dev/` also fails. The Cloudflare Pages project has most likely never been created, even though `build.last_pushed_main_at` is 2026-09-23T00:48Z (repo `restorationai/paul-davis-charleston-site`).
   - Network check: `https://staging.rankai-tdi-builders.pages.dev/` returned 200 (with `x-robots-tag: noindex`) from the same runner, so this is not a runner network problem.

### URL set that will be audited once unblocked (Mode B, from url-plan.json)

No `audit-urls.txt` exists, so the audit will use Mode B.

| Slot | Archetype | Path |
| --- | --- | --- |
| 1 | home | `/` |
| 2 | services-hub | `/services/` |
| 3 | service-landing | `/services/water-damage-restoration/` |
| 3 | service-landing | `/services/fire-damage-restoration/` |
| 4 | service-area | `/service-areas/mount-pleasant-sc/` |
| 5 | contact | `/contact/` |

Note: no service-area entry has `primary: true`, and the client record has no `business.address.city`. The first service-area in the plan was used as a fallback. A Charleston-city area page would be a better slot-4 pick once the address is in the record.

## Recommended next actions (priority order)

1. Create a Cloudflare Pages project named `rankai-paul-davis-charleston`, connect it to `restorationai/paul-davis-charleston-site`, and deploy the `staging` branch. Confirm that `https://staging.rankai-paul-davis-charleston.pages.dev/` returns 200. This has been open since at least 2026-09-24 and blocks every downstream audit.
2. When the client leaves onboarding, set `status` to `active` in `clients/paul-davis-charleston.json`.
3. Add `domain` and `business.address` to the client record. `domain` is needed for the eventual apex cutover, and the address is needed for service-area selection.
4. Re-run the onsite audit. It will be the first real audit for this client, so there will be no regression comparison.
5. Until item 1 is done, consider pausing this client in the monthly audit schedule. Each blocked run adds noise without adding data.

## Notes / caveats

- Re-checked in a later run on 2026-09-28: nothing has changed. `staging.rankai-paul-davis-charleston.pages.dev` still fails DNS (`Could not resolve host`), `rankai-paul-davis-charleston.pages.dev` also fails, and the control `staging.rankai-tdi-builders.pages.dev` returns 200 with `x-robots-tag: noindex`. The client record still has `status: onboarding` and `domain: null`. No DataForSEO calls were made and no state file was written.
- When the audit does run, Lighthouse will be desktop-only through the DataForSEO wrapper. Expect mobile performance scores to be 10-20 points lower.
- A staging audit will apply the noindex SEO-exclusion correction, so SEO will stay inconclusive until apex cutover.
- Re-checked later on 2026-09-28 (third blocked invocation). Nothing had changed: status is still `onboarding`, `domain` is still null, and both `staging.rankai-paul-davis-charleston.pages.dev` and `rankai-paul-davis-charleston.pages.dev` still return HTTP 000. The control origin `staging.rankai-tdi-builders.pages.dev` returned 200. No DataForSEO spend, and no state or client-record writes.
