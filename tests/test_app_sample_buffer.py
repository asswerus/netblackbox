from pathlib import Path

from netblackbox.app import NetBlackBoxApp
from netblackbox.buffer import SampleBuffer
from netblackbox.config import Config
from netblackbox.platforms import DiagnosticCommand, PlatformBackend


class FakeBackend(PlatformBackend):
    name = "fake"

    def ping_command(self, host: str) -> list[str]:
        return ["ping", host]

    def default_gateway(self) -> str | None:
        return "192.0.2.1"

    def diagnostics(self, modem_ip: str, gateway_ip: str) -> list[DiagnosticCommand]:
        return []


def test_app_uses_configured_sample_buffer(tmp_path: Path) -> None:
    config = Config(
        data_dir=str(tmp_path),
        ring_buffer_seconds=45,
        turbo_interval_seconds=0.5,
    )

    app = NetBlackBoxApp(config, FakeBackend())

    assert isinstance(app.ring, SampleBuffer)
    assert app.ring.window_seconds == 45
    assert app.ring.snapshot() == ()
