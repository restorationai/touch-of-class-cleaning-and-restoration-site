# System 4 v2 — Google Search Console activation guide

System 4 v1 (already shipped) scores URL refresh candidates using sitemap +
page-level date extraction. It catches `stale_12mo` and `aging` URLs but
cannot see indexing problems.

System 4 v2 adds Google Search Console URL Inspection so we can detect
`not_indexed` and `index_warning` flags. This unlocks two more actions in
the refresh recommender: `request_indexing` (for not-indexed URLs) and
`fix_canonical` (for canonical-mismatch URLs).

**When to activate this for a client:** wait until the client has been live
for 30-60 days post-cutover. Before that, GSC has nothing useful to report.

**One-time prerequisites:** Steps 1-4 below are done once globally (across
all Rank AI clients).
**Per-client prerequisites:** Steps 5-7 are done once per client.
**Activation:** Step 8.

---

## Step 1: Google Cloud project (one-time)

1. Go to https://console.cloud.google.com/.
2. Create a new project named `Rank AI Search Console` (or use an existing
   Rank AI project if you have one).
3. Note the project ID — used only for billing context.

## Step 2: Enable the Search Console API (one-time)

1. In the project, go to **APIs & Services → Library**.
2. Search for **Google Search Console API**.
3. Click **Enable**.

## Step 3: Create OAuth 2.0 credentials (one-time)

1. Go to **APIs & Services → Credentials**.
2. Click **Create credentials → OAuth client ID**.
3. If prompted, configure the OAuth consent screen:
   - User type: **External** (we won't publish; we'll keep it in testing mode)
   - App name: `Rank AI`
   - User support email: `contact@restorationai.io`
   - Developer contact: `contact@restorationai.io`
   - **Test users:** add `contact@restorationai.io` (the Google account that
     owns the GSC properties for all our clients)
   - Save — leave the app in **Testing** status. Internal use only; never
     submit for verification.
4. Back at **Create OAuth client ID**:
   - Application type: **Desktop app**
   - Name: `Rank AI System 4 v2`
   - Click **Create**.
5. Click **Download JSON** on the newly-created client.
6. Save the file as `rank-ai/.gsc-oauth-client.json`.
7. Verify it is gitignored: `git check-ignore rank-ai/.gsc-oauth-client.json`
   should return the path. If not, add `.gsc-oauth-client.json` to
   `rank-ai/.gitignore`.

## Step 4: Install Python deps (one-time)

```
pip install google-auth google-auth-oauthlib google-api-python-client
```

These are intentionally NOT in a `requirements.txt` — System 4 v1 runs
without them, so we keep them optional until v2 is activated.

---

## Step 5: Verify the client's domain in GSC (per client)

GSC URL Inspection only works on domain properties you've verified ownership
of. The cleanest verification method for our setup is DNS TXT, since we
control the Cloudflare zone:

1. Go to https://search.google.com/search-console.
2. **Add property → Domain** (NOT URL prefix).
3. Enter `{client.domain}` (e.g. `narestco.com`).
4. GSC will show a TXT record to add. Copy it.
5. Add the TXT record to the zone via the Cloudflare API:

```bash
ZONE_ID=$(curl -s -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones?name={client.domain}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['result'][0]['id'])")

curl -s -X POST -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  -H "Content-Type: application/json" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
  -d '{"type":"TXT","name":"{client.domain}","content":"google-site-verification=...","ttl":1}'
```

(or use the Cloudflare dashboard — both work)

6. Back in GSC, click **Verify**. Should succeed within seconds.

If the client already has a Google site-verification TXT in their zone from
a previous setup (check the existing DNS records — narestco does), that
verification still works and you can skip this step.

## Step 6: Add the GSC property to the OAuth account (per client)

After Step 5, the property is verified for the Google account that did the
verification. That same account must own the OAuth credentials from Step 3.
This is `contact@restorationai.io` in our setup — verify it has access in
GSC by visiting the property page.

## Step 7: Run the per-client OAuth flow (per client)

