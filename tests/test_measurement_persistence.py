from netblackbox.config import Config
from netblackbox.platforms import DiagnosticCommand, PlatformBackend
from netblackbox.plugins import FunctionProbePlugin, Measurement, ProbeRegistry
from netblackbox.probes import ProbeRunner


class FakeBackend(PlatformBackend):
    name = "fake"

    def ping_command(self, host: str) -> list[str]:
        return ["ping", host]

    def default_gateway(self) -> str | None:
        return "192.0.2.1"

    def diagnostics(self, modem_ip: str, gateway_ip: str) -> list[DiagnosticCommand]:
        return []


def test_external_measurement_is_embedded_in_probe_result() -> None:
    names = (
        "modem_ping",
        "modem_http",
        "modem_https",
        "gateway_ping",
        "cloudflare_tcp",
        "google_dns_tcp",
        "http_internet",
        "dns_resolution",
    )
    plugins = [
        FunctionProbePlugin(name, lambda _context: Measurement(True, 1.5))
        for name in names
    ]
    plugins.append(
        FunctionProbePlugin(
            "custom_jitter",
            lambda _context: Measurement(False, 42.25, "threshold exceeded"),
        )
    )

    runner = ProbeRunner(Config(), FakeBackend(), ProbeRegistry(plugins))
    result = runner.run("192.0.2.1")

    assert result.measurements["custom_jitter"] == {
        "ok": False,
        "latency_ms": 42.25,
        "detail": "threshold exceeded",
    }
    assert result.measurements["modem_ping"]["ok"] is True
