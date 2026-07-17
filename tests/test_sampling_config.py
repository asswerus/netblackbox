from pathlib import Path

from nbb.config import Config
from nbb.sampling import policy_from_config


def test_policy_uses_runtime_configuration(tmp_path: Path) -> None:
    config = Config(
        data_dir=str(tmp_path),
        check_interval_seconds=3.0,
        fast_interval_seconds=0.75,
        turbo_interval_seconds=0.2,
        fast_duration_seconds=12.0,
        turbo_duration_seconds=45,
    )

    policy = policy_from_config(config)

    assert policy.normal_interval_seconds == 3.0
    assert policy.fast_interval_seconds == 0.75
    assert policy.turbo_interval_seconds == 0.2
    assert policy.fast_duration_seconds == 12.0
    assert policy.turbo_duration_seconds == 45.0
