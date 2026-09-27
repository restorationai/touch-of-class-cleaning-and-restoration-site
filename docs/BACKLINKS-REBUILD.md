# Backlinks Rebuild — industry authority links (draft outline, 2026-09-27)

Companion to docs/ai-citation-roadmap.md (the AI-citation gameplan) and
docs/CITATIONS-REBUILD.md. Catalog + badges: scripts/backlinks.py and the
Build Stages Backlinks board (inline editor + nightly discover -> check).

## DECISIONS (Santino 2026-09-27, final)

- **Spotify: DROPPED.** Episode links are nofollow, show pages have no
  link. No new podcast episodes for anyone (podcast_feed.py was never on a
  schedule; it simply stops being run). NaRestCo's existing feed stays live.
- **Apple Podcasts: KEPT as a one-time task** (followed link on the show
  page). First test: finish NaRestCo's Apple connect on the Mini.
- **RIA: DETECT + RECOMMEND, never purchase.** discover v2 finds existing
  members (4 found); non-members get a client-paid recommendation from
  Monica. Generalizes per vertical as we expand (plumbing PHCC, roofing
  NRCA, HVAC ACCA — catalog is already keyed by category). RIA bulk email
  shelved; $3k-tier "industry association listing" = recommendation-led.
- **Mozilla add-ons: never built, not pursued** (links nofollow + routed
  through Mozilla's outgoing redirector, verified).

## CORRECTIONS (same day, after Santino's checks — these supersede the table)

- **C&R directory is a VENDOR directory** (categories: certification &
  training, equipment, marketing, professional services, software,
  supplies). Free + dofollow, but NOT for restoration contractors — it fits
  Rank AI only (Restoration AI already listed). For clients, C&R = articles.
- **R&R**: the listing anchor itself has no nofollow (what browser
  extensions show), but every listing page carries
  `<meta name="robots" content="nofollow">`, which Google applies to all
  links on the page. Listings = no SEO credit. **R&R ARTICLES still have
  value** (article pages have no robots meta, author-page links verified
  followed on one example, plus brand/AI-citation value) — keep as a
  lower-priority editorial lane after C&R.
- **Spotify**: show pages render NO website link at all (RSS <link> is not
  displayed) — presence/entity signal only, not a backlink.
- **Apple Podcasts**: show pages render the website link with
  rel="noopener noreferrer" (no nofollow, no robots meta) — a real
  followed link. NaRestCo is NOT on Apple yet (connect never completed).
- **RIA existing members** (discover v2, direct directory lookup, verified
  live 09-27): Air Care, Life Savers, QCI, NaRestCo. NaRestCo's profile
  link is malformed ("http:// www.narestco.com") — fix on the profile.

## Verified facts (research 2026-09-27 — rel attributes inspected, not assumed)

| Source | Cost | Link | Verdict |
|---|---|---|---|
| **C&R Buyer's Guide** (candrmagazine.com/cr-directory) | **FREE** basic (Premium $199/yr) | **dofollow** (plain target=_blank) | BEST free lane. Restoration AI already listed (04-25). Build per client. |
| **C&R articles / news** | free (editorial) | **dofollow** (article + author links) | Contributed article or press release via Michelle Blevins; Expert Panel form. |
| **RIA Find a Pro** (pro.restorationindustry.org) | membership | **dofollow** (extNofollow:false, no rel) | Per-client membership required. |
| **RIA Vendor Marketplace** | $875/yr Vendor Membership | **dofollow**, page index/follow | For Rank AI ITSELF — competitors (Ironclad, SEO Rank Media, 99calls...) already there. Lead-gen + link. |
| **R&R Buyer's Guide** (randrmagonline.com) | $110-$995, links only from $350 | **NOFOLLOW** (meta robots nofollow on listing pages) | DROP as a link target. |
| **R&R editorial / press releases** | free, no guarantee | author-page links can be dofollow | Keep as editorial lane only (Kayla McGowan). |
| **IICRC Certified Firm locator** | free w/ certification | not yet verified | Verify rel next; locator is a search tool (not indexed profiles). |

RIA contractor dues (by revenue): $500 (<$500k) / $806 / $1,520 / $2,030 /
$3,050 (>$10M). **First-year contractors: $299** (or $25/mo), prorated,
Jan-Dec cycle. Franchisee $250. No agency/bulk program, no API — each
client joins as its own company (YourMembership platform).

Corrections to the starting assumptions: no ~$200 RIA tier (closest: $299
first-year promo); the FREE dofollow listing is **C&R's**, not R&R's.

## The per-client ladder (fits the citations $100/mo cadence)

- **Month 1 (free, Mini):** C&R Buyer's Guide basic listing (new Mini lane,
  setup-{slug}@ login, real NAP). Discovery + checker verify it.
- **Month 1-2 ($299 first-year, package-included for the $3k tier):** RIA
  contractor membership -> Find a Pro profile with website link (Mini
  completes the profile once membership is active). Year 2 renews at the
  revenue tier ($500+) — price the package for it.
- **Ongoing (editorial, you-approve):** one contributed article or press
  release per client per quarter, pitched to C&R (dofollow) first, R&R
  second. Content engine drafts; Santino approves; submission via email.
- **IICRC:** record the locator URL where certified (editor/Mini lookup).

## Rank AI's own authority (separate from clients)

- RIA Vendor Membership $875/yr -> Vendor Marketplace dofollow listing
  beside our competitors + access to member lists. Recommended.
- C&R: existing listing points to restorationai.io — consider a second
  listing for Rank AI. $850 July leaderboard already bought (paid 07-31).

## Open loops found in the mail (Melia era, 2026-04..06)

- RIA blog: Amanda Bray (05-26) said posts need the education-committee
  form + an educational post. Melia drafted two (06-02, 06-03) — no
  submission visible (melia@ mailbox not searchable here).
- R&R article draft "Automating the Back Office..." (05-21) — never sent.
- BNP Buyer's Guide account (04-28) created, never published (paid/nofollow
  anyway — let it lapse). NOTE: that account password sits in plaintext in
  Gmail thread 19dd40cad23934e8.
- Santino joined RIA 09-08 — tier/company unknown; not yet in Find a Pro.

## Contacts

- RIA membership: info@restorationindustry.org, 856-439-9222 (Membership
  Coordinator Danielle Knights, 856-372-5175). Vendor/blog/ads: Amanda Bray,
  abray@restorationindustry.org, 856-437-4750.
- C&R: Michelle Blevins (publisher/owner), michelle@candrmagazine.com,
  574-242-9087 — existing paid relationship.
- R&R editorial: Kayla McGowan, mcgowank@bnpmedia.com, 757-849-2461.

## Build list (awaiting go)

1. Catalog: split C&R into `cr-directory` (free listing) + `cr-article`;
   re-mark `rr-magazine` as editorial-only (no directory target).
2. Mini lane: C&R Buyer's Guide listing per client (supervised first 3).
3. RIA: membership purchase flow per client (Santino pays) -> Mini fills
   the Find a Pro profile -> checker verifies.
4. Editorial lane: quarterly article/press-release drafts per client in the
   app approval queue, routed to C&R then R&R.
