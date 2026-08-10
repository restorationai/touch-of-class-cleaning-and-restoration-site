# Ops Journal — life-savers-restoration-llc

## 2026-08-10 21:10 UTC — imagery regenerated to the AI-FIRST polished look
- Doctrine reversal (Santino 2026-08-10, fleet-wide, scripts/dev_agent.md
  "Imagery doctrine"): polished AI-generated look for launch imagery; real
  photos become livery/PPE/equipment REFERENCES only. Trigger: Santino
  rejected the real team.webp pick (two guys pressure washing does not read
  as a team).
- photo-manifest.json: all 10 slot pins cleared (archived with provenance
  under `slots_retired_2026-08-10`); do not re-pin via photo_harvest apply
  without a new decision.
- image-style-guide.md v1.3-lsr: CLIENT DIRECTION rewritten for AI-first,
  facts kept (white fleet, LSR diamond wrap, sealed white Tyvek, white+gold
  #a07828 light look, Las Vegas Valley). VAN-OVERRIDE now the matched white
  fleet; CREW-OVERRIDE specifies the 3-4 person team composition.
- Regenerated + visually quality-gated all 10 slots. Attempts: hero 1;
  team 4 candidates + one surgical decal edit (rejects: "LSB" lettering,
  garbled van mark [fixed by edit], invented rainbow hood decals,
  anonymous-hazmat team feel); services 3 (magenta cluster, off-brand blue
  gear); water 3 ("LIFE BALERS" wrap garble, invented uniform patch);
  storm 3 ("COREC" box text + garbled van mark, wrong single-diamond logo);
  contents 2 ("Packing Box" label spam); fire/mold/sewage/biohazard 1 each.
- Accepted set: sealed white Tyvek where PPE is warranted, charcoal
  workwear otherwise, faithful diamond-cluster livery (clean LSR centers,
  all other wrap text as photographic blur), red LSR-stenciled air movers
  where gear shows, bright Mojave light. team.webp = 3 crew + both branded
  vehicles.
- All -480/-768/-1200 variants rebuilt (core via resize_images helpers,
  services via the generator); image-meta.json all 10 entries at 1376x768.
  TrustStrip, badges, logo.png, tailwind untouched. Build green (100 pages).

## 2026-08-10 20:00 UTC — visual pass (real-photo-first)
- All 10 launch slots are Rudy's REAL GBP photos, zero generated images:
  hero, team, services + 7 service cards (photo_harvest apply).
- HERO was manually promoted: eligible() rejects square originals for the
  16:9 hero (w/h < 1.25) and both of his fleet shots are 2048x2048, but the
  q88 box-truck+Transit shot crops cleanly at bias 0.5. Hand-checked
  visually, slot recorded in photo-manifest.json with a note. Same pattern
  as go-green's real-Transit hero. A future `apply --force` will NOT re-pick
  a hero (gate still rejects squares); the manifest slot protects it.
- MOLD CARD manually pinned: score-based pick was the "severe mold and fire
  damage" devastation shot (services 78); pinned the flood-cut/exposed-studs
  mid-remediation shot (75) instead — shows the work, not the apocalypse.
  `apply --force` would re-pick the devastation shot; keep the pin.
- image-style-guide.md v1.2-lsr: CLIENT DIRECTION block with real facts only
  (WHITE fleet w/ multicolor LSR diamond wrap, sealed white Tyvek crews, no
  branded uniform exists so none may be invented, white+gold #a07828 light
  theme from his Best of Las Vegas badges). LIVERY/PPE reference photos in
  harvested/.
- TrustStrip renders his real award art (Best of Las Vegas GOLD 2023/24/25,
  IICRC Certified Firm, USFCR Verified Vendor) from public/images/badges/ on
  white chips; home + certifications + emergency pages. EPA Lead-Safe badge
  also exists in the brand folder (not wired; task scoped to the five).
- Commits ede31d70 (visual pass) + e853cf71 (staging timestamp); staging
  deploy via sync-deploy.

## 2026-08-09 14:03 UTC — client ops sync
- Customer-list checklist completed: Customer list for the review campaign
