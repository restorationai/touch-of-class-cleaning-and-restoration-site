# Developer Handoff — Launch Form Payload Schema (`marketing_ads_jobs.payload`)

> Canonical contract for the **"Launch Ads" form** → `marketing_ads_jobs.payload` (job_type `full_launch`).
> The worker reads exactly these fields. The form should emit this shape; don't add/rename fields without syncing with the pipeline side.

## Why this shape

Campaign structure is built from **services × cities**:
- Each **service × city** → one **city SKAG** ad group (one tightly-themed keyword).
- For each **service**, the worker **auto-generates 7 high-intent ad groups** (near-me, emergency, cost, company, free-estimate, insurance, removal). **These are NOT operator input** — do not collect them in the form.
- **Keywords are auto-researched** (updated 2026-06-15): with Google Ads API Basic Access approved, the worker pulls real, volume-validated keywords (`KeywordPlanIdeaService`) and seeds the ad groups automatically. **The operator does NOT supply keywords.** `extra_keywords[]` remains an **optional override** for must-have terms.

So the form collects **structured Services and Cities**, budget/value, and the call-tracking forward target. That's it.

## Schema

```jsonc
{
  "rank_ai_slug": "narestco",                  // string, required — pipeline key

  "services": [                                 // required, 1+ ; drives city SKAGs + the 7 intent groups each
    { "slug": "water-damage-restoration", "label": "Water Damage Restoration" },
    { "slug": "fire-damage-restoration",  "label": "Fire Damage Restoration" }
  ],

  "cities": [                                   // required, 1+ ; each service × city = one city SKAG
    { "city": "Federal Way", "state": "WA", "radius_miles": 20 },   // radius_miles optional (default 20)
    { "city": "Tacoma",      "state": "WA" }
  ],

  "campaign": {
    "daily_budget": 50.00,                      // number, required — USD/day per campaign
    "lead_value": 300.00,                       // number, required — value of one phone-call lead
    "bidding_strategy": "MAXIMIZE_CONVERSIONS"  // optional, default MAXIMIZE_CONVERSIONS
  },

  "call_tracking": {
    "forward_to": "+12065551234",               // E.164, required — where the tracking number rings
    "forward_type": "pstn",                     // "pstn" (business line) | "sip" (AI voice agent) ; default "pstn"
    "recording_enabled": true                   // optional, default true
  },

  "extra_keywords": []                          // optional string[] — extra keywords to layer onto city SKAGs
}
```

## Form field mapping

| Form input | Payload path | Notes |
|---|---|---|
| Services (multi-add: label) | `services[]` | derive `slug` from label (kebab-case) or use your service registry |
| Cities (multi-add: city + state, optional radius) | `cities[]` | state is 2-letter |
| Daily budget ($) | `campaign.daily_budget` | per campaign |
| Lead value ($) | `campaign.lead_value` | |
| Forward destination (phone) | `call_tracking.forward_to` | E.164 |
| Forward type (toggle: Business line / AI agent) | `call_tracking.forward_type` | `pstn` / `sip` |
| Record calls (checkbox) | `call_tracking.recording_enabled` | |
| Extra keywords (optional textarea) | `extra_keywords[]` | one per line |

Intent ad groups, RSAs, landing-page slugs, and conversion actions are all derived by the worker — not collected here.
