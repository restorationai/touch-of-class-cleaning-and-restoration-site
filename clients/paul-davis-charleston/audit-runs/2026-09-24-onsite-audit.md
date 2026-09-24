# Onsite Audit - Paul Davis Restoration of Charleston - 2026-09-24

**Live origin audited:** none (pre-flight blocked)
**Site verdict:** not computed
**URLs audited:** 0
**Prior audit:** first audit (no prior `onsite-audit.json`)

## Status: BLOCKED at pre-flight

No Lighthouse or on-page calls were made, so no DataForSEO spend. No state file was written and the client record was not changed, so nothing downstream will read a fake result.

### Blockers

1. **Client status is `onboarding`, not `active`.** The audit requires `status == "active"`. (`build_status` is `pushed_main`, which is fine.)
2. **Nothing is live to audit.**
   - `domain` is `null` and there is no `apex_cutover.completed_at`, so the apex origin cannot be used.
   - The fallback staging origin `https://staging.rankai-paul-davis-charleston.pages.dev/` does not resolve (curl: `Could not resolve host`). The Cloudflare Pages project has most likely not been created or deployed yet, even though `build.last_pushed_main_at` is 2026-09-23T00:48Z (repo `restorationai/paul-davis-charleston-site`).
   - Network check: `https://staging.rankai-tdi-builders.pages.dev/` returned 200 from the same runner, so this is not a runner network problem.

### URL set that will be audited once unblocked (Mode B, from url-plan.json)

| Slot | Archetype | Path |
| --- | --- | --- |
| 1 | home | `/` |
| 2 | services-hub | `/services/` |
| 3 | service-landing | `/services/water-damage-restoration/` |
| 3 | service-landing | `/services/fire-damage-restoration/` |
| 4 | service-area | `/service-areas/mount-pleasant-sc/` |
| 5 | contact | `/contact/` |

Note: no service-area entry has `primary: true`, and the client record has no `business.address.city`. The first service-area in the plan was used as a fallback. Add `business.address` to the client record so the next run can select the home-city area page.

## Recommended next actions (priority order)

1. Connect `restorationai/paul-davis-charleston-site` to a Cloudflare Pages project named `rankai-paul-davis-charleston` and confirm the `staging` branch alias resolves at `https://staging.rankai-paul-davis-charleston.pages.dev/`.
2. When the client leaves onboarding, set `status` to `active` in `clients/paul-davis-charleston.json`.
3. Add `domain` and `business.address` to the client record. `domain` is needed for the eventual apex cutover, and the address is needed for service-area selection.
4. Re-run the onsite audit. It will be the first audit for this client, so there will be no regression comparison.

## Notes / caveats

- When the audit does run, Lighthouse will be desktop-only through the DataForSEO wrapper.
- A staging audit will apply the noindex SEO-exclusion correction.
