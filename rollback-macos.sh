#!/bin/bash
set -euo pipefail

BACKUP_ROOT="${1:-}"
NEW_PLIST="$HOME/Library/LaunchAgents/io.github.asswerus.netblackbox.plist"
LEGACY_PLIST="$HOME/Library/LaunchAgents/com.albano.network-monitor.plist"

if [[ -z "$BACKUP_ROOT" || ! -d "$BACKUP_ROOT" ]]; then
  echo "Usage: $0 /path/to/NetBlackBox-Migration-Backup-YYYYMMDD_HHMMSS"
  exit 1
fi

launchctl bootout "gui/$(id -u)" "$NEW_PLIST" 2>/dev/null || true

if [[ -f "$BACKUP_ROOT/com.albano.network-monitor.plist" ]]; then
  cp -a "$BACKUP_ROOT/com.albano.network-monitor.plist" "$LEGACY_PLIST"
  launchctl bootstrap "gui/$(id -u)" "$LEGACY_PLIST"
  launchctl enable "gui/$(id -u)/com.albano.network-monitor"
  launchctl kickstart -k "gui/$(id -u)/com.albano.network-monitor"
fi

echo "Rollback completed."
echo "The new NetBlackBox data directory was preserved for inspection."
