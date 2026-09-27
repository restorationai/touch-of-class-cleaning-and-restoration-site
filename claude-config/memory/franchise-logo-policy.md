---
name: franchise-logo-policy
description: "Franchise clients: grab the official logo online (franchisor site), never block citations waiting for the client"
metadata:
  type: feedback
---

Santino 2026-08-31: "For any franchise, we should just grab their logo from online."

**Why:** franchise brand logos are public, standardized assets; blocking the citations queue on a client upload wastes weeks (Paul Davis Charleston idled on a missing logo while pauldavis.com serves the SVG).

**How to apply:** fetch the franchisor site logo (render JS sites with playwright, grab the header img/svg), rasterize on white, upload to branding/{cid}/brand/logo-*.png (the citations gate reads the bucket) and sites/{slug}/public/images/logo.png when the site exists. Done for paul-davis-charleston 2026-08-31.
