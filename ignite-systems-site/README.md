# ignitesystems.io

Static site (homepage + legal pages for Meta / Google app review), built 2026-09-30.
Hosted on Cloudflare Pages project `ignite-systems-site` in the Ignitesystems3@gmail.com
Cloudflare account (id 17d53190624d44f0d8b5e70651bca232). Only the apex + www DNS
records point here; email (Google Workspace MX), app., link., grow., notifications. are untouched.
Previous records (rollback): A ignitesystems.io 162.159.140.166, CNAME www -> sites.ludicrous.cloud.

Deploy: CLOUDFLARE_API_TOKEN=$CLOUDFLARE_IGNITE_TOKEN CLOUDFLARE_ACCOUNT_ID=17d53190624d44f0d8b5e70651bca232 \
  npx wrangler@3 pages deploy ignite-systems-site --project-name ignite-systems-site --branch main
