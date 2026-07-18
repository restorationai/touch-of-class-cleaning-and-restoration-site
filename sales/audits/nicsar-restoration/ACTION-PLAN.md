# Action Plan — nicsar-restoration.com

Prioritized: Critical → High → Medium → Low. Effort in parentheses.

## 🔴 Critical — fix within 48 hours

| # | Action | Effort | Why |
|---|---|---|---|
| 1 | **Un-hide header phone on mobile/tablet** (remove `elementor-hidden-mobile elementor-hidden-tablet` from the header phone column) and wrap city-page sidebar numbers in `<a href="tel:+17732206751">` | 1–2 hrs | Emergency traffic is mobile; the primary conversion path is broken right now |
| 2 | **Launch a review engine.** Ask every completed job for a Google review; target 15 reviews in 60 days (competitors in the pack: 79 and 219 vs Nicsar's 2) | ongoing, start today | The #3 map-pack spot won't hold without review velocity; related search "…reviews" confirms demand |
| 3 | **Fix GBP description** — remove "Located in Carpentersville, IL" (business is in Hoffman Estates); point GBP website field at `https://nicsar-restoration.com/` (non-www) | 10 min | Factual error in the most-read profile field; kills a 2-hop redirect |
| 4 | **Rebuild `/fire-damage-restoration-barrington-hills-il/`** with actual Barrington Hills content (currently 100% Lemont: title, H1, schema, body) | 1 hr | Wasted page; wrong-city signals in schema |
| 5 | **Homepage H1**: set hero heading widget "Water Damage Restoration You Can Trust…" from H3 → H1 | 5 min | Zero H1s on the money page |
| 6 | **De-duplicate homepage title** (currently identical to the Hoffman Estates water page). New pattern: "Nicsar Restoration — 24/7 Water, Fire & Storm Damage Restoration | Chicagoland" | 15 min | Two pages cannibalize the #1 keyword |
| 7 | **Fix BBB listing**: address (shows Plainfield, IL) and primary category (shows "Kitchen Remodel") | 30 min | Tier-1 citation contradicting GBP |

## 🟠 High — this week

| # | Action | Effort |
|---|---|---|
| 8 | Meta descriptions for all 14 fire city pages (Yoast batch edit) | 30 min |
| 9 | Enable **Cloudflare APO** ($5/mo) or WP Rocket — fixes 2.7s cache-miss TTFB, defers jQuery, critical CSS, image dimensions in one move | 1–2 hrs |
| 10 | **Add a concrete response-time promise** to every hero: "On-site in 60 minutes or less — call (773) 220-6751." Add "24/7" and "emergency" to body copy (currently appear nowhere) | 1 day |
| 11 | Paste in the generated **LocalBusiness/EmergencyService JSON-LD** (full NAP, geo, 24/7 hours, 14-city areaServed) — ready in `schema.md` §4a | 1 hr |
| 12 | **FAQPage schema** on all city pages (template in `schema.md` §4c); promote FAQ headings H6→H2; expand answers to 80–150 words with one specific stat each ("mold can begin within 24 hours") | 1 day |
| 13 | **robots.txt: unblock GPTBot and ClaudeBot** (Cloudflare → Security → Bots → disable those two managed blocks). Keep CCBot/Bytespider/Google-Extended blocks + Content-Signal | 10 min |
| 14 | **Create/claim Yelp listing** + fix the footer Facebook icon (has no href) | 1–2 hrs |
| 15 | Security headers via one Cloudflare Transform Rule (HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy); WAF rule blocking `/readme.html` | 30 min |
| 16 | Fix services-hub "Read More" buttons that link to dead **Carpentersville** URLs from the old site | 30 min |
| 17 | Convert the two 400KB JPEG hero slides to WebP (or flip on Cloudflare Polish); preload first hero slide | 1 hr |
| 18 | Upload 20+ real job photos to GBP (currently 5); start weekly GBP posts | 2 hrs + ongoing |

## 🟡 Medium — this month

| # | Action | Effort |
|---|---|---|
| 19 | **De-doorway the top city pages** (Schaumburg, Naperville, Downers Grove, Bolingbrook first): city-specific intro (local flood/weather context, neighborhoods), city-pinned map embed (all 28 currently pin Hoffman Estates), a dated city-specific review, unique photo | 0.5 day/page |
| 20 | Retire the recycled "Michael R." testimonial from 28 pages; embed real Google reviews + AggregateRating with true reviewCount | 1 wk |
| 21 | E-E-A-T page work: street address in footer + contact page; name the owner/lead tech; name certifications (IICRC WRT/ASD if held) + IL license #; expand About with founding story | 1–2 days |
| 22 | Service schema on all 28 city pages (template in `schema.md` §4b) | 0.5 day |
| 23 | Build `/commercial-restoration/` page (property-manager persona currently 43/100, no page) | 1 wk |
| 24 | One research-mode linkable asset: "What to Do Immediately After Water Damage in Your Home" — direct-answer opening, H2 questions, 3 sourced stats (IICRC/FEMA), HowTo schema | 3–4 hrs |
| 25 | llms.txt at domain root listing services/areas/phone | 30 min |
| 26 | Citation build-out: Angi, HomeAdvisor, Thumbtack, Nextdoor Business, IICRC directory (if certified), chamber | 1 wk |
| 27 | Font fixes: Quicksand `display=swap`, trim to used weights, preconnect to Google Fonts (or self-host); dedupe Font Awesome (dequeue 3 UAEL handles) | 2 hrs |
| 28 | Insurance page: name carriers (State Farm, Allstate, Travelers…) + adjuster-coordination language | 2 hrs |
| 29 | Collapse www redirect to single hop (Cloudflare Redirect Rule); demote duplicate H1s on insurance + storm pages | 30 min |
| 30 | Flesh out gallery (captions, project context) and contact page (address, hours, map) | 2 hrs |

## ⚪ Low — backlog

- Enable IndexNow toggle in Yoast
- Defer reCAPTCHA until form interaction (Perfmatters / WP Rocket delay-JS)
- Suppress WordPress generator meta version
- Shorten the 2 titles >70 chars (storm page = 78)
- Width/height attributes on 8 gallery images
- LinkedIn/Facebook presence + sameAs array in schema
- Geo-grid rank tracking + GSC/GA4 hookup for real field data (unlocks measurable before/after)

---

**Expected impact sequence:** Items 1–7 protect revenue already being earned (calls + pack position). Items 8–18 are the ranking/visibility lift. Items 19–26 are what gets Schaumburg/Naperville pages out of the doorway-page pattern and into their own local packs — the actual growth story.
