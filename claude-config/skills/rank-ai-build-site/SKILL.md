---
name: rank-ai-build-site
description: Build a Rank AI client's site end-to-end — scaffold from the canonical starter, render real body content + FAQ via Claude, sync-deploy to per-client GitHub repo, preview on staging, push to production, then cut over the apex domain to go live. Wraps `rank-ai/scripts/build_site.py`. Runs after `rank-ai-plan-site`. Use whenever the user says "build the site", "render the content", "deploy to staging", "go live", "cut over", "rank-ai-build-site", or has a planned client ready to ship.
---

# Rank AI — Build a Client Site

Skill 3 of 4 in the Rank AI pipeline. Drives `rank-ai/scripts/build_site.py` through scaffold → render → sync-deploy → preview → production → cut-over.

## Project root

`/Users/santino/Desktop/mywebsitecode/rank-ai/` — this is the **pipeline monorepo**. All work happens here. Change directory at session start.

## Read first

- `rank-ai/docs/multi-client-workflow.md` — canonical topology and end-to-end flow (READ THIS to understand the monorepo + per-client repo split)
- `rank-ai/docs/build-site-skill-spec.md` — the build skill contract
- `rank-ai/docs/content-differentiation.md` — content uniqueness rules enforced by prompts
- `rank-ai/clients/{slug}.json` — must have `plan_status: planned` (from Skill 2)

## Topology you must understand

- **Monorepo**: `~/Desktop/mywebsitecode/rank-ai/` (everything — scripts, templates, prompts, sites/) is ONE git repo, remote at `github.com/restorationai/Rank-AI-Pipeline`. ALL development happens here.
- **Per-client repos**: each client has a separate GitHub repo at `github.com/restorationai/{slug}-site`. These are **derived deploy artifacts** — never edited directly. They get populated by `sync-deploy`.
- **Cloudflare Pages**: each client has a Pages project (`rankai-{slug}`) git-connected to its per-client repo. Auto-builds on push.

## Credentials in `rank-ai/.env`

- `CLOUDFLARE_R2_API_TOKEN` — has Pages:Edit + R2:Edit
- `GITHUB_PERSONAL_ACCESS_TOKEN` — restorationai user, `repo` scope (creates per-client repos)
- `ANTHROPIC_API_KEY` — content gen
- `GOOGLE_AI_API_KEY` — Nano Banana (image gen, when wired)

Source the env at session start:

```bash
set -a; . rank-ai/.env; set +a
```

## State machine

```
plan_status=planned
   │ scaffold (1 min, free)
   ▼
scaffolded
   │ render (~30-45 min background, ~$8)
   ▼
content_rendered
   │ sync-deploy --branch staging
   ▼
pushed_staging (Cloudflare preview build fires)
   │ user reviews at https://staging.rankai-{slug}.pages.dev/
   │ sync-deploy --branch main
   ▼
pushed_main (Cloudflare production build fires, lives at rankai-{slug}.pages.dev)
   │ cut-over (gated, requires typed-domain confirmation, irreversible)
   ▼
cut_over (site live at https://{domain}/)
```

## Step 1 — Pre-flight

Confirm the slug exists and has `plan_status: planned`. If not, suggest `rank-ai-plan-site` and stop.

Show: slug, display name, domain, plan URL count, planned services, planned areas. Ask the user to confirm the target.

## Step 2 — Scope of this run

```
What do you want to do?

a) Full pipeline: scaffold → render → sync-deploy staging → sync-deploy main → cut-over (Recommended for first launches)
b) Scaffold + render + sync to staging only (preview, defer production)
c) Scaffold only (set up infra, defer content)
d) Just render (scaffold already done — generate or refresh content)
e) Just sync-deploy (content already rendered, push existing files)
f) Just cut-over (production looks good at pages.dev, flip apex domain)
```

For (a) and (b), show the cost estimate before kicking off render:
- ~$0.03-0.05 per page × {plan URL count} pages = $X
- Time: ~30-45 min in background

Confirm before starting render.

## Step 3 — Scaffold

```bash
cd ~/Desktop/mywebsitecode/rank-ai
python3 scripts/build_site.py scaffold --slug <slug>
```

The script:
1. Copies `templates/astro-starter/` (canonical design) to `sites/<slug>/`
2. Substitutes ~35 brand tokens
3. Generates one content collection markdown per planned URL with placeholder body
4. Does NOT init a per-client `.git` (new topology — monorepo handles git)

