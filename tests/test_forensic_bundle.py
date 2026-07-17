from __future__ import annotations

import json
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from netblackbox.forensic_bundle import create_forensic_bundle


def create_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
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
                8.0, 'PARTIAL_CONNECTIVITY', 'WARNING', '{}'
            );
            INSERT INTO event_samples(
                event_id, timestamp, phase, state, gateway_ip, probes_json
            ) VALUES(
                7, '2026-07-16T12:00:01+00:00', 'active',
                'PARTIAL_CONNECTIVITY', '192.168.1.1', '{}'
            );
            """
        )


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
            "database.sqlite3",
            "metadata.json",
            "summary.json",
            "incidents.json",
            "report.html",
            "playback/7.json",
            "logs/netblackbox.log",
        } <= names

        metadata = json.loads(archive.read("metadata.json"))
        assert metadata["bundle_version"] == 1
        assert metadata["platform"] == "test-platform"

        summary = json.loads(archive.read("summary.json"))
        assert summary["event_count"] == 1
        assert summary["longest_duration_seconds"] == 8.0

        playback = json.loads(archive.read("playback/7.json"))
        assert playback["event"]["id"] == 7
        assert len(playback["samples"]) == 1

        extracted = tmp_path / "snapshot.sqlite3"
        extracted.write_bytes(archive.read("database.sqlite3"))
        with sqlite3.connect(extracted) as connection:
            assert connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1


def test_bundle_requires_an_existing_database(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        create_forensic_bundle(tmp_path)


def test_bundle_rejects_invalid_window(tmp_path: Path) -> None:
    create_database(tmp_path / "netblackbox.sqlite3")
    with pytest.raises(ValueError, match="days must be at least 1"):
        create_forensic_bundle(tmp_path, days=0)
