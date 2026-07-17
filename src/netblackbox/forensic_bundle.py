from __future__ import annotations

import html
import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timedelta
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from .incident_summary import build_incident_summary

BUNDLE_VERSION = 1


def _timestamp(value: datetime | None = None) -> str:
    return (value or datetime.now().astimezone()).isoformat(timespec="milliseconds")


def _package_version() -> str:
    try:
        return version("netblackbox")
    except PackageNotFoundError:
        return "development"


def _snapshot_database(source: Path, destination: Path) -> None:
    source_uri = f"file:{source.resolve()}?mode=ro"
    with (
        sqlite3.connect(source_uri, uri=True, timeout=10) as source_connection,
        sqlite3.connect(destination, timeout=10) as destination_connection,
    ):
        source_connection.backup(destination_connection)


def _read_events(database_path: Path, cutoff: str) -> list[dict[str, Any]]:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM events WHERE start_time >= ? ORDER BY start_time",
                (cutoff,),
            )
        ]


def _write_playback(database_path: Path, events: list[dict[str, Any]], folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        for event in events:
            samples = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM event_samples WHERE event_id=? ORDER BY timestamp",
                    (event["id"],),
                )
            ]
            payload = {"event": event, "samples": samples}
            (folder / f"{event['id']}.json").write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )


def _event_summary(events: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    completed = [event for event in events if event.get("duration_seconds") is not None]
    by_state: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for event in events:
        state = str(event["state"])
        severity = str(event.get("severity") or "UNKNOWN")
        by_state[state] = by_state.get(state, 0) + 1
        by_severity[severity] = by_severity.get(severity, 0) + 1
    return {
        "generated_at": generated_at,
        "event_count": len(events),
        "total_duration_seconds": round(
            sum(float(event["duration_seconds"]) for event in completed), 3
        ),
        "longest_duration_seconds": max(
            (float(event["duration_seconds"]) for event in completed), default=0
        ),
        "by_state": by_state,
        "by_severity": by_severity,
        "events": events,
    }


def _render_report(summary: dict[str, Any], incidents: dict[str, Any]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(event.get('start_time', '')))}</td>"
        f"<td>{html.escape(str(event.get('state', '')))}</td>"
        f"<td>{html.escape(str(event.get('severity', '')))}</td>"
        f"<td>{html.escape(str(event.get('duration_seconds', '')))}</td>"
        "</tr>"
        for event in summary["events"]
    )
    incident_count = incidents.get("incident_count", len(incidents.get("incidents", [])))
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>NetBlackBox forensic bundle</title>
<style>body{{font-family:system-ui;margin:2rem;max-width:1100px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccc;padding:.45rem;text-align:left}}code{{background:#eee;padding:.1rem .25rem}}</style></head>
<body><h1>NetBlackBox forensic bundle</h1>
<p>Generated: <code>{html.escape(str(summary['generated_at']))}</code></p>
<p>Events: <strong>{summary['event_count']}</strong> · Incidents: <strong>{incident_count}</strong> · Longest event: <strong>{summary['longest_duration_seconds']} s</strong></p>
<table><thead><tr><th>Start</th><th>State</th><th>Severity</th><th>Duration (s)</th></tr></thead><tbody>{rows}</tbody></table>
</body></html>"""


def create_forensic_bundle(
    base_dir: Path,
    *,
    output_path: Path | None = None,
    days: int = 30,
    now: datetime | None = None,
    platform: str = "unknown",
) -> Path:
    """Create a versioned ZIP containing data needed for offline incident analysis."""
    if days < 1:
        raise ValueError("days must be at least 1")

    generated = now or datetime.now().astimezone()
    generated_at = _timestamp(generated)
    database_path = base_dir / "netblackbox.sqlite3"
    if not database_path.is_file():
        raise FileNotFoundError(f"database not found: {database_path}")

    exports_dir = base_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    destination = output_path or exports_dir / f"netblackbox-{generated.strftime('%Y%m%d-%H%M%S')}.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="netblackbox-bundle-") as temporary:
        root = Path(temporary)
        snapshot = root / "database.sqlite3"
        _snapshot_database(database_path, snapshot)

        cutoff = _timestamp(generated - timedelta(days=days))
        events = _read_events(snapshot, cutoff)
        summary = _event_summary(events, generated_at)
        incidents = build_incident_summary(events, generated_at=generated_at, platform=platform)
        metadata = {
            "bundle_version": BUNDLE_VERSION,
            "netblackbox_version": _package_version(),
            "generated_at": generated_at,
            "platform": platform,
            "window_days": days,
            "database_filename": database_path.name,
        }

        (root / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (root / "incidents.json").write_text(json.dumps(incidents, indent=2), encoding="utf-8")
        (root / "report.html").write_text(_render_report(summary, incidents), encoding="utf-8")
        _write_playback(snapshot, events, root / "playback")

        for name in ("logs", "diagnostics"):
            source = base_dir / name
            if source.is_dir():
                shutil.copytree(source, root / name)

        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root))

    return destination
