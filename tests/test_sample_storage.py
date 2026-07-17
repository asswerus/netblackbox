import sqlite3

import pytest
from nbb.models import Sample
from nbb.sample_storage import (
    decode_sample_row,
    ensure_sample_context_columns,
    sample_context_values,
)


@pytest.mark.parametrize("table_name", ["samples", "event_samples"])
def test_context_columns_are_added_idempotently(table_name: str) -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        f"CREATE TABLE {table_name}(id INTEGER PRIMARY KEY, state TEXT, probes_json TEXT)"
    )

    ensure_sample_context_columns(connection, table_name)
    ensure_sample_context_columns(connection, table_name)

    columns = {row[1]: row[2] for row in connection.execute(f"PRAGMA table_info({table_name})")}
    assert columns["observed_state"] == "TEXT"
    assert columns["severity"] == "TEXT"
    assert columns["sampling_mode"] == "TEXT"
    assert columns["sampling_interval_seconds"] == "REAL"


def test_unknown_table_is_rejected() -> None:
    connection = sqlite3.connect(":memory:")

    with pytest.raises(ValueError, match="unsupported sample table"):
        ensure_sample_context_columns(connection, "events")


def test_sample_context_values_preserve_capture_metadata() -> None:
    sample = Sample(
        timestamp="2026-07-13T23:45:00+02:00",
        state="OK",
        gateway_ip="192.0.2.1",
        probes={"gateway_ping": False},
        observed_state="WAN_GATEWAY_KO",
        severity="MAJOR",
        sampling_mode="fast",
        sampling_interval_seconds=0.5,
    )

    assert sample_context_values(sample) == (
        "WAN_GATEWAY_KO",
        "MAJOR",
        "fast",
        0.5,
    )


def test_decode_sample_row_supports_new_and_legacy_rows() -> None:
    enriched = decode_sample_row(
        {
            "state": "OK",
            "observed_state": "DNS_KO",
            "severity": "WARNING",
            "sampling_mode": "fast",
            "sampling_interval_seconds": 0.5,
            "probes_json": '{"dns_resolution": false}',
        }
    )
    legacy = decode_sample_row(
        {
            "state": "OK",
            "probes_json": '{"dns_resolution": true}',
        }
    )

    assert enriched["raw_state"] == "DNS_KO"
    assert enriched["probes"] == {"dns_resolution": False}
    assert legacy["raw_state"] == "OK"
    assert legacy["sampling_mode"] == "normal"
    assert legacy["sampling_interval_seconds"] is None
