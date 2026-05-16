# Rank AI — Multi-Client Workflow

**Last updated:** 2026-05-16
**Topology version:** 2.0 (hybrid monorepo + per-client deploy repos)

This doc is the canonical reference for how Rank AI ships and maintains many client sites without confusion. It supersedes the per-client-repo-only assumptions in earlier scaffold docs.

---

## The topology in one diagram

```
PIPELINE MONOREPO                                PER-CLIENT DEPLOY REPOS                CLOUDFLARE PAGES PROJECTS
=================                                =======================                =========================
~/Desktop/mywebsitecode/rank-ai/
├── .git/                                        github.com/restorationai/
├── scripts/build_site.py                            narestco-site               ──►   rankai-narestco
├── templates/astro-starter/   (canonical)           (derived deploy artifact)         (Pages, git-connected)
├── templates/restoration/     (planning data)
├── prompts/                   (content prompts)     clientX-site                ──►   rankai-clientX
├── docs/                      (specs, contracts)    (derived deploy artifact)         (Pages, git-connected)
├── clients/{slug}.json        (client records)
└── sites/                     (per-client working   clientY-site                ──►   rankai-clientY
    ├── narestco/              trees)                (derived deploy artifact)         (Pages, git-connected)
    ├── clientX/
    └── clientY/

         ▲                            ▲                                                        ▲
         │ canonical source           │ derived artifact                                        │ auto-build on push
         │ all dev work happens here  │ never edited directly                                   │ Cloudflare watches
         │                            │ regenerated from monorepo                               │ the per-client repos
         │                            │ via `build_site.py sync-deploy`                         │
         │                            │
         └────────── one operation ───┘
                     pushes everything
                     to the right repo
```

**One sentence summary:** All dev work happens in the monorepo. `sync-deploy` is the bridge to per-client deploy repos. Cloudflare watches per-client repos and auto-builds. The per-client repos are never edited directly — they are deploy artifacts, not source.

---

## Why this topology

### What the monorepo gives us

- **One context for AI agents.** Claude / Antigravity / future tools see all clients, all scripts, all templates in one repository — easier cross-cutting refactors, easier "update the FAQ component across all clients" operations.
- **One source of truth** for the orchestration scripts (`scripts/*`), the canonical Astro starter (`templates/astro-starter/`), planning templates (`templates/restoration/`), and content-generation prompts (`prompts/`). When we update the starter, every client benefits.
- **One commit history for the agency's portfolio.** Cross-client work, like "improve the FAQ schema rendering for all clients," is a single commit, single review, single push.

### What per-client deploy repos give us

- **Native Cloudflare Pages fit.** Pages locks Git-integration vs Direct-Upload at project creation and is one-repo-per-project. Trying to drive N Pages projects from a single repo via path filters is workable but finicky at scale.
- **Per-client deploy isolation.** Client A's broken commit doesn't block Client B's deploy. Each client's Pages project has its own build pipeline, build minutes budget, and history.
- **Per-client preview URLs.** Each client gets `staging.rankai-{slug}.pages.dev` as a stable preview URL automatically, plus per-build hash URLs for every push.
- **Per-client API keys, env vars, secrets.** Each Pages project has its own env config — Google Maps key, analytics IDs, etc. — cleanly per-client.
- **Easy client handoff.** Transfer the per-client GitHub repo to the client; your pipeline IP stays in the monorepo.

### Why neither alone

A monorepo with Cloudflare watching it directly hits real friction at 20+ clients (build time, isolation, secrets). Per-client repos as the only source of truth force you to manually push improvements to N repos. Hybrid gets both wins.

---

## The flow for a new client (clientX)

### 1. Onboard infrastructure — `rank-ai-onboard` skill

What it does:
- Creates Cloudflare zone for `clientX.com`
- Mirrors existing DNS records (so the live legacy site stays up)
- Walks you through the registrar nameserver update at the registrar (manual step)
- Polls for NS propagation
- Provisions R2 bucket (`rankai-clientX`) and binds `images.clientX.com` as the custom domain

