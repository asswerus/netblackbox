from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_BACKUP_RETENTION = 10


def create_database_backup(
    database_path: Path,
    *,
    backup_dir: Path | None = None,
    retention: int = DEFAULT_BACKUP_RETENTION,
    now: datetime | None = None,
) -> Path | None:
    """Create a consistent timestamped SQLite backup and enforce retention.

    The SQLite backup API is used instead of copying the database file directly,
    so a database running in WAL mode is captured consistently.
    """
    if retention < 1:
        raise ValueError("retention must be at least 1")
    if not database_path.is_file():
        return None

    destination_dir = backup_dir or database_path.parent / "backups"
    destination_dir.mkdir(parents=True, exist_ok=True)

    timestamp = (now or datetime.now().astimezone()).strftime("%Y%m%d-%H%M%S-%f")
    destination = destination_dir / f"{database_path.stem}-{timestamp}{database_path.suffix}"

    source_uri = f"file:{database_path.resolve()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True, timeout=10) as source:
        with sqlite3.connect(destination, timeout=10) as target:
            source.backup(target)

    backups = sorted(
        destination_dir.glob(f"{database_path.stem}-*{database_path.suffix}"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for expired in backups[retention:]:
        expired.unlink(missing_ok=True)

    return destination
