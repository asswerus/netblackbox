from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from datetime import datetime, timedelta

from .models import Sample


class SampleBuffer:
    """Bounded in-memory history of recent forensic samples."""

    def __init__(self, window_seconds: float, minimum_interval_seconds: float) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than zero")
        if minimum_interval_seconds <= 0:
            raise ValueError("minimum_interval_seconds must be greater than zero")

        self.window_seconds = float(window_seconds)
        capacity = max(10, int(self.window_seconds / minimum_interval_seconds) + 1)
        self._samples: deque[Sample] = deque(maxlen=capacity)

    def push(self, sample: Sample) -> None:
        self._samples.append(sample)
        self._discard_expired(sample.timestamp)

    def snapshot(self) -> tuple[Sample, ...]:
        return tuple(self._samples)

    def last(self, seconds: float) -> tuple[Sample, ...]:
        if seconds <= 0 or not self._samples:
            return ()

        latest = self._parse_timestamp(self._samples[-1].timestamp)
        cutoff = latest - timedelta(seconds=seconds)
        return tuple(
            sample for sample in self._samples if self._parse_timestamp(sample.timestamp) >= cutoff
        )

    def clear(self) -> None:
        self._samples.clear()

    def extend(self, samples: Iterable[Sample]) -> None:
        for sample in samples:
            self.push(sample)

    def __len__(self) -> int:
        return len(self._samples)

    def _discard_expired(self, latest_timestamp: str) -> None:
        cutoff = self._parse_timestamp(latest_timestamp) - timedelta(seconds=self.window_seconds)
        while self._samples and self._parse_timestamp(self._samples[0].timestamp) < cutoff:
            self._samples.popleft()

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        return datetime.fromisoformat(value)
