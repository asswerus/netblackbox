#!/bin/bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_SUPPORT="$HOME/Library/Application Support/NetBlackBox"
VENV_DIR="$APP_SUPPORT/venv"
CONFIG_PATH="$APP_SUPPORT/config.json"
LOG_DIR="$APP_SUPPORT/logs"
PLIST="$HOME/Library/LaunchAgents/io.github.asswerus.netblackbox.plist"
PYTHON_PATH="$(command -v python3 || true)"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer currently supports macOS only."
  exit 1
fi

if [[ -z "$PYTHON_PATH" ]]; then
  echo "python3 was not found in PATH."
  exit 1
fi

mkdir -p "$APP_SUPPORT" "$LOG_DIR" "$APP_SUPPORT/diagnostics" "$APP_SUPPORT/reports" "$HOME/Library/LaunchAgents"

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_PATH" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install --upgrade "$SOURCE_DIR"

if [[ ! -f "$CONFIG_PATH" ]]; then
  cat > "$CONFIG_PATH" <<EOF
{
  "data_dir": "$APP_SUPPORT",
  "modem_ip": "192.168.1.254",
  "upstream_gateway_ip": null,
  "check_interval_seconds": 2.0,
  "turbo_interval_seconds": 0.25,
  "turbo_duration_seconds": 60,
  "confirmation_cycles": 2,
  "recovery_confirmation_cycles": 2,
  "ring_buffer_seconds": 60,
  "post_event_capture_seconds": 30,
  "diagnostic_repeat_interval_seconds": 3,
  "diagnostic_repeat_count": 4,
  "socket_timeout_seconds": 1.5,
  "http_timeout_seconds": 3.0,
  "public_ip_check_interval_seconds": 300,
  "http_host": "127.0.0.1",
  "http_port": 8080,
  "retention_days": 90
}
EOF
fi

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>io.github.asswerus.netblackbox</string>
  <key>ProgramArguments</key>
  <array>
    <string>${VENV_DIR}/bin/netblackbox</string>
    <string>--config</string>
    <string>${CONFIG_PATH}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${APP_SUPPORT}</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>${LOG_DIR}/launchd.stdout.log</string>
  <key>StandardErrorPath</key><string>${LOG_DIR}/launchd.stderr.log</string>
</dict>
</plist>
EOF

plutil -lint "$PLIST"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/io.github.asswerus.netblackbox"
launchctl kickstart -k "gui/$(id -u)/io.github.asswerus.netblackbox"

echo "NetBlackBox installed."
echo "Config: $CONFIG_PATH"
echo "Status: http://127.0.0.1:8080/status"
echo "Events: http://127.0.0.1:8080/api/events"
echo "Logs: $LOG_DIR/netblackbox.log"
