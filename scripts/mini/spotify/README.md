# Spotify RSS connect — operator scripts (Mac Mini)

Committed copy of the scripts that live (gitignored) in
`browser_agent/runtime/spotify/` on the Mini. Copy them back there if the
runtime dir is purged. Full wizard map, traps and run order:
`clients/_ops/mini-reports/2026-09-15-spotify-podcast-connect-handoff.md`.

Order per client: `podcast_feed.py sync --slug X` → `step_resend.py <feed>`
→ `step_verify.py <epoch>`. Needs the held Chrome on CDP port 9223 using the
suite profile, `~/.rankai/portal-creds.json` (`spotify:agency`), the Gmail
token in `~/.config/rankai/`, and `GOOGLE_OAUTH_CLIENT_ID/SECRET` in `.env`.
No secrets in these files.
