# Rank AI — Build Site Skill Spec (`rank-ai-build-site`)

**Last updated:** 2026-05-13
**Implementation:** `rank-ai/scripts/build_site.py`
**Skill wrapper:** `~/.claude/skills/rank-ai-build-site/SKILL.md` (interactive)
**Position in pipeline:** Skill 3 of 4. Runs *after* `rank-ai-plan-site` (the plan dir exists at `rank-ai/clients/{slug}/plan/`) and *before* `rank-ai-blog-routine`.

## Locked architectural decisions (2026-05-13)

These are non-negotiable choices because Cloudflare Pages locks them at project creation:

- **Deploy mechanism: Git-connected Cloudflare Pages.** Every push to a configured branch triggers a Cloudflare-side build + deploy. NOT `wrangler pages deploy` from local. Cannot be changed after the Pages project is created.
- **Per-client GitHub repo: required from day 1.** Each client gets a dedicated repo at `github.com/restorationai/{slug}-site`. Owned by the `restorationai` user account.
- **Branch strategy: `main` = production, `staging` = preview.** Push to `staging` → automatic preview deploy at `*.pages.dev`. Push to `main` → production build. Optionally bind `staging.{domain}` CNAME for a branded preview URL.
- **One-time per-Cloudflare-account prerequisite:** the Cloudflare ↔ GitHub OAuth integration must be authorized once in the Cloudflare dashboard (Workers & Pages → Create application → Pages → Connect to Git → authorize `restorationai`). Required before the first Skill 3 deploy.
- **Apex cut-over is gated:** binding `{domain}` (apex) to the Pages project is a separate, explicit step (`--cut-over` flag). Until that step, the existing live site stays up. This is the only irreversible action in the entire pipeline.

---

## Purpose

Turn a deterministic site plan into a deployed Astro site on Cloudflare Pages. Skill 2 produced the blueprint; Skill 3 instantiates it — scaffolds the Astro repo, generates content + images for every planned URL, builds the static output, and deploys to Cloudflare Pages bound to the client's domain.

Skill 1 produced infrastructure. Skill 2 produced the blueprint. Skill 3 produces the *site*. After Skill 3 succeeds the client has a live website at `https://{their-domain}/` and `images.{their-domain}/` serves the R2 bucket.

## Position relative to the plan

Skill 3 is intentionally **non-creative**. Every page-level decision (URLs, titles, meta, keywords, schema, internal links, image roles, target word counts) is already in the plan. Skill 3's job is:

1. Scaffold an Astro repo with the right files in the right places.
2. Generate the *content* (LLM prose) and *images* (Nano Banana) per the plan.
3. Build and deploy.

If Skill 3 catches itself making a decision Skill 2 should have made, that's a signal the plan is incomplete — fix the spec or template, not the build.

## Why a separate skill

1. **Content generation is expensive and slow.** Hundreds of LLM calls plus image generation per client. Decoupling it from planning means re-running the plan (cheap) doesn't trigger a re-render (expensive). Re-rendering specific pages is also possible without touching the rest.
2. **Build artifacts have a different lifecycle.** The plan is canonical. The Astro repo can be regenerated from the plan; it's a derivative artifact, not source of truth.
3. **Deploy is a permission-scoped operation.** Skill 3 needs Cloudflare Pages:Edit (different from Skill 1's Zone+R2 scope). Keeping it separate keeps token surface clean.
4. **Per-page re-renders need a fast path.** Skill 4's blog routine re-uses Skill 3's render subroutine to write a single blog post. Bundling render with scaffold would slow Skill 4.

## Contract

### Inputs

| Source                                                | Required | Notes                                                                 |
| ----------------------------------------------------- | -------- | --------------------------------------------------------------------- |
| `rank-ai/clients/{slug}.json`                         | yes      | Client record, must have `status=active` and `plan_status=planned`    |
| `rank-ai/clients/{slug}/plan/url-plan.json`           | yes      | Plan output from Skill 2                                              |
| `rank-ai/clients/{slug}/plan/content-map.csv`         | yes      | Per-page metadata                                                     |
| `rank-ai/clients/{slug}/plan/internal-links.json`     | yes      | Link graph                                                            |
| `rank-ai/clients/{slug}/plan/schema-stubs.json`       | yes      | Per-URL schema stub bindings                                          |
| `rank-ai/clients/{slug}/plan-input.json`              | yes      | Brand details + service catalog refs                                  |
| `rank-ai/templates/{template}/`                       | yes      | Archetype JSONs, schema stubs, linking-rules                          |
| `rank-ai/templates/astro-starter/`                    | yes      | Canonical Astro starter (forked per client)                           |

### Outputs

Two surfaces:

**A) Local working tree at `rank-ai/sites/{slug}/`** (also the git working directory for the GitHub repo):

