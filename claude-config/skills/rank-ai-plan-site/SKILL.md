---
name: rank-ai-plan-site
description: Plan a Rank AI client's site — produce the URL plan + content map CSV + internal-link graph + per-page schema stubs from the restoration template. Runs after `rank-ai-onboard` (client must already be `active`) and before `rank-ai-build-site`. Use whenever the user says "plan the site", "rank-ai-plan-site", "generate URL plan", "content map", or wants to take an onboarded restoration client through site planning. Wraps `rank-ai/scripts/plan_site.py`.
---

# Rank AI — Plan a Client Site

You are running Skill 2 of 4 in the Rank AI pipeline. This skill drives `rank-ai/scripts/plan_site.py` and produces the artifact set the build skill (Skill 3) consumes.

## Project root

`/Users/santino/Desktop/mywebsitecode/rank-ai/`

Change to this directory at the start of the run.

## Pre-flight context

Before doing anything, read these files so you understand the contract you're producing:

- `rank-ai/docs/site-plan-skill-spec.md` — the full spec for what this skill produces
- `rank-ai/docs/image-hosting-architecture.md` — Skill 4's contract, which Skill 3 (and therefore the plan's image roles) must respect
- `rank-ai/templates/restoration/template.json` — template descriptor + version
- `rank-ai/templates/restoration/services.json` — canonical 33-service catalog (user picks a subset)
- `rank-ai/templates/restoration/seed-blog-topics.json` — seed blog post backlog

The script + spec are authoritative; if anything in this skill conflicts with the spec, the spec wins.

## Pre-condition check

The client must already be onboarded via Skill 1. Verify before doing anything:

```bash
cat rank-ai/clients/<slug>.json
```

The record must show `"status": "active"`. If status is `pending_ns` or `ns_active`, the client isn't ready — surface that and suggest the user finish `rank-ai-onboard` first.

If the record has a `plan_status` of `planned` already, the client has been planned before. Ask the user whether to overwrite (re-run generate) or just inspect the existing artifacts.

## Credentials

This skill does NOT need Cloudflare credentials — the planner is filesystem-only. (DataForSEO keys will be needed once the keyword-enrichment hook is wired; for now the script falls back to template defaults and `search_volume`/`difficulty` columns stay blank.)

## Step 1 — Identify the client

Ask which client to plan (using `AskUserQuestion`). Offer existing slugs from `rank-ai/clients/*.json` plus an "Other" path. After the user picks a slug, confirm by showing the client record's `display_name` and `domain`.

## Step 2 — Gather inputs

If the client has a live website at their domain, **fetch it first** to pre-fill candidate services, service areas, and brand details:

1. **WebFetch the homepage** at `https://<domain>/` and any obvious "Services", "About", "Contact", or "Areas We Serve" pages. Pull out:
   - Listed services (match against `templates/restoration/services.json` slugs)
   - Service-area cities/states
   - Phone, email, hours, address, founded year, certifications, license numbers
2. **Look up their Google Business Profile** by searching for the business name. Pull additional service-area cities and any services mentioned there that weren't on the site. GBP service areas are often broader than what's published on the homepage.

Then walk the user through `AskUserQuestion` to confirm / edit each field:

1. **Services** — multi-select from the 33-entry catalog (group by `tier`: core / specialty / adjacent). Show fetched candidates pre-checked. Typical restoration company picks 8–15 services.
2. **Service areas** — start from fetched list, ask user to add/remove. Each area is `{city, state, slug?}` — derive slug from `city-state` if not provided (e.g., `phoenix-az`). Designate one as `primary` (default: first).
3. **Brand details** — show fetched values for `phone`, `email`, `hours`, `founded_year`, `license_numbers[]`, `certifications[]`. Ask the user to confirm or override.
4. **Google Maps API key** — ask for the client's `GOOGLE_MAPS_API_KEY` browser-restricted API key. This enables the embedded map on all service-area pages. It is optional — if omitted the `GoogleMap` component falls back to a "View on Google Maps" link. The key must be a browser API key (NOT an OAuth client ID or service account); it should be restricted to the client's domain in Google Cloud Console (APIs & Services → Credentials). If the user doesn't have one yet, tell them to create one at console.cloud.google.com → APIs & Services → Credentials → Create Credentials → API key, then restrict it to Maps Embed API and the client's domain.
5. **Cross-product pages** — default `true` (generates `/service-areas/{city}/{service}/` pages, the SEO gold for restoration). Only disable if the client explicitly doesn't want them.
6. **Blog seed count** — default `12`. Don't ask unless the user wants to override.

Echo back a single-screen summary of the resolved inputs and get one explicit "yes proceed" before writing anything.

## Step 3 — Write plan-input.json

Write `rank-ai/clients/<slug>/plan-input.json` with the resolved inputs in this shape:

```json
{
  "template": "restoration",
  "services": ["water-damage-restoration", "fire-damage-restoration", ...],
  "service_areas": [
    {"city": "Phoenix", "state": "AZ", "slug": "phoenix-az", "primary": true},
    ...
  ],
  "brand": {
    "display_name": "...",
    "phone": "...",
    "email": "...",
    "hours": "...",
    "founded_year": "...",
    "license_numbers": [...],
    "certifications": [...],
    "google_maps_api_key": "AIza..."
  },
  "cross_product": true,
  "keyword_strategy": "conservative",
  "blog_seed_count": 12
}
```

