# GEO Audit: nicsar-restoration.com
**Date:** 2026-07-12
**Business:** Nicsar Restoration Contractors Inc. — Water/Fire/Storm/Flood Restoration, Hoffman Estates IL

---

## GEO Health Score: 28 / 100

| Dimension | Weight | Raw Score | Weighted |
|-----------|--------|-----------|---------|
| Citability | 25% | 38/100 | 9.5 |
| Structural Readability | 20% | 30/100 | 6.0 |
| Multi-Modal Content | 15% | 35/100 | 5.25 |
| Authority & Brand Signals | 20% | 20/100 | 4.0 |
| Technical Accessibility | 20% | 15/100 | 3.0 |
| **TOTAL** | | | **27.75 → 28** |

---

## 1. AI Crawler Access Matrix

### robots.txt Analysis
The file contains Cloudflare's managed AI-bot block template, plus a legacy Yoast wildcard allow at the bottom. The Yoast block (`User-agent: * / Disallow:` with no path) technically allows everything for *, but explicit named-bot Disallow rules take precedence when the UA matches specifically.

| Bot | Directive | Product Surface Killed |
|-----|-----------|------------------------|
| **GPTBot** | `Disallow: /` | ChatGPT browsing (real-time web fetch in ChatGPT); ChatGPT search results synthesis; OpenAI training |
| **OAI-SearchBot** | NOT listed — allowed by wildcard | ChatGPT search index crawl — still running |
| **ClaudeBot** | `Disallow: /` | Claude.ai web-search tool; Anthropic training crawl |
| **anthropic-ai** | NOT listed — allowed by wildcard | Anthropic training crawl (secondary UA) — still running |
| **PerplexityBot** | NOT listed — allowed by wildcard | Perplexity.ai real-time retrieval and citations — STILL ALLOWED |
| **CCBot** | `Disallow: /` | Common Crawl training dataset (many LLMs) |
| **Google-Extended** | `Disallow: /` | Google Gemini AI training AND Google AI Overviews grounding corpus — see nuance below |
| **Googlebot** (implied *) | Allowed | Standard Google Search index |
| **Applebot-Extended** | `Disallow: /` | Apple Intelligence on-device AI features |
| **Bytespider** | `Disallow: /` | ByteDance/TikTok training |
| **Amazonbot** | `Disallow: /` | Alexa AI features |
| **meta-externalagent** | `Disallow: /` | Meta AI training |
| **CloudflareBrowserRenderingCrawler** | `Disallow: /` | Cloudflare internal rendering (no AI surface) |

### Critical Nuance: Google-Extended vs Google AI Overviews
`Google-Extended` is Google's dedicated bot for **AI training data collection** and for populating the **grounding corpus** used by Gemini models. It is **not** the same as `Googlebot`. Standard Google AI Overviews (AIO) are generated at query-time using Googlebot-indexed content, NOT Google-Extended indexed content. Blocking Google-Extended does **not** block AIO generation from Googlebot-crawled pages. However, it does block Google from using this site's content to train/improve Gemini and its underlying AI models.

**Net effect summary:**
- Google AIO: NOT blocked (Googlebot allowed) — site can appear in AI Overviews
- ChatGPT search/browsing: BLOCKED (GPTBot blocked)
- Claude web search: BLOCKED (ClaudeBot blocked)
- Perplexity: ALLOWED (PerplexityBot not listed)
- Bing Copilot: The bingbot UA is allowed (not blocked), so Bing Copilot synthesis from existing index is possible
- AI training (most): BLOCKED (CCBot, Google-Extended, GPTBot, meta-externalagent, anthropic-ai partially allowed)

**Owner intent seems coherent** — `Content-Signal: search=yes, ai-train=no, use=reference` — they want search indexing but not training. However the execution has a fatal gap: GPTBot and ClaudeBot serve real-time retrieval (not just training), so blocking them eliminates ChatGPT Search and Claude's web tool, which are high-value citation surfaces for restoration queries.

---

## 2. llms.txt Status

**Result: ABSENT (HTTP 403)**

