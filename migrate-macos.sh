#!/bin/bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
LEGACY_DIR="$HOME/network-monitor"
LEGACY_PLIST="$HOME/Library/LaunchAgents/com.albano.network-monitor.plist"
BACKUP_ROOT="$HOME/NetBlackBox-Migration-Backup-$STAMP"
APP_SUPPORT="$HOME/Library/Application Support/NetBlackBox"

mkdir -p "$BACKUP_ROOT"

if [[ -d "$LEGACY_DIR" ]]; then
  cp -a "$LEGACY_DIR" "$BACKUP_ROOT/network-monitor"
fi

if [[ -f "$LEGACY_PLIST" ]]; then
  cp -a "$LEGACY_PLIST" "$BACKUP_ROOT/com.albano.network-monitor.plist"
fi

cat > "$BACKUP_ROOT/migration.json" <<EOF
{
  "created_at": "$STAMP",
  "legacy_directory": "$LEGACY_DIR",
  "legacy_plist": "$LEGACY_PLIST",
  "new_directory": "$APP_SUPPORT"
}
EOF

launchctl bootout "gui/$(id -u)" "$LEGACY_PLIST" 2>/dev/null || true

"$SOURCE_DIR/install.sh"

CONFIG_PATH="$APP_SUPPORT/config.json"
python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
data["modem_ip"] = "192.168.1.254"
data["upstream_gateway_ip"] = "100.74.248.1"
data["http_host"] = "127.0.0.1"
data["http_port"] = 8080
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY

launchctl kickstart -k "gui/$(id -u)/io.github.asswerus.netblackbox"

sleep 4
if ! curl --fail --silent http://127.0.0.1:8080/status >/dev/null; then
  echo "NetBlackBox did not pass the health check. Rolling back."
  "$SOURCE_DIR/rollback-macos.sh" "$BACKUP_ROOT"
  exit 1
fi

echo "Migration completed successfully."
echo "Backup: $BACKUP_ROOT"
echo "Status: http://127.0.0.1:8080/status"
echo "Keep the backup until the new monitor has run reliably for at least 24 hours."
