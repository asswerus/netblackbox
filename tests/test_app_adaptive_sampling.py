from pathlib import Path

from nbb.app import NetBlackBoxApp
from nbb.config import Config
from nbb.platforms import DiagnosticCommand, PlatformBackend


class FakeBackend(PlatformBackend):
    name = "fake"

    def ping_command(self, host: str) -> list[str]:
        return ["ping", host]

    def default_gateway(self) -> str | None:
        return "192.0.2.1"

    def diagnostics(self, modem_ip: str, gateway_ip: str) -> list[DiagnosticCommand]:
        return []


def test_app_builds_adaptive_sampling_policy_from_config(tmp_path: Path) -> None:
    config = Config(
        data_dir=str(tmp_path),
        check_interval_seconds=3.0,
        fast_interval_seconds=0.75,
        turbo_interval_seconds=0.2,
        fast_duration_seconds=12.0,
        turbo_duration_seconds=45,
    )

    app = NetBlackBoxApp(config, FakeBackend())

    assert app.sampling.normal_interval_seconds == 3.0
    assert app.sampling.fast_interval_seconds == 0.75
    assert app.sampling.turbo_interval_seconds == 0.2
    assert app.sampling.fast_duration_seconds == 12.0
    assert app.sampling.turbo_duration_seconds == 45.0
