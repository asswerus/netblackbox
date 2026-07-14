from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

from netblackbox.server_app import IncidentApiApp


class Harness:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.backend = SimpleNamespace(name="test")

    @staticmethod
    def now() -> datetime:
        return datetime.fromisoformat("2026-07-14T16:30:00+02:00")

    @staticmethod
    def timestamp(value: datetime | None = None) -> str:
        return (value or Harness.now()).isoformat(timespec="milliseconds")

    @contextmanager
    def db(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()


def test_incident_summary_reads_events_and_coalesces_phases(tmp_path: Path) -> None:
    db_path = tmp_path / "events.sqlite3"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE events(
                id INTEGER PRIMARY KEY,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_seconds REAL,
                state TEXT NOT NULL,
                severity TEXT,
                probes_json TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO events(
                id,start_time,end_time,duration_seconds,state,severity,probes_json
            ) VALUES(?,?,?,?,?,?,?)
            """,
            [
                (
                    10,
                    "2026-07-14T15:12:24.286+02:00",
                    "2026-07-14T15:12:32.179+02:00",
                    7.893,
                    "MODEM_LAN_KO",
                    "MAJOR",
                    "{}",
                ),
                (
                    11,
                    "2026-07-14T15:12:32.182+02:00",
                    "2026-07-14T15:14:04.600+02:00",
                    92.419,
                    "PARTIAL_CONNECTIVITY",
                    "WARNING",
                    "{}",
                ),
            ],
        )

    harness = Harness(db_path)
    payload = IncidentApiApp.incident_summary(harness)  # type: ignore[arg-type]

    assert payload["platform"] == "test"
    assert payload["source_event_count"] == 2
    assert payload["incident_count"] == 1
    assert payload["incidents"][0]["event_ids"] == [10, 11]
    assert [phase["state"] for phase in payload["incidents"][0]["phases"]] == [
        "MODEM_LAN_KO",
        "PARTIAL_CONNECTIVITY",
    ]