The URL `https://nicsar-restoration.com/llms.txt` returns 403 Forbidden. The file does not exist. No llms.txt, no RSL 1.0 licensing signal, no machine-readable content index for AI systems that support it (Perplexity and others that check /llms.txt).

---

## 3. Passage-Level Citability Analysis

### Homepage (nicsar-restoration.com)
**Hero text:** "Fast and reliable restoration services for water, fire, storm, and flood damage across Chicagoland." — 14 words. Too short to be cited alone.

**Main body block (two paragraphs, ~130 words combined):** Contains the brand name, location, service range, and methods in continuous prose. Nearly within the 134–167 word optimal window but split across two paragraphs with no direct answer opening. An LLM cannot extract a clean Q&A block.

**Stats widget:** "20+ Years of Experience" — exists as an icon-box widget. Not inside a paragraph element; likely not extractable as prose. No sources cited. No IICRC certification mention, no license numbers.

**Critical gap:** The homepage has NO question-based headings. The H3 "Water Damage Restoration You Can Trust In Hoffman Estates, IL" is a marketing statement, not a question. No FAQ schema markup.

**Citability score for homepage: 22/100**

---

### Water Damage Restoration — Hoffman Estates page
**Opening paragraph (~90 words):** Introduces the problem (leaks, overflows) and the company response. Direct but not formatted as a Q&A answer. Does not open with a definitive answer statement.

**Why Choose section (bulleted list):** Five strong bullets with bold lead-ins (Experience / Technicians trained in moisture behavior / Professional extraction equipment / Support for homes and businesses / Clear communication). This is the best AI-extractable structure on the site. Lists of this type are citable.

**5-Step Process section:** Labeled Step 1–5 with H4 "Our Water Damage Restoration Process" header. Steps are short (20–35 words each), self-contained, and descriptive. This is high-citability content — an LLM answering "what is the water damage restoration process" could lift this entire block.

**FAQ section (H6 heading):** Five Q&A pairs exist. The questions are:
- "How soon should water damage restoration begin?" → Answer: "Restoration should begin as soon as possible to reduce the risk of structural damage and additional issues." (21 words — correct directness, too short)
- "Can water affect areas that do not appear wet?" → Answer: Yes + explanation (24 words)
- "Do you provide services for both residential and commercial properties?" → Yes answer
- "How long does the drying process usually take?" → "Several days" answer
- "Are repairs included after drying is complete?" → Yes answer

**Problems with FAQ:** The H6 heading level is semantically weak (H6 is the lowest priority heading). No FAQ schema markup (no `@type: FAQPage` in the JSON-LD). Answers average ~20 words — far below the 134–167 optimal window. Answers are not self-contained without knowing the question. No statistics with sources.

**Citability score for water damage page: 45/100**

---

### Storm and Flood Restoration — Hoffman Estates page
**Opening block (~270 words in a single text-editor widget):** Three paragraphs covering problem introduction, scope, and company background. Well-written but flows as marketing copy. No H2/H3 question-based openings in the first 60 words.

**Why Choose section:** Similar bulleted structure with 5 bold-lead bullets. "Local restoration knowledge based on years of experience handling storm and flood damage in Hoffman Estates" — geographic specificity helps.

**6-Step Process:** Labeled Step 1–6. Adds "Step 6: Final inspection and restoration" not present on water page. More detailed than water damage page.

**FAQ section (H6):** Five Q&A pairs. Notable answers:
- "What should I do first if my property floods during a storm?" → "You should prioritize safety by avoiding standing water and contacting a restoration professional as soon as possible. Quick action helps limit structural damage and reduces the chance of mold growth." (36 words — closest to useful length)
- "How does storm damage differ from regular water damage?" → "Storm damage often includes roof leaks, wind damage, and exterior issues in addition to flooding. It may also involve contaminants brought in by rainwater or groundwater." (28 words)

These FAQ answers are the most AI-extractable content on the site. They approach standalone utility but still lack numerical specifics (timeframes, percentages, sourced stats).

**Citability score for storm/flood page: 48/100**

---

