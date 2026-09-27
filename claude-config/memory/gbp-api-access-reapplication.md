---
name: gbp-api-access-reapplication
description: Google Business Profile API write access is now APPROVED (was disapproved 2026-06); unlocks GBP posts/photos/Q&A automation
metadata: 
  node_type: memory
  type: project
  originSessionId: acdb19a7-afd6-4946-9442-cbe973522dd1
---

**Google Business Profile API write access is now APPROVED** (confirmed by Santino 2026-07-01). Earlier it was **disapproved** (2026-06-24: "listing ID associated with a different website" — they'd applied attaching a client GBP but entered agency domain restorationai.io, which mismatched). The reapplication (with a listing whose website matches, e.g. Home Pride / narestco) went through.

**What this unlocks (build on it):**
- GBP **posts** already ship 2x/week (Mon+Thu) via [[gbp-optimizer-system]] (`scripts/gbp_post.py`, `gbp_manager.py`; v4 `mybusiness.googleapis.com/v4/.../localPosts`).
- **Photos** — now automatable: weekly upload of the client's REAL photos to GBP (collected via [[gbp-photo-intake]]). Do NOT use AI-generated before/after job photos on GBP (deceptive + Google's SynthID survives EXIF scrubbing).
- **Q&A** — ❌ **DEAD. Google fully retired GBP Q&A** — the API returns 501 "no longer supported" AND the manual "add a question" option was removed from the dashboard too. Do NOT chase this again. All Q&A value now lives in the on-site per-city **FAQ** (`FAQPage` schema, content pipeline). `scripts/gbp_qanda.py` is a leftover (prints copy) — moot; can be deleted.
- **Search Console API is enabled + working** (`webmasters` scope; `sites.list` returns all verified properties). Powers gsc_client/gsc_sync/gsc_setup/refresh/dashboard. Leave it on.

**Auth pattern (reuse `scripts/gbp.py`):** `get_access_token(company_id)` refreshes the client's `google` refresh_token from `user_integrations` (business.manage scope); `find_location(token, place_id)` returns the location dict (`name` = `accounts/X/locations/Y`) matched by `brand.place_id`. The agency account manages all client locations. narestco company_id `CO-1771290587387`.