```bash
cd /Users/santino/Desktop/mywebsitecode/rank-ai
python3 scripts/gsc_setup.py --slug {slug}
```

This will:
1. Open a browser to the Google OAuth consent screen
2. After consent, save `clients/{slug}/.gsc-token.json` (gitignored)
3. Make one test API call to verify the token works
4. Print the homepage's current indexing status

If the test call fails with "Permission denied" or similar:
- Confirm Step 5 verification succeeded
- Confirm the OAuth account is the same one that verified the property
- Re-run with `--force` to redo the flow

## Step 8: Activate (per client)

That's it. The next time `scripts/refresh_scorer.py --slug {slug}` runs, it
will:
- Detect that `GSCClient.is_configured(slug)` is True
- Call GSC URL Inspection per URL (one call per URL, rate-limited
  client-side by `google-api-python-client`)
- Populate `gsc` field on each candidate with index status + coverage state
- Set `gsc_enabled: true` in the output JSON

Layer 2 (the `rank-ai-refresh-recommender` skill) will then automatically
start producing `request_indexing` and `fix_canonical` actions when GSC
reports those issues.

---

## Verifying v2 is active

```bash
python3 -c "
from scripts.gsc_client import GSCClient
print('narestco:', GSCClient.is_configured('narestco'))
"
```

After a refresh_scorer run, check the candidates file:

```bash
python3 -c "
import json
c = json.load(open('clients/{slug}/refresh-candidates.json'))
print('gsc_enabled:', c['gsc_enabled'])
print('candidates with gsc data:',
      sum(1 for x in c['candidates'] if x.get('gsc')))
"
```

---

## Cost + rate limits

- **Cost:** GSC API is free. No spend.
- **Rate limits:** 1200 requests/min per project, 50,000/day. We use
  ~50-100 per client per month — trivially under quota even at 100 clients.
- **OAuth token lifetime:** the refresh token does NOT expire (when OAuth
  app is in Testing mode with verified test users). Access tokens expire
  hourly but `GSCClient` refreshes them automatically.

---

## Failure modes + fixes

| Symptom | Fix |
| --- | --- |
| `OAuth client secret not found` | Step 3 not completed — download and save to `rank-ai/.gsc-oauth-client.json` |
| `Permission denied` on inspect | Step 5/6 — property not verified or wrong Google account |
| `quota exceeded` | Rare — wait an hour, or paginate URLs more aggressively |
| Refresh token revoked (Testing mode 7-day limit only if app is NOT in Testing — but our app IS in Testing) | Re-run Step 7 with `--force` |
| `is_configured()` returns False after Step 7 | Confirm `clients/{slug}/.gsc-token.json` exists; check it's not corrupted |

---

## What v2 unlocks for the recommender

With `gsc_enabled: true`, the Layer 2 prompt starts using these flag → action mappings:

| Flag (from GSC) | Action | Recommendation |
| --- | --- | --- |
| `not_indexed` (verdict=FAIL, coverage in {"Crawled - currently not indexed", "Discovered - currently not indexed", "URL is unknown to Google"}) | `request_indexing` | Open GSC → URL Inspection → Request Indexing. Check page returns 200 and has no `noindex` meta. |
| `index_warning` (verdict=PARTIAL, coverage contains "alternate" or "duplicate") | `fix_canonical` | Align the page's `<link rel="canonical">` with the URL, or intentionally redirect/de-dupe. |
| `stale_12mo` + `not_indexed` (combined) | `audit_then_decide` | Inspect manually — page may be 410-able or genuinely useful but de-indexed. |

These actions are documented in `templates/restoration/prompts/refresh-recommender.md` — the prompt already references them as "deferred to v2," so once `gsc_enabled` flips, they activate automatically.

---

## Estimated activation time per client

Once Step 1-4 are done globally:
- Step 5 (DNS TXT verify): ~2 min if using the Cloudflare API helper above
- Step 6 (account access check): ~1 min
- Step 7 (OAuth flow): ~2 min, browser-based

**Total: ~5 min per client.** Multiply by client count.
