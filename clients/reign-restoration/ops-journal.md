# Ops Journal — reign-restoration

## 2026-08-05 14:04 UTC — client ops sync
- Customer-list checklist completed: Customer list for the review campaign

## 2026-08-05 16:03 UTC — phone call, Jerrott x Santino (transcript: `calls/2026-08-05-jerrott.md`)
Source: GHL call recording (not Fathom, this was a cell call). 367s.

- **The call was about DATA ACCESS, not design.** The 15:19 swap put photos on
  his site he had never sent us: *"she changed it to like photos that I've
  never sent you guys ... how does he gain access to that?"* Traced: 6 of 8
  slots came from his connected GBP, and hero + fire-damage were downloaded
  from his own public Wix site (`found_on:
  https://www.reign-restoration.com/fire-damage-restoration`). We hold no
  Google Drive access. He is worried about claim numbers and HIPAA. He asked
  for this in writing; Santino owes him a same-day answer.
- **He wants the GENERATED About photo back** (round 2, `02f85dc8`), with the
  van livery no longer mirrored. This reverses part of round 3.
- **AI images are fine with him** — round 3's "real photographs only" was an
  overcorrection. RULE 0 in `image-style-guide.md` amended to "true
  representation" accordingly.
- **Gold is CLOSED**: *"the colors definitely look better. They definitely
  match a lot better."* `#f2b623` accepted.
- **Go-live is gated on his explicit sign-off.**

## 2026-08-09 — dev agent — white-background logo corrected (client feedback: Jerrott)
- Jerrott (client feedback, conf=high): "The logo on the white still needs to
  be corrected. I emailed the logo for a white back round."
- Root cause: the footer is `bg-white` but rendered `brand.logoUrl`
  (/images/logo.png = gold shield + WHITE wordmark on transparent), so the
  wordmark was invisible on white and only the shield showed. Header, About and
  the LP layout are all dark/navy backgrounds, where logo.png reads correctly —
  they were left untouched.
- Fix: pulled the file he emailed (email-intake bucket
  CO-1785771354136/19fd8a28680b3544/"Reign Restoration - Icon - White- BG.jpg"),
  trimmed the empty white canvas, saved faithfully (no recolour) as
  `public/images/logo-light-bg.png`, and pointed the Footer <img> at it.
- REGEN NOTE: this is a per-site component edit (Footer.astro) + a static asset;
  a full re-scaffold (copy_starter) would overwrite Footer.astro and revert the
  swap. If the starter footer ever needs the light-bg logo by default, that is a
  starter-template change, not a per-client one.
- Monica stays gagged. Jerrott's EMAIL was still on `CONCIERGE_ALLOWLIST` even
  though his phone had been removed; removed locally. The GitHub Actions
  secret still needs the same edit — see the report.
