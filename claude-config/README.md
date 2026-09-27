# claude-config — Claude's brain, backed up

Mirror of `~/.claude` skills, commands, scheduled tasks and the
cross-session memory for this project. Refreshed daily by
`scripts/claude_config_backup.py` (secret-scanned, fail-closed).
Secrets are NOT here — they live in the encrypted `secrets-vault/`.

## New computer: pick up where we left off
1. Install Claude Code + git; `git clone` github.com/restorationai/Rank-AI-Pipeline
   (private) to ~/Desktop/mywebsitecode/rank-ai.
2. `python3 scripts/secrets_backup.py restore` — enter the vault passphrase
   (password manager). Restores .env, OAuth tokens, portal creds,
   ~/.claude/settings*.json, per-client Ads tokens.
3. `python3 scripts/claude_config_backup.py restore` — restores skills,
   commands, scheduled tasks and memory into ~/.claude.
4. Clone the app: github.com/restorationai/Restoration-AI-APP (private).
5. Re-login CLIs that keep tokens in the OS keychain: `supabase login`,
   `gh auth login`, `npx wrangler login`.
6. Store the vault passphrase for the daily job:
   `security add-generic-password -a "$USER" -s rankai-secrets-backup -w`
7. Reinstall the daily backup: `bash scripts/macbook/install_backup_job.sh`.
Then open Claude in the repo — memory + docs/WORKING-STATE.md carry the context.
