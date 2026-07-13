#!/bin/bash
set -euo pipefail

APP_DIR="$HOME/netblackbox"
PLIST="$HOME/Library/LaunchAgents/io.github.asswerus.netblackbox.plist"
PYTHON_PATH="$(command -v python3)"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ -z "${PYTHON_PATH}" ]]; then
  echo "python3 was not found in PATH."
  exit 1
fi

mkdir -p "$APP_DIR" "$APP_DIR/logs" "$APP_DIR/diagnostics" "$APP_DIR/reports" "$HOME/Library/LaunchAgents"
cp "$SOURCE_DIR/netblackbox.py" "$APP_DIR/netblackbox.py"
chmod 700 "$APP_DIR/netblackbox.py"

if [[ ! -f "$APP_DIR/config.json" ]]; then
  cp "$SOURCE_DIR/config.example.json" "$APP_DIR/config.json"
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
    <string>${PYTHON_PATH}</string>
    <string>${APP_DIR}/netblackbox.py</string>
    <string>--config</string>
    <string>${APP_DIR}/config.json</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${APP_DIR}</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>${APP_DIR}/logs/launchd.stdout.log</string>
  <key>StandardErrorPath</key><string>${APP_DIR}/logs/launchd.stderr.log</string>
</dict>
</plist>
EOF

plutil -lint "$PLIST"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/io.github.asswerus.netblackbox"
launchctl kickstart -k "gui/$(id -u)/io.github.asswerus.netblackbox"

echo "NetBlackBox installed."
echo "Dashboard: http://127.0.0.1:8080/"
echo "Logs: $APP_DIR/logs/netblackbox.log"
