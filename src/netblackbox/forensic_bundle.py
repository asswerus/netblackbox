from __future__ import annotations

import hashlib
import json
import platform as platform_module
import shutil
import socket
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timedelta
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from .forensic_report import render_forensic_report
from .incident_summary import build_incident_summary

BUNDLE_VERSION = 1
MANIFEST_VERSION = 1
EXCLUDED_ARCHIVE_NAMES = {
    ".directory",
    ".ds_store",
    "desktop.ini",
    "thumbs.db",
}
EXCLUDED_ARCHIVE_PARTS = {"__macosx"}


def should_archive(path: Path) -> bool:
    """Return whether a file belongs in a portable forensic archive."""
    if path.name.casefold() in EXCLUDED_ARCHIVE_NAMES:
        return False
    if path.name.endswith("~"):
        return False
    return not any(part.casefold() in EXCLUDED_ARCHIVE_PARTS for part in path.parts)


def _timestamp(value: datetime | None = None) -> str:
    return (value or datetime.now().astimezone()).isoformat(timespec="milliseconds")


def _package_version() -> str:
    try:
        return version("netblackbox")
    except PackageNotFoundError:
        return "development"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _database_schema_version(database_path: Path) -> int:
    with sqlite3.connect(database_path) as connection:
        return int(connection.execute("PRAGMA user_version").fetchone()[0])


def _utc_offset(value: datetime) -> str | None:
    offset = value.utcoffset()
    if offset is None:
        return None
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def _decode_probes(record: dict[str, Any]) -> dict[str, Any]:
    """Replace the persisted probes_json string with a structured probes value."""
    exported = dict(record)
    if "probes_json" not in exported:
        return exported

    encoded = exported.pop("probes_json")
    try:
        exported["probes"] = json.loads(encoded)
    except (json.JSONDecodeError, TypeError):
        exported["probes"] = None
        warnings = list(exported.get("warnings") or [])
        warnings.append("Unable to decode probes_json")
        exported["warnings"] = warnings
    return exported


def _build_metadata(
    *,
    snapshot: Path,
    generated: datetime,
    generated_at: str,
    platform: str,
    days: int,
) -> dict[str, Any]:
    return {
        "bundle_version": BUNDLE_VERSION,
        "netblackbox_version": _package_version(),
        "created_with": "nbb bundle",
        "generated_at": generated_at,
        "platform": platform,
        "window_days": days,
        "database_filename": snapshot.name,
        "hostname": socket.gethostname(),
        "timezone": {
            "name": generated.tzname(),
            "utc_offset": _utc_offset(generated),
        },
        "os": {
            "system": platform_module.system(),
            "release": platform_module.release(),
            "version": platform_module.version(),
            "machine": platform_module.machine(),
            "python": platform_module.python_version(),
        },
        "database": {
            "filename": snapshot.name,
            "size_bytes": snapshot.stat().st_size,
            "sha256": _sha256(snapshot),
            "schema_version": _database_schema_version(snapshot),
        },
        "bundle": {
            "format": "zip",
            "compression": "zip-deflated",
        },
    }


def _render_readme(
    metadata: dict[str, Any], summary: dict[str, Any], incidents: dict[str, Any]
) -> str:
    """Render a human-readable entry point for an extracted forensic bundle."""
    incident_count = incidents.get("incident_count", len(incidents.get("incidents", [])))
    return f"""NetBlackBox Forensic Bundle
===========================

This archive is a self-contained snapshot intended for offline incident analysis.
Start with report.html for a human-readable overview or incidents.json for structured analysis.

Bundle information
------------------

Generated:          {metadata['generated_at']}
Created with:       {metadata['created_with']}
NetBlackBox version:{metadata['netblackbox_version']}
Bundle version:     {metadata['bundle_version']}
Platform backend:   {metadata['platform']}
Window:             {metadata['window_days']} days
Events:             {summary['event_count']}
Incidents:          {incident_count}

Contents
--------

README.txt
    This guide and suggested entry points.

report.html
    Human-readable event overview. Open it in a web browser.

incidents.json
    Incident-oriented aggregation with ordered phases and source event IDs.

summary.json
    Raw event summary and aggregate counts.

metadata.json
    Bundle, host, operating-system, timezone, and database metadata.

manifest.json
    SHA-256 hashes and byte sizes for every other archived file.

{metadata['database']['filename']}
    Consistent SQLite snapshot captured through SQLite's backup API.

playback/
    One JSON file per event, including the event row and its samples.

diagnostics/
    Diagnostic artifacts collected by NetBlackBox, when available.

logs/
    NetBlackBox log files, when available.

Integrity
---------

manifest.json lists the expected SHA-256 digest and size of every file except itself.
The database digest is also repeated in metadata.json for convenient verification.

Privacy
-------

This bundle may contain hostnames, local or public IP addresses, routing information,
probe results, diagnostics, and log data. Inspect it before sharing it with others.
"""


def _build_manifest(root: Path, generated_at: str) -> dict[str, Any]:
    files: dict[str, dict[str, Any]] = {}
    total_size = 0

    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or not should_archive(relative) or relative == Path("manifest.json"):
            continue
        size = path.stat().st_size
        total_size += size
        files[relative.as_posix()] = {
            "size_bytes": size,
            "sha256": _sha256(path),
        }

    return {
        "manifest_version": MANIFEST_VERSION,
        "generated_at": generated_at,
        "hash_algorithm": "sha256",
        "manifest_includes_itself": False,
        "file_count": len(files),
        "total_size_bytes": total_size,
        "files": files,
    }


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
            _decode_probes(dict(row))
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
                _decode_probes(dict(row))
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
    destination = (
        output_path or exports_dir / f"netblackbox-{generated.strftime('%Y%m%d-%H%M%S')}.zip"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="netblackbox-bundle-") as temporary:
        root = Path(temporary)
        snapshot = root / "database.sqlite3"
        _snapshot_database(database_path, snapshot)

        cutoff = _timestamp(generated - timedelta(days=days))
        events = _read_events(snapshot, cutoff)
        summary = _event_summary(events, generated_at)
        incidents = build_incident_summary(events, generated_at=generated_at, platform=platform)
        metadata = _build_metadata(
            snapshot=snapshot,
            generated=generated,
            generated_at=generated_at,
            platform=platform,
            days=days,
        )

        (root / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (root / "incidents.json").write_text(json.dumps(incidents, indent=2), encoding="utf-8")
        (root / "report.html").write_text(
            render_forensic_report(summary, incidents, metadata), encoding="utf-8"
        )
        (root / "README.txt").write_text(
            _render_readme(metadata, summary, incidents), encoding="utf-8"
        )
        _write_playback(snapshot, events, root / "playback")

        for name in ("logs", "diagnostics"):
            source = base_dir / name
            if source.is_dir():
                shutil.copytree(source, root / name)

        manifest = _build_manifest(root, generated_at)
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file() and should_archive(path.relative_to(root)):
                    archive.write(path, path.relative_to(root))

    return destination
