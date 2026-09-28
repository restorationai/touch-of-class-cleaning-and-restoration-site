# Expansion System: multiple Google Business Profiles per client

Owner: Santino. Started 2026-09-27. Status: **scouting + GBP planner built, outreach next.**
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
| 8 | **Create + verify the GBP** (new name applied before verification) | GBP Profile Planner: app Locations > Profile + edge fn `gbp-planner` (see below) | BUILT 09-27 (branch `feat/gbp-planner`, awaiting merge) |
| 9 | **Citations** under the location's DBA | `brightlocal.py` ladder + Mini lanes | BUILT (per client; per-location variant TO BUILD) |
| 10 | **Reviews** routed per location (customers served from that town review that profile) | review reactivation + ongoing review campaigns | EXISTING (routing TO BUILD) |

**Contacts (built 2026-09-28):** Google Maps options get the Maps phone plus an email from the business's own site (homepage, /contact, /contact-us, /about). CRE listings (LoopNet, Crexi, CityFeet, Showcase, CommercialCafe) block every fetcher, DataForSEO OnPage included (tested: 403 / empty), so the broker comes from Google snippets ("Contact Colliers for more information", CityFeet broker names) plus the brokerage's own property page (vCard / agent block), then one SERP on the broker's name for phone/email. Craigslist records the post as a relay link only. Twilio Lookup sets mobile/landline/voip; the app shows a Text link only for mobiles. Never invented: blank means not found. ProRestoration run (33 options): 18 phone, 10 email, 8 named broker; contacts pass $0.22 (SERP $0.09 + Twilio $0.13), whole run $0.64.

## GBP Profile Planner (step 8, built 2026-09-27)

**Where:** app, Marketing > Locations > Profile, "Google Business Profile Planner" card (Restoration-AI-APP branch `feat/gbp-planner`, `components/GbpPlannerCard.tsx`). Superadmins edit and act; clients see the read-only mock. Backend: edge function `gbp-planner` (deployed, superadmin-gated).

**What it is:** a mock Google Business Profile of exactly what we will create, or what an existing UNVERIFIED profile becomes, then one button that writes it. The keyword name from the rename strategy goes on BEFORE verification (Google reviews the name at verification; a later rename can trigger a re-review).

**Single source of truth:** `companies.integration_settings.gbp_plan` = {title, primary_category, additional_categories, description, services [{name, description, description_source, site_page, suggested_removal, removed, decision}], service_areas, regular_hours, real_phone (editable), tracking_phone (call_tracking.gbp), phone_phase (verification|tracking), phone + additional_phones (DERIVED from the phase), verified_at, phone_swap, website_url, address, hide_address, cover_photo, logo, photos, pending_media, status (draft/ready/created/verifying/verified/failed), google_location, last_error, updated_at} plus `current` (snapshot of the live profile), `check`, `last_validation`, `verification`, `sources`, `edited`.

**Auto-draft (never asks for data we hold):** name = chosen rename (`marketing_gbp_suggestions` item_type=name status=chosen, else a non-caps `rename_intent.dba_name`); primary category = the existing profile's, else Water damage restoration service; additional = declared services mapped to real category ids (fire, building restoration, sewage) + optimizer category suggestions, validated with `categories:batchGet`; services = company services + existing profile + optimizer service suggestions; areas = `site_brief.cities` + existing profile areas (cap 20); hours = existing profile, else 24/7; phone = the client's real main number through verification, DNI GBP tracking number primary 3 days after verification (v3, see Phone timing); website = live Rank AI site; description = open optimizer suggestion, else drafted from badges/credentials/services/cities (<=750, no em dashes); photos = site hero cover + logo + real uploads, then site images (v2). Human edits (`edited`) survive "Refresh draft".

**Gates (server-enforced on the real write, shown as a checklist):** client confirmed the name; planned name = confirmed name; DBA filed; no other profile (duplicate check); existing target is unverified (update mode) or the client's own Google grant is connected (create mode); required fields; service areas matched to Google place IDs; text rules (description <= 750, name <= 90, no em/en dashes).

**How to use:**
1. Open the client's Locations > Profile. "Draft the profile" (or "Refresh draft").
2. "Duplicate check": scans every connected Google grant's Business Profile accounts plus Maps (`googleLocations:search`) by phone, website and brand name. A single unverified match is ADOPTED, the button becomes "Update & verify" and the card shows CURRENT vs PLANNED. Other matches are listed (with Request access for Maps listings) and block the write.
3. Edit if needed (name, categories via Google's taxonomy search, description, phone, website, hours, areas, services, address/hide, photos). Save.
4. If "Service areas matched to Google places" fails: `python3 scripts/gbp_planner_areas.py --slug X` (fills the shared ops_kv `geocode-place-ids` cache), then Refresh draft. Google rejects name-only areas.
5. "Validate with Google (writes nothing)": `validateOnly=true` create/patch; Google's answer is shown.
6. "Create Listing" / "Update & verify" (locked until every gate passes; confirm dialog). Create uses the client's own OAuth grant so the client owns the profile; update uses whichever grant can read the location (Veterans lives in Santino's account).
7. Verification: "Verification options" -> start SMS / call / email -> enter the code -> "Refresh status". Verify refuses to start until the live name equals the planned name.

