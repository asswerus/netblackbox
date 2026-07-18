from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from netblackbox.bundle_analysis import analyze_bundle, read_bundle_analysis


def write_bundle(path: Path) -> None:
    metadata = {
        "bundle_version": 1,
        "generated_at": "2026-07-17T10:30:00.000+00:00",
        "platform": "test-platform",
        "hostname": "test-host",
    }
    summary = {
        "event_count": 3,
        "total_duration_seconds": 18.5,
        "longest_duration_seconds": 8.0,
        "by_severity": {"WARNING": 2, "INFO": 1},
        "by_state": {"OFFLINE": 1, "PARTIAL_CONNECTIVITY": 2},
    }
    incidents = {"incident_count": 2, "incidents": []}
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("metadata.json", json.dumps(metadata))
        archive.writestr("summary.json", json.dumps(summary))
        archive.writestr("incidents.json", json.dumps(incidents))


def test_analyze_bundle_renders_stable_summary(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.zip"
    write_bundle(bundle)

    output = analyze_bundle(bundle)

    assert output.startswith("NetBlackBox Forensic Bundle\n")
    assert "Bundle version : 1" in output
    assert "Platform       : test-platform" in output
    assert "Hostname       : test-host" in output
    assert "Events         : 3" in output
    assert "Incidents      : 2" in output
    assert "Longest event  : 8.0 s" in output
    assert "WARNING  2" in output
    assert "PARTIAL_CONNECTIVITY  2" in output


def test_read_bundle_analysis_rejects_missing_payload(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("metadata.json", "{}")

    with pytest.raises(ValueError, match="missing required files"):
        read_bundle_analysis(bundle)


def test_read_bundle_analysis_rejects_invalid_zip(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.zip"
    bundle.write_text("not a zip", encoding="utf-8")

    with pytest.raises(ValueError, match="not a valid ZIP bundle"):
        read_bundle_analysis(bundle)


def test_read_bundle_analysis_rejects_non_object_json(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("metadata.json", "[]")
        archive.writestr("summary.json", "{}")
        archive.writestr("incidents.json", "{}")

    with pytest.raises(ValueError, match="JSON root must be an object"):
        read_bundle_analysis(bundle)
