from __future__ import annotations

from dataclasses import dataclass

from .config import Config


@dataclass(frozen=True, slots=True)
class SamplingDecision:
    mode: str
    interval_seconds: float


class AdaptiveSamplingPolicy:
    """Select normal, fast, or turbo sampling without owning the monitor loop."""

    def __init__(
        self,
        normal_interval_seconds: float,
        fast_interval_seconds: float,
        turbo_interval_seconds: float,
        fast_duration_seconds: float,
        turbo_duration_seconds: float,
    ) -> None:
        intervals = (
            normal_interval_seconds,
            fast_interval_seconds,
            turbo_interval_seconds,
        )
        if any(interval <= 0 for interval in intervals):
            raise ValueError("sampling intervals must be greater than zero")
        if not turbo_interval_seconds <= fast_interval_seconds <= normal_interval_seconds:
            raise ValueError("sampling intervals must satisfy turbo <= fast <= normal")
        if fast_duration_seconds <= 0 or turbo_duration_seconds <= 0:
            raise ValueError("sampling durations must be greater than zero")

        self.normal_interval_seconds = float(normal_interval_seconds)
        self.fast_interval_seconds = float(fast_interval_seconds)
        self.turbo_interval_seconds = float(turbo_interval_seconds)
        self.fast_duration_seconds = float(fast_duration_seconds)
        self.turbo_duration_seconds = float(turbo_duration_seconds)
        self._fast_until = 0.0
        self._turbo_until = 0.0

    def observe(self, healthy: bool, now: float) -> None:
        """Accelerate immediately when a suspicious sample appears."""
        if not healthy:
            self._fast_until = max(self._fast_until, now + self.fast_duration_seconds)

    def activate_turbo(self, now: float) -> None:
        """Use the fastest cadence after a fault has been confirmed."""
        self._turbo_until = max(
            self._turbo_until,
            now + self.turbo_duration_seconds,
        )

    def decision(self, now: float) -> SamplingDecision:
        if now <= self._turbo_until:
            return SamplingDecision("turbo", self.turbo_interval_seconds)
        if now <= self._fast_until:
            return SamplingDecision("fast", self.fast_interval_seconds)
        return SamplingDecision("normal", self.normal_interval_seconds)

    def reset(self) -> None:
        self._fast_until = 0.0
        self._turbo_until = 0.0


def policy_from_config(config: Config) -> AdaptiveSamplingPolicy:
    """Create the runtime policy from the public NetBlackBox configuration."""
    return AdaptiveSamplingPolicy(
        normal_interval_seconds=config.check_interval_seconds,
        fast_interval_seconds=config.fast_interval_seconds,
        turbo_interval_seconds=config.turbo_interval_seconds,
        fast_duration_seconds=config.fast_duration_seconds,
        turbo_duration_seconds=config.turbo_duration_seconds,
    )