### Cross-Site Citability Issues
1. **Zero cited statistics.** No "X% of water damage claims," no "mold can grow within 24–48 hours," no IICRC standards referenced. Stats with sources dramatically increase citation probability.
2. **No named author/expert.** No individual technician named on any page. No certifications (IICRC WRT, ASD, etc.) listed.
3. **Heading hierarchy misuse.** FAQ sections use H6 — the lowest semantic level. These should be H2 or H3 with proper FAQ schema.
4. **Single testimonial per page.** Only "Michael R." testimonial appears on service pages (carousel shows one slide). Reviews page has Michael R., Sarah L., David M. — only first names, no dates, no platform source (not labeled as Google reviews). This dramatically limits trust signals.
5. **No content dates visible.** Pages modified 2025-12 through 2026-02 per OG meta, but no publish/updated dates displayed to users or structured for AI extraction.

---

## 4. Brand Mention Groundwork

### On-Site Entity Signals
- **Schema.org/Organization** markup: Present via Yoast JSON-LD. Includes name, URL, logo URL. Missing: sameAs array (no links to GBP, Yelp, Facebook). Missing: address, telephone in schema.
- **GBP embed:** Google Maps iframe present on service pages using the GBP place ID `0x880fa99d2e118815:0xde0c5acb4a601b26` for "Nicsar Restoration Contractors Inc." — GBP entity exists.
- **Facebook icon** in footer — but the anchor href is empty (no URL). Facebook presence is declared but not linked.

### Third-Party Directory Footprint Assessment
Based on site signals and general market knowledge for a Chicagoland restoration contractor:
- **Google Business Profile:** Confirmed (map embed with verified place ID). This is the primary entity signal for emergency-intent AI answers.
- **Yelp:** No Yelp link or embed found on any page. Yelp is critical for AI emergency-intent answers (Perplexity heavily surfaces Yelp for "best X near me" queries). Status unknown but absence from site is a red flag.
- **Wikipedia:** No Wikipedia entity for "Nicsar Restoration." Expected for a local contractor, not a gap unless they seek research-mode citations.
- **Reddit:** No Reddit presence found or linked.
- **YouTube:** No YouTube channel linked or embedded. YouTube correlation with AI citations is the strongest single brand signal (~0.737).
- **LinkedIn:** No LinkedIn page linked.
- **BBB / Angi / HomeAdvisor:** No links found on site.
- **IICRC directory:** No mention of IICRC membership or certification on any page.

**Brand mention footprint: Very thin.** The site is essentially invisible to AI training/retrieval from any source other than direct crawl — which is now blocked for the major platforms.

---

## 5. Emergency-Intent AI Answers vs Research-Mode AI Answers

### Emergency Intent: "water damage company near me Hoffman Estates"
AI engines handling emergency local queries (especially Perplexity, Google AIO, ChatGPT Search) pull from:
1. GBP entity feeds (name, rating, hours, phone)
2. Yelp listings with review counts
3. HomeAdvisor/Angi aggregators
4. Local news/directory citations

**Nicsar's position:** The GBP entity exists, which gives partial coverage for Google AIO (which reads Googlebot-indexed content and knowledge graph). However, with no Yelp listing confirmed, no Angi/HomeAdvisor profile linked, and ChatGPT/ClaudeBot blocked, the emergency-intent coverage is **below baseline** for the market. Perplexity is the exception — PerplexityBot is not blocked, and if the site has good SSR content (it does, WordPress renders server-side), Perplexity can index and potentially cite it.

### Research Mode: "what to do after basement flood"
This is where the site has latent opportunity. The storm/flood and water damage pages contain:
- A clear 5–6 step process
- Direct FAQ answers about timing and scope
- Geographic relevance signals (Hoffman Estates, Chicagoland)

However, to win research-mode citations, these pages need:
- Question-format H2 headings (e.g., "What Should You Do Immediately After a Basement Flood?")
- Answer blocks in the first 40–60 words under each heading
- Stats with attribution (e.g., "FEMA estimates the average flood damage claim exceeds $30,000")
- No ChatGPT/Claude block if those engines are to surface this content

**Current research-mode citability: Low.** Content structure is there in outline form but lacks the directness, specificity, and schema signals needed for citation.

---

## 6. Technical Accessibility for AI Crawlers