**Test run 2026-09-27 (validateOnly only, nothing written):** Veterans (`locations/11814819342496578403`, Santino's account) and Dry Bros (`locations/8755232768131418210`, Amin's account) were both adopted as updates; all gates pass; Google accepted both patches (HTTP 200: Veterans 53 service items / 11 areas, Dry Bros 67 / 17). A CREATE preview for Dry Bros in Amin's account also validated 200. `fetchVerificationOptions` returned `[{}]` for both: no method the API can start, which in practice means video verification in the Business Profile / Maps app (the planner then only tracks status).

**v2 (2026-09-28, owner feedback):**
- **Service descriptions:** `draft` writes a description for every service (<= 300 chars, no em/en dashes, 1 to 2 cities woven in, claims limited to the claims_lint truth table). Grounded in the client's built service page when one matches, else Claude (`claude-sonnet-5`, parallel batches of 12, edge secret `ANTHROPIC_API_KEY`). Text already on Google and hand edits are never overwritten; "Rewrite descriptions" redrafts the rest. In the mock, click a service to read or edit its description.
- **Trim:** services that don't fit the market or offerings (Hurricane Damage Restoration in Chicago, duplicates) get `suggested_removal {reason}` + `removed: true`. Declared services and anything backed by a site page are never flagged. The mock shows them collapsed under "Suggested removals (N)" with Restore / Remove; apply sends only non-removed services.
- **Phone timing (owner decision 2026-09-28, supersedes "tracking number primary from day one"):** at creation/update and THROUGH VERIFICATION the GBP primary phone is the client's REAL main number (`plan.real_phone`, default = company phone), with NO tracking number anywhere on the profile, so Google's phone/SMS verification reaches the client and NAP matches citations/DBA while Google reviews it. Once Google reports the profile VERIFIED, `verified_at` is stamped and 3 days later the planner swaps: primary = our DNI GBP tracking number (`integration_settings.call_tracking.gbp.number`), `additionalPhones` = [real number], via one `locations.patch` with `updateMask=phoneNumbers`, logged to `marketing_gbp_changes` (change_type `phone_swap`). Rules: `plan.phone_phase` = `verification` | `tracking`; `phone` / `additional_phones` are derived, never edited; apply refuses any write that carries the tracking number during the verification phase; the swap runs ONLY on profiles the planner itself applied, only if the live primary is still the real number (anything else = `blocked`, never overwritten), and only while the edge-function secret `GBP_PLANNER_PHONE_SWAP=1` is set (unset = the tick reports `due_disabled`). Enable: `supabase secrets set GBP_PLANNER_PHONE_SWAP=1 --project-ref nyscciinkhlutvqkgyvq`. Detection: `verification_status`, run nightly for every applied plan by `python3 scripts/gbp_site_media.py planner-tick --company-id X` (client-ops-sync; service-role auth, which may run only that action). Gate: "Phone: client's real number through verification". No tracking number provisioned = the swap waits (`waiting`), creation is not blocked.
- **Photos:** `cover_photo` (default: the live site hero), `logo` (uploaded logo first, else the site logo), `photos[]` = client job-photo uploads first, then real site photos, then AI-generated site images (tagged "AI" in the mock), capped at 14. Each carries `{key, url, gbp_url, category (COVER|LOGO|EXTERIOR|INTERIOR|AT_WORK|TEAMS|ADDITIONAL), source (site|upload), caption, ai}`. Site images come from the ops_kv mirror `site-assets/{company_id}` published by `scripts/gbp_site_media.py manifest` (nightly); WebP is mirrored to JPG in storage because Business Profile media takes JPG/PNG only. In the mock: click a strip photo to make it the cover, hover to remove.
- **Media on apply:** validateOnly preflights every source URL (HTTP 200, JPG/PNG, 10KB-5MB) and reports push-now vs queued. A real apply on an unverified profile stores them as `pending_media` (never fails the apply); `verification_status` / `complete_verification` push them automatically once verified, and `push_media` does it on demand (v4 `accounts/{a}/locations/{l}/media`). Pushed images go into the shared ledger ops_kv `gbp-site-media/{company_id}`; pushed job-photo uploads move to `job-photos/posted/` so gbp_photos.py never re-posts them.

## Site-photo parity lane (2026-09-28)

`scripts/gbp_site_media.py` adds the client's website images to their GBP over time, for EVERY client with an existing verified GBP (owner-approved fleet-wide 2026-09-28, not only planner profiles). Runs nightly in client-ops-sync after the Parity Engine, one process per client (`list-due` roster). Only when (a) the real domain answers (fresh HTTP probe) and serves our build's images and (b) the GBP is verified. **Selection:** ONLY the hero + per-service images, plus real client photos in any site slot (photo-manifest), which keep priority; team / before-after / services-hub AI images stay in the site-assets mirror for the planner but never ride the lane. **Cadence:** 1 new photo per client per rolling 7 days (`GBP_SITE_PHOTOS_WEEKLY_CAP`, default 1) until that client's hero + service images are exhausted, then the lane goes quiet for them. **Never** sets or changes a COVER (hero goes up as EXTERIOR; the planner's push_media also skips COVER/LOGO when the listing already has one) and never uploads a logo. Dedupe by sha1 + URL in ops_kv `gbp-site-media/{company_id}` (shared with the planner). **Writes ON since 2026-09-28** (repo variable `GBP_SITE_PHOTOS_WRITE=1`, owner-approved); turn off with `gh variable delete GBP_SITE_PHOTOS_WRITE -R restorationai/Rank-AI-Pipeline`. Manual runs are dry unless `--apply` is passed AND the env flag is set. Manual: `python3 scripts/gbp_site_media.py run --slug X` (manifest + dry push), `push --slug X --real-only`.

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
