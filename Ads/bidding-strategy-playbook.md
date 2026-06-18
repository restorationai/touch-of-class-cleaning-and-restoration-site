# Bidding Strategy Playbook (Google Ads — Rank AI restoration)

The SOP (`build-your-first-skag.md`) and the `ads-campaigns` skill reference this file.
It exists because a brand-new campaign started on Maximize Conversions **does not serve** —
this is the failure that left NaRestCo's SKAGs at $0 spend / 0 clicks for 30 days.

## The lifecycle (never skip Phase 0)

| Phase | When | Strategy | Why |
|---|---|---|---|
| **0 · Cold-start** | Day 1, 0 conversions | **Maximize Clicks + max-CPC ceiling ($30)** | Smart Bidding needs conversion history to bid. A fresh campaign has none → it bids microscopically → **~90% impression share lost to rank → ~$0 spend, 0 clicks**. Maximize Clicks forces it into the auction to win clicks + gather data. |
| **1 · Convert** | ~15–30 conversions | **Maximize Conversions** | Enough signal to optimize toward leads instead of raw clicks. |
| **2 · Efficiency** | 30 conv / 30 days | **+ Target CPA** | Hold a cost-per-lead target. |
| **3 · Value** | 50 conv + conversion-value tracking live | **Maximize Conversion Value + tROAS** | Optimize revenue, not lead count. (Requires real per-lead value — a $1 placeholder makes tROAS meaningless.) |

Don't change strategy more than once per **14 days** (each change resets the learning period).

Graduate with:
```
ads_manager.py set-bid-strategy --slug <slug> --campaign <campaign_resource> \
    --strategy maximize-conversions
```

## Budget sizing

**Budget = target max-CPC × clicks/day you want.** Emergency restoration CPCs run ~$15–30,
so **~$75–150/day per service campaign**. A budget below this just starves a campaign that
would otherwise spend. Raising budget while bids are too low does **nothing** — fix bids first.

## Diagnostic: "why isn't it spending?"

Pull impression-share metrics per campaign:
```
SELECT campaign.name, metrics.search_impression_share,
       metrics.search_budget_lost_impression_share,
       metrics.search_rank_lost_impression_share
FROM campaign WHERE segments.date DURING LAST_30_DAYS
```
- **Lost to RANK high** → bids too low. Raise the CPC ceiling / graduate the strategy.
- **Lost to BUDGET high** → bids are fine; raise the daily budget.
- **Both ~0 and IS still low** → low search volume or targeting too narrow (not a bidding problem).

## Default in code

`ads_manager.py create_campaign()` defaults new campaigns to **TARGET_SPEND (Maximize Clicks)
with a $30 CPC ceiling** (`cold_start_max_cpc=30.0`). The scaffold therefore births every SKAG
in Phase 0 automatically — graduate per the table above once conversions accumulate.