```
rank-ai/sites/{slug}/                       # the per-client Astro repo (git working tree)
├── .git/                                   # initialized at scaffold; remote = github.com/restorationai/{slug}-site
├── .gitignore
├── astro.config.mjs
├── package.json
├── tsconfig.json
├── public/
│   ├── favicon.ico
│   ├── robots.txt                          # generated at scaffold
│   ├── llms.txt                            # AI crawler ingestion surface
│   └── ai.txt                              # AI crawler allow/disallow policy
├── src/
│   ├── content/
│   │   └── config.ts                       # Astro content collections schema
│   ├── content/pages/                      # one markdown file per fixed page (home/about/contact)
│   ├── content/services/                   # one per service-landing
│   ├── content/service-areas/              # one per service-area
│   ├── content/locations/                  # one per service-area-service (cross-product)
│   ├── content/blog/                       # one per blog-post
│   ├── content/legal/                      # privacy/terms/accessibility
│   ├── layouts/
│   ├── components/
│   ├── pages/                              # Astro route files (dynamic routing)
│   └── styles/
└── .rank-ai/
    ├── build-state.json                    # render queue, last-built timestamps, content hashes
    └── cost-log.jsonl                      # per-render telemetry
```

Note: `wrangler.toml` is intentionally absent — Git-connected Cloudflare Pages reads its build config from the Pages dashboard (configured by the `deploy` subcommand on project creation), not from a local toml.

**B) Remote GitHub repo at `github.com/restorationai/{slug}-site`**:

- Created via `mcp__github__create_repository` on `scaffold`
- Initial push includes the full local tree (above)
- Cloudflare Pages project `rankai-{slug}` is bound to this repo at deploy time
- Push to `main` → production build by Cloudflare
- Push to `staging` → preview build at `*.pages.dev`
- All long-running state of the site (commit history) lives here, not locally

Also writes back to `rank-ai/clients/{slug}.json`:

```json
{
  ...,
  "build": {
    "scaffolded_at": "...",
    "rendered_at": "...",
    "last_pushed_at": "...",
    "cut_over_at": "...",
    "github_repo": "restorationai/narestco-site",
    "pages_project": "rankai-narestco",
    "preview_url": "https://rankai-narestco.pages.dev",
    "deploy_url": "https://narestco.com"
  },
  "build_status": "scaffolded|content_queued|content_rendered|pushed_staging|pushed_main|cut_over"
}
```

### Side effects

