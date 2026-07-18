# nicsar-restoration.com — Core Web Vitals & Performance Audit
**Date:** 2026-07-12  
**Stack:** WordPress 7.0.1 + Elementor 4.1.4 (Pro) + Hello Elementor theme + Cloudflare (non-APO)

---

## PageSpeed Insights API

Both keyless calls (homepage + Schaumburg city page) returned **HTTP 429 — daily quota exhausted**. All findings below are from static HTML analysis + HTTP header inspection. No CrUX field data was retrievable.

---

## Estimated Performance Score

**~30–40 / 100 (mobile)**  
Rationale: 32 render-blocking stylesheets in `<head>`, jQuery blocking in `<head>`, two uncompressed JPEGs at 392–418 KB as hero images in the slideshow, no caching plugin, and Quicksand loaded via external Google Fonts with `display=auto` all point to a mobile LCP well above 4 s on a cache miss (TTFB 2.7 s confirmed by crawl). Desktop will fare better but is unlikely above 55–60.

---

## TTFB

| Condition | Observed |
|-----------|----------|
| Cloudflare cache HIT | ~0.2 s |
| Origin miss | ~2.7 s |

Homepage `cf-cache-status: DYNAMIC` — the HTML is **not** being edge-cached by Cloudflare. Static assets (images, CSS) are cached at the edge (all returned `HIT`). No Cloudflare APO is active. No WordPress caching plugin detected in HTML or response headers (no `x-rocket`, `x-lscache`, `x-nitro`, `x-wp-*` headers). Every uncached visit hits the origin PHP stack, producing 2.7 s TTFB before a single byte of content renders.

---

## 1. Render-Blocking Resources

### CSS — 32 stylesheets in `<head>`, none deferred

All 32 `<link rel="stylesheet">` tags are in `<head>` with `media="all"`, making every one of them render-blocking.

Breakdown:
- Hello Elementor theme: 3 files (`reset.css`, `theme.css`, `header-footer.css`)
- Elementor core widget CSS: 8 files (widget-image, widget-heading, widget-social-icons, widget-icon-list, widget-icon-box, swiper, e-swiper, elementor-icons)
- Elementor uploads/generated CSS: 7 files (`custom-frontend.min.css`, `post-6.css`, `post-7.css`, `post-1198.css`, `post-1243.css`, `custom-widget-icon-list.min.css`, `custom-widget-icon-box.min.css`, `custom-apple-webkit.min.css`, `custom-frontend.min.css`)
- Elementor Pro: 1 file (`widget-form.min.css`)
- Ultimate Elementor (UAEL): 1 file (`uael-frontend.min.css`)
- Font Awesome 5.15.3: **7 CSS files loaded** — including both `.css` (non-minified) AND `.min.css` duplicates of `fontawesome`, `solid`, and `brands`. This is a clear double-load caused by Elementor core + UAEL both registering FA separately.
- Swiper: 2 files (one from Elementor, one conditional)
- Call Now Button plugin: 1 file
- Web fonts: Roboto (self-hosted via Elementor), Roboto Slab (self-hosted), Quicksand (external Google Fonts — see font section)

### JS — jQuery sync-loaded in `<head>`

```
jquery.min.js (ver=3.7.1)     — sync, in <head>, RENDER-BLOCKING
jquery-migrate.min.js (ver=3.4.1) — sync, in <head>, RENDER-BLOCKING
```

All other JS (17 files) loads in the footer, which is correct placement, but none have `defer` or `async`. Body-footer placement avoids blocking rendering but creates a large Total Blocking Time (TBT) budget from the synchronous execution chain: hello-frontend → elementor webpack-runtime → elementor frontend-modules → jquery-ui-core → elementor-frontend → uael-nav-menu + resize + cookie → swiper → recaptcha → elementor-pro webpack + frontend + elements-handlers.

Only 3 scripts have `async`/`defer`: `gtag.js` (async — correct), and two Cloudflare injected scripts. **17 body scripts execute synchronously**, which produces heavy long tasks on the main thread.

---

## 2. Image Analysis

### Hero Slideshow (LCP element)

