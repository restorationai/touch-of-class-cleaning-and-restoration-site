# Expansion System: multiple Google Business Profiles per client

Owner: Santino. Started 2026-09-27. Status: **scouting built, outreach + profile creation next.**
Related build-queue items: `docs/IMPLEMENTATION-QUEUE.md` #21 (office scout, GBP planner) and #22 (this system).

## Why

The goal is **digital real estate**: most restoration jobs come from Google (map pack, LSA, AI Overviews), ChatGPT and Bing. One Google Business Profile (GBP) only ranks roughly 2 to 10 miles from its pin. Nothing else extends that radius: service areas are cosmetic, and reviews and links don't move the pin. The only lever is **more pins**.

**End state per client:** 2 to 5 GBPs, each in a different town, each with hundreds of reviews. Combined with the SEO site, profile parity, citations and press releases we already build, this is the core of a ~$5k/month offer where the client does almost nothing beyond filing DBAs.

**Evidence:**
- **Power Dry (Kansas City):** 3 GBPs. ChatGPT's #1 Kansas City answer cites the one at a Regus coworking address.
- **Alert Restoration (Bakersfield):** satellite offices in Hanford and Tehachapi.
- **Servpro:** one owner on the Central Coast runs Santa Maria, Atascadero/Paso Robles and Pismo Beach listings.
- **Rob Carpenter (TDI, call 09-18):** paid the seller of a vacant Modesto office $200/mo ($500 deposit plus 6 months up front) "just for an address", staged it, and is doing Google video verification. He filed fictitious business names in 3 counties before building the profiles.

## The pipeline (per new location)

| # | Step | Tool | Status |
|---|---|---|---|
| 1 | **Which towns** are worth a pin (outside current reach, clustered demand) | `scripts/location_scout.py` -> table `marketing_location_scout` -> app Locations tab | BUILT (geocode guard fixed 09-27) |
| 2 | **Which spaces** can we get in each town: flex/office suites, coworking private offices, storage units, brokers | `scripts/office_scout.py` -> table `marketing_office_scout` -> "Office options" in the Locations tab | BUILT (branch `feat/office-scout-panel`, awaiting merge) |
| 3 | **Contacts** for each space: broker/manager name, phone (mobile vs landline), email | office_scout `--contacts` (default on with `--apply`) -> contact columns on `marketing_office_scout` -> contact block per option in the app | BUILT 09-28 (same app branch) |
| 4 | **Outreach** to lock an address: small monthly fee for address + mail + staging access | see "Outreach" below | TO BUILD |
| 5 | **Name + DBA:** client files "{Brand} of {City}" | Monica asks; DBA intake already exists | Existing flow |
| 6 | **Identity per location:** own email alias, own local Twilio number, own page on the client's site | alias routing + Twilio + site build | TO BUILD (pieces exist) |
| 7 | **Staging kit:** branded sign, equipment, video-verification script | checklist in the app | TO BUILD |
| 8 | **Create + verify the GBP** (new name applied before verification) | GBP Profile Planner (queue #21) | NEXT BUILD |
| 9 | **Citations** under the location's DBA | `brightlocal.py` ladder + Mini lanes | BUILT (per client; per-location variant TO BUILD) |
| 10 | **Reviews** routed per location (customers served from that town review that profile) | review reactivation + ongoing review campaigns | EXISTING (routing TO BUILD) |

**Contacts (built 2026-09-28):** Google Maps options get the Maps phone plus an email from the business's own site (homepage, /contact, /contact-us, /about). CRE listings (LoopNet, Crexi, CityFeet, Showcase, CommercialCafe) block every fetcher, DataForSEO OnPage included (tested: 403 / empty), so the broker comes from Google snippets ("Contact Colliers for more information", CityFeet broker names) plus the brokerage's own property page (vCard / agent block), then one SERP on the broker's name for phone/email. Craigslist records the post as a relay link only. Twilio Lookup sets mobile/landline/voip; the app shows a Text link only for mobiles. Never invented: blank means not found. ProRestoration run (33 options): 18 phone, 10 email, 8 named broker; contacts pass $0.22 (SERP $0.09 + Twilio $0.13), whole run $0.64.

## Decisions (Santino 2026-09-27)

- **Location naming:** "{Brand} of {City}", used in the DBA, GBP, signage and site page. Prefer the city people actually search ("of Temecula", "of Pacific Beach") over regions ("Northern San Diego").
- **One shared website** with a dedicated page per location (the Servpro/ServiceMaster model). One suspended profile does not take down the others.
- **Isolation per location:** separate Google account/email, phone number, address and DBA. Use separate payment methods where possible (a possible linkage point). Isolation limits the blast radius but can't be guaranteed.
- **Reviews:** built over time by the existing review reactivation and ongoing review campaigns. No bar/giveaway reviews from non-customers.
- **Coworking/virtual offices** are allowed as the client's informed choice (highest suspension risk). Real suites and bays with signage are preferred.

## Space types and Google verification

Restoration companies almost always get **video verification**. What Google's reviewers look for: one continuous shot from the street to the space, **your** signage, business equipment or a branded vehicle, and proof you control the space (unlocking it, tools, business documents). Mail only matters when Google offers postcard verification.

| Space | Rough cost | Verification odds | Notes |
|---|---|---|---|
| Flex / small office / industrial suite (LoopNet, Crexi, brokers) | $500-3,000/mo | High | Real space, signage allowed. Rob's play: vacant office owner, $200/mo for the address. |
| Storage unit (drive-up, branded door sign, drying equipment inside) | $120-350/mo | Medium | Believable as an equipment base. Ask: accepts tenant mail? sign on the door? drive-up with power? |
| Coworking private office with signage (Regus/IWG, local) | $200-500/mo | Medium | Ask for a private office, not a "virtual office". |
| Virtual office / mailbox-only | $50-150/mo | Low | Usually fails video; filtered out by the scout (UPS Store, Davinci, Opus). |

## Outreach (to build)

- **In the app:** a contact card per space (name, role, company, phone with a mobile/landline tag, email, listing link) and a status: new, contacted, replied, negotiating, secured, declined.
- **Email (automated first touch):**
  - **Identity:** sent from an alias on the **client's own domain** where we manage DNS (e.g. locations@{clientdomain}; Cloudflare Email Routing inbound, SendGrid domain-authenticated outbound). Fallback: a {slug}.{city}@ alias on a dedicated outreach subdomain. Never the main restorationai.io, to protect Monica's deliverability.
  - **Sender name:** "{First name} at {Brand} {City}". The city adds local familiarity.
  - **Compliance:** CAN-SPAM (real sender, physical address, opt-out).
- **Text + call, 1:1 by a team member:** landlords close on the phone. No automated cold texts (TCPA consent risk). The review-request SMS registration can't carry this traffic; register a separate SMS campaign if we automate later.
- **The ask (script):** "We're a restoration company expanding into {City}. We're looking for a small space or address, month to month, mainly for mail and occasional access. Would you consider a small monthly fee?"
- **Replies** land in the app thread and update the status.

## Future lanes

- **Facebook Marketplace listings:** Mac Mini logged-in browser lane (Marketplace is login-walled and not indexed).
- **Per-location citation ladders and review routing.**
- **"Expansion" section in the Locations tab:** scout, office options, outreach status and per-location profile status in one view.
