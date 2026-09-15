# Mini self-install (the mini agent runs these steps ONCE)

1. `echo "$(pwd)" > ~/.rankai-repo-path` from the repo root.
2. Copy `scripts/mini/start-agent.command` to `~/Desktop/Start Rank AI Agent.command`
   and `chmod +x` it. Santino double-clicks this to start a session — no terminal.
3. Install the trigger watcher (5-min launchd interval):
   write `~/Library/LaunchAgents/com.rankai.mini-trigger.plist` running
   `scripts/mini/check_trigger.sh` with StartInterval 300, then
   `launchctl bootstrap gui/$(id -u) <plist>` and VERIFY with
   `launchctl print gui/$(id -u)/com.rankai.mini-trigger` (a plist that
   isn't bootstrapped never fires — house lesson).
4. Report the install in the daily report.

After install: MacBook Claude starts unsupervised sessions by pushing a new
token to `clients/_ops/mini-trigger`; Santino starts supervised ones by
double-clicking the Desktop icon.
