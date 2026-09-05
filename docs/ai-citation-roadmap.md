# AI Citation & Rankings Roadmap

Living gameplan. Started 2026-08-26 from the Bakersfield research sprint
(ChatGPT/AI Overview screenshots + award-site investigation + the James Ranks
8-video series analysis). Update as results land. Companion data:
`review_campaign_stats` view + `review_count_history` table in Supabase.

## The mechanism (what each AI engine actually reads)

- **ChatGPT**: classic third-party authority — Yelp, BBB, Angi, Houzz,
  Birdeye, plus curated listicles (Expertise.com). Review counts quoted
  directly.
- **Google AI Mode / AI Overviews**: indexable third-party validation pages —
  listicles, award pages, even personal-profile Facebook posts in public
  local groups (verified in the Enid case study: a $30 award page and an FB
  group post both appeared in the citation pack).
- **Gemini**: reads Google Maps. Same battle as the map pack: review count,
  rating, categories, photos.

Everything below feeds one of those three lanes. Review mass is the common
denominator of all three.

## Source stack (the system)

| Layer | What | How it runs | Status |
|---|---|---|---|
| Reviews | Review reactivation engine (sender pool, filter page, staged lists) | App, live | RUNNING (RT Olson 6,667 @4/20; Dry County 1,248 @3/20; default pace 3) |
| High-value directories | Yelp, BBB, Angi, Houzz, ThreeBestRated, TrustAnalytica, Facebook, HomeGuide, Bing, ContractorsRanked | Browser agent, nightly rotation + supervised runs | threebestrated/houzz/trustanalytica seeded fleet-wide 08-25 (21 clients each); contractorsranked = Pro pilot (watch lead-billing terms) |
| Long tail + aggregators | Data Axle, Localeze, Foursquare, voice assistants, DexKnows-class directories | **BrightLocal Citation Builder via API** (persist after cancel, we pick directories) | Emily Hamblyn thread reopened 08-26; subscribe to a plan w/ API (Track/Manage/Grow all include API; 250-req trial key; CB-via-API may need Enterprise — asked) |
| Award pages | Quality Business Awards ($30 on acceptance, indexed, dofollow, one proven AI Mode citation) | Manual application per client, 4.8+ real ratings only | Pro queued as pilot (payment needs Santino). businessrate.com = SCAM, never pay |
| Press releases | **38 Digital Market first** (AP News, Digital Journal, Google News; $97 std / $197 PR Booster w/ tier-2s + podcasts + entity stack), EIN Presswire second ($999/15 = $67 ea, explicit "AI/LLM platforms" distribution). IssueWire = never (own-network PBN) | We write (press_release.py drafts, app approval), Santino submits + pays | Pro release LIVE 09-01 ($202 std+dofollow): 493 pickups = Digital Journal (the 1 strong domain) + 47-site Big News Network syndicate + long tail; NO AP News; dofollow links to prorestorationca.com confirmed; published copy has a truncated Google-reviews link (ask Randy to fix). Bulk/agency pricing email SENT to randy@ 09-04 (5-10/mo volume) — awaiting reply; 38DM-vs-EIN alternation decision hinges on how this release indexes (~09-15 check). |
| Owned social surfaces | FB posts w/ NAP burned into images + link in first comment; native FB video uploads; best-of listicle posts; per-client podcast feed (System 5 audio → RSS → Spotify/Apple = DR16-class links) | Content engine additions | TO BUILD: podcast layer + FB mechanics |
| Local FB groups | Personal-profile recommendation posts in public "{city} reviews/recommendations" groups are AI Mode-citable. Path: client OWNER posts, or genuinely happy customers asked at the thank-you step. We draft copy. NOT us astroturfing from fake/staff profiles | Manual, per campaign | Santino joined the Bakersfield-relevant group; Pro first |
| Measurement | review_campaign_stats view, review_count_history (daily 03:30 UTC pg_cron), geo-grid, AI-answer citation loop (add "best water damage restoration bakersfield") | Automated | LIVE 08-25 |

