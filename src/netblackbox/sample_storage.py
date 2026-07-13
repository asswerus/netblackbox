from __future__ import annotations

import json
import sqlite3
from typing import Any

from .models import Sample

SAMPLE_CONTEXT_COLUMNS: dict[str, str] = {
    "observed_state": "TEXT",
    "severity": "TEXT",
    "sampling_mode": "TEXT NOT NULL DEFAULT 'normal'",
    "sampling_interval_seconds": "REAL",
}


def ensure_sample_context_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> None:
    """Add forensic sample context columns to an existing SQLite table."""
    if table_name not in {"samples", "event_samples"}:
        raise ValueError(f"unsupported sample table: {table_name}")

    existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table_name})")}
    for column, definition in SAMPLE_CONTEXT_COLUMNS.items():
        if column not in existing:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column} {definition}")


def sample_context_values(sample: Sample) -> tuple[str | None, str | None, str, float | None]:
    return (
        sample.observed_state,
        sample.severity,
        sample.sampling_mode,
        sample.sampling_interval_seconds,
    )


def decode_sample_row(row: dict[str, Any]) -> dict[str, Any]:
    """Decode a persisted sample while remaining compatible with old rows."""
    decoded = dict(row)
    probes_json = decoded.pop("probes_json", "{}")
    decoded["probes"] = json.loads(probes_json)
    decoded.setdefault("observed_state", None)
    decoded.setdefault("severity", None)
    decoded.setdefault("sampling_mode", "normal")
    decoded.setdefault("sampling_interval_seconds", None)
    decoded["raw_state"] = decoded.get("observed_state") or decoded.get("state")
    return decoded
