# Onsite Audit - The Restoration Group - 2026-09-24

**Live origin audited:** https://therestorationgroup.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-09-07
**Form factor:** desktop only (DataForSEO Lighthouse wrapper). Mobile scores would typically run 10-20 performance points lower.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 97.3 | -0.3 |
| Accessibility | 90.0 | -4.8 |
| Best Practices | 98.0 | -2.0 |
| SEO | 100 | 0 |

Pages by verdict: {green: 5, amber: 1, red: 0, error: 0}

Accessibility fell almost 5 points site-wide (over the 3-point site-level threshold). The cause is one new template defect: an empty header logo link and an empty email link on every page. The Best Practices dip is a crawler proxy artifact (see Notes), not a site change.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | amber | 89 | 88 | 100 | 100 | 0.86s | 0.219 |
| /services/ | services-hub | green | 99 | 90 | 96 | 100 | 0.91s | 0.004 |
| /services/water-damage-restoration/ | service-landing | green | 99 | 90 | 100 | 100 | 0.89s | 0.006 |
| /services/fire-damage-restoration/ | service-landing | green | 98 | 90 | 100 | 100 | 1.19s | 0.006 |
| /service-areas/union-nj/ | service-area | green | 99 | 91 | 96 | 100 | 0.88s | 0.057 |
| /contact/ | contact | green | 100 | 91 | 96 | 100 | 0.53s | 0.044 |

TBT is 0 ms on every page. INP was not returned (lab run with no interaction).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `link-name` | 6 | high | Put the logo `<img alt="The Restoration Group">` or brand text inside the header `<a href="/">`. Render the email row only when the email value is non-empty. |
| `color-contrast` | 6 | medium | Darken `.text-primary` footer links from #1498d5 (3.23:1) to at least #0b6fa0 (about 5.3:1 on white), or apply the darker shade only in the footer. On /service-areas/union-nj/, swap `text-slate-400` for `text-slate-500` or darker. |
| `render-blocking-insight` | 6 | medium | Delete the second, blocking `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter...">`. The async `media="print" onload` copy already loads the same file. |
| `unused-javascript` | 6 | medium | GA4 gtag.js ships 69 KB unused. Load it after the `load` event or through Partytown. On /services/fire-damage-restoration/ it costs an estimated 150 ms of LCP. |
| `lcp-discovery-insight` | 3 | medium | Add `fetchpriority="high"` (keep `loading="eager"`) to the hero `<img>` in the service-landing template, and to the first service card on /services/. |
| `image-delivery-insight` | 3 | medium | Generate 400w card variants and add `sizes="(min-width:1024px) 400px, 100vw"` on the hub grid (est 109 KB). Add a srcset to service-landing hero images (water hero 71 KB, est 36 KB saving). |
| `forced-reflow-insight` | 4 | low | 32-49 ms of unattributed reflow. Low priority. Recheck after the font fix. |

## Money page alerts

- **`/`** - verdict: amber. Performance 89, CLS 0.219 (poor; reproduced at 0.214 on a second run), accessibility 88. When the Inter web font swaps in, the hero copy block (`main > header.relative > div.container-wide`, shift score 0.207) reflows. Inter is loaded twice with `display=swap` and has no metric-matched fallback font. Accessibility also loses points for the empty logo link, the blank footer email link, footer contrast at 3.23:1, and `link-in-text-block` (inline service links in the dark section are 1.08:1 against the surrounding text).
- **`/contact/`** - verdict is green on the rubric, but the conversion page has a visible defect: the "Email" card in the contact panel is blank (empty anchor). See action 2.

## Regressions vs prior audit

**Verdict transitions:** none. All 6 URLs kept their September verdict (home amber, the other 5 green).

**Score regressions (5-point drop or more):**
- Accessibility down 5 on `/` (93 to 88), `/services/` (95 to 90), `/services/water-damage-restoration/` (95 to 90), `/services/fire-damage-restoration/` (95 to 90) and `/contact/` (96 to 91). `/service-areas/union-nj/` fell 4 (95 to 91). All caused by the new `link-name` failure.

**Core Web Vitals regressions:**
- `/`: CLS 0.155 to 0.219 (+0.064). Same culprit as September (hero copy reflow on Inter font swap), now larger. Performance 92 to 89.