The homepage hero is an **Elementor Ken Burns slideshow** with 5 background images loaded via JS (`data-settings`). The LCP image is injected as a CSS background by Elementor's JS — meaning it **cannot be preloaded** with a standard `<link rel="preload">` without additional tooling. It is invisible until the 32 CSS files finish parsing and Elementor's JS bundle initialises.

| Image | Format | Size |
|-------|--------|------|
| Nicsar-Restoration.webp | WebP | 147 KB |
| water-damage-restoration.webp | WebP | 35 KB |
| full-restotation-services.jpg | **JPEG** | **408 KB** |
| fire-damage-restoration.webp | WebP | 92 KB |
| restore-after-water-damage.jpg | **JPEG** | **382 KB** |

Two of the five slideshow images are uncompressed JPEGs at ~400 KB each. The JPEG format means ~60–70% additional weight vs. equivalent WebP. At 408 KB, `full-restotation-services.jpg` is the largest single asset on the page — a strong candidate for the actual measured LCP element depending on which slide loads first.

### Logo

`nicsar-restoration-contractors-inc.png` — 144 KB PNG. Has `fetchpriority="high"` applied by WordPress (good), and dimensions are declared (812×307 — no CLS risk). However, this is a **logo being prioritised over the hero background**, which is the opposite of what the browser should be doing. The hero is the LCP element, not the logo.

### Gallery Thumbnails (below-fold)

8 Elementor thumbnail JPEGs, all lacking `width`/`height` attributes. These are all `loading="lazy"` which is correct, but the missing dimensions mean the browser cannot reserve space, creating potential CLS as they load.

| Image | Size |
|-------|------|
| full-restotation-services thumb 1 | 148 KB |
| restore-after-water-damage thumb | 157 KB |
| (6 more thumbnails) | ~30–160 KB each |

### City Page (Schaumburg)

Hero is also an Elementor slideshow background. First thumb: `water-damage-1` JPEG at 32 KB — acceptable weight. Logo again gets `fetchpriority="high"` instead of the hero. Page HTML: 107 KB (vs. 152 KB homepage).

### Cloudflare Polish / Image Optimization

All images are served from Cloudflare CDN with `max-age=31536000`. However, there is no evidence of Cloudflare Images or Cloudflare Polish being enabled (the JPEGs are served unchanged, not auto-converted to WebP).

---

## 3. Font Loading

| Font | Method | Issue |
|------|--------|-------|
| Roboto | Self-hosted via Elementor (`/elementor/google-fonts/css/roboto.css`) | Render-blocking CSS, font file delay |
| Roboto Slab | Self-hosted via Elementor | Render-blocking CSS, font file delay |
| Quicksand | External Google Fonts (`fonts.googleapis.com`) | External DNS + render-blocking; `display=auto` not `swap` |

Critical issue: **Quicksand uses `display=auto`**, which defaults to browser behaviour (typically `block` for 3 s, then `swap`). This means up to 3 seconds of invisible text (FOIT) on slow connections — directly damaging LCP for text-based LCP candidates and INP (users cannot read/interact with invisible text). It should be `display=swap` at minimum, or `display=optional` if fallback tolerance is acceptable.

Additionally, Quicksand is loading **all 9 weight variants** (100–900, normal + italic = 18 variants). Only a fraction of these are actually used on the site. This inflates font CSS and font file requests needlessly.

No `<link rel="preconnect">` to `fonts.googleapis.com` or `fonts.gstatic.com` is present.

---

## 4. Third-Party Scripts

| Script | Load Method | Impact |
|--------|-------------|--------|
| Google Analytics (gtag.js) | `async` | Low — correctly async |
| Google reCAPTCHA v3 | **Sync, no defer** | High — external script, blocks main thread |
| Google Maps iframe | `loading="lazy"` | Acceptable — iframe lazy |
| Cloudflare email-decode | `data-cfasync="false"` | Low — CF-injected |
| Cloudflare Insights beacon | Injected by CF | Low |

**reCAPTCHA v3** (`google.com/recaptcha/api.js`) is loaded synchronously in the footer without `defer`. It fires for every page load (even pages not submitting forms) because Elementor Pro registers it site-wide. This adds a cross-origin script evaluation to the main thread on every page.

