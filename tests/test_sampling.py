import pytest
from netblackbox.sampling import AdaptiveSamplingPolicy


def policy() -> AdaptiveSamplingPolicy:
    return AdaptiveSamplingPolicy(
        normal_interval_seconds=2.0,
        fast_interval_seconds=0.5,
        turbo_interval_seconds=0.25,
        fast_duration_seconds=15,
        turbo_duration_seconds=60,
    )


def test_policy_starts_in_normal_mode() -> None:
    decision = policy().decision(now=100)

    assert decision.mode == "normal"
    assert decision.interval_seconds == 2.0


def test_unhealthy_observation_enables_fast_sampling() -> None:
    sampling = policy()

    sampling.observe(healthy=False, now=100)

    assert sampling.decision(now=110).mode == "fast"
    assert sampling.decision(now=116).mode == "normal"


def test_healthy_observation_does_not_accelerate_sampling() -> None:
    sampling = policy()

    sampling.observe(healthy=True, now=100)

    assert sampling.decision(now=100).mode == "normal"


def test_repeated_unhealthy_observations_extend_fast_window() -> None:
    sampling = policy()

    sampling.observe(healthy=False, now=100)
    sampling.observe(healthy=False, now=110)

    assert sampling.decision(now=120).mode == "fast"
    assert sampling.decision(now=126).mode == "normal"


def test_turbo_mode_overrides_fast_mode() -> None:
    sampling = policy()

    sampling.observe(healthy=False, now=100)
    sampling.activate_turbo(now=105)

    assert sampling.decision(now=110).mode == "turbo"
    assert sampling.decision(now=166).mode == "normal"


def test_reset_returns_policy_to_normal_mode() -> None:
    sampling = policy()
    sampling.observe(healthy=False, now=100)
    sampling.activate_turbo(now=100)

    sampling.reset()

    assert sampling.decision(now=100).mode == "normal"


@pytest.mark.parametrize(
    "normal,fast,turbo",
    [
        (0, 0.5, 0.25),
        (2, 0, 0.25),
        (2, 0.5, 0),
        (0.5, 1, 0.25),
        (2, 0.25, 0.5),
    ],
)
def test_invalid_intervals_are_rejected(
    normal: float,
    fast: float,
    turbo: float,
) -> None:
    with pytest.raises(ValueError):
        AdaptiveSamplingPolicy(
            normal_interval_seconds=normal,
            fast_interval_seconds=fast,
            turbo_interval_seconds=turbo,
            fast_duration_seconds=15,
            turbo_duration_seconds=60,
        )


@pytest.mark.parametrize("fast_duration,turbo_duration", [(0, 60), (15, 0)])
def test_invalid_durations_are_rejected(
    fast_duration: float,
    turbo_duration: float,
) -> None:
    with pytest.raises(ValueError):
        AdaptiveSamplingPolicy(
            normal_interval_seconds=2,
            fast_interval_seconds=0.5,
            turbo_interval_seconds=0.25,
            fast_duration_seconds=fast_duration,
            turbo_duration_seconds=turbo_duration,
        )
