# Migrating the legacy macOS monitor

The migration script performs a reversible cutover from the original `~/network-monitor` LaunchAgent to the packaged NetBlackBox service.

## Before migration

Pull the latest repository state and confirm that no uncommitted work would be lost:

```bash
git checkout main
git pull --ff-only
git checkout feature/macos-migration-installer
```

## Run migration

```bash
chmod +x install.sh migrate-macos.sh rollback-macos.sh
./migrate-macos.sh
```

The script:

1. copies `~/network-monitor` and the legacy plist into a timestamped backup;
2. stops the old LaunchAgent;
3. installs NetBlackBox into a dedicated virtual environment under `~/Library/Application Support/NetBlackBox`;
4. writes the Fastweb test configuration;
5. starts the new LaunchAgent;
6. checks `http://127.0.0.1:8080/status`;
7. automatically rolls back if the health check fails.

## Verify

```bash
launchctl print gui/$(id -u)/io.github.asswerus.netblackbox
curl -s http://127.0.0.1:8080/status | python3 -m json.tool
tail -f "$HOME/Library/Application Support/NetBlackBox/logs/netblackbox.log"
```

Keep the generated backup for at least 24 hours.

## Manual rollback

```bash
./rollback-macos.sh "$HOME/NetBlackBox-Migration-Backup-YYYYMMDD_HHMMSS"
```

Rollback stops NetBlackBox and restores the legacy LaunchAgent. New NetBlackBox data is preserved for inspection.
