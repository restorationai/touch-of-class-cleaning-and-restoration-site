# Ops Journal — go-green-restoration-of-nc

## 2026-08-03 16:43 UTC — client ops sync
- Customer-list checklist completed: Customer list for the review campaign

## 2026-08-09 — dev agent — Recent Work gallery populated (client feedback: Todd)
- Todd (client feedback, conf=high): "They said they would add my pictures."
  The staging preview's Recent Work gallery was empty because the site was
  scaffolded before any photos were uploaded, so `brand.jobPhotos` was `[]`.
- His photos DO exist in supabase (branding/CO-1784905385326/job-photos —
  48 root + 35 posted). Populated `brand.jobPhotos` with a curated top-12 from
  the photo-manifest.json triage (quality>=55; excluded categories
  unusable/graphic/logo/document and flags screenshot/duplicate/blurry;
  ranked best-first). Lead image is the real branded Transit van.
- WHY CURATED, NOT RAW: `build_site.fetch_job_photos()` returns supabase newest-
  first with NO quality filter. For this client the two newest are a black-
  screen screenshot (manifest q=0, cat=unusable) and a plain green-circle
  graphic (q=10) — a raw feed would make those the first two gallery tiles.
- DURABILITY GAP FOR SANTINO: this curation lives in brand.ts. A future full
  `build_site.py scaffold` re-runs fetch_job_photos (raw) and would reintroduce
  the junk at the top. Hardening fetch_job_photos to honour the per-client
  photo-manifest triage is a fleet-wide change I did not make in a headless run
  (couldn't verify it across other clients) — flagging it for a human decision.

## 2026-08-09 — logo + hero replaced (Santino's direct instruction)
- The site "logo" was an iPhone SCREENSHOT from Todd's camera roll (status bar,
  "June 16, 2021", photo-app chrome all baked in) — he never had a real logo file.
- Generated a brand-matched logo from his actual van wrap: NC state silhouette
  split fire-into-water with a lightning bolt at the seam, GO GREEN /
  RESTORATION OF NC in green caps. public/images/logo.png (863x159, white bg).
- Promoted his REAL wrapped Transit (lead job-photo) to hero-bg.webp (16:9
  center crop), replacing the generated green-and-white van scene.
- ⚠️ NAME DISCREPANCY for Santino/Todd: the van wrap reads "GO GREEN
  RESTORATIONS OF NC" (plural) — every record we hold (plan-input, GBP, site)
  says "Go Green Restoration of NC" (singular). Logo follows our records;
  confirm with Todd which is legally right.
