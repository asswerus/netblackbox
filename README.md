# NetBlackBox

> Because “everything looks fine from here” is not a diagnosis.

NetBlackBox is a dependency-free, cross-platform network outage recorder and forensic diagnostic toolkit for macOS, Linux, and Windows. It captures intermittent failures that disappear before an ISP support agent can inspect them, preserving what happened before, during, and after each incident.

## What it records

- Router reachability over ICMP, HTTP, and HTTPS
- Upstream gateway reachability
- Internet reachability over TCP and HTTP
- DNS resolution failures
- Probe latency and plugin-provided measurements
- Raw observed state and confirmed state
- Normal, fast, and turbo sampling context
- Outage start time, end time, duration, type, and severity
- Repeated platform-specific diagnostic snapshots during failures
- Pre-event, active-event, and post-event forensic samples

Data is stored locally in SQLite. NetBlackBox exposes local JSON endpoints and can render an interactive, self-contained HTML timeline from event playback data.

## Adaptive sampling

NetBlackBox normally monitors at a low-cost cadence. A suspicious sample switches it to fast mode before the incident is confirmed; a confirmed fault activates turbo sampling.

```text
normal -> suspicious sample -> fast -> confirmed incident -> turbo -> normal
```

This captures short transitions without continuously polling at maximum frequency.

## Status types

- `MODEM_LAN_KO` — the router is unreachable from the local machine
- `WAN_GATEWAY_KO` — the router is reachable, but the upstream gateway and Internet are not
- `INTERNET_KO_MODEM_OK` — the router and upstream gateway respond, but Internet probes fail
- `DNS_KO` — Internet connectivity works, but DNS resolution fails
- `OK_GATEWAY_ICMP_BLOCKED` — connectivity works although the upstream gateway ignores ICMP
- `OK` — connectivity is healthy

## Requirements

- macOS, Linux, or Windows
- Python 3.10 or newer
- No third-party runtime Python packages

## Development install

```bash
git clone https://github.com/asswerus/netblackbox.git
cd netblackbox
python3 -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
```

The repository includes Black, Ruff, mypy, pre-commit, and a GitHub Actions matrix covering macOS, Linux, and Windows.

## Configuration

Copy the example configuration and adjust addresses and intervals for your environment:

```bash
cp config.example.json config.json
```

Adaptive-sampling settings include:

```json
{
  "check_interval_seconds": 2.0,
  "fast_interval_seconds": 0.5,
  "turbo_interval_seconds": 0.25,
  "fast_duration_seconds": 10.0,
  "turbo_duration_seconds": 60
}
```

Existing configuration files remain compatible because new settings have defaults.

## Local endpoints

With the monitor running on the default bind address:

- Current state: `http://127.0.0.1:8080/status`
- Event summary: `http://127.0.0.1:8080/api/events`
- Event playback JSON: `http://127.0.0.1:8080/api/events/<id>`

The timeline renderer and route adapter are available in the codebase; direct server exposure of `/events/<id>/timeline` is the next integration step.

A playback sample can distinguish the displayed state from the raw observation that triggered faster sampling:

```json
{
  "state": "OK",
  "observed_state": "WAN_GATEWAY_KO",
  "raw_state": "WAN_GATEWAY_KO",
  "severity": "MAJOR",
  "sampling_mode": "fast",
  "sampling_interval_seconds": 0.5
}
```

## Plugin probes

External probes can be discovered through the Python entry-point group:

```text
netblackbox.probes
```

They are opt-in through `external_probe_plugins`. Plugin measurements are persisted in samples and playback, but do not silently alter the built-in incident classification.

## Storage and privacy

NetBlackBox runs locally and binds to `127.0.0.1` by default. SQLite data, logs, and diagnostic snapshots may contain local addressing, routing details, public IP information, and other network metadata. Inspect any exported material before sharing it.

## Project status

The current development line includes:

- cross-platform probe and diagnostic backends
- forensic sample buffering
- adaptive three-speed sampling
- SQLite event playback
- external probe discovery and measurement persistence
- interactive HTML event timeline rendering
- multiplaform CI, linting, formatting, and strict typing gates

The project is under active development; installation and service-management workflows are still being consolidated across operating systems.

## License

MIT
