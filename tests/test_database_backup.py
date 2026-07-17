from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from nbb.database_backup import create_database_backup


def create_test_database(path: Path, value: str = "preserved") -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE evidence(value TEXT NOT NULL)")
        connection.execute("INSERT INTO evidence(value) VALUES(?)", (value,))


def test_missing_database_does_not_create_backup_directory(tmp_path: Path) -> None:
    database = tmp_path / "netblackbox.sqlite3"

    result = create_database_backup(database)

    assert result is None
    assert not (tmp_path / "backups").exists()


def test_backup_contains_a_consistent_copy(tmp_path: Path) -> None:
    database = tmp_path / "netblackbox.sqlite3"
    create_test_database(database)

    backup = create_database_backup(
        database,
        now=datetime(2026, 7, 17, 10, 30, tzinfo=timezone.utc),
    )

    assert backup == tmp_path / "backups" / "netblackbox-20260717-103000-000000.sqlite3"
    assert backup.is_file()
    with sqlite3.connect(backup) as connection:
        value = connection.execute("SELECT value FROM evidence").fetchone()[0]
    assert value == "preserved"


def test_retention_keeps_only_the_newest_backups(tmp_path: Path) -> None:
    database = tmp_path / "netblackbox.sqlite3"
    create_test_database(database)
    start = datetime(2026, 7, 17, 10, 30, tzinfo=timezone.utc)

    for offset in range(4):
        create_database_backup(database, retention=2, now=start + timedelta(seconds=offset))

    backups = sorted((tmp_path / "backups").glob("*.sqlite3"))
    assert [path.name for path in backups] == [
        "netblackbox-20260717-103002-000000.sqlite3",
        "netblackbox-20260717-103003-000000.sqlite3",
    ]


def test_retention_must_be_positive(tmp_path: Path) -> None:
    database = tmp_path / "netblackbox.sqlite3"
    create_test_database(database)

    with pytest.raises(ValueError, match="at least 1"):
        create_database_backup(database, retention=0)
