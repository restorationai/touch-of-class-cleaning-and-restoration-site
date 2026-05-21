# System 4 v2 Activation — Agency GSC Model

System 4 v1 scores pages using sitemap dates only (no GSC needed).
v2 layers in real Google Search Console impression + indexing data per URL.

## How the agency model works

One OAuth token for `contact@restorationai.io` covers all clients.
Each client simply adds the agency email to their GSC property — no per-client
OAuth flow, no client-side API keys.

```
Agency setup (once):     python3 scripts/gsc_setup.py
Per client (30 seconds): client adds contact@restorationai.io to their GSC
Verify access:           python3 scripts/gsc_setup.py --test-slug {slug}
```

---

## Step 1 — Create a Google Cloud project (once)

1. Go to https://console.cloud.google.com/
2. Create a new project named "Rank AI GSC"
3. APIs & Services > Enable APIs > search "Google Search Console API" > Enable

## Step 2 — Create OAuth credentials (once)

1. APIs & Services > Credentials > Create Credentials > OAuth client ID
2. Application type: **Desktop app**
3. Name: "Rank AI Agency"
4. Download the JSON and save to `rank-ai/.gsc-oauth-client.json`

## Step 3 — Configure OAuth consent screen (once)

1. APIs & Services > OAuth consent screen
2. User type: External
3. App name: "Rank AI", support email: contact@restorationai.io
4. Scopes: add `https://www.googleapis.com/auth/webmasters.readonly`
5. Test users: add `contact@restorationai.io`
6. Status: leave as "Testing" (sufficient for internal agency use)

## Step 4 — Run the agency OAuth flow (once)

```bash
cd /Users/santino/Desktop/mywebsitecode/rank-ai
pip install google-auth google-auth-oauthlib google-api-python-client
python3 scripts/gsc_setup.py
```

Sign in as `contact@restorationai.io` when the browser opens.
Token saved to `.gsc-agency-token.json` (gitignored).

---

## Per-client activation (30 seconds per client)

### Client side (they do this once)

1. Client logs into Google Search Console
2. Settings > Users and permissions > Add user
3. Email: `contact@restorationai.io`
4. Permission level: **Full**

### Your side (optional override only)

If the client's GSC property is a URL-prefix property (e.g. `https://www.narestco.com/`)
rather than a domain property, add this to `clients/{slug}.json`:

```json
"gsc_property_url": "https://www.narestco.com/"
```

If omitted, defaults to `sc-domain:{domain}` (domain property format, correct for most clients).

### Verify access

```bash
python3 scripts/gsc_setup.py --test-slug narestco
```

A successful test prints the homepage verdict + last crawl time.
A 403 means the client has not yet added the agency email.

---

## What changes in System 4 once v2 is active

`refresh_scorer.py` calls `GSCClient.is_configured(slug)` at startup:
- `False` — sitemap-only scoring (v1 behavior, no change)
- `True` — adds GSC indexing flags to each page score:
  - Pages with `FAIL` verdict elevated to highest priority regardless of age
  - Pages never crawled flagged immediately
  - Pages with `last_crawl > 60 days` flagged even if content is recent

No other changes needed. The switch is automatic once token + client access exist.

---

## Adding the agency token to GitHub Actions (for CI)

When ready for CI to run S4 v2:

```bash
cat .gsc-agency-token.json   # copy the JSON content
# GitHub repo > Settings > Secrets and variables > Actions > New secret
# Name: GSC_AGENCY_TOKEN  Value: (paste the JSON)
```

Then add this step to `.github/workflows/weekly-maintenance.yml` before the run step:

```yaml
- name: Write GSC agency token
  if: ${{ secrets.GSC_AGENCY_TOKEN != '' }}
  run: echo '${{ secrets.GSC_AGENCY_TOKEN }}' > .gsc-agency-token.json
```

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `Agency token not found` | Setup not run | `python3 scripts/gsc_setup.py` |
| `403 does not have permission` | Client has not added agency email | Ask client to add contact@restorationai.io to GSC |
| `Token invalid` | Token expired or revoked | `python3 scripts/gsc_setup.py --force` |
| `Property not found` | Wrong property URL format | Add `gsc_property_url` to clients/{slug}.json |