The script also reads `display_name`, `domain`, `canonical_url`, `primary_city`, `primary_state` and other brand fields from the client record + the primary area. You don't need to duplicate them — but if the user wants to override the canonical brand `display_name` (e.g., to use a marketing name distinct from the legal company name), set it explicitly in `brand`.

## Step 4 — Preview, then generate

Before running, compute and show:

```
With these inputs, this plan will produce:
  - 1 home + 5 hubs/fixed pages (about, contact, services-hub, service-areas-hub, blog-index)
  - 3 legal pages (privacy / terms / accessibility)
  - {len(services)} service-landing pages
  - {len(service_areas)} service-area pages
  - {len(services) * len(service_areas)} cross-product pages (service-area-service)
  - {blog_seed_count} blog seed posts
  ----------------------------------------------------
  Total: ~{computed total} URLs at launch
```

Get one final confirmation before running. Then:

```bash
cd /Users/santino/Desktop/mywebsitecode
python3 rank-ai/scripts/plan_site.py generate --slug <slug>
```

Surface the script's stdout verbatim.

## Step 5 — Review

After generate succeeds, display:

1. The full `rank-ai/clients/<slug>/plan/plan-report.md` (it's small and renders well)
2. The first 30 rows of `rank-ai/clients/<slug>/plan/content-map.csv`
3. A note that the rest of the CSV + internal-links.json + schema-stubs.json + url-plan.json are on disk for Skill 3 to consume

If the report shows validation issues, do NOT advance to Step 6. Walk the user through fixing the inputs (or the templates if the issue is template-side) and re-running `generate`.

## Step 6 — Validate

Run validate explicitly so the user sees a clean signal:

```bash
python3 rank-ai/scripts/plan_site.py validate --slug <slug>
```

If it exits non-zero, surface the issues and stop.

## Step 7 — Output summary + auto-chain to build

Once validate passes, give the user:

```
==> Site plan complete for <display_name>

  Template:        restoration v<version>
  URLs planned:    <N>
  Internal links:  <M> edges
  Plan dir:        rank-ai/clients/<slug>/plan/
```

Then ask: **"Ready to scaffold + render the site now? (yes / let me review the plan first)"**

- If yes → invoke `rank-ai-build-site` skill with the same slug. The build skill takes over (scaffold → render → sync-deploy staging → preview → push main → cut-over). The whole launch happens in one continuous flow with the user just confirming the irreversible transitions.
- If they want to review first → tell them where the artifacts live and stop. They can resume by invoking `rank-ai-build-site` whenever.

This auto-chain is the key to the "minimal user interference" workflow. Skill 1 onboards. Skill 2 plans. Skill 2 auto-suggests skill 3. Skill 3 walks the rest of the launch.

## Emergency naming (Santino 2026-09-30)

URGENT services only: water damage restoration, emergency water removal, flood damage, burst pipe / leak, sewage cleanup, fire damage, smoke damage, storm damage, emergency board-up / tarping, biohazard / trauma, and emergency plumbing where the client is licensed for plumbing (plumbing vertical, a plumbing license type, or a license shared with a plumbing client).

- Title tag + H1 lead with "24/7 Emergency" when plan-input `brand.hours` says 24/7, else "Emergency" ("24/7 Emergency Water Damage Restoration in {City}"). Never doubled. The headline before " | Brand" stays under ~60 chars: drop "24/7" first, then ", ST".
- Meta description carries the same lead. The body opens with one emergency-response line (bold hook + call to act); "We answer 24/7" only on 24/7 truth, an on-site time only when `brand.response_minutes` is set, otherwise no number.
- Not for non-urgent services (mold inspection/remediation unless the GBP/site already frames it as emergency, remodeling, carpet/upholstery, air ducts, GC, testing, insurance). Clients with explicit business hours that are not 24/7 (Davis) get none.
- Code: `scripts/emergency_naming.py` (plan_site.py applies it to planned titles/H1s/metas; build_site.py render pins the opening line; `python3 scripts/emergency_naming.py --all --apply` re-applies to existing pages).

## Error handling

- Surface the full script error message verbatim. The script is the source of truth on what's wrong.
- The script is idempotent — re-running `generate` with different inputs overwrites artifacts (and backs up prior versions as `*.{timestamp}.bak`).
- If a service slug from the user's selection isn't in `services.json`, the script will die with a clear list of unknown slugs. Update the catalog (with user approval — this is a template change, affects all future clients) or correct the input.
- If the user wants to add a service that doesn't exist in the catalog, ask whether to add it to `templates/restoration/services.json` permanently (yes = template edit) or skip it for this client only (no = drop from selection).

## What this skill does NOT do (out of scope)

- Cloudflare changes — that's `rank-ai-onboard`
- Astro scaffolding, HTML rendering, content generation — that's `rank-ai-build-site` (not yet built)
- Blog post writing — that's `rank-ai-blog-routine` (not yet built)
- Image generation — that's Skill 4 via Nano Banana
- Deployment — Skill 3 / Skill 5
- DataForSEO live calls — the spec calls for them, the script has TODO stubs; until wired, search_volume and difficulty stay blank in the CSV

## Template-edit guardrails

If you find yourself wanting to edit `templates/restoration/` to handle a per-client edge case, **stop and ask**. The template is a shared resource — changes affect every Rank AI client. The right places to encode per-client variation are:

- The client's `plan-input.json` (run-specific inputs)
- The client record's `image_policy` field (per-client image budget tier)
- After plan generation, manual edits to the client's `content-map.csv` (single-client only)

If the desired change is genuinely template-wide (e.g., a service everyone offers that we missed), then yes, edit the template — but version-bump `template.json` and note the change in the commit message.
