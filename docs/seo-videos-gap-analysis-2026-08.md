# SEO Videos + Citations Gap Analysis (Aug 2026)

Source: two videos from the creator our original systems came from, plus his attached resources
(Website Structure Audit/Blueprint prompts, Site Structure Architect prompt, Area Page Writer
prompt, Area Page Checklist, citation directory screenshots).

- Video 1: https://www.youtube.com/watch?v=7t4HuUfg3Es (structure audit with DataForSEO + Claude)
- Video 2: https://www.youtube.com/watch?v=r0VzvG7N9Ls (2026 local SEO plan: structure, GBP, trust, AI citations)

Status: ON HOLD per Santino 08-18. Nothing below is started unless marked done earlier.

---

## Part 1: Citation priority (which directory next)

Most of the directory list is online phone books. Value = NAP consistency plus a small handful
that actually reach customers or feed AI answers. Already covered: GBP, Bing Places (done),
Apple Business Connect (3 listings in review), Facebook pages.

**Next most important: Yelp, and it's not close.** Our AI-visibility program found ChatGPT and
Perplexity lean on Yelp for "who do I call" emergency answers, the layer we currently lose.
Free to claim. NaRestCo's Yelp overhaul was already flagged top manual item; extend fleet-wide.

Then, in order:
1. Nextdoor Business (neighbors literally ask for restoration recs; free)
2. Foursquare (database feeds Apple, Uber, dozens of platforms; free)
3. BBB (trust with older homeowners + AI "best of" answers; free profile, skip paid accreditation)

Deprioritize: Angi / HomeAdvisor / Thumbtack / Porch / Houzz are lead marketplaces, not citations.
Long tail (Superpages, Yellow Pages, Manta, Hotfrog, Brownbook, Cylex, EZlocal, Citysearch,
MapQuest, Local.com, Crunchbase, Alignable): tiny value each; batch later or outsource (see
BrightLocal below). Chambers of Commerce: real local links but paid membership, per-client call.
LinkedIn company page: free, mild value.

Yelp automation note: claiming requires a verification call/text to the business phone (the
client's real phone under our GBP-primary policy), so the playbook needs light client
coordination, same pattern Monica already handles for other verifications.

## Part 2: Our fleet vs. his structure rules (verified against built sites)

Audited Reign's dist in depth; spot-checked NaRestCo, Air Care, Home Pride, Flood Fixers, Crew.

Already passing (his own architecture, which we built from):
- One page per service under /services/; area pages at /service-areas/{city}-{state}/
- Service-plus-city pages; hub-and-spoke links both directions
- Search-phrase H1s ("Water Damage Restoration in Dallas"), unique titles
- Area page uniqueness: Dallas vs Plano measured at 16% shared 6-gram phrasing (his bar: under
  50% shared). Content genuinely local (Blackland Prairie clay, 1920s Tudors in Lakewood/M Streets,
  named neighborhoods)
- Schema: LocalBusiness, Service, FAQPage (service + service-city pages), BreadcrumbList
- Map embed, 24/7 banner, sticky mobile tap-to-call bar, NAP on page, sitemaps

### Gaps found (ranked)

1. **Home-city cannibalization, fleet-wide, two levels.** Every home page targets "Restoration
   Services in {home city}" AND every site also builds /service-areas/{home-city}/ with the
   identical H1/title. Deeper: main /services/{service}/ pages target service + home city, and
   /service-areas/{home-city}/{service}/ pages target the exact same phrase. Two of our own pages
   compete for every home-city search. Confirmed on all 6 sites checked. Fix: skip home city in
   plan_site.py's area + cross-product loops (expand_ia, ~lines 405-427; home city =
   brand.primary_city) for new builds; 301 existing home-city pages into home + main service
   pages for live sites; update internal links + sitemaps.
2. **Area hub pages have no FAQ section** (checklist MUST: 4-6 locally specific Q&As + FAQPage schema). Ours live on service and service-city pages only.
3. **No recurring "wrong page ranks" check**: keywords at positions 5-30 where homepage/blog ranks instead of the money page. We have DataForSEO + GSC; belongs in the monthly loop.
4. **Area pages not fed by real jobs.** His moat: pages built from jobs actually done there. Wire
   case-study intake + photo intake into the matching area page ("Recent work in {city}") over time.
5. Smaller: city-matched review quotes on area pages (we have GBP review data); nightly NAP
   byte-for-byte parity assert vs GBP; "last updated" freshness stamp.

## Part 3: What the videos add beyond the docs (verified against our tooling)

Already ours: GBP services named exactly as site pages = gbp_site_parity.py; his review-reply
guardrail (negatives never auto-post) = review_responder.py exactly; YouTube-most-cited-by-AI =
System 5 pilot; fan-out-query content = roughly System 0; review QR card = hub card.

Adopt (all small):
1. **Review card wording** (best idea in either video): ask happy customers to mention the service and the city in their review. Feeds Google's Ask Maps "review justifications" and AI matching. One copy change: hub request-a-review screen + physical cards.
2. **GBP posts should deep-link.** gbp_post.py due-mode CTA falls back to the homepage
   (create_local_post line ~159: cta_url or websiteUri). When a post spotlights a service, link that service page; blog-repurposed posts link the post.
3. **Post cadence 2x -> 3x per week** (currently Mon + Thu via weekly-maintenance.yml).
4. **Connect clients' YouTube/social accounts in Search Console** (new GSC feature).
5. **BrightLocal for junk-tier citations** at roughly $2-3 each instead of browser-agent playbooks for fifteen low-value directories. Keep Yelp/Nextdoor/BBB/Foursquare/Apple in-house. Needs Santino's yes (per-client spend). BrightLocal was already in the standing build queue.
6. Minor: review_responder cadence is 2x/week (rides weekly-maintenance); his is daily. Could move to daily for reply latency.

Contradiction between his videos, our call: Video 2 says don't build service-in-city pages unless the niche is extremely competitive; Video 1's case study builds city/niche pages freely. Emergency restoration IS the competitive carve-out, and our grid clears his uniqueness bar, so keep the grid.
The home-city duplicates are the pages that genuinely waste effort (see gap 1).

Volume note: Video 1 explicitly says 0-10 monthly searches is still worth targeting (specificity beats volume), which matches restoration reality and overrides his written blueprint's volume-gating.

## Queue recommendation

1. ~~Home-city cannibalization fix~~ DONE 2026-08-18: plan_site.py skips the
   primary area for all future builds; scripts/home_city_migrate.py folded
   home-city pages on 23 sites (301s to home + main service pages), deployed
   to production AND staging branches fleet-wide, live-verified on
   reign-restoration.com, crew3r.com, narestco.com, gogreenrestorationofnc.com
   and therestorationgroup.com; work_log lines written for all 23 clients.
2. Yelp claiming playbook (browser agent, supervised runs)
3. Area-page FAQs (FAQPage schema on area hubs)
4. Wrong-page-ranks monthly check (DataForSEO + GSC)
5. Small batch: review-card wording, GBP post deep links, third weekly post slot, GSC social
   connections
6. Santino yes/no: BrightLocal spend for long-tail citations
