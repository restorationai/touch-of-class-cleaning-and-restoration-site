# Onsite Audit, All Pro Plumbing Heating and Air, 2026-08-31

**Live origin audited:** https://allproplumbingheatingandair.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-07-30
**Lighthouse:** v13.4.0, DESKTOP form factor

## Read this first

Two framing notes before the numbers, because they change how you read the amber verdict.

**1. The verdict moved for a detection reason, not a breakage reason.** Three pages went green to amber this month. Nothing on the site got worse: every Lighthouse category is flat within 2 points and no category dropped by the 5-point regression threshold. The amber comes from LocalBusiness schema defects that this run inspected for the first time. Those defects were almost certainly present in July too. Treat them as a newly found backlog, not a new fire.

**2. Last month's service-area row was invalid.** The July audit scored `/service-areas/bakersfield-ca/` green. That URL 301-redirects to the homepage and is not a distinct page, so July was scoring homepage content under a service-area label. `url-plan.json` has no Bakersfield area page and no service-area entry carries `primary: true`, so this run re-baselined the slot to the plan's first area slug, `/service-areas/oildale-ca/`. The Bakersfield redirect itself looks intentional (the homepage already targets Bakersfield) and needs no fix.

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 98.5 | -0.8 |
| Accessibility | 93.5 | 0.0 |
| Best Practices | 100.0 | 0.0 |
| SEO | 100.0 | 0.0 |

Pages by verdict: green 0, amber 6, red 0, error 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 100 | 93 | 100 | 100 | 0.63s | 0.015 | 0ms |
| `/services/` | services-hub | amber | 98 | 91 | 100 | 100 | 1.10s | 0.025 | 0ms |
| `/services/emergency-plumbing/` | service-landing | amber | 97 | 95 | 100 | 100 | 1.05s | 0.052 | 98ms |
| `/services/drain-cleaning/` | service-landing | amber | 99 | 95 | 100 | 100 | 0.97s | 0.003 | 0ms |
| `/service-areas/oildale-ca/` | service-area | amber | 98 | 95 | 100 | 100 | 0.96s | 0.003 | 65ms |
| `/contact/` | contact | amber | 99 | 92 | 100 | 100 | 0.99s | 0.004 | 0ms |

Core Web Vitals are all comfortably inside Google's "good" thresholds on desktop (LCP under 2.5s, CLS under 0.1, TBT low). No page has a performance problem that would hurt rankings today.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `schema_sameas_entity_mismatch` | 6 | medium | Remove the 4 non-client profiles from `sameAs` in the shared LocalBusiness/Organization block |
| `schema_localbusiness_empty_required_fields` | 6 | medium | Omit `streetAddress`, `postalCode`, `geo`, `foundingDate` rather than emitting `""`, or populate from GBP |
| `schema_localbusiness_relative_image_url` | 6 | medium | Make `image` and `logo` absolute URLs, not `/images/logo.webp` |
| `image-delivery-insight` | 6 | low | Serve `logo.webp` at rendered size, 105KB wasted per page |
| `unused-javascript` | 6 | low | GA4 `gtag/js` ships 157KB, 70KB unused (44%) |
| `has_render_blocking_resources` | 6 | low | `_astro/_slug_.*.css` blocks for 50-64ms |
| `no_image_title` | 6 | low | Cosmetic only, images have 100% alt coverage. Safe to ignore |
| `color-contrast` | 5 | medium | Breadcrumb links are #888c93 on #ffffff, 3.37:1, below the 4.5:1 minimum |
| `has_micromarkup_errors` | 5 | medium | Validator flags the FAQPage block, see caveat below |
| `lcp-discovery-insight` | 5 | low | Hero image not discoverable early, needs `fetchpriority="high"` |
| `link-in-text-block` | 3 | medium | Body links sit at 1.59:1 against surrounding text with no underline |
| `high_loading_time` | 2 | medium | `/` and `/services/`, driven by the oversized logo and hero |
| `meta_description_length_off` | 2 | medium | `/` is 170 chars, `/services/` is 173, target is 70-160 |
| `low_content_rate` | 2 | low | Text-to-HTML ratio on `/` and `/services/` |

## Money page alerts

All 5 money pages are amber. Every one of them is amber for the same sitewide schema reason, not for a page-specific performance problem.

