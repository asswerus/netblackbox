#!/bin/bash
set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/io.github.asswerus.netblackbox.plist"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "NetBlackBox service removed. Data under ~/netblackbox was preserved."