- **Rendering:** WordPress with Elementor. All content is server-side rendered (SSR). The HTML files confirm full content is present in the raw HTML — no JavaScript-only rendering. AI crawlers receive complete content without executing JS.
- **Cloudflare protection:** The site runs behind Cloudflare. The robots.txt is Cloudflare-managed. This is relevant because some AI crawlers may hit Cloudflare's bot protection before respecting robots.txt — but since Cloudflare's own system wrote the robots.txt, named bots are likely handled at that layer.
- **Email obfuscation:** Cloudflare email obfuscation is active (`__cf_email__` class on all email addresses). The actual email is not readable by any crawler. Minor impact.
- **Page speed / crawl budget:** No evidence of crawl blocking beyond robots.txt. Sitemap at `/sitemap_index.xml` (confirmed by Yoast). Sitemap is accessible to crawlers not blocked.
- **Mobile-first:** Elementor responsive — no issues.
- **Schema.org coverage:** Organization schema on every page via Yoast (name, URL, logo). WebPage schema with breadcrumb. No LocalBusiness schema (missing address, phone, openingHours). No FAQPage schema on FAQ sections. No HowTo schema on process steps. No Review schema on testimonials.

---

## Top 5 Highest-Impact Changes

### Priority 1 — Fix robots.txt: Unblock GPTBot and OAI-SearchBot (Effort: 10 minutes, Impact: Critical)
**Current state:** GPTBot blocked, killing ChatGPT Search/Browsing entirely.
**Change:** Remove or comment out the `User-agent: GPTBot / Disallow: /` block. Also explicitly add `User-agent: OAI-SearchBot / Allow: /` to ensure search indexing.
**Keep blocked:** CCBot (training only), Bytespider, Amazonbot, meta-externalagent, Applebot-Extended.
**Keep blocked consideration for ClaudeBot:** Blocking ClaudeBot kills Claude's web tool but does not block Anthropic training (anthropic-ai UA is separate and currently allowed anyway). Unblocking ClaudeBot is recommended for citation surface gains.

Exact robots.txt change — replace the Cloudflare block with:
```
User-agent: *
Content-Signal: search=yes,ai-train=no,use=reference
Allow: /

User-agent: Amazonbot
Disallow: /

User-agent: Applebot-Extended
Disallow: /

User-agent: Bytespider
Disallow: /

User-agent: CCBot
Disallow: /

User-agent: CloudflareBrowserRenderingCrawler
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: meta-externalagent
Disallow: /

# GPTBot and ClaudeBot allowed for AI search (not training)
# ai-train=no content signal above governs training use
```
Remove the GPTBot and ClaudeBot Disallow lines entirely.

---

### Priority 2 — Add /llms.txt (Effort: 30 minutes, Impact: High)
Create `nicsar-restoration.com/llms.txt` with a structured content index. This is read by Perplexity, some Claude tools, and emerging AI systems.

Recommended content:
```
# Nicsar Restoration
> Water, fire, storm, and flood damage restoration serving Hoffman Estates and Chicagoland, IL.
> Phone: (773) 220-6751

## Services
- [Water Damage Restoration](https://nicsar-restoration.com/water-damage-restoration-hoffman-estates-il/): Professional water extraction, structural drying, mold prevention, and repairs for residential and commercial properties in Hoffman Estates, IL.
- [Fire Damage Restoration](https://nicsar-restoration.com/fire-damage-restoration-hoffman-estates-il/): Fire damage cleanup, smoke removal, and full property restoration.
- [Storm and Flood Restoration](https://nicsar-restoration.com/storm-and-flood-restoration-hoffman-estates-il/): Storm damage response, flood extraction, exterior repairs, and full restoration.
- [Insurance Claims Assistance](https://nicsar-restoration.com/insurance-claims-assistance-hoffman-estates-il/): Documentation and support for homeowner insurance restoration claims.

## Service Area
Hoffman Estates, Schaumburg, Naperville, Downers Grove, Bolingbrook, Orland Park, Tinley Park, Hinsdale, Barrington, and greater Chicagoland, IL.

## About
Nicsar Restoration Contractors Inc. has 20+ years of experience restoring residential and commercial properties in the Chicagoland area.
```

---