- **`/`** (home), amber. Perf 100, a11y 93, LCP 0.63s. The performance picture is excellent. Amber is driven by the three LocalBusiness schema defects plus a meta description of 170 chars (trim to 160 or under) and a newly flagged `high_loading_time`. Word count 1173 sits just under the plan target of 1200.
- **`/services/`** (services-hub), amber. Perf 98, a11y 91 (lowest on the site), LCP 1.10s, up 225ms from July. Carries 17 images totalling 1,009,862 bytes. Meta description is 173 chars, trim to 160 or under.
- **`/services/emergency-plumbing/`** (service-landing), amber. Perf 97 (lowest on the site), LCP 1.05s, up 253ms from July, TBT 98ms. Good news: `high_loading_time` cleared here since July.
- **`/services/drain-cleaning/`** (service-landing), amber. Perf 99, LCP 0.97s. Only new Lighthouse item is `forced-reflow-insight`.
- **`/contact/`** (contact), amber. Perf 99, a11y 92, LCP 0.99s, up 341ms from July, the largest CWV movement on the site. Canonical, title (53 chars) and meta description (140 chars) are all correct. Zero broken links.

## Regressions vs prior audit

**Verdict transitions:**
- `/services/emergency-plumbing/` went green to amber
- `/services/drain-cleaning/` went green to amber
- `/contact/` went green to amber

All three are caused by the sitewide LocalBusiness schema defects being detected for the first time. No Lighthouse category regressed on any of them (perf moved -2, 0 and -1 respectively).

**Category regressions (5+ point drop):** none.

**Core Web Vitals regressions:**
- `/contact/` LCP 652ms to 993ms (+341ms)
- `/services/emergency-plumbing/` LCP 796ms to 1049ms (+253ms)
- `/services/` LCP 871ms to 1096ms (+225ms)

These cross the 200ms flag threshold but all three still land under 1.1s, which is well inside "good". The common factor is the oversized `hero-bg.webp` combined with the LCP image not being preloaded. Worth fixing, not worth alarm.

**New issues this month (on-page, reliable):**
- All 6 pages: `schema_sameas_entity_mismatch`, `schema_localbusiness_relative_image_url`, `schema_localbusiness_empty_required_fields`
- `/services/`, `/services/emergency-plumbing/`, `/services/drain-cleaning/`, `/contact/`: `has_micromarkup_errors`
- `/`: `high_loading_time`, `low_content_rate`

**New issues this month (Lighthouse, lower confidence):**
- `/`, `/services/`, `/services/emergency-plumbing/`, `/services/drain-cleaning/`, `/contact/`: `unused-javascript`
- `/services/drain-cleaning/`: `forced-reflow-insight`
- `/services/emergency-plumbing/`: `image-delivery-insight`

These compare against July's top-5 capture only, so an audit that was already failing below rank 5 in July can appear here without a real change. Do not treat them as confirmed regressions.

**Issues resolved since last audit:** (positive, keep doing this)
- `/services/emergency-plumbing/`: `high_loading_time` is no longer flagged

No Lighthouse audit that failed in July passes now. This was verified against the complete current failing-audit set, not the top-5 capture, so it is a real result rather than a reporting artifact.

## Recommended next actions (priority order)

1. **(template, high impact, performance)** Resize `/images/logo.webp`. It is a 107,502 byte file rendered at 56px tall in the header (`img.h-14`) and 64px in the footer (`img.h-16`). Lighthouse reports 106,801 of those bytes as wasted, on all 6 audited pages and therefore on all 204 pages of the site. Export it at roughly 112px wide for 2x retina and it should land near 5-8KB. This is the single largest byte win available and it is one file.

2. **(template, money pages, schema correctness)** Strip the wrong-business profiles out of `sameAs`. The shared LocalBusiness and Organization blocks currently link the client to at least four businesses that are not them: a Yelp profile for an Oceanside CA company, a BBB profile for "All Pro Plumbing Heating Cooling Electrical LLC" in Ontario CA, and Thumbtack and Nextdoor pages for those same Ontario and Oceanside entities. `nap-audit.json` independently confirms the Yelp profile carries phone (760) 681-0313, not the client's (661) 863-9242. This actively tells Google the Bakersfield business is the same entity as unrelated companies in other cities, which undermines local entity resolution. Keep only profiles that verifiably belong to the Bakersfield business, and drop the rest rather than leaving placeholders.