Surface stdout verbatim. End state: `sites/<slug>/` is a complete Astro project that builds but has placeholder content.

## Step 4 — Render

```bash
python3 scripts/build_site.py render --slug <slug> --workers 4
```

- Skips already-rendered pages (`rendered: true` in frontmatter) unless `--force`
- Priority-ordered (highest priority pages render first)
- Calls Claude Sonnet 4.6 with the strict-differentiation prompts
- Writes body + FAQ to each page's markdown
- Logs per-page cost to `sites/<slug>/.rank-ai/cost-log.jsonl`

**Run in the background** via `run_in_background: true` because render takes 30-45 min. Set up a monitor or background watcher that fires when "Render summary" appears in the output:

```bash
until grep -q "Render summary" {output-file}; do sleep 30; done
```

When the watcher fires, read the output file and report success/failure count + total cost.

If pages failed (timeout, non-JSON, etc.), re-run render — the idempotency check skips the 220+ successful pages and just retries the failed ones.

## Step 5 — Commit to monorepo

After render completes, commit the rendered content to the pipeline monorepo:

```bash
cd ~/Desktop/mywebsitecode/rank-ai
git add sites/<slug>/
git commit -m "Render <slug>: {N} pages via build_site.py"
git push origin main
```

## Step 6 — Sync to staging

```bash
python3 scripts/build_site.py sync-deploy --slug <slug> --branch staging
```

What this does (internally):
1. Verifies the monorepo working tree is clean
2. Ensures `github.com/restorationai/<slug>-site` exists (creates if missing)
3. Configures a git remote `deploy-<slug>` on the monorepo
4. Runs `git subtree split --prefix=sites/<slug>` to extract a synthetic branch
5. Force-pushes that branch to the per-client repo's `staging` branch
6. Cloudflare Pages auto-builds the preview

After the push completes, poll Cloudflare's API for the new staging deployment until `deploy/success`. Surface the URL to the user:

```
Preview live at: https://staging.rankai-<slug>.pages.dev/
```

Wait for the user to review. Don't proceed to main without explicit approval.

## Step 7 — User review on staging

Tell the user the staging URL and what to look at:
- Home page (overall design + brand identity)
- Top 1-2 service pages (real rendered content)
- Top 1-2 cross-product pages (the SEO money pages — most are city × water-damage)
- Blog index
- 404
- Footer NAP, license #
- FAQ schema present (visible in dev tools or via `curl ... | grep "@type"`)

If issues:
- Content quality issue on specific pages → `render --slug X --url /problem/path/ --force`
- Layout / design issue → fix in `templates/astro-starter/`, re-sync to sites/<slug>/ (or directly fix in sites/<slug>/ — your call), re-commit, re-sync-deploy staging
- Missing brand info → fix `plan-input.json`, re-scaffold (preserves rendered content), re-sync

Pause here until the user explicitly approves the staging.

## Step 8 — Sync to production

```bash
python3 scripts/build_site.py sync-deploy --slug <slug> --branch main
```

Same operation, target `main` branch. Cloudflare auto-builds production. Lives at `https://rankai-<slug>.pages.dev/`.

Verify the production deploy succeeded via the Cloudflare API.

The client's actual domain (`<domain>`) still points at their legacy host — apex cut-over is a separate step.

## Step 9 — Cut-over to apex (the irreversible step)

`build_site.py cut-over --slug <slug>` is currently spec'd but not yet implemented as a subcommand. The work it should do:

1. Confirm with the user explicitly: *"This will replace the existing live site at `https://<domain>/` with the Cloudflare Pages build. Old hosting stops serving for this domain within minutes. Type the domain to confirm."*
2. Only proceed if the typed string matches the domain exactly.
3. POST to `/accounts/{id}/pages/projects/rankai-<slug>/domains` with `{"name": "<domain>"}`. Cloudflare auto-updates the zone DNS — the apex A record (previously pointing at the legacy host from `mirror-dns`) is replaced with Pages.
4. Optionally bind `www.<domain>` too for canonical redirect handling.
5. Update client record: `cut_over_at`, `build_status: cut_over`, `deploy_url: https://<domain>`.

Until the subcommand exists, do this manually:

```bash
set -a; . rank-ai/.env; set +a
curl -X POST "https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID/pages/projects/rankai-<slug>/domains" \
  -H "Authorization: Bearer $CLOUDFLARE_R2_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "<domain>"}'
```

Watch DNS propagation (1-2 minutes) and verify `https://<domain>/` resolves to the new site.

