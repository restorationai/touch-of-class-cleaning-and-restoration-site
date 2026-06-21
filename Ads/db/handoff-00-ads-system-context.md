# Developer Handoff — Ads System Context & Rationale (READ FIRST)

> Read this before the two schema handoffs (`handoff-ads-call-tracking.md`, `handoff-ads-schema.md`). It explains **what the Rank AI ads system is, how it works, and *why* each table exists**, so the implementation reflects the product — not just the column list. You already understand the app; this gives you the missing half: the ads pipeline that feeds it.

---

## 1. What Rank AI is, and what we're adding

Rank AI is a **productized marketing service for home-service contractors** (water/fire/mold restoration, construction, plumbing). It already builds and operates SEO-optimized websites and runs automated content/audit pipelines, all surfaced in the app at **app.restorationai.io** (React + Supabase) under a **Marketing tab** with four pages: **Site, Content, Connect, Reports**.

**We are adding a fifth capability: managed Google Ads.** A new **"Ads" page** in the Marketing tab will show each contractor their campaigns, ad copy, landing pages, phone calls, and performance.

Behind that page is an **automation pipeline** (Python + Claude "skills") that *fully builds and runs* a contractor's Google Ads account end to end. Today that pipeline writes its state to local JSON files on our machine; we are migrating it to **write into Supabase `marketing_ads_*` tables** so everything lives in the cloud and the app can read it. **Your job is the DB migrations + the app UI; our pipeline writes the data via the service-role key.**

---

## 2. The ads pipeline — what produces the data (and the why)

The pipeline runs as a sequence of steps. Each step produces some of the data you'll be storing, so here's what each does and *why it matters*:

1. **Campaign structure** — builds the Google Ads campaigns and ad groups using a **SKAG** model (Single Keyword Ad Group). For each *service × city* there's a tightly-themed ad group with one core keyword, plus 7 **intent** ad groups per service (near-me, emergency, cost, company, free-estimate, insurance, removal).
   - *Why:* one keyword per ad group = maximum **Quality Score** control. Google rewards tight keyword→ad→landing-page relevance with lower costs. This is why ad groups store their `keyword` and `final_url`, and why each maps to a Google Ads `resource_name`.
   → feeds `marketing_ads_campaigns`, `marketing_ads_ad_groups`

2. **Ad copy (RSAs)** — generates 3 Responsive Search Ads per ad group, each from a different angle (speed / trust / value), each with 15 headlines + 4 descriptions. Three keyword headlines are **pinned** to position 1.
   - *Why:* pinned keyword headlines protect Quality Score; multiple angles let Google optimize. This is why `marketing_ads_creatives` stores headlines as JSON **with pin positions** and an `angle`, plus `ad_strength`.
   → feeds `marketing_ads_creatives`

3. **Negative keywords** — applies a universal negative-keyword list to filter junk traffic (jobs, DIY, "free", wrong trades).
   - *Why:* protects budget. (Roadmap table only — not in the first Ads page.)

4. **Landing pages** — builds a **dedicated landing page per ad group**, deployed as static Astro pages on Cloudflare Pages. Each page's `<h1>` **exactly matches the ad's keyword** (e.g. "Water Damage Restoration in Federal Way, WA").
   - *Why:* Google scores **Landing Page Experience** as part of Quality Score; a keyword-matched, fast, dedicated page scores "Above Average" and lowers cost-per-click. This is why `marketing_ads_landing_pages` stores `slug`, `url`, and `h1`.
   - These pages are **phone-first / call-driven**: every CTA is a "Call Now" button (`tel:` link). There is **no lead form** — restoration is an emergency purchase; people call. This is the single most important thing to understand about the conversion model.
   - We run **multiple design variants** (`v1`, `v2`, `v3`) and **A/B split-test** them — a "champion" vs a "challenger" — to find the highest-converting design. This is why landing pages carry `variant`, `split_test_id`, and `split_test_arm`.
   → feeds `marketing_ads_landing_pages`

