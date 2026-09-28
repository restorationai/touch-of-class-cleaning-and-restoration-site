# Onsite Audit - Paul Davis Restoration of Charleston - 2026-09-28

**Live origin audited:** none (pre-flight blocked)
**Site verdict:** not computed
**URLs audited:** 0
**Prior audit:** first audit (no prior `onsite-audit.json`; the 2026-09-24 run was also blocked at pre-flight)

## Status: BLOCKED at pre-flight (unchanged since 2026-09-24)

No Lighthouse or on-page calls were made, so there was no DataForSEO spend. No state file was written and the client record was not changed, so nothing downstream will read a fake result.

### Blockers

1. **Client status is still `onboarding`, not `active`.** The audit requires `status == "active"`. `build_status` is `pushed_main`, which is fine.
2. **Nothing is live to audit.**
   - `domain` is `null` and there is no `apex_cutover.completed_at`, so the apex origin cannot be used.
   - The staging origin `https://staging.rankai-paul-davis-charleston.pages.dev/` still does not resolve (curl returned no HTTP response, code 000). The production alias `https://rankai-paul-davis-charleston.pages.dev/` does not resolve either. The Cloudflare Pages project has most likely never been created or deployed, even though `build.last_pushed_main_at` is 2026-09-23T00:48Z (repo `restorationai/paul-davis-charleston-site`).
   - Control check: `https://staging.rankai-tdi-builders.pages.dev/` returned 200 from the same runner, so the runner network is fine.

### URL set that will be audited once unblocked (Mode B, from url-plan.json)

| Slot | Archetype | Path |
| --- | --- | --- |
| 1 | home | `/` |
| 2 | services-hub | `/services/` |
| 3 | service-landing | `/services/water-damage-restoration/` |
| 3 | service-landing | `/services/fire-damage-restoration/` |
| 4 | service-area | `/service-areas/mount-pleasant-sc/` |
| 5 | contact | `/contact/` |

No service-area entry has `primary: true`, and the client record has no `business.address.city`, so the first service-area in the plan is the fallback. The plan has 19 service-area pages and none is for Charleston itself (the home city is likely covered by the homepage), so Mount Pleasant is a reasonable pick. To choose a different one, mark it `primary: true` in the url-plan.

## Recommended next actions (priority order)

1. Create a Cloudflare Pages project named `rankai-paul-davis-charleston`, connect it to `restorationai/paul-davis-charleston-site`, and deploy the `staging` branch. Then confirm `https://staging.rankai-paul-davis-charleston.pages.dev/` returns 200.
2. When the client leaves onboarding, set `status` to `active` in `clients/paul-davis-charleston.json`.
3. Add `domain` and `business.address` to the client record. `domain` is needed for the eventual apex cutover.
4. Re-run the onsite audit. It will be the first real audit for this client, so there will be no regression comparison.

## Notes / caveats

- This is the second blocked run in a row (2026-09-24, 2026-09-28). Scheduling it again before step 1 is done will just produce another blocked report.
- When the audit does run, Lighthouse will be desktop-only through the DataForSEO wrapper.
- A staging audit will apply the noindex SEO-exclusion correction (SEO left out of the verdict).