3. **(template, money pages, schema correctness)** Fix the LocalBusiness block's empty and relative values. It emits `streetAddress: ""`, `postalCode: ""`, `geo.latitude: ""`, `geo.longitude: ""` and `foundingDate: ""`. Empty strings are worse than omitting the property, and `geo` expects numbers so empty strings are invalid. The GBP record in `nap-audit.json` already has the real address, 3556 Bowman Ct suite C, Bakersfield, CA 93308-5000, so populate `streetAddress` and `postalCode` from it (subject to the pending SAB decision in `onboarding_notes.awaiting_intake`) and drop `geo` and `foundingDate` until you have real values. In the same block, change `image` and `logo` from `/images/logo.webp` to the absolute `https://allproplumbingheatingandair.com/images/logo.webp`, since structured data requires absolute URLs.

4. **(money pages, LCP)** Fix the hero image on the layout that `/services/`, `/contact/`, `/services/emergency-plumbing/` and `/service-areas/*` share. `hero-bg.webp` is 167,726 bytes with 51KB to 103KB wasted depending on the page, and `lcp-discovery-insight` fails on 5 pages because the LCP image sits in a `div.absolute > img.w-full` with no priority hint. Add `fetchpriority="high"` and a matching `<link rel="preload">` to the hero, and generate width-matched variants via `srcset`. This is the direct cause of the three LCP regressions above.

5. **(template, accessibility)** Raise breadcrumb and body-link contrast. Breadcrumb links use the `text-dark/50` utility, rendering #888c93 on #ffffff at 3.37:1, below the 4.5:1 WCAG AA minimum for normal text. Bump to roughly `text-dark/70` or darker. Separately, inline links inside `div.prose-body > p` have only 1.59:1 contrast against the surrounding paragraph text with no underline, which fails `link-in-text-block`; add `text-decoration: underline` to prose body links. Together these lift accessibility on all 6 pages and would move `/services/` off its site-low 91.

## Notes and caveats

- **Apex audited, so SEO counts.** This run hit the production apex, not a Pages preview, so the staging noindex correction does not apply. SEO scored a clean 100 on all 6 pages and counted toward every verdict.
- **Desktop only.** Lighthouse ran with `formFactor=desktop`. Mobile scores typically run 10 to 20 performance points lower and were not measured, so do not read the 98.5 average as a mobile result.
- **Tooling deviation worth flagging to the methodology owner.** This MCP build exposes only the generic `dataforseo api_request` tool, not the `on_page_lighthouse` and `on_page_instant_pages` wrappers the method assumes. Calls went directly to `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages`, with responses piped to disk and parsed there. The raw API **does** expose a `for_mobile` parameter that the wrapper did not. Desktop was kept this run to stay comparable with the July baseline, but a mobile baseline is now technically available and should be considered for a future run.
- **FAQPage micromarkup flag is unconfirmed.** DataForSEO sets `has_micromarkup_errors` on exactly the 5 pages carrying a FAQPage block, and not on `/`, which has no FAQPage. `/privacy/`, which carries only a BreadcrumbList, reports no errors, which rules breadcrumbs out. Direct inspection of the FAQPage JSON-LD on all 5 pages found it structurally valid: every entry has `@type: Question`, a non-empty `name`, and an `acceptedAnswer` of `@type: Answer` with non-empty plain-text `text`. So this is most likely a validator-level warning rather than broken markup. Confirm in Google's Rich Results Test before spending dev time on it.
- **Severity rubric versus business impact.** The `sameAs` entity mismatch is scored medium because the audit rubric reserves high for broken links, mixed content, and missing or broken canonicals and schema on money pages. The schema here is present and type-correct, so it does not meet the rubric's high bar. Its business impact is nonetheless the highest of anything found, which is why it ranks second in the action list despite the medium label.
- **One retry.** `/services/emergency-plumbing/` returned a DataForSEO Internal Error (status 50000) on the first Lighthouse attempt and succeeded on retry. The failed attempt was not billed.
- **Clean bill of health on the basics.** Across all 6 pages: zero broken internal links, zero broken external links, zero broken resources, no duplicate titles or descriptions, exactly one H1 each, correct self-referencing canonicals, HTTPS with HSTS and no mixed content, and 100% image alt coverage. Word counts beat plan targets everywhere except `/`, which is 1173 against a 1200 target.
