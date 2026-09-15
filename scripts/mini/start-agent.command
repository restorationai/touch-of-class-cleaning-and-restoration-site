#!/bin/zsh
# Rank AI — Mini agent launcher. COPY THIS FILE TO THE DESKTOP (the mini
# agent does this during self-install). Double-click = pull latest orders
# and start the operator session. No terminal knowledge needed.
cd "$(cat ~/.rankai-repo-path 2>/dev/null || echo $HOME/dev/rank-ai)"
git pull --rebase --autostash
exec claude "Read docs/MINI-OPERATOR.md and work clients/_ops/mini-inbox.md top to bottom. Santino may be present for supervised items; ask him."
