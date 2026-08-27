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

**QBA operating procedure** (tracked as `quality_business_awards` in
citation_listings, shows in the app's Business Listings build-out queue):
1. Apply at https://qualitybusinessawards.com/request-consideration (free).
   Only submit clients holding a REAL 4.8+ Google average (their criteria:
   review quality across Google/Facebook/Yelp, low complaints, multi-year
   record). Never submit a client below 4.8.
2. They evaluate; on acceptance the award page costs $30 (Santino's card).
3. On acceptance: pay, grab the award-page URL, flip the citation_listings
   row to live with the URL, add the URL to the citation tracker + IndexNow
   ping, and (optional) badge on the client site footer.
4. Cadence: one client per batch, only after their review campaign has
   pushed them solidly over 4.8 with volume. Pro = pilot.
| Press releases | **38 Digital Market first** (AP News, Digital Journal, Google News), EIN Presswire second ($999/15 = $67 ea, explicit "AI/LLM platforms" distribution). IssueWire = never (own-network PBN) | We write (press_release.py drafts, app approval + Download .docx), Santino submits + pays | **ORDERED 08-26/27 for Pro**: Standard $97 + Do-Follow $60 + Podcast $45; intakes submitted (podcast order CE21B016_3, company-name link field). Await placement-URL report -> citation tracker. Verify Jack OK'd the quote before publication (editable via order ticket) |
| Owned social surfaces | FB posts w/ NAP burned into images + link in first comment; native FB video uploads; best-of listicle posts; per-client podcast feed (System 5 audio → RSS → Spotify/Apple = DR16-class links) | Content engine additions | TO BUILD: podcast layer + FB mechanics |
| Local FB groups | Personal-profile recommendation posts in public "{city} reviews/recommendations" groups are AI Mode-citable. Path: client OWNER posts, or genuinely happy customers asked at the thank-you step. We draft copy. NOT us astroturfing from fake/staff profiles | Manual, per campaign | Santino joined the Bakersfield group; Pro first. 08-27: default format switching to DIRECT owner-voice post modeled on the cited Enid example (FB post is login-walled to us — Santino pasting text; question-thread stays as the alternate). App drafts to be regenerated on the new template |
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

1. **Jack's customer list** → review campaign: **LIVE 2026-08-27.** Jack's
   Encircle export (1,516 rows → 1,357 clean contacts, names hand-sanitized)
   staged via the app, activated by Santino. Sender: pool number Highridge
   +18338929547 (pinned for campaign lifetime), pace 3/20min, filter page ON,
   tz America/Los_Angeles (was NULL = would have texted at 5am PT). THE
   lever: gap is ~450 reviews; at ~35%% review-rate ceiling this list alone
   can close most of it.
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

## 38 Digital Market ordering gameplan (2026-08-26)

Their menu decoded: 3 base tiers (Standard $97 / Advanced $197 / Premium
$487), bundled "Power Packages", and ~12 add-ons.

**Round 1 (Pro, order now): Standard PR $97 + Do-Follow Distribution $60 +
Podcast Publishing $45 ≈ $202.** Standard already carries the citable core
(Google News, 50+ ABC/NBC/FOX affiliate sites, local newswires); Do-Follow
turns placements into followed links; Podcast adds the entity surfaces we
want. Submit OUR prepared copy (one release = one client) + NAP + site URL
+ logo. Ask for the full placement-URL report (feeds the citation tracker,
and it is the future tier-2 target list if the gray lane ever activates).

**Skip**: Premium $487 (Yahoo/Benzinga finance angle, irrelevant for local),
Google Stacks / Cloud Site Stacks add-ons (unproven entity-stack lane),
PR Booster Links (tier-2 blast — gray lane on hold), Canada/International/
Benzinga/Crypto add-ons, a-la-carte featured articles $197 (38DM's own
guest posts at $20-95 are the better version). **APNews add-on $75** only
if round 1 shows AP didn't come through standard distribution.

**Measure after round 1** (2-3 weeks): indexed placements, AP pickup,
referring domains on the release, whether the release URL shows in AI
answers. Then either make the $202 trio the quarterly per-client standard
or drop to Standard-only $97.

## Facebook group post playbook (modeled on the cited Enid post)

The AI-cited unit = a personal-voice post in a PUBLIC local
reviews/recommendations group naming the business with specifics. Templates:

- **A. Owner voice (Jack)**: "Hit a milestone I'm proud of — ProRestoration
  just passed 100 five-star Google reviews. 15(?) years of Bakersfield
  homes and businesses trusting us with water and fire damage. If we've
  ever helped you out, it'd mean a lot if you shared your experience here
  or on Google." + crew/team photo.
- **B. Question thread (honest, anyone)**: "Who's the best water damage
  restoration company in Bakersfield? Pipe burst horror stories welcome."
  The REPLIES naming the business are the citable content. Jack + real
  customers answer.
- **C. Customer voice**: added to the review thank-you flow — "if you're in
  {group}, a quick mention there helps other locals find us."

Guardrail: we never post first-person customer recommendations from our
own or staff profiles. Group must be PUBLIC or Google/AI can't read it.

## Standing watch items

- James Ranks (@jamesrankseverything) new weekly videos — SEO Neo results
  diary. Check weekly through September, fold findings into the gray lane.
- BrightLocal thread (Emily Hamblyn, ticket 728727).
- QBA acceptance + $30 payment step (Santino).
- ContractorsRanked pilot: capture the lead-billing terms during listing
  creation before any fleet rollout.
- GSC "Generative AI" API surface (probe queued in weekly maintenance).
