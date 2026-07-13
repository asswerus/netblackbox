# Cross-platform architecture

NetBlackBox now separates the portable monitoring core from operating-system integrations.

## Shared core

The following modules are platform-neutral:

- `config.py` — configuration and data-directory selection
- `models.py` — probe result models
- `probes.py` — TCP, HTTP, DNS and router probes
- `app.py` — event lifecycle, SQLite storage, diagnostics orchestration and local API

## Platform backends

`platforms.py` selects one backend at runtime using `platform.system()`:

- macOS: `route`, `netstat`, `arp`, `scutil`, `ifconfig`, `traceroute`
- Linux: `ip route`, `ip addr`, `ip neigh`, `resolvectl`, `traceroute` or `tracepath`
- Windows: PowerShell network cmdlets, `ipconfig`, `route`, `arp`, `tracert`

The backend owns only operating-system commands and default-gateway discovery. Monitoring and classification stay identical on all systems.

## Service installation roadmap

The current `install.sh` remains the macOS service installer. Follow-up work will add:

- a `systemd` unit and installer for Linux;
- a Task Scheduler installer for Windows;
- platform-specific packaging and release artifacts.
