# Mini launchd jobs — install by hand (one paste, Terminal on the Mini)

The operator agent's permission classifier refuses to write into
`~/Library/LaunchAgents` or run `launchctl bootstrap` (flagged as
"persistence"), so these two plists live here and Santino installs them:

```zsh
cp ~/dev/rank-ai/scripts/mini/launchd/com.rankai.mini-trigger.plist ~/Library/LaunchAgents/
cp ~/dev/rank-ai/scripts/mini/launchd/com.rankai.mini-sweep.plist   ~/Library/LaunchAgents/
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.rankai.mini-trigger.plist
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.rankai.mini-sweep.plist
launchctl print gui/501/com.rankai.mini-trigger | head -5   # must show state
launchctl print gui/501/com.rankai.mini-sweep   | head -5
```

Notes:
- `claude` is not on the system PATH on the Mini; the working binary is the
  IDE extension's native build, symlinked at `~/.local/bin/claude`
  (2.1.272, authenticated — verified with a `-p` call 2026-09-15). Both
  plists put `~/.local/bin` first on PATH. `Start Rank AI Agent.command`
  on the Desktop relies on the Terminal shell's PATH — if double-click says
  `claude: command not found`, also `sudo ln -sf ~/.local/bin/claude /usr/local/bin/claude`.
- The sweep job needs a live Microsoft session on the suite Chrome
  profile first (Bing step 2.1) and must not overlap the held CDP Chrome
  on that profile (SingletonLock) — quit that Chrome before 11:30.
