# Awards research pass — 2026-10-02

Candidates to add to scripts/awards.py CATALOG (the canonical store). Raw research notes below, verbatim from the research pass; unverified items are labeled.

QBA domain facts (checked 2026-10-02): registered 2018-12-04 (DreamHost), backlinks first seen 2022-04, 1,756 referring domains / ~49k backlinks, DataForSEO rank 396, ~35.8k ranking keywords, ~70k est. monthly organic visits. ~87% of a 200-domain sample are WINNERS' award badges/links back; rest = winners' press releases (prnewswire/abnewswire/financialcontent) + link spam (shorturl, pastelink, bookmark sites).

Own award site: NO (see IMPLEMENTATION-QUEUE NEVER list + awards.py header): agency-owned award for paying clients = undisclosed material connection (FTC endorsement guides / 2024 consumer-review rule), a controlled link network, and a reputational/churn risk if exposed.

# Awards research raw notes (2026-10-02)
Indexability checks: curl -sL with Chrome UA; see curl-log.txt + html/ (chk.sh). "idx" = 200, no noindex meta/X-Robots.
"link" = page links out to the business's own site.

## Review-platform / criteria
- Thumbtack Top Pro. Criteria (Thumbtack Pro Center, cited by search): >=10 hires in last 12 mo, >=4.8 avg verified rating (12 mo), >=5 verified reviews (12 mo). Quarterly evaluation; annual badge shows in Jan if qualified >=2 periods. ~4% of pros. Cost: free profile, but hires come through paid leads.
  CHECK: thumbtack.com/ca/bakersfield/plumbing = 200, no robots meta, canonical, title "The 10 Best Plumbing Services in Bakersfield, CA", "Top Pro" labels on page. No outbound link to pro sites (only app.link).
