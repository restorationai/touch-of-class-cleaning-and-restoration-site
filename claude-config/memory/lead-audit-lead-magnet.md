# Free-Audit Lead Magnet (rank.restorationai.io)

Built 2026-07-05. Live end to end.

## What serves what
- **rank.restorationai.io** = Cloudflare Pages project `rank-ai-landing-page` (DIRECT upload, no git integration). Source: `sales/rank-ai/` (Astro). Deploy: `cd sales/rank-ai && npm run build && CLOUDFLARE_API_TOKEN=$CLOUDFLARE_PAGES_API_TOKEN npx wrangler pages deploy dist --project-name rank-ai-landing-page`.
- Hero form (site+name+email+phone) POSTs to `https://rank-ai-api-production.up.railway.app/lead-audit`, polls `GET /lead-audit/{id}` every 20s, shows report link when done.
- Pipeline: `scripts/lead_audit.py` (also CLI: `--url --email --phone [--email-mode internal|none]`). Steps: Claude profile → GBP confirm (DFS Maps) → 9 organic queries → 5x5 geo-grid ×2 cities (reuses geogrid_scan/render) → ChatGPT + Google AIO citations → map-pack reviews compare → revenue-range math → Claude report copy (structured outputs, claude-opus-4-8) into locked `templates/lead-audit/report-template.html`.
- GBP confirm (fixed 2026-07-26, commit 6c247d9): candidate whose listing domain == audited domain wins outright; name-matches linking to a DIFFERENT domain get -0.35 (fuzzy match once picked tree service "Coastal Treetenders" for callcrs.com and the report said "fix your profile name"); 14z miss retries at 11z (HQ pin can sit outside tight viewport). CLI `--email-mode none` skips sales_mode → NO teaser generated; rebuild one post-hoc from private audit.json via make_teaser_image (needs data["business"], copy.game_plan, _google_bullets).
- Stats in reports come ONLY from `docs/audit-stats-library.md` (vetted, sourced; re-verify quarterly).

## Storage / delivery
- Report + heat-map PNGs: **public** R2 `restorationai-media` → `https://pub-8020f9b4a75d4346b4d17d9e4bec7392.r2.dev/lead-audits/{id}/report.html`.
- Lead PII (`audit.json`, `leads.jsonl`): **private** R2 bucket `rankai-leads-private` (r2.dev disabled). NO contacts-table insert — no Rank AI house company exists in app `companies` (only "Test (Rank AI)").
- Email via SendGrid REST from contact@restorationai.io: report to requester + `[Rank AI lead]` notification to contact@.

## Jobs / rate limits
- Jobs = `marketing_jobs` rows, `type='lead_audit'`, `company_id`/`triggered_by` NULL (triggered_by is a UUID col — don't put strings there). Limits derived from same table: 10/day global, 3/day/IP, 2/day/domain.
- Cost per audit: ~$0.40 DataForSEO + ~$0.15 Claude (≈$0.55).

## Env gotchas
- Railway `rank-ai-api` service now has DATAFORSEO_*, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_R2_API_TOKEN, SENDGRID_API_KEY (copied from geogrid-cron).
- Local `.env` `CLOUDFLARE_API_TOKEN` is INVALID/stale; `CLOUDFLARE_R2_API_TOKEN` is the working R2 token (bucket create/list/read/write).
- Local machine = system python3.9, anthropic SDK installed --user (0.116.0). Keep scripts 3.9-compatible.
- A redeploy of rank-ai-api kills in-flight audit threads → job can stick in "running" (mark failed manually if seen).

## Teaser FINAL "version B" (approved 2026-07-19)
- Portrait 1080x1350 crop-of-the-report, DEEP PETROL palette (final 2026-07-20): BLUE (14,88,116), gradient (20,123,165)->(10,58,82) — Santino rejected stock Tailwind hues; report itself still purple. Google/ChatGPT box text bumped to 21-22pt for phone readability (chip pads/gap floor tightened to fit). Header: big "ONLINE VISIBILITY REPORT" title + business name on SOFT yellow bar (254,246,189) + grade badge TOP RIGHT (136px). Then light "Google can't find you" box: max 2 x-bullets, bold label + consequence, real map-pack leader names via _google_bullets(gbp, rankings, mappack) — every claim data-backed or omitted (NEVER invent percentages like "capturing 100% of traffic"). Then dark ChatGPT box (prose ON PURPOSE — Google box = scan, ChatGPT box = story; Santino asked about bulletizing it, decision: keep prose), gradient money box, THE PLAN with step-1 title bisected at card edge. Verdict sentence no longer on teaser (report-only).
- Delivery: GHL custom fields audit_teaser_image_url (attach in SMS via merge field) + audit_report_url; framing = "my team just finished your report", image only in the text, NO report link by text (report opens on the call).
- NO EM DASHES anywhere client-facing: _strip_dashes() sanitizes teaser text; REPORT_SYSTEM hard rule 6 bans them in generated report copy; report ai_headline now leads with ChatGPT.
- Every audit.json in rankai-leads-private is a full "day 0" baseline: rankings+positions, geo-grid, AI answers w/ excerpts+sources, map-pack competitors w/ ratings/reviews, GBP state, revenue math, search_volumes (added 07-18). Before/after client progress reports can be built from this + existing client tracking (geo-grid runs, keyword CSVs, GBP face-audit scores).