5. **Conversion tracking** — because the pages are phone-first, the conversion is a **click-to-call**: tapping a phone CTA fires a Google `gtag` conversion event. It runs in the browser, so it carries the Google click id (`gclid`) → Google attributes the call to the exact keyword.
   - *Why:* this is the day-1, no-extra-cost way to get call conversions attributed to keywords. This is why `marketing_ads_conversions` records the conversion **action** (its `conversion_label`, kind = `click_to_call`).
   → feeds `marketing_ads_conversions`

6. **Call tracking (Twilio)** — a dedicated **Google Ads phone number** per contractor, provisioned in **their existing Twilio subaccount**, shown only on the landing pages. It bridges the call (with optional recording) to wherever the contractor wants — usually their business line, sometimes straight to our **AI voice agent (Retell)** over a SIP trunk.
   - *Why this matters and why it's separate:* the contractor already has a Twilio subaccount + (often) an AI agent that answers/qualifies/books calls. We **must not duplicate or disturb that** — we read their Twilio credentials from the existing `company_phone_setup` table and route the new ad number into their setup. A *dedicated* ad number means every call to it is provably ad-sourced, and bridging through Twilio means we can **record and log** the call even after it forwards. This is exactly how CallRail works, except on the contractor's own Twilio.
   - This is why we add `number_type` to `company_phone_numbers` (a number is either their **AI agent** number or a **call tracking** number) and why `marketing_ads_call_tracking` stores `forward_to` + `forward_type` (`pstn` business line vs `sip` AI agent).
   → feeds `marketing_ads_call_tracking`, `marketing_ads_calls`

7. **Performance** — the pipeline pulls daily spend/clicks/conversions/calls from the Google Ads reporting API.
   - *Why:* the Ads page needs to show results, not just structure. This is why we recommend `marketing_ads_metrics`.
   → feeds `marketing_ads_metrics`

---

## 3. Why the data lives where it does (boundaries)

- **`marketing_ads_*` = pipeline-owned.** Our automation writes these via the **service-role key**; the app only reads them. This mirrors the existing `marketing_*` tables (`marketing_sites`, `marketing_content_items`, etc.) that already back the Content page.
- **Core tables (`companies`, `company_phone_setup`, `company_phone_numbers`) = app/DB-owned.** The pipeline **reads** Twilio credentials from `company_phone_setup` but does **not** write core tables directly. Where a tracking number needs to appear in the core `company_phone_numbers` registry, a **DB trigger** mirrors it from `marketing_ads_call_tracking` (see the call-tracking handoff) — so the pipeline stays strictly inside `marketing_*`.
- **Keying:** every row carries `company_id` (FK → `companies`, for app joins + RLS) and `rank_ai_slug` (the pipeline's key). Google Ads `resource_name`s are the unique upsert keys so the sync is idempotent.
- **Secrets never reach the frontend.** Twilio/Google credentials stay server-side; call recordings are served through an authenticated endpoint, never with raw Twilio creds client-side.

---

## 4. How it maps to the Ads page (what the contractor sees)

| Section of the Ads page | Tables |
|---|---|
| KPIs / charts (spend, clicks, conversions, CPA, calls) | `marketing_ads_metrics` (account scope) |
| Campaigns (budget, status, results) | `marketing_ads_campaigns` + campaign metrics |
| Ad groups & keywords | `marketing_ads_ad_groups` |
| Ad copy preview + ad strength | `marketing_ads_creatives` |
| Landing pages, grouped by split test (champion vs challenger) | `marketing_ads_landing_pages` |
| Conversion actions being tracked | `marketing_ads_conversions` |
| Calls log + recording playback (likely under Reports) | `marketing_ads_calls` |

---

## 5. The two schema handoffs
- **`handoff-ads-call-tracking.md`** — `company_phone_numbers.number_type` + `marketing_ads_call_tracking` + `marketing_ads_calls` + the sync trigger. Ready to build now.
- **`handoff-ads-schema.md`** — campaigns, ad groups, creatives, landing pages, conversions, and the recommended metrics table.

Implement the migrations from both, then build the Ads page + Reports call log against them. Everything is read-only for the app; the pipeline keeps the data current.