- HomeAdvisor Top Rated / Elite Service (legacy): Top Rated = 4+ overall, 90% recommend, 5+ reviews, no complaints 6 mo; Elite Service = 5-star reviews, 4.5+ customer service, no complaints. HomeAdvisor consumer brand folded into Angi; whether still issued = UNVERIFIED. homeadvisor.com/rated.* = 403 Cloudflare + noindex to curl.
- Angi companylist = 403 Cloudflare to curl (already in catalog via Super Service Award).
- Best of Porch: "top 1% of pros annually" (older trade press). Current status UNVERIFIED.
- Top Rated Local (Marketing 360): Rating Score (# verified review sites, avg stars, review count). "Highest Rated in [State]" awards announced via PR Newswire 2019-2023. topratedlocal.com/awards = 404 on 10-02; profile pages (e.g. /marketing-360-reviews) 200, no robots meta, no 'award' text. Program likely dormant = UNVERIFIED.
- Yelp: no award program. "People Love Us on Yelp" sticker, auto-mailed twice a year, criteria undisclosed, no public winner page.
- Google: no award program. Birdeye/Podium: no consumer-facing award found (only vendor's own G2 awards).
- Trustindex Review Certificate: only for paying Trustindex subscribers (5-point criteria). Widget badge, no indexable winner page. Trustpilot: no award.
- BBB Accreditation: ~$500-1,500/yr for small firms (third-party pricing write-ups; varies per local BBB) + ~$75 application (UNVERIFIED per BBB). Standards: 6+ months operating, licensed, B+ rating or better, resolves complaints. bbb.org = Cloudflare 403 to curl; profiles are Google-indexed and show website link (known). Internal note: ChatGPT leans on BBB + Angi.

## Survey/certification programs (contractor pays)
- GuildQuality Guildmaster: members only; >=20 survey responses, >=90% likely-to-recommend, >=50% response rate OR 12 consecutive weeks of uploads. Distinction 95-97.9%, Highest Distinction 98%+. No extra fee beyond membership; pricing = quote only (UNVERIFIED amount). Profile CHECK: guildquality.com/profile/Best-Pick-Reports-Publication = 200, no robots meta, links out to bestpickreports.com. Best Pick Reports is "powered by GuildQuality".
- Best Pick Reports (EBSCO): 30+ metros (Baltimore, Boston, Long Island, MD/DC, NJ, N. Virginia, Philadelphia, Atlanta, Charlotte, Ft Myers/Naples, Jacksonville, Miami/S. FL, Nashville, Orlando, Sarasota/Bradenton, St Pete, Tampa, Boulder, Chicago, Colorado Springs, Denver, Minneapolis, N. Colorado, Portland, Seattle, Austin, Dallas, Houston, Phoenix). Categories include Water Damage Restoration, Fire Damage Restoration, Mold Removal, Plumbers. Criteria: 4.0+ rating & 80% recommend from independent surveys, licensed+insured, 1+ yr, annual recert. "Our service is funded by the contractors who value the Best Pick certification" = paid; price not public (UNVERIFIED).
  CHECK: /water-damage-restoration/atlanta = 200, index,follow, title "Best Water Damage Restoration Companies in Atlanta, GA". Company page /water-damage-restoration/atlanta/ars-restoration = 200 index,follow; NO outbound link to company site in static HTML.
- Diamond Certified (American Ratings Corp): SF Bay Area + Monterey/Santa Cruz/San Benito (12 counties). Phone surveys of real customers, must score 90+/100 + credential checks. Company pays to be rated/marketed (amount UNVERIFIED); "does not earn ... regardless of how much it's willing to pay". diamondcertified.org index,follow.

## Industry / trade
- RIA Phoenix Awards: project awards (Innovation in Restoration / Reconstruction). Members AND non-members. Application fees apply (amount UNVERIFIED). 2026 cycle: projects completed Jan-Dec 2025, deadline Jan 26 2026 -> 2027 cycle expect ~late Jan 2027. Winners skew large (ATI 2024/2025, Kelmann, BluSky). restorationindustry.org/phoenix-awards index,follow.
- RIA + C&R "Emerging Leaders in Restoration": under 40, self-nominations encouraged; inaugural 2025. candrmagazine.com winners page 200, no noindex.
- RIA Ladder Award (35 and under), Martin L. King Award (lifetime) = individuals, low relevance.
- R&R Women in Restoration Award: women with 10+ yrs in restoration, self-nom OK, US/Canada; 2026 deadline Feb 28 2026, winner at The Experience (Las Vegas, Sep 9-11 2026). Article pages indexable.
- R&R "Top 100"/"Restorer of the Year": NOT FOUND. Cleanfax: no contractor-of-year program found (covers others' awards).
- PHCC National: Plumbing Contractor of the Year (Delta), HVAC CotY (Rheem), apprentice/instructor awards. Members, nominated; judged on professionalism, management, innovation, trade involvement, community service. phccweb.org/news/celebrating-the-very-best-of-2025 = index,follow, names winners. State/local PHCC chapters have their own awards (better odds; UNVERIFIED per chapter).
- PM (Plumbing & Mechanical, BNP) Plumber of the Month: employer nominates a plumbing/pipefitting tech with 1+ yr; no self-nomination. pmmag.com/plumber-of-the-month-submission 200. Winner articles name tech + company.
- Plumber magazine / Cleaner magazine (COLE Publishing): monthly company profiles (editorial pitch, not an award).
- ACHR News Best Contractor to Work For: HVACR companies (US/Canada) only; self/employee/peer nomination. Not for pure restoration/plumbing (combo plumbing+HVAC shops may qualify).
- NARI CotY: NARI members only; project binders; regional + national; categories include whole-house, additions, historic restoration. Fees UNVERIFIED. Chapter-level CotY more attainable.
- IICRC Certified Firm: $25 processing + $125/yr; >=1 IICRC certified tech; listed in IICRC locator (dynamic; indexability UNVERIFIED, iicrc.org blocked/changed paths to curl). Credential not award.
- Contractor Connection (Crawford): Golden Hammer (top 200 of 4,000+ network contractors) and regional Contractor of the Year. Network members only; public evidence = press releases.
- CAI / IREM / BOMA chapters: "Business Partner of the Year"/"Industry Partner of the Year" (e.g. ATI's Jen Petras, IREM Boston 2020 Industry Partner of the Year). Membership + volunteering.

## Local institutional
- SBA National Small Business Week awards (2027): deadline Dec 7 2026 3:00pm ET (sba.gov awards page, fetched 10-02; an OMB doc said Nov 9, sba.gov wins). Small Business Person of the Year: US citizen/national owning 51%+, operating 3+ years, received >=1 SBA assistance (SBA loan, SCORE, SBDC), good standing on federal obligations; SELF-NOMINATION ALLOWED. Judged: staying power, financial performance, community impact. District -> state -> national. sba.gov page index,follow.
- Chamber Small Business of the Year: per chamber; examples NorthStar Restoration Services won Greater Wausau Chamber 2026 SBOY; Wichita Regional Chamber 2025 Small Businesses of the Year (Rhoden Roofing). Wichita page 200 no robots meta. Wausau growthzone member-news URL now 404 (chamber pages rot).
- Business journal Best Places to Work (Quantum Workplace): independent US co, >=5 FT/PT employees excl owners (some markets 10+); employee participation thresholds (<=50 emp = 85%). Cost UNVERIFIED (historically free to participate).
- Business journal 40 Under 40: nominate (self-nom generally allowed), judged on business + community; free. Deadlines vary by market.
- Fast 50 (business journals): e.g. Pittsburgh: 2023 revenue >$2M + 3 yrs disclosed; Twin Cities: $500k (2022) and $1M (2024). 
- Inc. 5000 (2026 list): $100k revenue 2022, $2M 2025, founded+revenue by 3/31/2022, private/independent US. Fee ~$495 (2024 figure; 2027 fee UNVERIFIED). Inc. Regionals: $100k (2022) / $1M (2024) for 2026 edition.
- Top Workplaces (Energage): free to participate/survey/win; regional min usually 35 or 50 employees. topworkplaces.com/company/{slug} = index,follow + links to company site.

## Newspaper/community poll platforms
- NERUS Strategies "Optimum" (LV Review-Journal Best of Las Vegas, Bradenton Herald "Bradenton's Best", Seattle Times "Best in PNW", The Tribune SLO): listing pages e.g. bestoflasvegas.com/listing/k:las-vegas-handyman = 200, no robots meta, canonical, links OUT to winner site (handymanoflasvegas.com).
- VoterFly (chambers + community papers: Katy, Fair Oaks, Carmichael, Greater Vidalia chambers; Castro Valley/Eden Area): {x}.voterfly.com/contender/{id}/{slug} = 200, canonical, links OUT to nominee site (boldgc.com).
- SecondStreet (Upland Software; 4,000+ media cos; Lee Enterprises papers, many independents): nomination round -> 1-2 voting rounds -> top 3/5 finalists; ballots hosted at {paper}.secondstreetapp.com or embedded; winners usually republished as a newspaper article/special section.
- Ogden (Marietta Times), Daily Record (Baltimore) "Reader Rankings", alt-weeklies (Westword Best of Denver Readers' Choice has "Best Home Renovation and Restoration").

## Vanity / AVOID
- *.awardprogram.org "Best of [City] Award" (e.g. "{city} Award Program"), US Commerce Association (USCA), US Local Business Association ("Best of Local Business"), Small Business Commerce Association, "{City} Best Awards" network (Best Memphis Awards, Seattle Best Awards, Peoria Best Awards), BusinessRate, CityBestAwards (catalog already flags). BBB has issued warnings on these.
- Consumers' Choice Award: mostly Canada, winners historically paid $300-$3,900 to use the logo. Low value.
- Stevie / American Business Awards: real judging but pay-to-enter ($285 individual / $510 org early-bird) with high win rates; low local AI value.
