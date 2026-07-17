from pathlib import Path

from nbb.app import NetBlackBoxApp
from nbb.config import Config
from nbb.models import ProbeResult, Sample
from nbb.platforms import DiagnosticCommand, PlatformBackend


class FakeBackend(PlatformBackend):
    name = "fake"

    def ping_command(self, host: str) -> list[str]:
        return ["ping", host]

    def default_gateway(self) -> str | None:
        return "192.0.2.1"

    def diagnostics(self, modem_ip: str, gateway_ip: str) -> list[DiagnosticCommand]:
        return []


def probe_result() -> ProbeResult:
    return ProbeResult(
        modem_ping=True,
        modem_http=True,
        modem_https=True,
        gateway_ping=False,
        cloudflare_tcp=False,
        google_dns_tcp=False,
        http_internet=False,
        dns_resolution=False,
    )


def test_sample_context_is_persisted_and_returned_in_playback(tmp_path: Path) -> None:
    app = NetBlackBoxApp(Config(data_dir=str(tmp_path)), FakeBackend())
    sample = Sample(
        timestamp="2026-07-13T23:59:00+02:00",
        state="OK",
        gateway_ip="192.0.2.1",
        probes={"gateway_ping": False},
        observed_state="WAN_GATEWAY_KO",
        severity="MAJOR",
        sampling_mode="fast",
        sampling_interval_seconds=0.5,
    )

    event_id = app.open_event("WAN_GATEWAY_KO", probe_result())
    app.save_event_sample(event_id, "active", sample)

    persisted = app.event_playback(event_id)["samples"][-1]

    assert persisted["state"] == "OK"
    assert persisted["raw_state"] == "WAN_GATEWAY_KO"
    assert persisted["severity"] == "MAJOR"
    assert persisted["sampling_mode"] == "fast"
    assert persisted["sampling_interval_seconds"] == 0.5