## Adopted vs avoided (from the James Ranks series analysis)

**Adopted**: 38 Digital Market; podcast layer; FB post mechanics (NAP-in-image,
link-in-comment, native video); local guest posts w/ map embeds ($20-95, via
38DM); cheap-listicle awareness; free-trial-lead sales framing (for our own
prospecting).

**Avoided, permanently (real clients, real risk)**: fake reviews; expired-GBP
hijacking; bought followers; fabricated personas; PBN links at client sites;
CTR / "Chrome virality" manipulation (unproven even in his own footage).

**Gray lane, approved in principle (Santino 2026-08-26), CONTAINED targets
only**: tiered link pyramids (t3→t2→t1→cloud/"bunny" site→GOOGLE LISTING).
Rules of engagement: link juice may ONLY point at (a) the client's Google
Maps URL / GBP embed, (b) third-party pages about the client (award pages,
listicles, press releases, citations). NEVER the client's own domain. Maps
URLs can't be penalized the way a domain can, and third-party pages are
disposable; worst case = wasted spend. Trigger to actually start: James
Ranks' next month of documented SEO Neo results (free R&D, we're watching
his channel through late September), or a citable third-party page that
stalls unindexed after IndexNow + time. Tool if triggered: SEO Neo $149/mo
or a one-off tier-2 package aimed at the third-party pages.

## Bakersfield: ProRestoration to #1 (the pilot war)

Standings (08-25, from Pro's coordinates): #6. Ahead: 911 Restoration
(4.9/316, 152 photos), Alert Disaster (4.9/553), Paul Davis Bakersfield
(5.0/46), two thin listings. Pro: 4.8/106, 45 photos. ChatGPT already names
Pro as an "other excellent choice" (BBB A+ doing the work).

1. **Jack's customer list** → review campaign (own approved TF +17605128274,
   filter ON, photo ON). Monica's ask to Angie is queued. THE lever: gap is
   ~450 reviews.
2. Citations queue (already seeded): Angi > ContractorsRanked >
   homeservices.review > Expertise portal application > QBA.
3. 38DM press release (draft ready, above).
4. FB: page posts via content engine + owner posts in local groups.
5. GBP: photos 45 → 150+ (crew hub), categories audit.
6. Watch: geo-grid weekly + AI-answer checks + review_count_history.

## Vendor decision log

- **BrightLocal**: replied to Emily 08-26 asking plan rec + CB-API scope +
  agency pricing at 20→50 locations. Subscribe when she answers (or sooner,
  any API plan, and start on the 250-req trial). They answered BOTH earlier
  tickets same-day; the failure was our unread inbox.
- **Merchynt Paige (Rob's screenshots)**: PASS. Competitor white-label,
  aggregator-reseller under the hood, rented sync, and it's the tool behind
  NaRestCo's double-posting mess.
- **EIN vs Press Advantage vs 38DM**: 38DM single ($197) first for Pro,
  measure indexed placements vs cost, then pick the fleet workhorse
  (likely EIN 15-pack for volume + 38DM Booster for pushes). Press
  Advantage only if we later want an always-on org page ($349+/mo).
- **SEO NEO**: hold. Watching James Ranks' documented results through
  ~late Sept 2026.
- **businessrate.com**: never (vanity mailer mill, non-indexable trophy).

## Standing watch items

- James Ranks (@jamesrankseverything) new weekly videos — SEO Neo results
  diary. Check weekly through September, fold findings into the gray lane.
- BrightLocal thread (Emily Hamblyn, ticket 728727).
- QBA acceptance + $30 payment step (Santino).
- ContractorsRanked pilot: capture the lead-billing terms during listing
  creation before any fleet rollout.
- GSC "Generative AI" API surface (probe queued in weekly maintenance).
