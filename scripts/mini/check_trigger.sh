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
claude -p "Remote trigger $TOKEN: read docs/MINI-OPERATOR.md and work clients/_ops/mini-inbox.md. UNSUPERVISED session: skip any item marked supervised; report per the operator doc." \
  >> /tmp/rankai-mini-trigger.log 2>&1
