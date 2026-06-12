# Rank AI — System Context

Last updated: 2026-06-11. Read this file to fully understand the Rank AI system before starting any work.

---

## What Is Rank AI

Rank AI is a productized SEO + website service for home-service contractors (restoration, construction, plumbing). It builds and operates SEO-optimized Astro websites, runs automated content and audit pipelines, and surfaces everything through a React dashboard at app.restorationai.io.

**Operated by:** Santino Velci (contact@restorationai.io)
**Pipeline repo:** github.com/restorationai/Rank-AI-Pipeline
**Local root:** `/Users/santino/Desktop/mywebsitecode/rank-ai/`

---

## Stack

| Layer | Tech |
|---|---|
| Sites | Astro 5 on Cloudflare Pages |
| Images | Cloudflare R2 (`rankai-{slug}` bucket → `images.{domain}`) |
| Content pipeline | Python scripts + Claude Sonnet 4.6 |
| Keyword/audit data | DataForSEO API |
| Image generation | Google Gemini (Nano Banana MCP) |
| API backend | FastAPI on Railway |
| Database | Supabase (marketing_* tables only — do NOT touch other tables) |
| Email | SendGrid (via urllib REST — NOT MCP, MCP send_mail is broken) |
| Automation | GitHub Actions (weekly + monthly cron) |
| React app | app.restorationai.io on Netlify |

---

## Repository Topology

ONE monorepo for all dev work. ONE separate GitHub repo per client for Cloudflare Pages deploys.

- **Monorepo:** `github.com/restorationai/Rank-AI-Pipeline` — scripts, templates, prompts, docs, sites/, clients/
- **Per-client repos:** `github.com/restorationai/{slug}-site` — derived deploy artifacts, NEVER edited directly
- **Bridge:** `python3 scripts/build_site.py sync-deploy --slug {slug} --branch main` uses `git subtree split` to push `sites/{slug}/` to the per-client repo. Cloudflare auto-builds on push.

Never clone or edit per-client repos directly. Always work in the monorepo.

---

## Credentials (all in `rank-ai/.env`, gitignored)

```
ANTHROPIC_API_KEY
CLOUDFLARE_API_TOKEN          # zone management
CLOUDFLARE_R2_API_TOKEN       # R2 + Pages
CLOUDFLARE_PAGES_API_TOKEN    # Pages:Edit (apex cutover)
CLOUDFLARE_ACCOUNT_ID=5920ebccc5be1810cc288681e1383608
GITHUB_PERSONAL_ACCESS_TOKEN  # restorationai org, repo scope
GOOGLE_AI_API_KEY             # Gemini image gen
GOOGLE_MAPS_API_KEY
GOOGLE_CLOUD_API_KEY
GOOGLE_ADS_DEVELOPER_TOKEN=VmvnCTgD3eDRphJnYN1mwA
GOOGLE_ADS_MCC_CUSTOMER_ID=2018844125
SENDGRID_API_KEY
PEXELS_API_KEY
ELEVENLABS_API_KEY
SUPABASE_URL=https://nyscciinkhlutvqkgyvq.supabase.co
SUPABASE_SERVICE_ROLE_KEY     # service role — marketing_* tables only
RAILWAY_API_KEY=c19de8fa-df6e-4a5e-91ca-8095ec58bda3
RAILWAY_PROJECT_ID=5de30f6c-c143-4c3b-b7c8-12654c4fa54c
API_SECRET_KEY=rkai_prod_a8f3k2x9m1
RAILWAY_API_URL=https://rank-ai-api-production.up.railway.app
```

---

## SEO Pipeline — Four Systems

All four systems are built and operational.

| System | Script | Mode | Cadence |
|---|---|---|---|
| S1 Keyword Researcher | agent-driven (Claude + DataForSEO) | headless via `claude -p` | monthly per client |
| S2 Content Writer | `scripts/content_writer.py` | direct subprocess | Mon + Thu per client |
| S3 Onsite Audit | agent-driven (Claude + DataForSEO Lighthouse) | headless via `claude -p` | monthly per client |
| S4 Refresh Recommender | Layer 1: `scripts/refresh_scorer.py`; Layer 2: agent | direct + headless | monthly per client |

**Master scheduler:** `python3 scripts/master_scheduler.py [status | run-due --all --headless | force-run --slug {slug} --system {1-4}]`

**GitHub Actions (live):**
- `.github/workflows/weekly-maintenance.yml` — every Monday 9am PDT: `master_scheduler.py run-due --all --headless`
- `.github/workflows/monthly-reports.yml` — 1st of month 10am PDT: HTML reports + portfolio digest to contact@restorationai.io
- `.github/workflows/on-demand.yml` — triggered by Railway API via workflow_dispatch for app-initiated runs

---

## FastAPI Backend (Phase 3) — Railway

**URL:** https://rank-ai-api-production.up.railway.app
**Auth:** `Authorization: Bearer rkai_prod_a8f3k2x9m1`
**Service ID:** ab0c3454-90ac-437a-b981-ca82398a6be4
**Service Instance ID:** 76e0918b-84e2-402c-b49e-d5133c56136b

Endpoints:
```
GET  /health                    service health check
GET  /status                    last-run timestamps for all clients
GET  /status?slug={slug}        single client
POST /jobs/run                  trigger S1-S4 run → { "slug": "...", "system": 1-4 }
GET  /jobs/{job_id}             poll job status
GET  /jobs                      list recent jobs
POST /jobs/{job_id}/complete    GitHub Actions callback
```

S2 and S4 run as direct subprocesses on Railway. S1 and S3 dispatch to GitHub Actions (`on-demand.yml`) because they need Claude CLI + DataForSEO MCP.

