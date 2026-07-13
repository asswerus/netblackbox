from datetime import datetime, timedelta, timezone

import pytest

from netblackbox.buffer import SampleBuffer
from netblackbox.models import Sample


def sample_at(offset_seconds: float) -> Sample:
    timestamp = datetime(2026, 7, 13, tzinfo=timezone.utc) + timedelta(seconds=offset_seconds)
    return Sample(
        timestamp=timestamp.isoformat(timespec="milliseconds"),
        state="OK",
        gateway_ip="192.0.2.1",
        probes={"offset": offset_seconds},
    )


def test_buffer_preserves_order_and_returns_snapshot() -> None:
    buffer = SampleBuffer(window_seconds=60, minimum_interval_seconds=1)
    buffer.extend([sample_at(0), sample_at(1), sample_at(2)])

    assert [item.probes["offset"] for item in buffer.snapshot()] == [0, 1, 2]
    assert len(buffer) == 3


def test_buffer_discards_samples_older_than_window() -> None:
    buffer = SampleBuffer(window_seconds=5, minimum_interval_seconds=1)
    buffer.extend([sample_at(0), sample_at(4), sample_at(6)])

    assert [item.probes["offset"] for item in buffer.snapshot()] == [4, 6]


def test_last_returns_requested_time_slice() -> None:
    buffer = SampleBuffer(window_seconds=60, minimum_interval_seconds=1)
    buffer.extend([sample_at(0), sample_at(10), sample_at(20)])

    assert [item.probes["offset"] for item in buffer.last(11)] == [10, 20]
    assert buffer.last(0) == ()


def test_clear_removes_all_samples() -> None:
    buffer = SampleBuffer(window_seconds=60, minimum_interval_seconds=1)
    buffer.push(sample_at(0))

    buffer.clear()

    assert buffer.snapshot() == ()
    assert len(buffer) == 0


@pytest.mark.parametrize("window,interval", [(0, 1), (-1, 1), (1, 0), (1, -1)])
def test_invalid_configuration_is_rejected(window: float, interval: float) -> None:
    with pytest.raises(ValueError):
        SampleBuffer(window_seconds=window, minimum_interval_seconds=interval)