- Creates a directory tree at `rank-ai/sites/{slug}/`
- Creates a GitHub repository at `restorationai/{slug}-site` (one per client, via `mcp__github__create_repository`)
- Pushes initial commits to the repo (via `mcp__github__push_files` or git+token-over-https)
- Anthropic API calls for content generation (cost: ~5–15¢ per page)
- Nano Banana API calls for images (per the image policy: ~$0.04/Pro, lower for Flash; ~3–6 images per page)
- R2 PUTs for every generated image (uses Skill 1's bucket binding)
- Cloudflare Pages project creation (one per client, idempotent) bound to the GitHub repo
- Cloudflare DNS A/CNAME record updates to point the apex at Pages (final cut-over step only)
- Cloudflare-side `npm install && npm run build` triggered by every git push (no local build necessary except for `preview`)

### Idempotency

Every subcommand is idempotent:

- `scaffold` — re-running diffs the repo against the plan and applies only changed files. Never destroys uncommitted local edits.
- `render` — content_hash per page; only re-generates pages whose plan-row hash has changed since last render. Manual edits to generated content are preserved via a sentinel (frontmatter `manual_override: true`).
- `build` — vanilla `npm run build`; no state.
- `deploy` — wrangler `pages deploy` is itself idempotent.

## State machine

```
(plan_status=planned)
       │
       │ scaffold        creates local tree + GitHub repo, first push to `main`
       ▼
scaffolded               repo exists locally and on GitHub; no page content yet
       │
       │ queue           (optional explicit step; render implies it)
       ▼
content_queued           render queue populated in .rank-ai/build-state.json
       │
       │ render          generates content + images, commits locally
       ▼
content_rendered         every queued page has body content + frontmatter
       │
       │ push-staging    pushes to `staging` branch
       ▼
pushed_staging           Cloudflare auto-built and served preview at *.pages.dev
       │
       │ push-main       (after review) PR merge or fast-forward to `main`
       ▼
pushed_main              Cloudflare auto-built production; lives at {project}.pages.dev
       │
       │ cut-over        binds apex domain {client-domain} → Pages project
       ▼
cut_over                 site live at https://{domain}/, old hosting bypassed
```

Each transition is recorded with a timestamp on the client record. Failures hold the state at the in-progress step so re-runs resume from where it stopped. The Cloudflare-side build is the slow step — `push-staging` and `push-main` return as soon as the push completes; users poll the Pages deployment URL or use `status` to monitor.

## Subcommands

| Subcommand        | Purpose                                                                                                       | Cost    |
| ----------------- | ------------------------------------------------------------------------------------------------------------- | ------- |
| `scaffold`        | Materialize local Astro repo; create GitHub repo; push initial commit; create Cloudflare Pages project bound to it | Free    |
| `queue`           | Populate `.rank-ai/build-state.json` render queue from plan diff                                              | Free    |
| `render`          | Generate content + images for queued pages; commit locally                                                    | $$$     |
| `build`           | Local `npm install && npm run build` (sanity check only — actual build runs on Cloudflare)                    | Free    |
| `preview`         | Run `npm run dev` for visual review on localhost                                                              | Free    |
| `push-staging`    | `git push origin staging` — triggers Cloudflare preview build at *.pages.dev                                  | Free    |
| `push-main`       | `git push origin main` — triggers Cloudflare production build                                                 | Free    |
| `cut-over`        | Bind apex domain `{client-domain}` to Pages project (irreversible go-live step; requires explicit confirmation) | Free*   |
| `status`          | Show build state + per-page render status + latest deployment URL from Cloudflare API                         | Free    |
| `rerender`        | Force re-render of specific pages (`--paths` filter or `--archetype`)                                         | $$      |

\* Cloudflare Pages free tier covers 500 builds/month, unlimited bandwidth, unlimited preview deployments.

## Algorithm

### Pass 1 — Scaffold

The Astro starter at `rank-ai/templates/astro-starter/` is copied to `rank-ai/sites/{slug}/`. The starter is a fully-working Astro project with:

- TypeScript + Astro content collections configured
- Tailwind CSS (or vanilla CSS — locked at starter level)
- Per-page schema injection component
- Internal-link rendering component (reads `internal-links.json`)
- Layout components: Header, Footer, HeroSection, FAQSection, CtaBanner, ScrollToTop
- Cloudflare Pages adapter configured

After copy, brand theming is applied via a token sweep:

- `BRAND_DISPLAY_NAME`, `BRAND_PHONE`, `BRAND_EMAIL`, etc. → substituted in starter components
- Brand colors / fonts — if the client supplied custom values in plan-input, applied; otherwise use restoration-vertical defaults (deep navy + emergency-red accent, sans-serif system font)
- Logo URL → injected into Header component (if missing, generate placeholder via Nano Banana with the brand name + a simple mark)

The starter contains *no* per-page content — only layout primitives. Content collections are empty after scaffold.

Routes wire up automatically from collections:

```
src/pages/index.astro                    # → /
src/pages/[fixed].astro                  # → /about/, /contact/, /services/, etc.
src/pages/services/[slug].astro          # → /services/{service-slug}/
src/pages/service-areas/[area].astro     # → /service-areas/{area-slug}/
src/pages/service-areas/[area]/[service].astro    # → /service-areas/{area-slug}/{service-slug}/
src/pages/blog/[slug].astro              # → /blog/{post-slug}/
src/pages/[legal].astro                  # → /privacy/, /terms/, /accessibility/
```

### Pass 2 — Queue

Walk `content-map.csv`. For each row:

1. Compute `plan_hash` = sha256 of the row's plan-relevant fields.
2. Look up existing content collection entry for the URL.
3. If no entry or its frontmatter `plan_hash` differs, mark for render.
4. If frontmatter `manual_override: true`, skip (the client edited this by hand).

Output: `.rank-ai/build-state.json` with the list of queued URLs.

### Pass 3 — Render

For each queued page:

1. **Resolve archetype prompt** — `.rank-ai/prompts/{archetype}.md` is the LLM prompt template. Populated with the row's primary keyword, secondaries, intent, target word count, brand voice tokens, internal-link context.
2. **Generate body content** — call Claude API. Output is markdown body. Caches under `.rank-ai/cache/content/{url-hash}.md` (regen only re-pulls if plan_hash changed).
3. **Generate images** — for each role in `image_roles`:
   - `hero`, `og` → Nano Banana Pro (or per `image_policy`)
   - `inline-N` → Nano Banana Flash
   - Image prompt = archetype-level image prompt + per-page context (city, service, etc.)
   - Upload to R2: `blog/{YYYY}/{MM}/{slug}/{role}.png` for blog posts, `pages/{slug}/{role}.png` for site pages
   - Returned URLs are written to frontmatter
4. **Compose markdown** — title, meta description, schema (hydrated from stubs), internal links list, image refs, body content, FAQ block (if archetype has one and content gen produced it).
5. **Write to content collection** — `src/content/{collection}/{slug}.md`
6. **Sensitive content guardrails** — for services flagged `content_guardrails: sensitive` (biohazard, crime scene, hoarding, meth lab), the prompt template uses a different tone register: clinical, empathetic, no graphic detail.
7. **Cost telemetry** — every render emits a line to `.rank-ai/cost-log.jsonl` with token + image counts. Skill prints a per-run summary.

Render is parallelizable — by default it runs 4 pages concurrently. Concurrency is configurable.

### Pass 4 — Build

`cd rank-ai/sites/{slug} && npm install --silent && npm run build`

Output goes to `dist/`. Astro handles route generation from content collections automatically.

### Pass 5 — Deploy (split into three discrete steps)

**Step 5a — GitHub push (`push-staging` and `push-main`):**

After `render` commits content locally, the deploy mechanism is just git:

```
git push origin staging      # → Cloudflare auto-builds and serves preview at rankai-{slug}.pages.dev
git push origin main         # → Cloudflare auto-builds production; lives at {project}.pages.dev
```

Cloudflare Pages watches both branches via the GitHub integration set up at scaffold. Each push fires a webhook to Cloudflare, which runs `npm install && npm run build` in their build environment and serves `dist/`. We do not run wrangler locally for any of this.

For programmatic pushes, the script uses `mcp__github__push_files` (commits files to the repo via the GitHub API; no local git required) OR `git push` with the token from `restorationai`'s PAT. We default to `git push` since it preserves local commit history and conventional git workflow.

**Step 5b — Watching the Cloudflare build:**

After push, poll the Cloudflare Pages API:

```
GET /accounts/{account_id}/pages/projects/rankai-{slug}/deployments
```

Surface the deployment URL and status (queued / building / success / failure). On success: print the URL. On failure: print the build log URL.

**Step 5c — Cut-over (`cut-over`):**

The cut-over is the only step that touches the apex DNS:

1. Confirm with the user explicitly: "This will replace the existing live site at `https://{domain}/` with the new Cloudflare Pages build. Type the domain to confirm."
2. Bind the apex domain to the Pages project:
   ```
   POST /accounts/{id}/pages/projects/rankai-{slug}/domains
   { "name": "{domain}" }
   ```
3. Cloudflare automatically updates the zone DNS — the apex A record (which was pointing at the legacy host from `mirror-dns`) is replaced with Pages.
4. Optionally bind `www.{domain}` to the same project for canonical redirect handling.
5. Update client record: `cut_over_at`, `deploy_url=https://{domain}`.

This is the only irreversible action in the entire pipeline. The skill wrapper requires the user to type the domain (not just click yes) before executing.

**Pre-cut-over staging:**

For a branded staging URL ahead of cut-over (e.g., to share with a client for review), bind `staging.{domain}` as a separate Pages domain pointing at the `staging` branch's preview environment:

```
POST /accounts/{id}/pages/projects/rankai-{slug}/domains
{ "name": "staging.{domain}", "branch_alias": "staging" }
```

This is optional and reversible — unbinding the subdomain doesn't affect the live site.

## Astro starter contents (`rank-ai/templates/astro-starter/`)

Locked-in choices:

- **Astro 5+** with strict TypeScript
- **Tailwind CSS** — for restoration sites, a utility-first approach lets each client's brand colors be applied via tailwind config without re-authoring components.
- **Content collections** — every URL is a content collection entry; route files are thin wrappers
- **No JS hydration by default** — Astro Islands only where genuinely needed (e.g., scroll-to-top button, contact form). Default to zero JS for SEO and load speed.
- **Image strategy** — Cloudflare Image Transformations on the R2 URL (no per-build image processing). The `<Image>` component emits responsive `srcset` pointing at `cdn-cgi/image/...` transforms.
- **Schema injection** — single `<Schema>` component that takes the page's schema stubs + hydrated brand vars and emits one `<script type="application/ld+json">` block per stub.
- **Sitemap.xml** — auto-generated by `@astrojs/sitemap`, includes every page in collections.
- **Robots.txt** — generated at scaffold time, allows all crawlers.
- **OG/Twitter meta** — derived from page frontmatter (title, meta_description, hero image URL).

## Content generation policy

**Prompt templates live with the starter**, not the plan template. Why: prompt iteration is frequent and copy-tweaking shouldn't churn the planner. The plan defines *what* (keywords, intent, word count); the prompt defines *how* (tone, structure, brand voice).

Prompt structure per archetype:

```
.rank-ai/prompts/service-area-service.md
.rank-ai/prompts/service-landing.md
.rank-ai/prompts/blog-post.md
.rank-ai/prompts/home.md
...
```

Each prompt is a markdown file with frontmatter declaring required input variables. At render time, variables are populated from the page row + brand block.

### Sensitive content rules

Pages whose service has `content_guardrails: sensitive` (biohazard, crime-scene, hoarding, meth-lab) use a stricter prompt:

- No graphic descriptions of trauma scenes or substances
- Empathetic, professional tone (acknowledging the human context)
- Focus on process, certifications, discretion, and 24/7 availability rather than the scene itself
- FAQ-block questions are about logistics, insurance, privacy — not the incident
- Image generation prompts avoid depicting blood, bodily fluids, or distressing scenes — defaults to clinical "team in PPE in a clean room" framing

These rules are encoded in the per-archetype prompts and the image-gen role mappings.

## Per-client repo layout: one GitHub repo per client (locked)

Every client gets a dedicated GitHub repo at `github.com/restorationai/{slug}-site`. The local working tree at `rank-ai/sites/{slug}/` is just the checked-out copy — the canonical state lives on GitHub, because that's what Cloudflare Pages watches.

Why locked here (not deferrable):

- Cloudflare Pages locks "Git-connected vs Direct Upload" at project creation. We need git-connected so that pushes auto-deploy. So we need a repo to point at, *before* the first deploy.
- Per-client repos are required for the Git integration to work cleanly (Pages does support monorepo path filters, but the per-client domain binding gets messy and the build trigger is one-build-per-monorepo-push which doesn't make sense at our scale).

Implications:

- Repo creation is part of `scaffold`, not a later phase. If the user wants to opt-out of GitHub for a specific client, that's a manual operation and the client doesn't go through the standard Skill 3 path.
- Repo visibility: **public by default** (no secret IP in restoration marketing sites; cheaper on GitHub's free tier). Override with `--private` per client if needed.
- Client handoff later: if the agency ever sells a client back to them, the GitHub repo can be transferred to the client's account. Cloudflare Pages will need to re-authorize the new owner.

## Credentials

Three credentials enter the Skill 3 surface; all stored in `rank-ai/.env`:

| Env var                      | Scope needed                          | Source                                                            |
| ---------------------------- | ------------------------------------- | ----------------------------------------------------------------- |
| `CLOUDFLARE_API_TOKEN`       | Zone:Edit (DNS) + Pages:Edit          | Existing zone token; add Pages:Edit scope, or issue a new combined token |
| `CLOUDFLARE_R2_API_TOKEN`    | R2:Edit                               | Already exists (image uploads from `render`)                      |
| `CLOUDFLARE_ACCOUNT_ID`      | n/a                                   | Already exists                                                    |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | repo (full)                         | Already exists for `restorationai` user; verified working via GitHub MCP |
| `ANTHROPIC_API_KEY`          | n/a                                   | Set for content generation in `render`                            |
| `GEMINI_API_KEY`             | n/a                                   | Already used by Nano Banana for image generation                  |

The `CLOUDFLARE_API_TOKEN` needs to grow a new scope (Account → Cloudflare Pages → Edit). Easy to do at the Cloudflare dashboard → My Profile → API Tokens → edit the existing zone token. Confirm scope is added before first `scaffold` runs.

**One-time Cloudflare ↔ GitHub OAuth (manual, dashboard-only):**

Before the first `scaffold` deploys a Pages project, the Cloudflare account needs to have authorized GitHub access:

1. Open `https://dash.cloudflare.com/{account_id}/workers-and-pages`
2. Click **Create application** → **Pages** → **Connect to Git**
3. Authorize GitHub for the `restorationai` user account
4. Grant Cloudflare access to "All repositories" (or selectively whitelist; "All" is simpler)

This is a one-time per-Cloudflare-account action. After it's done, every Pages project creation via the API can reference any repo on `restorationai`'s GitHub. The skill wrapper will surface this prerequisite check before the first deploy.

## Failure modes & recovery

| Failure                                       | Cause                                                | Recovery                                                      |
| --------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------- |
| `scaffold` aborts: plan not found             | Skill 2 not run for this slug                        | Run `rank-ai-plan-site` first                                 |
| `render` LLM rate limit                       | Anthropic API throttled                              | Auto-backoff + retry; surface remaining quota                 |
| `render` Nano Banana quota                    | Gemini Pro quota exhausted                           | Auto-downgrade to Flash for non-hero/og images; warn          |
| `render` image upload to R2 fails             | R2 token revoked or bucket missing                   | Re-check `rank-ai/.env`; re-run scaffold to recreate binding  |
| `build` npm install fails                     | Network or starter dependency issue                  | Surface logs; retry; if persistent, rebuild starter           |
| `build` astro build fails                     | Generated content has broken markdown/MDX            | Surface failing page; mark for re-render with `--validate-md` |
| `scaffold` GitHub repo already exists         | Slug collision or rerun                              | Skip create, fast-forward to push                             |
| `scaffold` GitHub auth fails                  | PAT scope missing or revoked                         | Re-issue token; the existing one has `repo` scope confirmed working |
| `scaffold` Cloudflare Pages project create fails: "GitHub not authorized" | One-time OAuth not done | Walk user through Cloudflare dashboard authorization step (above)  |
| `push-staging` / `push-main` git rejection    | Local branch behind remote                           | Surface error; ask user to investigate (no auto-force-push)   |
| Pages build fails on Cloudflare side          | Bad markdown, broken JSON-LD, missing dep            | Print build log URL from Pages API; user inspects and fixes locally |
| `cut-over` apex domain bind fails             | Existing A record conflict from mirror-dns           | Spec is to *replace* the record — Cloudflare API does this in one call; if it errors, surface verbatim |
| `cut-over` confirmation typo                  | Safety guard                                         | Re-run; user types the exact domain to confirm                |

## Skill wrapper UX (`rank-ai-build-site`)

The interactive wrapper:

1. Verifies client has a plan (`plan_status=planned`). If not, suggests `rank-ai-plan-site`.
2. Confirms slug + display name + URL count (from the plan).
3. Asks: scaffold-only / full-build / full-build-and-deploy?
4. If full-build, shows estimated cost (pages × per-page render cost + image counts × policy-weighted cost). Confirms.
5. Shells out to `build_site.py scaffold`. Shows generated file count.
6. Optionally shells out to `render` with progress bar.
7. Optionally shells out to `build` and `preview` (offers to open localhost:4321).
8. If user approves: `deploy --cut-over` and watches for green deploy URL.
9. Final summary block: live URL, sitemap URL, deploy ID, cost incurred.

The skill is the conversational glue; the script does the work.

## Cost guardrails

Build into the skill:

1. **Per-build ceiling.** If a render would exceed N dollars (default $50/client), pause and ask for explicit confirmation.
2. **Hero image cap.** Per-client absolute limit on Pro-tier images per build (default 25). Excess gets downgraded to Flash.
3. **Skip-if-cached.** Default behavior is to never re-render a page whose plan_hash hasn't changed. Force with `--force-rerender`.
4. **Render-by-priority.** Render order = top priority first. If the run hits an error halfway, the highest-value pages are already done.
5. **Cost log.** Every API call appended to `.rank-ai/cost-log.jsonl`. End-of-run summary prints totals by API + by archetype.

## Versioning

The starter has its own version (`templates/astro-starter/VERSION`). The client record stamps `starter_version` on every build. Updating the starter for one client doesn't auto-update others — clients get pinned to the starter version they were built against until explicitly re-scaffolded.

This matters when we iterate on the starter: existing client sites don't silently break.

## Out of scope

- Designing the site IA — Skill 2
- Recurring blog post generation after launch — Skill 4
- Domain registration — manual / out of band
- A/B testing infrastructure — separate project
- CMS or content backend — Astro content collections are the "CMS"; clients don't have a dashboard yet
- Analytics — Cloudflare Web Analytics tags auto-inserted by the starter; GA4 wiring left to a Skill 5 or manual step
- Multi-language sites — restoration is monolingual (en-US) for now

## What this skill bakes in

By committing to this spec, downstream skills (Skill 4 and beyond) never have to:

- Decide where in the repo new blog posts go (always `src/content/blog/{slug}.md`)
- Pick the deploy mechanism (always `wrangler pages deploy`)
- Re-create Pages projects (one-per-client, locked at first deploy)
- Wire image storage (R2 bucket already bound by Skill 1, image URLs follow the convention from `image-hosting-architecture.md`)
- Re-derive the link graph (it's in the plan; Skill 4 re-uses it for related-posts blocks)

## Resolved decisions (2026-05-13)

1. **Starter framework** — Astro 5 + Tailwind, hand-rolled UI primitives (no component lib). Locked.
2. **Per-client GitHub repos** — required from day 1, owned by `restorationai` user, named `{slug}-site`. Locked.
3. **Branch strategy** — `main` (production) + `staging` (preview). Both are git-connected branches on the Cloudflare Pages project. Locked.
4. **Prompt template versioning** — bundled with the Astro starter; both share `templates/astro-starter/VERSION`. Layout + prompt iterate together. Locked.
5. **Anthropic Sonnet 4.6** for launch content (Skill 3). Skill 4 (blog routine) can use a cheaper model for ongoing posts. Per-archetype model override configurable.
6. **Sitemap** — auto-generated by `@astrojs/sitemap` plugin; lastmod derived from page frontmatter `plan_hash` + `updated_at`. Locked.
7. **`llms.txt` and `ai.txt`** — both written at scaffold time. `llms.txt` is a markdown index of the site for AI ingestion (services, areas, top pages, key blog posts). `ai.txt` is a robots.txt-style allow/disallow for AI crawlers. Locked.
8. **404 page** — static, with hero CTA back to home + services hub. Locked.
9. **Contact form** — Cloudflare Workers POST handler with Turnstile (free, same-stack, no third-party form service). The handler emails the brand's `info@` address and stores submissions in a Cloudflare D1 table. Locked.
10. **Apex cut-over** — explicit step (`cut-over`), requires user to type the domain to confirm. Locked.
11. **Schema stubs (added 2026-05-13):**
    - `local-business.json` (existing) — every page
    - `service.json` (existing) — service-landing, service-area-service
    - `blog-posting.json` (existing) — blog posts
    - `faq.json` (existing) — pages with FAQ blocks
    - `organization.json` (new) — site-wide
    - `website.json` (new) — site-wide
    - `breadcrumb-list.json` (new) — non-home pages
    - `aggregate-rating.json` (new) — home + about (uses GBP rating)

## Open implementation questions

1. **Cloudflare Workers vs Pages Functions for the contact form** — Pages Functions is integrated, no separate Workers project needed. Recommendation: Pages Functions.
2. **Form storage** — Cloudflare D1 table per client, or a shared D1 across all clients? Per-client is cleaner; shared is cheaper at scale. Defer until we see usage.

## Default to lock in

Make the architecture a hard convention: **every Rank AI client gets the same Astro starter, the same content-collection layout, the same Cloudflare Pages project structure.** Per-client variation only appears at three layers:

1. Brand tokens (colors, logo, fonts) — substituted at scaffold.
2. Page content + images — generated at render from the plan.
3. Domain binding — set at deploy.

Everything else (layouts, components, schema injection, build config, deploy mechanism) is identical across clients. Single code path for the agency.

---

*This spec is the contract for the Skill 3 implementation. Implementation lives at `rank-ai/scripts/build_site.py` and `rank-ai/templates/astro-starter/`. State of truth is `rank-ai/clients/{slug}.json` plus `rank-ai/sites/{slug}/.rank-ai/build-state.json`.*