**New issues this month:**
- All 6 URLs: `link-name`. Header logo `<a href="/">` is empty, and the footer email `<a>` renders empty. `/contact/` also has an empty Email link in the contact card.
- `/`: `link-in-text-block`. Inline service links in the dark section differ from body text by color alone (1.08:1).
- `/services/`, `/service-areas/union-nj/`, `/contact/`: `errors-in-console`. These are net::ERR_SOCKS_CONNECTION_FAILED crawler proxy errors, not site errors (see Notes).

**Issues resolved since last audit:** (positive - keep doing this)
- LocalBusiness JSON-LD now publishes 500 S 31st St, Kenilworth, NJ 07033 on every page, and the Union NJ map embed now points at Kenilworth instead of Fair Lawn. This closes the high-severity NAP conflict open since July.
- Static HTML and schema telephone are now +1 855-650-7422, the GBP line. (908) 970-8533 no longer appears anywhere.
- schema `sameAs` no longer lists the pre-rebrand Elite Restoration Group profiles.

## Recommended next actions (priority order)

1. **(money page, home)** Stop the Inter font swap from moving the homepage hero. Self-host Inter (for example `@fontsource-variable/inter`) with `<link rel="preload" as="font" type="font/woff2" crossorigin>`. Add a metric-matched fallback `@font-face` (Arial with `size-adjust`/`ascent-override`, as generated by `fontaine` or Astro's font fallback), and delete both Google Fonts `<link>` tags. Target: CLS below 0.1 and performance back above 90. This also clears the render-blocking font stylesheet on every page.
2. **(money page + template, high)** Fix the blank email. The site's email value is empty: the Cloudflare email-protection href holds no address, and JSON-LD emits `"email": ""`. The 7/15 onboarding notes say "email stays office@restorationgroups.com", but `contact.email` in the client record is `mikior7@gmail.com`, a personal Gmail. Confirm office@restorationgroups.com with the owner and set it as the site email. Until then, change the template to hide the footer email row, the /contact/ Email card and the schema `email` property when the value is empty.
3. **(template, high)** Restore the header brand. The sticky-header `<a href="/">` contains nothing, so no logo or name shows on any page. Add the logo image with `alt="The Restoration Group"` (or the brand name as text) inside that anchor. Actions 2 and 3 together clear `link-name` on all 6 pages and should recover about 5 accessibility points site-wide.
4. **(template, medium)** Fix footer contrast. Change footer `.text-primary` links (phone, Services, Emergency) from #1498d5 to a shade with at least 4.5:1 on white. On the homepage dark section, underline the inline service links so they no longer rely on color.
5. **(per-page, medium)** Shorten the homepage meta description from 188 to 150-160 characters (open since July). In the service-landing hero template, add `fetchpriority="high"` to the hero `<img>`. This page type has the site's slowest LCP (1.19s on fire damage).

## Notes / caveats

- Desktop-only Lighthouse (formFactor=desktop), same as prior runs, so deltas are like-for-like.
- The on_page_lighthouse / on_page_instant_pages MCP wrappers were not available. The audit called the DataForSEO REST endpoints directly with the same parameters and saved the full responses to disk before parsing.
- The homepage was audited twice to confirm the CLS finding: run 1 CLS 0.2192, run 2 CLS 0.2142, same culprit node and performance 89 both times. The state file records run 1.
- Best Practices 96 on /services/, /service-areas/union-nj/ and /contact/ comes only from `errors-in-console` entries reading net::ERR_SOCKS_CONNECTION_FAILED. That is the DataForSEO crawler's proxy failing, not a site resource. No action needed.
- Call tracking: Lighthouse sees tel:+19083419611 because an inline swap script replaces (855) 650-7422 at runtime. Static HTML, footer NAP and schema all carry the GBP line, so this is intended tracking and not a NAP defect.
- Still open for an owner decision: `sameAs` lists both Google cids (Kenilworth 8008820373441604497 and Fair Lawn 5612453956771500683), plus Yelp (Highland Park) and HomeGuide (Paterson) listings in other towns. The services hub and service-landing titles still target Kenilworth while the homepage uses NJ/NY/PA framing.
- Service-landing slot: fire, mold and water tie at url-plan priority 9.0. Water and fire were kept so the comparison with the baseline holds.
- No broken links, no mixed content, one H1 per page, self-referencing canonicals and HSTS present on all 6 URLs. Alt text coverage is unchanged (the `no_image_title` flag is the cosmetic title attribute, not alt).
- Run cost: about $0.046 (7 Lighthouse calls + 6 instant_pages calls).
