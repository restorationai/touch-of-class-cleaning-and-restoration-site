#!/bin/zsh
# Rank AI — remote trigger watcher (runs on the mini via launchd every 5
# min). MacBook Claude pushes clients/_ops/mini-trigger with a fresh token;
# if we haven't consumed that token yet, start a headless operator session.
REPO="$(cat ~/.rankai-repo-path 2>/dev/null || echo $HOME/dev/rank-ai)"
cd "$REPO" || exit 0
git fetch -q origin main && git pull -q --rebase --autostash origin main
TRIG="clients/_ops/mini-trigger"
[ -f "$TRIG" ] || exit 0
TOKEN=$(head -1 "$TRIG")
LAST=$(cat ~/.rankai-mini-trigger-consumed 2>/dev/null || echo "")
[ "$TOKEN" = "$LAST" ] && exit 0
echo "$TOKEN" > ~/.rankai-mini-trigger-consumed
# PRESENCE (2026-09-27): a trigger whose 2nd line is
#   PRESENT-UNTIL <unix-epoch>
# means Santino told MacBook Claude he is at/near the Mini, so supervised
# items may run (he approves 2FA prompts etc.). Expired = unsupervised.
MODE="UNSUPERVISED session: skip any item marked supervised"
UNTIL=$(sed -n '2p' "$TRIG" | awk '/^PRESENT-UNTIL/{print $2}')
if [ -n "$UNTIL" ] && [ "$(date +%s)" -lt "$UNTIL" ]; then
  MODE="SANTINO IS PRESENT (confirmed via MacBook Claude, window until epoch $UNTIL): supervised items MAY run now, in inbox order; he will approve 2FA/device prompts. If a step needs him to type something, pause and print exactly what you need in your report"
fi
claude -p "Remote trigger $TOKEN: read docs/MINI-OPERATOR.md and work clients/_ops/mini-inbox.md. $MODE; report per the operator doc." \
  >> /tmp/rankai-mini-trigger.log 2>&1