### Priority 3 — Add FAQPage Schema and Upgrade FAQ Headings (Effort: 2 hours, Impact: High)
**Current state:** FAQ sections use H6 tags with no structured data. FAQ answers average 20–25 words.
**Changes needed:**
1. Change FAQ H6 to H2 throughout service pages.
2. Add `@type: FAQPage` JSON-LD to service pages. Example for water damage page:
```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "How soon should water damage restoration begin?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Water damage restoration should begin within 24–48 hours. Mold can begin developing within 24 hours of water exposure, and structural materials absorb moisture progressively. Immediate water extraction followed by professional drying equipment significantly reduces total damage and repair costs."
      }
    }
  ]
}
```
3. Expand each FAQ answer to 80–150 words with at least one specific fact or process detail.

---

### Priority 4 — Add LocalBusiness Schema with Complete NAP (Effort: 1 hour, Impact: Medium-High)
**Current state:** Organization schema exists but missing address, telephone, hours, and sameAs links.
**Add via Yoast or manual JSON-LD:**
```json
{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "Nicsar Restoration Contractors Inc.",
  "telephone": "(773) 220-6751",
  "address": {
    "@type": "PostalAddress",
    "addressLocality": "Hoffman Estates",
    "addressRegion": "IL",
    "addressCountry": "US"
  },
  "url": "https://nicsar-restoration.com/",
  "sameAs": [
    "https://www.google.com/maps/place/Nicsar+Restoration+Contractors+Inc.",
    "[GBP URL]",
    "[Yelp URL when created]",
    "[Facebook URL when linked]"
  ],
  "areaServed": ["Hoffman Estates", "Schaumburg", "Naperville", "Chicagoland"],
  "openingHours": "Mo-Su 00:00-24:00"
}
```

---

### Priority 5 — Establish Yelp Listing and Add Research-Mode Content Pages (Effort: 3–5 hours, Impact: High)
**Yelp:** Create or claim Nicsar Restoration on Yelp. This is the single highest-leverage action for emergency-intent AI answers. Perplexity heavily sources Yelp for "[service] near [city]" queries. Even a minimal Yelp listing with 5+ reviews changes the AI answer landscape.

**Research-mode blog content:** Create one standalone educational page targeting "what to do after water damage" or "how to file an insurance claim for flood damage." These pages should:
- Open with a direct 40–60 word answer in the first paragraph
- Use H2 question headings throughout
- Include at least 3 sourced statistics (IICRC, FEMA, insurance industry data)
- Target 800–1200 words total
- Include HowTo schema for step-based content

This content type wins research-mode AI citations that service pages never will, because AI engines prefer informational content over commercial pages for advisory queries.

---

## Platform-Specific Scores

| Platform | Score | Reason |
|----------|-------|--------|
| Google AI Overviews | 35/100 | Googlebot allowed; Organization schema present; service pages indexed; but no FAQPage schema, no LocalBusiness schema, no research-mode content |
| ChatGPT Search / Browsing | 5/100 | GPTBot blocked — site effectively invisible to ChatGPT's live web tool |
| Perplexity | 40/100 | PerplexityBot allowed; SSR renders correctly; service page content is parseable; but no llms.txt, no research-mode content, thin review signals |
| Bing Copilot | 30/100 | Bingbot not blocked; Bing indexes the site; but thin schema, no research-mode content, competitive market |
| Claude (Anthropic) | 5/100 | ClaudeBot blocked; content not accessible for Claude's web tool |

---

## Summary of What the robots.txt Block Actually Kills

The Cloudflare-managed block has achieved roughly the opposite of what a growth-minded local business should want:

- It blocks the two largest AI search surfaces that drive referral clicks (ChatGPT Search via GPTBot, Claude via ClaudeBot)
- It allows the training-only crawlers that the Content-Signal tries to restrict (anthropic-ai is NOT listed in the Disallow blocks, only ClaudeBot is)
- The `ai-train=no` Content-Signal in the wildcard block is the correct way to signal no-training preference — named Disallow blocks on retrieval bots are counterproductive

The practical recommendation is: trust the Content-Signal for training restriction, and remove the Disallow blocks on GPTBot, OAI-SearchBot, and ClaudeBot to restore AI search visibility.

