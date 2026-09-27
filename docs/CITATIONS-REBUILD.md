# Citations System Rebuild — confirmed outline (Santino, 2026-09-26)

The reference doc for the citations rebuild. Companion docs:
docs/MINI-CITATIONS-PROGRAM.md (Mini operator program),
docs/MINI-OPERATOR.md (standing orders), scripts/brightlocal.py (bought
layer), scripts/citations_audit.py + citations_sync.py (feedback loop).

Confirmed facts this plan stands on (verified 09-26): credits cost
$2.40 each ($1,200 / 500 bundle, Harvey Godden email 09-04); balance 236;
each aggregator = 15 credits ($36), annual, ladder discount at 3+;
BL menu = ~117 sites, scored tier tops out ~DA 87 after Google/Yelp;
BBB, Angi, Facebook, Nextdoor, Thumbtack, Houzz are NOT BL-orderable;
maps.apple.com is in the menu but unscored (was never auto-picked);
BL attempted to CREATE a Google listing for Dry Bros (duplicate risk).

## 1. The $100/month ladder (confirmed)

Fired per client when their name is settled (rename-complete or launch).
Never exceeds ~$108 in a month; total ~$264 over three months; a real
deliverable every month. Aligned to retention: a client who stays 3
months gets the full stack.

- **Month 1 — rename authority wall (~$108 paid + $0 owned layer)**
  - BUY: aggregator trio in ONE order (3+ ladder discount): Data Axle,
    Neustar/Localeze, YP Network (45 credits). YP goes live fast
    (yellowpages + dexknows + superpages — Kenneth proof, live under his
    full keyworded name).
  - MINI (free, same month): Bing Places, BBB claim/create,
    chamberofcommerce.com (already a Connect-tab handled listing),
    Houzz, and **Apple Business Connect directly** (owned listing beats
    BL's Apple data submission; skip Apple in BL orders entirely).
- **Month 2 — remaining feeds + visible breadth (~$96)**
  - BUY: Foursquare + GPS Network (30 credits — eligible now that
    addresses are visible) + hand-picked cb10 of the top-scored
    directories (10 credits).
- **Month 3 — completion (~$60)**
  - BUY: cb25 top-off of the remaining scored tier, deduped against
    everything already live.
  - MINI: editorial one-offs (ThreeBestRated, TrustAnalytica — the
    AI-citation gold).
- After month 3: NOTHING recurring except the annual aggregator renewal.
  The live-checker triggers reactive gap-fills only when listings die.
  Recurring budget goes to the reviews program instead (decided 09-26).

## 2. Ordering rules (bake into brightlocal.py)

1. **google.com EXCLUDED always** — we own GBP; BL created a listing for
   Dry Bros ("will go live once verified") = duplicate-suspension risk.
   Follow-up: check Dry Bros GBP for a BL-spawned duplicate.
2. **yelp.com STAYS in picks** — BL is currently our only working Yelp
   mechanism (no creds, no API, one bot-walled fix attempt on record).
   Revisit only when the Mini Yelp lane has 3 clean supervised runs.
3. **Apple via Business Connect (Mini), never via BL credits.**
4. **Addresses VISIBLE by default** (makes Apple + Foursquare + GPS
   Network viable and strengthens every submission). Per-client opt-out
   reserved for genuine home-address privacy cases only — record the
   opt-out on plan-input, and those clients skip Apple + the two
   non-SAB feeds.
5. **Dedupe before every order** against citation_listings + prior BL
   campaigns + the audit's found listings.
6. Wire BL create-secondary-campaign (a location's first campaign is
   one-shot; months 2/3 need it).

## 3. NAP phone policy (CORRECTED 2026-09-26 — Santino overruled the tracking-number idea, and he is right)

System truth (verified): the canonical NAP number is the REAL business
line — it is what the website JSON-LD/schema carries (DNI displays the
tracker visually but schema keeps the real number), and on GBP the
tracker is primary ONLY because Google explicitly sanctions that pattern
via the real number sitting as the additional/secondary number.

Policy: **citations and aggregators carry the REAL business number.**
Reasons: (1) it matches the site schema and the GBP additional number —
the two anchors Google reconciles against; (2) aggregator feeds
propagate for months and are nearly impossible to claw back — an
agency-owned tracking number pushed through Data Axle/Neustar becomes a
churn liability with a huge blast radius; (3) citation-call attribution
is low-volume nice-to-have, not worth the risk.

Tracking numbers in citations are allowed in exactly ONE role: as the
**verification/account contact** during signup (the number that rings
lines we answer), wherever a platform distinguishes contact phone from
displayed business phone. Where a platform has only one phone field, the
real number goes in and verification rides the code-relay instead.

## 4. Verification-code relay (outline — TESTS FIRST)

Purpose: platforms that text a one-time code to the CLIENT's own phone
(BBB claim, some directories). Email codes to setup@ are already
machine-read; codes to our GBP-primary numbers already land in systems
we control. This covers the last gap.

Build pieces:
1. **Consent ask (Monica)**: "We're setting up your {platform} listing.
   A verification code will come to your phone — reply here when you're
   free and we'll fire it." Nothing runs until the client says yes
   (codes expire ~10 min; consent-first guarantees they're holding the
   phone).
2. **Task activation**: the yes flips a mini-inbox task from
   `code-wait-parked` to `active` (ops_kv mirror so the Mini sees it
   without a git pull).
3. **Code capture**: client texts the code to Monica; the inbound
   webhook writes it to ops_kv `verification-codes:{company_id}`
   {code, platform, at} (10-minute TTL).
4. **Mini consumption**: mid-run, the Mini polls the key (2-3s
   interval), enters the code, clears the key, logs the outcome to its
   daily report.
5. **Failure paths**: code never arrives -> Mini aborts cleanly + files
   a retry task; wrong/expired code -> one re-request through Monica,
   then park + flag.

Test plan (in order, before any client):
- T1: dry loop — fake task, Santino texts a fake code to the canary,
  verify webhook -> ops_kv -> Mini poll round-trip and TTL expiry.
- T2: live claim on OUR OWN listing (Restoration AI / Rank AI test
  entity) end-to-end.
- T3: first client run, supervised (Santino present), BBB claim for a
  friendly client (narestco per the standing re-test batch).
- Graduation per the 3-supervised-runs rule before autonomous use.

## 5. Household / owned lanes (Mini) — month-1 set

Bing Places (GBP import), BBB claim-or-create (+ rename edits through
the claimed profile — DBA certificate is the documentation BBB wants),
chamberofcommerce.com (already a handled Connect-tab listing — badge
"we handle this"), Houzz, Apple Business Connect. Client-identity
re-test batch (Angi, Nextdoor, Thumbtack, Facebook) continues per
MINI-CITATIONS-PROGRAM.md.

BBB Accreditation (~$500-1,000/yr, chapter-dependent, seal only, no
citation value) = client-paid upsell, never our cost.

### BBB pilot tests (Santino 2026-09-26)

Audit data (40 clients): real unclaimed bbb.org profiles exist for
Coastal, Crew, DISS, Desert Valley, Heritage, Life Savers, NaRestCo
(+ hands-off Go Green, Paul Davis). Wrong-entity namesakes flagged for
All Pro, CRW, Home Pride (Idaho) — NEVER claim those. (Audit noise: a
few "found" rows point at Facebook/YouTube — audit URL-quality fix
queued.)

- **Claim test: NaRestCo** (real profile, bbb.org/us/wa/federal-way, and
  already the designated supervised re-test client). Flow: claim ->
  email/phone verification (setup@ + answered lines; code-relay if it
  texts the client) -> update NAP per policy above. Backup candidate:
  Heritage — bonus value there is testing the RENAME EDIT on a claimed
  profile later (DBA cert as documentation).
- **Creation test: Dry Bros** (no profile, brand-new company). BBB
  add-a-business flow under the final keyworded DBA name — a BBB profile
  born under the exact chosen string, the founding-client pattern at its
  best. Expect BBB vetting (days-to-weeks, possible verification call ->
  our answered lines).
- Both supervised-first per the 3-runs rule; file per-run verdicts in
  the Mini daily report.

### Wrong-entity namesakes — QUEUED FOR REVIEW (Santino, get back to this)

Three clients have BBB profiles that belong to DIFFERENT companies with
similar names. Never claim these; review later and decide per case
(ignore / monitor for confusion / disambiguation steps):

1. **All Pro Plumbing Heating and Air** — bbb.org/us/ca/ontario/...
   (an Ontario, CA plumber that is not Jack's company)
2. **California Restoration West** — bbb.org/us/ca/camarillo/...
   (a Camarillo restoration co; Chris's CRW is not this entity)
3. **Home Pride Restoration and Cleaning** — bbb.org/us/id/rigby/...
   (an IDAHO namesake — same one that likely caused the wrong-logo
   bucket file in August)

Related data-quality item queued with it: citations_audit "found" rows
sometimes carry junk URLs (FFS -> a Facebook post, MCC -> YouTube,
Davis -> their own site) — tighten the audit's URL validation so only
real profile URLs count as found.

## 5b. The full platform registry (Connect-tab owners, snapshot 09-26)

**WE HANDLE (owner: us — the Mini's lane list, DEDUPED 09-26 against
the aggregator feeds):** Bing Places, Apple Maps (Business Connect),
BBB, Expertise.com, Houzz, Porch, HomeGuide,
**yellowpagesdirectory.com** (added 09-26 — the unrelated third YP
company; free manual listing, Life Savers precedent),
ContractorsRanked, ChamberofCommerce.com — plus the two EARNED (no
submit form, picked up from review volume + consistent NAP):
ThreeBestRated, TrustAnalytica.

**REMOVED AS REDUNDANT (aggregator-covered, 09-26):**
- *Manual Foursquare* — the Foursquare aggregator feed (month 2) IS the
  FS listing plus its whole Places network; a hand-made page adds
  nothing. Wrong-data corrections stay a manual lane.
- *Manual MapQuest* — MapQuest sources from Neustar/Localeze, which
  rides month 1. Same corrections carve-out (the Reign fix was exactly
  this).
- *YellowPages off the client list entirely* — YP Network aggregator
  creates yellowpages.com (+dexknows +superpages), proven live.
Overlap guards that stay: yelp stays in BL picks ONLY until the owned
lane graduates, then flips out; Apple never bought through BL (ABC is
the owned listing; the GPS Network feed complements it by pushing NAP
into navigation data, different consumers); BL orders always send
remove_duplicates so month-3 top-offs never re-buy what a feed already
propagated.

**YOURS TO SET UP (owner: client — the supervised RE-TEST batch, now
with the code-relay concept sanctioned):** Yelp, Angi (free claim),
HomeAdvisor (paid tier, existing-only check), Thumbtack, Facebook Page,
Nextdoor, YellowPages*. Re-test goal per platform: US-BUILDABLE /
NEEDS-CLIENT-STEP (named — usually just a texted code, which the relay
covers) / HARD-BLOCKED.

**YellowPages — DETERMINED 09-26:** *yellowpages.com listings are
created by the YP NETWORK AGGREGATOR* (15 credits via BL — Kenneth +
Heritage have live yellowpages/dexknows/superpages pages to prove it).
Never use yellowpages.com's own claim flow (it is a Thryv sales funnel
that creates nothing, case e11a81a6); ignore yellowpages.net in the BL
directory menu (unrelated low-value site). The Connect-tab slot's
"client" badge predates the aggregator finding — re-badge to
us-via-aggregator on the next app pass. yellowpagesdirectory.com (a
third, unrelated company) stays valid for hand-entered client listings.

## 6. Chamber lanes

- **chamberofcommerce.com** (the directory): ours, free tier, Mini lane,
  already represented in the app's Connect tab.
- **Local chamber membership** (the real chambers, ~$200-500/yr): new
  first-class BACKLINK TARGET type on the backlinks board — states:
  recommended -> client-decided -> joined -> live. Client-paid; Monica
  delivers the pitch. Extra potent post-rename: membership under the new
  DBA name is real-world evidence for aggressive names.

## 7. BrightLocal housekeeping

- Open support ticket: 43-credit discrepancy (128 debited vs 85
  itemized, ticket 743649) — BL replied 09-17/18, unanswered by us since
  09-16. Aggregator charges (~45 credits) likely explain it; reconcile
  and close.
- Credits runway: 236 on hand. Month-1 ladder = 45/client -> ~5 clients
  per bundle-refill at current balance. Top-ups ping Santino (no
  auto-purchase) until told otherwise.

## 8. Dependencies + rollout order

1. **Mini revival** (Santino: keyboard sitting; launchctl + heartbeat) —
   gates every $0 lane above.
2. Wire ordering rules + ladder into brightlocal.py (secondary
   campaigns, exclusions, visible-address default, dedupe).
3. Code-relay build + T1/T2 tests.
4. Supervised Mini sitting: takes every lane to 1/3 (one sitting by
   design), including first BBB + chamberofcommerce.com runs.
5. First ladder client end-to-end (suggest: QCI — DBA verified, sitting
   in "your click places the order").
6. Fleet rollout per the retention ladder; backlinks board gains the
   chamber target type; Monica gains the chamber + BBB-accreditation
   pitch content.

## Signup email standard (LIVE 2026-09-27)

Every NEW platform signup uses **setup-{slug}@restorationai.io** as the
login/account email (e.g. setup-drybros@, setup-desert-valley@). A Google
Workspace routing rule (pattern `(?i)^setup-[a-z0-9-]+@restorationai\.io$`,
rule a68b5) delivers all of them into contact@ with an X-Gm-Original-To
header naming the alias, so verification codes stay machine-readable via
the Gmail helper and each client stays separable (no one-account-per-email
collisions). No per-client setup needed. Plain setup@ remains only for
listings already created with it (DV BBB, Dry Bros BBB, DV
chamberofcommerce.com 09-27) — never migrate those. The login email is
ours permanently; any PUBLIC business email field gets the client's own
address. Offboarding = hand ownership over on the platform, not a mass
email swap.
