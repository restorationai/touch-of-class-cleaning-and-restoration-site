# What Rank AI Adds Beyond the TDI Website Architecture SOP

Prepared 2026-08-23 for the TDI Builders kickoff meeting (Rob Carpenter).
The SOP (v1.0, May 2026) is excellent and we execute it nearly as written.
This document lists what our system delivers that the SOP does not ask for,
plus the three decisions and the access list we need from TDI.

## Things we add that the SOP does not cover

1. **AI search visibility (Google AI Overviews, ChatGPT, Perplexity)**
   - llms.txt on the site so AI assistants can read and cite TDI accurately
   - Emergency-intent pages engineered for AI answer engines, not just
     classic rankings; citation-target content formats (best-of, cost,
     who-to-call, case-study rotation)
   - IndexNow pings on every deploy so Bing and AI crawlers see new pages
     within minutes instead of weeks

2. **Automated Google Business Profile management**
   - Posts published on schedule, photo pipeline from field crews
     (EXIF/GPS stripped automatically), services kept in parity with site
     pages, review responses
   - The SOP asks for monthly manual GBP review; ours runs continuously

3. **Review reactivation engine**
   - Past-customer SMS campaigns with a branded feedback page (logo,
     sentiment routing, private feedback capture with manager alerts)
   - Live Google rating and review count sync into the site weekly, which
     also satisfies the SOP's "review schema pulling live from GBP" line

4. **Geo-grid map rank tracking**
   - Weekly map-pack position scans across the service radius, visible in
     the client dashboard; the SOP only tracks classic keyword rankings

5. **Biweekly plain-language performance analysis**
   - Written analysis of search, maps, GBP and calls delivered in the
     dashboard every two weeks, not just a monthly GSC check

6. **Launch press release + citation building**
   - Press release drafted at launch; directory citations built and
     verified on a nightly rotation (the SOP lists "top 50 citations" as a
     one-time task with no verification loop)

7. **Truth-enforced copy**
   - Automated claims lint: the build fails if a page claims a license,
     certification, or capability not in the client truth table. This is
     the SOP's "Marketing-Operations Rule" enforced by machine instead of
     by quarterly audit.

## Decisions we need from Rob

1. ~~Platform~~ — settled: our Astro static build on Cloudflare Pages
   (beats every performance target in SOP Section 7; removes the
   WordPress plugin/malware/WAF maintenance burden entirely)
2. **Phasing**: SOP Phase 1 is 22 pages over 3 months. Our content engine
   produces genuinely unique pages automatically, so we propose launching
   roughly half the architecture up front (~275 pages: full
   residential + commercial + insurance silos, top 15 cities x 7
   services, Sacramento neighborhoods, about/trust/contact), with the
   remaining cities, industry verticals, and expert services rolled out
   as the ongoing-content story.
3. **Futura PT licensing**: needs an Adobe Fonts/Monotype web license from
   TDI, or we ship the SOP's own approved fallback (Inter) until then.

## Access + inputs we need from TDI

- **CSLB license number** (not on the current site and not in the SOP;
  site carries a placeholder until received and cannot cut over without it)
- **HubSpot** (portal 48033708): either a user seat for
  contact@restorationai.io, or the form GUIDs for estimate / commercial /
  adjuster forms so submissions post into their CRM with full attribution;
  we embed their tracking code either way
- **CallRail**: account invite (or the DNI snippet) so tracked numbers
  render per traffic source as the SOP specifies
- **tdiusa.com DNS control** (registrar/zone access) for the cutover, and
  Scorpion coordination for the 301 redirects off buildwithtdi.com
- **Google Business Profile access** + Search Console for both domains
- Photography drive access (their SOP's DAM) for real project imagery