---

## 5. HTML Payload

**Homepage: 152 KB HTML** — large for a service page. Contributors:
- 11 KB inline CSS (WordPress global styles block is 11,154 bytes — the WP block editor variable dump that cannot be deferred)
- Elementor `data-settings` JSON attributes embedded in section HTML (slideshow configuration, animation settings, breakpoint configs serialised into `data-settings` attributes on every widget)
- Yoast SEO Schema JSON-LD: ~3 KB inline

**Speculation Rules (Cloudflare-injected):** Present and configured for conservative prefetch of internal links. This is a net positive for navigation LCP on internal links.

---

## 6. DOM Size

~796 opening tags detected in the homepage HTML. Elementor generates deeply nested DOM structures (section > container > column > widget-wrap > widget-container > actual element). This is within acceptable range for now but will grow with page content.

---

## 7. CLS Risks

| Element | CLS Risk | Reason |
|---------|----------|--------|
| 8 gallery thumbnails | Medium | No `width`/`height` on `<img>` tags |
| Hero slideshow | Low-Medium | CSS background injected by JS — no initial space reserved |
| Quicksand font (display=auto) | Low | FOIT → text reflow on load |
| Google Maps iframe | Low | Has explicit `width="600" height="450"` |

---

## 8. What Is NOT Present

- No WordPress page caching plugin (no WP Rocket, W3 Total Cache, LiteSpeed Cache, WP Super Cache, Autoptimize, Flying Press, NitroPack)
- No Cloudflare APO (Automatic Platform Optimization for WordPress)
- No `<link rel="preload">` for any resource
- No `<link rel="preconnect">` for Google Fonts
- No critical CSS / above-the-fold CSS inlining

---

## Prioritised Recommendations

### Priority 1 — LCP (High Impact, Immediate)

**1a. Install a WordPress caching plugin with HTML caching + CSS/JS optimization.**  
WP Rocket is the most compatible with Elementor. This single step can reduce TTFB from 2.7 s to ~0.2 s sitewide (same as the CF cache-hit path), deliver critical CSS inlining, and defer/concat JS. Alternative: Cloudflare APO (Cloudflare dashboard > Speed > Optimization > Cloudflare APO — $5/mo add-on for WP, caches HTML at Cloudflare edge). Either eliminates the 2.7 s cold TTFB.

**1b. Convert `full-restotation-services.jpg` (408 KB) and `restore-after-water-damage.jpg` (382 KB) to WebP.**  
Expected savings: ~240 KB and ~230 KB respectively. Enable Cloudflare Polish (Cloudflare dashboard > Speed > Optimization > Polish = Lossy) to auto-convert and resize without touching WordPress. Alternatively, re-upload as WebP natively in WordPress.

**1c. Add `<link rel="preload">` for the first hero slideshow image.**  
The Elementor slideshow injects background images via JS, making the LCP image invisible to the browser preloader. Workaround: In the WordPress theme's `<head>` (or via Elementor Custom Code), add:
```html
<link rel="preload" as="image" href="/wp-content/uploads/2025/11/Nicsar-Restoration.webp" fetchpriority="high">
```
If WP Rocket or similar is used, it can detect and generate this automatically.

**1d. Fix `fetchpriority="high"` being assigned to the logo instead of the hero.**  
WordPress 6.3+ auto-assigns `fetchpriority="high"` to the first LCP-detected image. It is attaching to the logo (first `<img>` in document order) because the actual hero is a CSS background, not an `<img>`. The hero preload (1c above) is the fix. Optionally, remove `fetchpriority="high"` from the logo tag manually or via plugin, to avoid competing priority signals.

### Priority 2 — LCP / TBT (High Impact)

