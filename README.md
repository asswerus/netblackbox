# NetBlackBox

> Because “everything looks fine from here” is not a diagnosis.

NetBlackBox is a dependency-free network outage recorder and diagnostic toolkit for macOS. It is designed to capture intermittent failures that disappear before an ISP support agent can inspect them.

## What it records

- Router reachability over ICMP, HTTP, and HTTPS
- Upstream gateway reachability
- Internet reachability over TCP and HTTP
- DNS resolution failures
- Outage start time, end time, duration, and type
- Public IP changes
- Routing table, ARP table, DNS configuration, interface state, ping, traceroute, and curl diagnostics during failures

Data is stored locally in SQLite. NetBlackBox also provides a local dashboard, JSON endpoints, rotating logs, HTML reports, and an exportable ZIP bundle for support cases.

## Status types

- `MODEM_LAN_KO` — the router is unreachable from the Mac
- `WAN_GATEWAY_KO` — the router is reachable, but the configured upstream gateway and Internet are not
- `INTERNET_KO_MODEM_OK` — the router and upstream gateway respond, but Internet probes fail
- `DNS_KO` — Internet works, but DNS resolution fails
- `OK_GATEWAY_ICMP_BLOCCATO` — connectivity works although the upstream gateway ignores ICMP
- `OK` — connectivity is healthy

## Requirements

- macOS
- Python 3
- No third-party Python packages

## Install

```bash
git clone https://github.com/asswerus/netblackbox.git
cd netblackbox
chmod +x install.sh uninstall.sh
./install.sh
```

The installer copies the application to `~/netblackbox`, creates a `launchd` agent, starts it immediately, and restarts it automatically if it exits.

## Local endpoints

- Dashboard: `http://127.0.0.1:8080/`
- Current state: `http://127.0.0.1:8080/status`
- Event data: `http://127.0.0.1:8080/api/events`

## Useful commands

```bash
# Follow the application log
tail -f ~/netblackbox/logs/netblackbox.log

# Inspect the launchd job
launchctl print gui/$(id -u)/io.github.asswerus.netblackbox

# Read current state
curl -s http://127.0.0.1:8080/status | python3 -m json.tool

# Generate a static report
python3 ~/netblackbox/netblackbox.py --report

# Print a 30-day JSON summary
python3 ~/netblackbox/netblackbox.py --summary

# Build a ZIP bundle for an ISP support case
python3 ~/netblackbox/netblackbox.py --export
```

## Configuration

The active configuration is stored at:

```text
~/netblackbox/config.json
```

The included `config.example.json` contains the defaults used during installation. The `fastweb_gateway_ip` field currently reflects the original test environment; users of other ISPs should replace it with their upstream gateway address when known.

After changing the configuration, restart the service:

```bash
launchctl kickstart -k gui/$(id -u)/io.github.asswerus.netblackbox
```

## Uninstall the service

```bash
./uninstall.sh
```

This removes the `launchd` agent but preserves collected data under `~/netblackbox`.

## Privacy

NetBlackBox runs locally. The dashboard binds to `127.0.0.1` by default. Diagnostic exports may contain local addressing, routing information, public IP history, and other network metadata; inspect archives before sharing them.

## License

MIT