End state:
- Client record at `rank-ai/clients/clientX.json` with `status: active`
- `images.clientX.com` serves the R2 bucket
- Old live site still serves `clientX.com` (legacy host, unchanged)

User effort: 5 minutes plus a wait for NS propagation (15-60 min depending on registrar).

### 2. Plan the site — `rank-ai-plan-site` skill

What it does:
- Walks you through selecting services from the 33-entry catalog
- Collects service-area cities (and supports rich local context: neighborhoods, landmarks, ZIP codes, local-notes per the content-differentiation doc)
- Collects brand details (NAP, founded year, license #, certifications, **brand colors derived from the client's logo / existing site**)
- Optionally fetches the client's existing website + Google Business Profile to pre-fill candidate values
- Writes `rank-ai/clients/clientX/plan-input.json` with the resolved inputs
- Runs `plan_site.py generate` to produce:
  - `url-plan.json` — every URL the site will have (typically 200-250)
  - `content-map.csv` — per-page metadata for human review
  - `internal-links.json` — internal-link graph
  - `schema-stubs.json` — JSON-LD bindings per page
  - `plan-report.md` — human-readable summary
  - `clients/{slug}/image-style-guide.md` — per-client image style guide (camera, lens, lighting, brand colors, worker-in-uniform conventions, regional environment context, per-service PPE/equipment requirements). **Every Nano Banana image generation call must consult this file** so all client images look like one cohesive photo shoot. Resolved from `templates/restoration/image-style-guide.template.md` with per-client brand colors + neighborhood/landmark/climate substitutions.

End state:
- Client record updated: `plan_status: planned`
- Plan artifacts on disk at `rank-ai/clients/clientX/plan/`

User effort: 10-15 minutes (mostly answering AskUserQuestion prompts to collect inputs).

### 3. Build the site — `rank-ai-build-site` skill

The build skill orchestrates the whole launch sequence. Subcommands run in this order:

**3a. `build_site.py scaffold --slug clientX`**

- Copies the canonical Astro starter (`templates/astro-starter/`, which is the post-Antigravity design) into `rank-ai/sites/clientX/`
- Substitutes ~35 brand tokens (colors, NAP, fonts, etc.) from `plan-input.json` + client record
- Generates one content collection markdown file per planned URL with placeholder body content
- Does NOT init a per-client `.git` (the new topology — monorepo handles this)
- Result: `sites/clientX/` is a fully-formed Astro project that builds the entire planned URL structure (just with placeholder bodies for now)

**3b. `build_site.py render --slug clientX --workers 4`**

- Walks every URL in the plan
- For each page, loads the appropriate archetype prompt from `templates/astro-starter/prompts/` (the strict-differentiation versions per the content-differentiation rules)
- Calls Claude Sonnet 4.6 with the prompt + local context for that page
- Parses JSON response, writes body + FAQ into the page's markdown file
- Logs per-page cost to `sites/clientX/.rank-ai/cost-log.jsonl`
- Skip-if-already-rendered logic preserves prior work; `--force` re-renders
- Cost estimate: ~$0.03/page × 200-250 pages = $6-9 total
- Time: ~30-45 min at 4 concurrent workers (Anthropic Tier 1 output-token rate-limited)

**3c. Commit to the monorepo**

After render finishes, commit the rendered content to the pipeline monorepo. Single commit per client per render pass:

```bash
cd ~/Desktop/mywebsitecode/rank-ai
git add sites/clientX/
git commit -m "Render clientX: {N} pages via build_site.py"
git push origin main
```

**3d. `build_site.py sync-deploy --slug clientX --branch staging`**

- Verifies the monorepo working tree is clean
- Ensures `github.com/restorationai/clientX-site` exists (creates it if not)
- Configures a per-client git remote on the monorepo (`deploy-clientX`)
- Runs `git subtree split --prefix=sites/clientX -b _tmp` to extract a synthetic branch of just the subtree's commits
- Force-pushes that synthetic branch to `clientX-site`'s `staging` branch
- Cloudflare Pages sees the push and auto-builds the preview deploy
- Preview URL: `https://staging.rankai-clientX.pages.dev/`

**3e. Review on staging**

- Visit `https://staging.rankai-clientX.pages.dev/`
- Spot-check the home, a few service pages, a few cross-product pages, the FAQ, the breadcrumbs, the Google Map embed (if a Maps API key is configured)
- If something needs fixing: edit in the monorepo's `sites/clientX/`, commit, re-run `sync-deploy --branch staging`. Iterate.

**3f. `build_site.py sync-deploy --slug clientX --branch main`**

- Same operation, but pushes to the per-client repo's `main` branch
- Cloudflare builds the production deploy at `https://rankai-clientX.pages.dev/`
- The client's actual domain (`clientX.com`) still points at their legacy host — the apex cut-over is a separate step

**3g. Cut-over to apex (`cut-over` subcommand — currently spec'd, not yet implemented as a script subcommand)**

- The skill prompts you to type the domain to confirm
- Binds `clientX.com` (apex) to the Pages project via the Cloudflare API
- Cloudflare automatically updates the zone DNS — the apex A record (previously pointing at the legacy host from `mirror-dns`) is replaced with Pages
- The site is now live at `https://clientX.com/`

User effort across step 3: maybe 30 minutes of attention spread over ~1 hour of automated work (render is the slow part, runs in the background).

### 4. Ongoing blog content — `rank-ai-blog-routine` skill (not yet built)

The blog routine is Skill 4, designed but not yet implemented. When it ships, the loop is:

- Pick the next blog topic from the seed queue
- Generate body content + hero image (Nano Banana Pro)
- Upload image to R2
- Write the markdown to `sites/clientX/src/content/blog/{slug}.md`
- Commit to monorepo
- `sync-deploy --slug clientX --branch main`
- Cloudflare auto-builds, new blog post is live

Runs on a schedule (cron) per client.

---

## What's in the canonical starter as of today

`templates/astro-starter/` is the design template every new client inherits. As of 2026-05-16, it represents the post-Antigravity restoration design:

- **Theme**: Deep red (`#a83227`) + dark grays/blacks (`#111827`) palette. Inter font family. Heavy vertical rhythm. Optional uppercase tracking-widest treatments.
- **Sections** (from probritegen's structural reference): Hero (full-bleed, branded image), TrustStrip (certifications), AboutSection (single-paragraph condensed), ServicesStrip (card grid), ProcessSection, GallerySection, ReviewsWidget (dynamic), CtaBanner (emergency contact, py-40), ServiceAreasSection, FAQSection (ChevronDown disclosure), InternalLinks, Footer (inverted-light).
- **Sensitive-content treatment**: `isSensitive` flag on biohazard and sewage routes triggers muted button styling (a softer CTA color rather than the emergency-red default).
- **Integrations baked in**: Restoration AI Chat Widget script in BaseLayout. Lucide icon library for FAQ disclosure carets and similar primitives.
- **GoogleMap component**: at the bottom of every service-area and city × service page. Falls back to a "View on Google Maps" link when no API key is configured.
- **JSON-LD schema injection**: Organization, WebSite, LocalBusiness with embedded AggregateRating, Service, BlogPosting, FAQPage, BreadcrumbList — automatically emitted per archetype.

When a new client is scaffolded, the starter is **substituted with their brand tokens** (display name, NAP, license, certifications, GBP rating, colors, fonts, logo URL, etc.) and copied into `sites/{slug}/`. The visual design is preserved; the brand identity is the client's.

---

## What's in the content-generation prompts today

`templates/astro-starter/prompts/` holds 11 archetype prompts plus a shared `_system.md`. The content-differentiation rules (`docs/content-differentiation.md`) are enforced via hard-required instructions in three prompts:

- **`service-area.md`** — requires 3+ named neighborhoods, 2+ landmarks, 2+ ZIP codes, a neighborhood-specific paragraph about restoration characteristics, an illustrative customer scenario
- **`service-area-service.md`** — requires 2+ landmarks or neighborhoods, 1+ ZIP code, an opening that combines service AND local conditions, FAQs that combine both contexts, a local tip paragraph
- **`service-landing.md`** — requires service-specific (not generic) FAQs, process steps, common problems, and CTAs

These prompts read **rich local context** from the `service_areas[]` array in `plan-input.json` — each area has `neighborhoods[]`, `landmarks[]`, `zip_codes[]`, and `local_notes` fields that the planner threads into the prompt context. This is how the LLM gets the per-city specificity that defends against thin-content penalties.

For a new client, populate `service_areas[]` with the rich per-area context during planning (the plan-site skill walks you through this). The prompts will use it automatically.

---

## Running the full flow for the next client

The shortest version for client X with domain `clientx.com`:

```bash
# 1. Onboard infrastructure (5 min interactive + NS propagation wait)
# Invoke skill: rank-ai-onboard
#   inputs: display_name=Client X, domain=clientx.com, tier=standard

# 2. Plan the site (10-15 min interactive)
# Invoke skill: rank-ai-plan-site
#   inputs: services (subset of 33), service_areas with rich local context, brand details

# 3. Build the site
# Invoke skill: rank-ai-build-site
#   - scaffold
#   - render (background, ~30-45 min, ~$8)
#   - sync-deploy --branch staging
#   - review at https://staging.rankai-clientx.pages.dev/
#   - sync-deploy --branch main
#   - cut-over (gated, requires typed-domain confirmation)
```

The skills are designed to auto-chain — each one suggests the next when its work completes, so the user mostly just confirms transitions.

---

## Why per-client `.git` was removed during the topology consolidation

Originally, `sites/{slug}/` was its own git repo with its own `.git/` and its own remote pointing at the per-client deploy repo. This worked but had operational pain:

- Cross-client refactors required pushing to N repos
- AI agents could only see one client's tree at a time
- The pipeline scripts had to navigate between repo boundaries

The hybrid topology removes nested `.git`s and uses `git subtree push` instead. The monorepo is one git repo. The per-client deploy repos still exist (Cloudflare needs them) but are populated via subtree push, not via direct edits.

This is a one-way move: editing per-client repos directly would create divergence. Always edit in the monorepo, sync via `sync-deploy`.

---

## Failure modes and recovery

| Failure | Cause | Recovery |
| --- | --- | --- |
| `sync-deploy` errors "remote rejected — non-fast-forward" | First push to an existing client repo with incompatible history | Re-run; force-push handles this. If you see this twice, the script is broken — file a bug. |
| `sync-deploy` errors "Working tree has uncommitted changes" | Safety check — sync from a dirty tree is risky | Commit or stash first. `--allow-dirty` overrides if you really mean it. |
| `git subtree: command not found` | Older git distribution | Install a git ≥ 1.7.11 (probably already there on macOS). |
| Cloudflare doesn't build after sync-deploy | Webhook delay (rare) or Pages project misconfigured | Wait 30s. If still stale, check Pages project source config: it should reference the per-client repo with `production_branch: main` and `preview_branch_includes: ["staging"]`. |
| Render produces non-JSON output | LLM returned prose around JSON | The script catches this and surfaces the failing pages. Re-run render — usually succeeds on the second pass. |
| `cut-over` errors "domain already bound" | Apex was already bound to Pages | Idempotent — no harm. |

---

## What this enables

A single operator can launch a new restoration site end-to-end in under 2 hours of attention plus ~1 hour of background automation. The per-client variations are limited to:

1. The brand block in `plan-input.json` (colors, NAP, license, certifications, logo)
2. The services array (which subset of 33 to enable)
3. The service-areas array (which cities + rich local context per area)
4. Their domain

Everything else — the visual design, the layout structure, the content quality bar, the JSON-LD shape, the AI chat widget, the SEO infrastructure — is shared via the canonical starter and the canonical prompts.

When you improve the starter or the prompts, every future client inherits the improvement. When you want existing clients to inherit it too, re-run scaffold (preserving rendered content) and re-deploy.

---

*Topology version 2.0 — supersedes earlier per-client-repo-only assumptions. Pipeline monorepo at `~/Desktop/mywebsitecode/rank-ai/.git`. Per-client repos at `github.com/restorationai/{slug}-site`. Bridge: `git subtree push` via `build_site.py sync-deploy`.*
