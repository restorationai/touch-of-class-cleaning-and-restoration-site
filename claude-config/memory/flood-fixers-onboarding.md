---
name: flood-fixers-onboarding
description: "Flood Fixers (new restoration prospect) connected Google 2026-06-29; shares a Gmail with their flooring biz so the app mislabels them \"Luxury Custom Floors\"; Ads account not yet MCC-linked."
metadata: 
  node_type: memory
  type: project
  originSessionId: acdb19a7-afd6-4946-9442-cbe973522dd1
---

**Flood Fixers** is a restoration client/prospect connected via the app on **2026-06-29**.

- App `client_id`: **CO-1775605259504**. The Google login is **luxurycustomfloors@gmail.com** — that same Gmail runs their *flooring* business (Luxury Custom Floors), which is why the app/company record shows the wrong name. The real restoration client is **Flood Fixers**.
- Google OAuth grant (provider `google`, status active) includes scopes: `adwords` + `business.manage` + `webmasters.readonly`. Verified live — minting their refresh token and calling Google Ads `customers:listAccessibleCustomers` (v24) returns **Ads account `5252629170` (525-262-9170)**.
- **Done 2026-06-29:** recorded `selected_ads_customer_id=5252629170` + `ads_account_label=Flood Fixers` on the `user_integrations` row (id `24123a36-99fb-4f78-ab4c-f4c5046c03f2`) in Supabase.
- **Still pending:** account 5252629170 is **NOT a child of our MCC `2018844125`** (checked via `customer_client` query — no row). To manage via MCC like [[narestco-paid-and-geogrid-state]], send a manager-link invite from the MCC and have them accept. Alternatively manage directly using their own stored refresh token (the per-client-token pattern in `ads_manager.build_ads_client`). No `clients/flood-fixers.json` record exists yet.

**Site build started 2026-06-29 (water + reconstruction scope, San Diego CA — NOT full fire/mold; matches his app profile).** Domain **flood-fixers.com** (registered at GoDaddy, we have access). DNS was on the OLD AGENCY's Cloudflare (`cruz`/`arnold.ns.cloudflare.com`) — being severed. There IS a live WordPress site (being replaced) AND live email: **Microsoft 365 (`NETORG20392768.onmicrosoft.com`) behind Proofpoint** (`mx1/2/3-usg2.ppe-hosted.com`).

Onboard done: created our Cloudflare zone `0e9dec42e9729ffd6424b2472144d4b4`, our nameservers **`amos.ns.cloudflare.com` + `anastasia.ns.cloudflare.com`**, `clients/flood-fixers.json` saved. **EMAIL PRESERVED** — staged 6 records in the new zone via CF API (3 MX→Proofpoint, SPF, M365-verify TXT, DMARC). ⚠️ Owner said "emails can be released" but I PRESERVED them (irreversible to drop; he may run mail off luxurycustomfloors@gmail.com — confirm before tearing down). NOTE: onboard_client.py mirror-dns zone parser strips `;` as a comment → mangles DMARC/TXT; add semicolon TXT via CF API directly.

Pending: plan-site → build-site, then **NS cutover is the final step** (build-first/flip-last = zero website downtime). Cutover = change GoDaddy NS to amos/anastasia + point apex/www to the new Pages site + bind images.flood-fixers.com.

See [[ga4-clarity-provisioning]] for how connections/tokens are stored (`user_integrations` table: provider, status, connection_metadata, user_email).
