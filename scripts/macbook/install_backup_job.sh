#!/bin/zsh
cp "$(dirname $0)/com.rankai.daily-backup.plist" ~/Library/LaunchAgents/
launchctl bootout gui/$(id -u)/com.rankai.daily-backup 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.rankai.daily-backup.plist
launchctl print gui/$(id -u)/com.rankai.daily-backup | grep -E "state|path" | head -3
