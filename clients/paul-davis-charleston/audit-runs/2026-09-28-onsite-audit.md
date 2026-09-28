# Onsite Audit - Paul Davis Restoration of Charleston - 2026-09-28

**Live origin audited:** none (pre-flight blocked)
**Site verdict:** not computed
**URLs audited:** 0
**Prior audit:** first audit (no prior `onsite-audit.json`; the 2026-09-24 run was also blocked at pre-flight)

## Status: BLOCKED at pre-flight (unchanged since 2026-09-24)

No Lighthouse or on-page calls were made, so there was no DataForSEO spend. No state file was written and the client record was not changed, so nothing downstream will read a fake result.

### Blockers (re-checked 2026-09-28)

1. **Client status is still `onboarding`, not `active`.** The audit requires `status == "active"`. `build_status` is `pushed_main`, which is fine.
2. **Nothing is live to audit.**
   - `domain` is still `null` and there is no `apex_cutover.completed_at`, so the apex origin cannot be used.
   - `https://staging.rankai-paul-davis-charleston.pages.dev/` still does not resolve (curl exit 6, `Could not resolve host`). The production alias `https://rankai-paul-davis-charleston.pages.dev/` does not resolve either, which means the Cloudflare Pages project does not exist yet. A branch that simply hasn't been deployed would still leave the production alias resolving.
   - Control check: `https://staging.rankai-tdi-builders.pages.dev/` returned 200 from the same runner, so the runner's network is fine.
   - Repo `restorationai/paul-davis-charleston-site` was last pushed to main on 2026-09-23T00:48Z. The code exists, but nothing is hosting it.

### URL set that will be audited once unblocked (Mode B, from url-plan.json)

| Slot | Archetype | Path |
| --- | --- | --- |
| 1 | home | `/` |
| 2 | services-hub | `/services/` |
| 3 | service-landing | `/services/water-damage-restoration/` |
| 3 | service-landing | `/services/fire-damage-restoration/` |
| 4 | service-area | `/service-areas/mount-pleasant-sc/` |
| 5 | contact | `/contact/` |

No service-area entry has `primary: true`, and the client record has no `business.address.city`. The first service-area in the plan was used as a fallback.

## Recommended next actions (priority order)

1. Create a Cloudflare Pages project named `rankai-paul-davis-charleston` connected to `restorationai/paul-davis-charleston-site`, then deploy the `staging` branch. Confirm that `https://staging.rankai-paul-davis-charleston.pages.dev/` returns 200.
2. When the client leaves onboarding, set `status` to `active` in `clients/paul-davis-charleston.json`.
3. Add `domain` and `business.address` (at least `city`) to the client record. The address lets the audit pick the Charleston service-area page instead of the first area in the plan.
4. Re-run the onsite audit. It will be the client's first real audit, so there will be no regression comparison.

## Notes / caveats

- This is the second blocked run in a row (2026-09-24 and 2026-09-28). Until blocker 1 is fixed, further scheduled runs will produce the same result.
- When the audit does run, Lighthouse will be desktop-only through the DataForSEO wrapper.
- A staging audit will apply the noindex SEO-exclusion correction from Step 4.
