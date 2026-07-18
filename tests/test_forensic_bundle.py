from __future__ import annotations

import hashlib
import json
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from netblackbox.forensic_bundle import create_forensic_bundle


def create_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            PRAGMA user_version = 3;
            CREATE TABLE events(
                id INTEGER PRIMARY KEY,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_seconds REAL,
                state TEXT NOT NULL,
                severity TEXT,
                probes_json TEXT NOT NULL,
                diagnostics_path TEXT,
                diagnostics_started_at TEXT,
                diagnostics_finished_at TEXT
            );
            CREATE TABLE event_samples(
                id INTEGER PRIMARY KEY,
                event_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                phase TEXT NOT NULL,
                state TEXT NOT NULL,
                gateway_ip TEXT NOT NULL,
                probes_json TEXT NOT NULL
            );
            INSERT INTO events(
                id, start_time, end_time, duration_seconds, state, severity, probes_json
            ) VALUES(
                7, '2026-07-16T12:00:00+00:00', '2026-07-16T12:00:08+00:00',
                8.0, 'PARTIAL_CONNECTIVITY', 'WARNING',
                '{"dns":{"ok":true,"latency_ms":12.5}}'
            );
            INSERT INTO event_samples(
                event_id, timestamp, phase, state, gateway_ip, probes_json
            ) VALUES(
                7, '2026-07-16T12:00:01+00:00', 'active',
                'PARTIAL_CONNECTIVITY', '192.168.1.1',
                '{"gateway":{"reachable":true}}'
            );
            """)


def test_bundle_contains_stable_analysis_files(tmp_path: Path) -> None:
    create_database(tmp_path / "netblackbox.sqlite3")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "netblackbox.log").write_text("monitor started\n", encoding="utf-8")

    destination = create_forensic_bundle(
        tmp_path,
        now=datetime(2026, 7, 17, 10, 30, tzinfo=timezone.utc),
        platform="test-platform",
    )

    with zipfile.ZipFile(destination) as archive:
        names = set(archive.namelist())
        assert {
            "README.txt",
            "database.sqlite3",
            "metadata.json",
            "manifest.json",
            "summary.json",
            "incidents.json",
            "report.html",
            "playback/7.json",
            "logs/netblackbox.log",
        } <= names

        database_bytes = archive.read("database.sqlite3")
        metadata = json.loads(archive.read("metadata.json"))
        assert metadata["bundle_version"] == 1
        assert metadata["platform"] == "test-platform"
        assert metadata["created_with"] == "nbb bundle"
        assert metadata["hostname"]
        assert metadata["timezone"] == {"name": "UTC", "utc_offset": "+00:00"}
        assert metadata["bundle"] == {
            "format": "zip",
            "compression": "zip-deflated",
        }
        assert metadata["os"]["system"]
        assert metadata["os"]["python"]
        assert metadata["database"] == {
            "filename": "database.sqlite3",
            "size_bytes": len(database_bytes),
            "sha256": hashlib.sha256(database_bytes).hexdigest(),
            "schema_version": 3,
        }

        readme = archive.read("README.txt").decode("utf-8")
        assert readme.splitlines()[0] == "NetBlackBox Forensic Bundle"
        assert "Generated:          2026-07-17T10:30:00.000+00:00" in readme
        assert "Platform backend:   test-platform" in readme
        assert "Window:             30 days" in readme
        assert "Events:             1" in readme
        assert "Incidents:          1" in readme
        assert "Start with report.html" in readme
        assert "Inspect it before sharing it with others." in readme

        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["manifest_version"] == 1
        assert manifest["generated_at"] == "2026-07-17T10:30:00.000+00:00"
        assert manifest["hash_algorithm"] == "sha256"
        assert manifest["manifest_includes_itself"] is False
        assert set(manifest["files"]) == names - {"manifest.json"}
        assert manifest["file_count"] == len(names) - 1
        assert manifest["total_size_bytes"] == sum(
            entry["size_bytes"] for entry in manifest["files"].values()
        )
        for name, entry in manifest["files"].items():
            content = archive.read(name)
            assert entry == {
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }

        summary = json.loads(archive.read("summary.json"))
        assert summary["event_count"] == 1
        assert summary["longest_duration_seconds"] == 8.0
        assert summary["events"][0]["probes"] == {
            "dns": {"ok": True, "latency_ms": 12.5}
        }
        assert "probes_json" not in summary["events"][0]

        playback = json.loads(archive.read("playback/7.json"))
        assert playback["event"]["id"] == 7
        assert playback["event"]["probes"] == {
            "dns": {"ok": True, "latency_ms": 12.5}
        }
        assert len(playback["samples"]) == 1
        assert playback["samples"][0]["probes"] == {
            "gateway": {"reachable": True}
        }
        assert "probes_json" not in playback["samples"][0]

        extracted = tmp_path / "snapshot.sqlite3"
        extracted.write_bytes(database_bytes)
        with sqlite3.connect(extracted) as connection:
            assert connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1


def test_bundle_marks_malformed_probe_payloads_without_failing(tmp_path: Path) -> None:
    database = tmp_path / "netblackbox.sqlite3"
    create_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE events SET probes_json='not-json' WHERE id=7")

    destination = create_forensic_bundle(tmp_path)

    with zipfile.ZipFile(destination) as archive:
        event = json.loads(archive.read("summary.json"))["events"][0]

    assert event["probes"] is None
    assert event["warnings"] == ["Unable to decode probes_json"]
    assert "probes_json" not in event


def test_bundle_excludes_os_metadata_and_temporary_files(tmp_path: Path) -> None:
    create_database(tmp_path / "netblackbox.sqlite3")
    diagnostics = tmp_path / "diagnostics"
    diagnostics.mkdir()
    (diagnostics / "snapshot.json").write_text("{}", encoding="utf-8")
    for name in (".DS_Store", "Thumbs.db", "desktop.ini", ".directory", "notes.txt~"):
        (diagnostics / name).write_text("noise", encoding="utf-8")
    macosx = diagnostics / "__MACOSX"
    macosx.mkdir()
    (macosx / "snapshot.json").write_text("noise", encoding="utf-8")

    destination = create_forensic_bundle(tmp_path)

    with zipfile.ZipFile(destination) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))

    assert "diagnostics/snapshot.json" in names
    assert "diagnostics/snapshot.json" in manifest["files"]
    assert not any(
        name.casefold().endswith((".ds_store", "thumbs.db", "desktop.ini", ".directory"))
        or "__macosx" in name.casefold()
        or name.endswith("~")
        for name in names | set(manifest["files"])
    )


def test_bundle_requires_an_existing_database(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        create_forensic_bundle(tmp_path)


def test_bundle_rejects_invalid_window(tmp_path: Path) -> None:
    create_database(tmp_path / "netblackbox.sqlite3")
    with pytest.raises(ValueError, match="days must be at least 1"):
        create_forensic_bundle(tmp_path, days=0)
