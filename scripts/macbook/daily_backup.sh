#!/bin/zsh
# Daily MacBook backup: Claude config mirror + encrypted secrets vault.
cd "$HOME/Desktop/mywebsitecode/rank-ai" || exit 1
set -a; . ./.env; set +a
echo "== $(date) =="
python3 scripts/claude_config_backup.py backup
if security find-generic-password -s rankai-secrets-backup -w >/dev/null 2>&1; then
  python3 scripts/secrets_backup.py backup && \
  git add secrets-vault/vault.tar.gz.enc && \
  git commit -q -m "vault refresh [automated]" -- secrets-vault/vault.tar.gz.enc && \
  git pull -q --rebase --autostash origin main && git push -q origin main
else
  echo "vault skipped: passphrase not in keychain (service rankai-secrets-backup)"
fi