**Deployment notes:** nixpacks.toml forces Python 3.11 + `/opt/venv` (nix Python is PEP 668 externally managed — bare pip install fails).

---

## React App Integration

**App:** app.restorationai.io (Netlify)
**Supabase project:** nyscciinkhlutvqkgyvq (production dataset)

React app reads from Supabase `marketing_*` tables. `scripts/supabase_sync.py` syncs pipeline state → Supabase after each S1-S4 run.

Frontend env vars:
```
VITE_RANK_AI_API_URL=https://rank-ai-api-production.up.railway.app
VITE_RANK_AI_API_SECRET=rkai_prod_a8f3k2x9m1
VITE_GOOGLE_CLIENT_ID=936081984190-6p9t4du982u4lh7purv34t8gcbnshig9.apps.googleusercontent.com
```

Google OAuth app: "Restoration AI" on GCP (existing app, originally for Calendar via n8n).
- Client ID: 936081984190-6p9t4du982u4lh7purv34t8gcbnshig9.apps.googleusercontent.com
- Scopes: webmasters.readonly, adwords
- Redirect URIs: https://app.restorationai.io/connect/google/callback + https://nyscciinkhlutvqkgyvq.supabase.co/functions/v1/google-oauth-exchange

---

## Clients

### narestco — National Restoration Construction
- **Domain:** narestco.com (live since 2026-05-17)
- **build_status:** cut_over
- **Company ID (app):** CO-1771290587387
- **Cloudflare zone:** 30f8272d671672a14bae7ed64e0d4d71
- **R2 bucket:** rankai-narestco → images.narestco.com
- **Pages project:** rankai-narestco
- **GSC:** sc-domain:narestco.com (verified)
- **Google Ads customer:** 3832550597
- **Last audit:** 2026-05-17, verdict: amber
- **S2 cadence:** Mon + Thu automated via GitHub Actions

### davis-construction — Davis Construction Contractors
- **Domain:** davisconstructioncontractors.com (live)
- **build_status:** cut_over
- **Company ID (app):** CO-1778778644861
- **Location:** Madison, Alabama
- **Vertical:** construction
- **Status:** Site live, S1-S4 runs not yet started

### probritegen — ProBrite Gen (CHURNED 2026-05-28)
- Client left before apex cutover. Cloudflare Pages project deleted, DNS record removed. Do not run any systems. Do not include in app.

---

## Key File Paths

```
clients/{slug}.json                           client record (status, build_status, brand, audit, refresh)
clients/{slug}/content-queue.json             items: queued → written → published
clients/{slug}/keyword-bank.json              seeds_researched[], keyword entries
clients/{slug}/onsite-audit.json              latest audit state (overwritten each run)
clients/{slug}/audit-runs/{date}-*.md         per-run audit reports
clients/{slug}/refresh-runs/{date}-*.md       per-run refresh reports
clients/{slug}/reports/{YYYY-MM}-monthly.html client report
sites/{slug}/                                 Astro site source (synced to per-client deploy repo)
scripts/                                      all Python automation
api/main.py                                   FastAPI app
api/runner.py                                 job execution logic
templates/restoration/prompts/                S1-S4 prompt files
templates/construction/                       NOT YET BUILT
docs/                                         architecture docs
.env                                          all credentials (gitignored)
nixpacks.toml                                 forces Python 3.11 on Railway
railway.toml                                  Railway build + deploy config
```

---

## Onboarding a New Client

Skill chain (auto-chains by default):
1. `/rank-ai-onboard` — Cloudflare zone + R2 bucket + DNS mirror (~30 min)
2. `/rank-ai-plan-site` — URL plan + content map + schema stubs (~20 min)
3. `/rank-ai-build-site` — Astro scaffold + render + deploy + cutover (~45 min)
4. First S1-S4 runs (~60 min)

After onboarding: fully automated via GitHub Actions.

**COMPANY_MAP** (hardcoded in supabase_sync.py and runner.py — update when adding clients):
```python
COMPANY_MAP = {
    "narestco": "CO-1771290587387",
    "davis-construction": "CO-1778778644861"
}
```

---

## Pending Work

### App / integration
- Add VITE_RANK_AI_API_URL and VITE_RANK_AI_API_SECRET to Netlify dashboard (production build)
- Publish Terms of Service and Privacy Policy to restorationai.io/terms and restorationai.io/privacy
- Submit Google OAuth app for Google verification after legal docs are live
- Wire supabase_sync.py into master_scheduler.py so dashboards auto-update after each run

### Pipeline
- Start S1-S4 runs for davis-construction
- Build templates/construction/ vertical (prompts for all four systems)
- narestco YouTube: client needs to add contact@restorationai.io as Channel Manager, then run `python3 scripts/video_maker.py auth --slug narestco`
- Add CI failure email alerting via SendGrid

### Future
- GoDaddy DNS automation for new client cutover
- GSC v2 per client (real search data in S4)
- Client report emails (flip report_email_enabled: true per client)
- Multi-vertical client support (verticals: [] field in client records)

---

## Claude Skills (invoke with /skill-name)

| Skill | Purpose |
|---|---|
| `/rank-ai-onboard` | Onboard a new client (DNS, R2, zone) |
| `/rank-ai-plan-site` | Generate URL plan + content map |
| `/rank-ai-build-site` | Scaffold + render + deploy + cutover |
| `/rank-ai-keyword-researcher` | S1: fill content queue |
| `/rank-ai-content-writer` | S2: write next blog post |
| `/rank-ai-onsite-audit` | S3: Lighthouse + on-page audit |
| `/rank-ai-refresh-recommender` | S4: detect content decay |
| `/schedule` | Create/manage GitHub Actions cron routines |
