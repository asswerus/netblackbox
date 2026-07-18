from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any


REQUIRED_ANALYSIS_FILES = {"metadata.json", "summary.json", "incidents.json"}


def _read_json(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        payload = json.loads(archive.read(name))
    except KeyError as error:
        raise ValueError(f"bundle is missing required file: {name}") from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError(f"bundle contains invalid JSON: {name}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"bundle JSON root must be an object: {name}")
    return payload


def read_bundle_analysis(bundle_path: Path) -> dict[str, Any]:
    """Read stable analysis payloads from a forensic bundle without extracting it."""
    if not bundle_path.is_file():
        raise FileNotFoundError(f"bundle not found: {bundle_path}")

    try:
        with zipfile.ZipFile(bundle_path) as archive:
            missing = REQUIRED_ANALYSIS_FILES - set(archive.namelist())
            if missing:
                names = ", ".join(sorted(missing))
                raise ValueError(f"bundle is missing required files: {names}")
            return {
                "metadata": _read_json(archive, "metadata.json"),
                "summary": _read_json(archive, "summary.json"),
                "incidents": _read_json(archive, "incidents.json"),
            }
    except zipfile.BadZipFile as error:
        raise ValueError(f"not a valid ZIP bundle: {bundle_path}") from error


def _render_counts(title: str, counts: dict[str, Any]) -> list[str]:
    lines = [title, "-" * len(title)]
    if not counts:
        return [*lines, "None"]
    width = max(len(str(name)) for name in counts)
    lines.extend(f"{name:<{width}}  {count}" for name, count in sorted(counts.items()))
    return lines


def render_bundle_analysis(analysis: dict[str, Any]) -> str:
    """Render a deterministic, terminal-friendly forensic bundle summary."""
    metadata = analysis["metadata"]
    summary = analysis["summary"]
    incidents = analysis["incidents"]
    incident_count = incidents.get("incident_count", len(incidents.get("incidents", [])))

    lines = [
        "NetBlackBox Forensic Bundle",
        "===========================",
        "",
        f"Bundle version : {metadata.get('bundle_version', 'unknown')}",
        f"Generated      : {metadata.get('generated_at', 'unknown')}",
        f"Platform       : {metadata.get('platform', 'unknown')}",
        f"Hostname       : {metadata.get('hostname', 'unknown')}",
        "",
        "Summary",
        "-------",
        f"Events         : {summary.get('event_count', 0)}",
        f"Incidents      : {incident_count}",
        f"Total duration : {summary.get('total_duration_seconds', 0)} s",
        f"Longest event  : {summary.get('longest_duration_seconds', 0)} s",
        "",
        *_render_counts("Severity", summary.get("by_severity", {})),
        "",
        *_render_counts("States", summary.get("by_state", {})),
    ]
    return "\n".join(lines)


def analyze_bundle(bundle_path: Path) -> str:
    """Read and render an offline forensic bundle."""
    return render_bundle_analysis(read_bundle_analysis(bundle_path))