## Step 9b — Provision Google Search Console (get the new site indexed)

Immediately after the apex resolves on Cloudflare Pages, register the site with Google Search Console under the **agency account** and submit the sitemap, so Google starts crawling and indexing the new site. This is **headless and requires nothing from the client** — we control the Cloudflare DNS, so we self-verify the property:

```bash
python3 scripts/gsc_setup.py provision --slug <slug>
```

This: verifies the domain (adds a DNS TXT record via the Cloudflare API), adds the `sc-domain:<domain>` property to the agency GSC account (`contact@restorationai.io`), submits `https://<domain>/sitemap-index.xml`, and writes `gsc_property_url` + `sitemap_url` back into `clients/<slug>.json`.

- **Always run this at cut-over.** A site that isn't in Search Console with a submitted sitemap is slower to get discovered/indexed — this step is the difference between "live" and "actually findable on Google."
- Prerequisite: the agency GSC token must exist (`python3 scripts/gsc_setup.py` run once, agency-wide). If it's missing, the command says so — run the one-time setup, then re-run provision.
- Non-fatal: if sitemap submission warns, the property is still created and indexing proceeds from crawl. Surface the warning, don't block the launch.
- Confirm in the output that the property was added and the sitemap was accepted.

## Step 9c — Draft the launch press release

Right after GSC provisioning, draft the client's first press release so it's
ready to syndicate the same week the site goes live (launch + citations landing
together is the strongest entity-building window):

```bash
python3 scripts/press_release.py draft --slug <slug>
```

The script's catch-up logic drafts immediately for any client with no row this
quarter — which is always true at launch. The draft lands in the app
(Marketing → Reports → Press Releases) as `draft`; remind the user it still
needs the manual approve → paste into EIN Presswire / Press Advantage → mark
published flow. Quarterly cadence continues automatically from the authority
cron afterwards.

## Step 10 — Output summary

```
==> Build + deploy complete for {display_name}

  Slug:              {slug}
  Production URL:    https://{domain}/
  Staging URL:       https://staging.rankai-{slug}.pages.dev/
  GitHub repo:       https://github.com/restorationai/{slug}-site
  Pages project:     https://dash.cloudflare.com/{account_id}/pages/view/rankai-{slug}
  Total pages live:  {N}
  Total cost (build): ${sum from cost-log.jsonl}
  GSC property:      sc-domain:{domain} (sitemap submitted)

Next:
  - Verify https://{domain}/ resolves correctly (DNS propagation can be 1-2 min)
  - Verify https://www.{domain}/ if you want www binding
  - Confirm the GSC property + sitemap in the agency Search Console account (indexing begins within hours to days)
  - Once https://{domain}/ is verified, the next routine is `rank-ai-blog-routine` (Skill 4, not yet built) for ongoing blog content
```


## Before/After slider imagery — first-pass quality standards

Learned across the FIX Restoration revision cycles (2026-09-22). The
PAIR_CATALOG prompts in `scripts/gen_site_images.py` ENFORCE these in code;
this section is the reasoning, for judging output and writing new kinds.

1. **Restoration physics must be respected.** The damage shown dictates the
   repair shown: inches of standing water on wood = the floor was TORN OUT,
   never "dried and shiny"; heavy char = structural rebuild, not a repaint.
   A homeowner (and an adjuster) reads a mismatch instantly as fake.
2. **The transformation must be unmistakable in one glance.** Same-pattern
   recolors read as a filter, not a repair. Prove replacement with geometry:
   new plank DIRECTION (perpendicular), different plank WIDTH, clearly
   different TONE. If the before and after could be the same surface, redo.
3. **Always an upgrade, never a downgrade.** The after shows equal-or-better
   materials (premium wide plank, never hardwood-to-carpet). The section
   sells the outcome; nobody wants the flood that got them cheaper floors.
4. **Contents follow the story.** Burned furniture is HAULED AWAY and
   replaced with different pieces; identical couches surviving a total-loss
   fire breaks the fiction. Water-damage furniture may survive (it gets
   restored); fire contents do not.
5. **Severity at Home Pride grade.** Befores go full-effect: fire = charred
   structure with exposed joists; sewage = wall-to-wall contaminated water
   with floating debris; mold = a spreading colony with peeling paint. A
   single soot plume or a puddle by a drain undersells the service.
6. **Same room, honestly.** Identical camera angle and architecture between
   before and after — the pair's credibility rests on it being one room.
   Only restoration-plausible changes (damage, surfaces, contents).