**2a. Move jQuery out of `<head>` or add `defer`.**  
`jquery.min.js` and `jquery-migrate.min.js` are synchronous in `<head>`. This blocks HTML parsing and all rendering until both download and execute. Use a plugin (WP Rocket's "Load jQuery Deferred" option, or Perfmatters) to defer jQuery. Test thoroughly — Elementor depends on jQuery but loads after it in the footer, so deferring jQuery to footer-position is generally safe on Elementor sites.

**2b. Defer reCAPTCHA v3.**  
Add `defer` to the reCAPTCHA script or use a facade/conditional load (only load reCAPTCHA when the contact form is in the viewport or about to be submitted). WP Rocket has a reCAPTCHA delay option. This removes one cross-origin blocking script from every page load across all 36 pages.

**2c. Eliminate Font Awesome double-loading.**  
The HTML shows both un-minified and minified versions of `fontawesome.css`, `solid.css`, and `brands.css` — all six loaded simultaneously. This is caused by UAEL registering FA dependencies against an older Elementor version handle. In Ultimate Elementor settings, disable "Load Font Awesome Compatibility" (if present), or use a plugin like Asset CleanUp to dequeue the duplicate handles (`uael-social-share-icons-brands-css`, `uael-social-share-icons-fontawesome-css`, `uael-nav-menu-icons-css`).

### Priority 3 — LCP / Font (Medium Impact)

**3a. Change Quicksand from `display=auto` to `display=swap` and subset to used weights only.**  
In Elementor > Site Settings > Custom Fonts or via the Google Fonts URL: change `display=auto` to `display=swap`. Also reduce the weight variants from all 18 (100–900 + italics) to the 2–3 actually used (likely 400, 600, 700). Self-host it the same way Elementor has done for Roboto/Roboto Slab to eliminate the cross-origin Google Fonts connection.

**3b. Add `<link rel="preconnect">` for fonts.googleapis.com.**  
Since Quicksand remains external in the interim:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
```
Add via Elementor Custom Code in `<head>`.

### Priority 4 — CLS (Low-Medium Impact)

**4a. Add `width` and `height` attributes to the 8 dimensionless gallery thumbnail `<img>` tags.**  
In Elementor's Image Carousel or Gallery widget, dimensions are not always persisted in the HTML output. WP Rocket and similar plugins can add missing dimensions automatically, or regenerate thumbnails with proper sizes.

**4b. Replace the Elementor Ken Burns hero slideshow with a static LCP image on mobile.**  
The full slideshow (Swiper JS + 5 images) is expensive for mobile. Consider showing a static `<img>` hero on mobile (using responsive `display:none` CSS) and reserving the animated slideshow for desktop. This eliminates the Swiper dependency for mobile users and converts the LCP element from a JS-injected background to a preloadable `<img>`.

### Priority 5 — General (Quick Wins)

- **Enable Cloudflare Brotli compression** if not already active (check with `curl -H "Accept-Encoding: br"` — not tested here, only `Accept-Encoding: gzip` was inspected via `vary` header)
- **Enable Cloudflare HTML minification** (Cloudflare dashboard > Speed > Optimization > Minify — HTML, CSS, JS)
- **Remove `wp-emoji-styles-inline-css`** if emoji are not used on the site (eliminates one inline style block and the emoji-related JS)

---

## Summary Table

| Issue | Metric Impact | Fix Effort |
|-------|--------------|------------|
| No HTML caching (2.7 s TTFB on miss) | LCP critical | Low — install WP Rocket or enable CF APO |
| 2 hero JPEGs at ~400 KB each | LCP critical | Low — re-upload as WebP or enable CF Polish |
| 32 render-blocking CSS in `<head>` | LCP high | Medium — critical CSS via caching plugin |
| jQuery sync in `<head>` | LCP/TBT high | Low — defer via WP Rocket |
| Hero LCP is JS-injected background (no preload) | LCP high | Low — add manual preload tag |
| 17 footer scripts without defer | TBT/INP medium | Medium — defer non-critical JS |
| Font Awesome loaded 6× (3 duplicate pairs) | LCP medium | Low — dequeue duplicate handles |
| Quicksand via external Google Fonts, display=auto | LCP/CLS low-medium | Low — switch to swap, self-host |
| reCAPTCHA v3 loaded on all pages, no defer | INP medium | Low — facade or conditional load |
| 8 gallery images missing width/height | CLS medium | Low — plugin auto-fix |
| No Cloudflare APO (HTML edge caching) | LCP/TTFB high | Low — $5/mo toggle in CF dashboard |
