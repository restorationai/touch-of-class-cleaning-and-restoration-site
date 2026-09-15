#!/bin/zsh
# One-shot 2026-09-15 08:35 PT: open the rename conversation with Alfredo
# (ACS Enterprise) 60+ min after Santino's own text (quiet-window respect).
# Self-removes after running so the daily StartCalendarInterval never
# re-fires it.
cd /Users/santino/Desktop/mywebsitecode/rank-ai
/opt/homebrew/bin/python3 scripts/client_concierge.py rename-pitch --company CO-1788916409529 --send
launchctl bootout gui/$(id -u)/com.rankai.oneshot.acs-rename 2>/dev/null
rm -f ~/Library/LaunchAgents/com.rankai.oneshot.acs-rename.plist