7. **Service-matched only, max 5 pairs.** Only services the client actually
   sells (truth-table law); storm/mold/carpet pairs exist only when offered.
8. **Ship webp, keep PNG masters.** 1400px webp q78 (~90KB vs 700-900KB
   PNG); work.ts references the webp. The 7MB-slider page-lag class.
9. **VIEW every generated pair before deploy.** Generation is probabilistic;
   the catalog prompt raises the floor, eyes on the output raise the
   ceiling. One look catches the same-pattern recolor instantly.
10. **Afters are COMPLETELY FINISHED rooms** (Heritage 2026-09-22): no
    exposed framing/beams/joists (a rebuilt ceiling is closed drywall), no
    leftover materials, rolled rugs, tools or debris, and furniture is
    professionally clean or replaced — a stained couch beside brand-new
    flooring reads as a half-done job.
11. **Textiles refresh with the room.** A storm-wrecked bed comes back made
    with brand-new different bedding, not the same white sheets that sat
    under fallen drywall.
12. **EVEN pair count, always.** The slider grid never ships an odd number
    of pairs; the generator trims 3+ to the nearest even (and extends to a
    sixth kind when the client's services support it).

## Auto-chain behavior

This skill is the orchestrator for the build + launch phase. The auto-chain rules:

1. **Don't auto-run cut-over.** Cut-over is irreversible — always require explicit user typed-domain confirmation.
2. **Auto-progress through scaffold → render → sync-staging.** These are reversible and benefit from being run as a single sequence. After staging is built, pause for user review.
3. **From staging review → sync-main**: ask the user "Staging looks good, push to production?" Their yes triggers sync-main. After production is built, pause again before cut-over.
4. **From production → cut-over**: ask the user "Production looks correct at pages.dev. Cut over to apex?" Their yes triggers the cut-over flow (which has its own typed-domain confirmation).

If the user previously selected option (a) "Full pipeline" in Step 2, they're implicitly authorizing this auto-progression — but the cut-over still requires the typed-domain confirm.

## Error handling

- Surface the script's full error output. Don't summarize.
- Render failures: the script reports which URLs failed and why. Re-run render — the idempotency check skips successes and retries just the failures.
- Anthropic rate limits: built-in retry-with-backoff handles 429s and 5xx automatically. If sustained, surface and stop.
- `sync-deploy` errors:
  - "Working tree has uncommitted changes" → commit first or use `--allow-dirty` if you mean it
  - "Repo missing" → script creates it automatically; if it fails to create, check GitHub PAT scope (needs `repo`)
  - "non-fast-forward push" → force-push handles this; if it fails twice, file a bug
- Cloudflare Pages build failure: log URL is in the deployment detail; user inspects build log and fixes locally before re-syncing

## What this skill does NOT do (out of scope)

- DNS or zone management — that's `rank-ai-onboard`
- URL planning, content map, schema stubs — that's `rank-ai-plan-site`
- Ongoing blog post writing — that's `rank-ai-blog-routine` (not yet built)
- Site analytics setup, email infrastructure
- One-off content edits — use a code editor + commit directly in the monorepo

## Before/after images — MANDATORY knowledge base

Any task that creates or edits before/after slider pairs MUST first read
`rank-ai/docs/image-standards/before-after.md` and follow it on the FIRST
pass (core law: restoration REPLACES materials — never the same damaged
item returning identical; weather/window continuity rules; QC checklist).
Agent briefs for pair generation must instruct the agent to read that file
before generating. Pairs also require: files in
public/images/before-after/, wiring in src/data/work.ts, and any new
service image registered in src/data/image-meta.json (unregistered images
silently fail to render).

## Local-first media rule (ProRest/Davis 2026-09-26)

A site may only reference images.{domain} URLs once that client's apex is
LIVE on our DNS. Preview-phase clients get LOCAL copies (public/images/)
of every referenced asset — a dead imagesBase domain hangs page loads and
breaks logos/heroes/blog images silently.

## Guardrails

- Never push to `main` without explicit user approval — it's production.
- Never cut-over without typed-domain confirmation.
- Never run `render --force` on hundreds of pages without showing the cost estimate first.
- Never commit `rank-ai/.env`.
- If a render produces content violating the sensitive-content guardrails (biohazard/crime/hoarding/meth-lab → must be clinical, not graphic), flag the page and stop — don't push problematic content to staging.
