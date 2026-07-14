from __future__ import annotations

import re
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

from .config import Config
from .models import ProbeResult
from .platforms import PlatformBackend
from .plugins import (
    FunctionProbePlugin,
    Measurement,
    ProbeContext,
    ProbeRegistry,
    discover_probe_plugins,
)


class ProbeRunner:
    def __init__(
        self,
        config: Config,
        backend: PlatformBackend,
        registry: ProbeRegistry | None = None,
    ):
        self.config = config
        self.backend = backend
        self.registry = registry or self._default_registry()
        self._validate_required_plugins()
        self.last_measurements: dict[str, Measurement] = {}

    def ping(self, host: str) -> Measurement:
        try:
            result = subprocess.run(
                self.backend.ping_command(host),
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            output = f"{result.stdout}\n{result.stderr}"
            match = re.search(
                r"time[=<]\s*([0-9]+(?:\.[0-9]+)?)\s*ms", output, re.IGNORECASE
            )
            latency = float(match.group(1)) if match else None
            return Measurement(result.returncode == 0, latency)
        except Exception as exc:
            return Measurement(False, detail=f"{type(exc).__name__}: {exc}")

    def tcp(self, host: str, port: int) -> Measurement:
        started = time.perf_counter()
        try:
            with socket.create_connection(
                (host, port), timeout=self.config.socket_timeout_seconds
            ):
                return Measurement(True, round((time.perf_counter() - started) * 1000, 2))
        except OSError as exc:
            return Measurement(False, detail=f"{type(exc).__name__}: {exc}")

    @staticmethod
    def dns() -> Measurement:
        started = time.perf_counter()
        try:
            socket.getaddrinfo("example.com", 443, type=socket.SOCK_STREAM)
            return Measurement(True, round((time.perf_counter() - started) * 1000, 2))
        except socket.gaierror as exc:
            return Measurement(False, detail=f"{type(exc).__name__}: {exc}")

    def http(self) -> Measurement:
        started = time.perf_counter()
        try:
            request = Request(
                "https://www.google.com/generate_204",
                headers={"User-Agent": "NetBlackBox/0.3.0", "Cache-Control": "no-cache"},
            )
            with urlopen(request, timeout=self.config.http_timeout_seconds) as response:
                ok = 200 <= response.status < 400
                latency = round((time.perf_counter() - started) * 1000, 2) if ok else None
                return Measurement(ok, latency, detail=f"HTTP {response.status}")
        except Exception as exc:
            return Measurement(False, detail=f"{type(exc).__name__}: {exc}")

    def _built_in_plugins(self) -> tuple[FunctionProbePlugin, ...]:
        return (
            FunctionProbePlugin("modem_ping", lambda ctx: self.ping(ctx.modem_ip)),
            FunctionProbePlugin("modem_http", lambda ctx: self.tcp(ctx.modem_ip, 80)),
            FunctionProbePlugin("modem_https", lambda ctx: self.tcp(ctx.modem_ip, 443)),
            FunctionProbePlugin("gateway_ping", lambda ctx: self.ping(ctx.gateway_ip)),
            FunctionProbePlugin("cloudflare_tcp", lambda _ctx: self.tcp("1.1.1.1", 443)),
            FunctionProbePlugin("google_dns_tcp", lambda _ctx: self.tcp("8.8.8.8", 53)),
            FunctionProbePlugin("http_internet", lambda _ctx: self.http()),
            FunctionProbePlugin("dns_resolution", lambda _ctx: self.dns()),
        )

    def _default_registry(self) -> ProbeRegistry:
        registry = ProbeRegistry(self._built_in_plugins())
        for plugin in discover_probe_plugins(self.config.external_probe_plugins):
            registry.register(plugin)
        return registry

    def _validate_required_plugins(self) -> None:
        required = {
            "modem_ping",
            "modem_http",
            "modem_https",
            "gateway_ping",
            "cloudflare_tcp",
            "google_dns_tcp",
            "http_internet",
            "dns_resolution",
        }
        missing = required.difference(self.registry.names())
        if missing:
            raise ValueError(f"missing required probe plugins: {', '.join(sorted(missing))}")

    def run_measurements(self, gateway_ip: str) -> dict[str, Measurement]:
        context = ProbeContext(modem_ip=self.config.modem_ip, gateway_ip=gateway_ip)
        plugins = self.registry.plugins()
        with ThreadPoolExecutor(max_workers=len(plugins)) as pool:
            futures = {plugin.name: pool.submit(plugin.collect, context) for plugin in plugins}
            measurements = {name: future.result() for name, future in futures.items()}
        self.last_measurements = measurements
        return measurements

    @staticmethod
    def serialise_measurements(
        measurements: dict[str, Measurement],
    ) -> dict[str, dict[str, object]]:
        return {
            name: {
                "ok": measurement.ok,
                "latency_ms": measurement.latency_ms,
                "detail": measurement.detail,
            }
            for name, measurement in measurements.items()
        }

    def run(self, gateway_ip: str) -> ProbeResult:
        measurements = self.run_measurements(gateway_ip)
        return ProbeResult(
            modem_ping=measurements["modem_ping"].ok,
            modem_http=measurements["modem_http"].ok,
            modem_https=measurements["modem_https"].ok,
            gateway_ping=measurements["gateway_ping"].ok,
            cloudflare_tcp=measurements["cloudflare_tcp"].ok,
            google_dns_tcp=measurements["google_dns_tcp"].ok,
            http_internet=measurements["http_internet"].ok,
            dns_resolution=measurements["dns_resolution"].ok,
            modem_ping_ms=measurements["modem_ping"].latency_ms,
            modem_http_ms=measurements["modem_http"].latency_ms,
            modem_https_ms=measurements["modem_https"].latency_ms,
            gateway_ping_ms=measurements["gateway_ping"].latency_ms,
            cloudflare_tcp_ms=measurements["cloudflare_tcp"].latency_ms,
            google_dns_tcp_ms=measurements["google_dns_tcp"].latency_ms,
            http_internet_ms=measurements["http_internet"].latency_ms,
            dns_resolution_ms=measurements["dns_resolution"].latency_ms,
            measurements=self.serialise_measurements(measurements),
        )


def classify(probes: ProbeResult) -> str:
    internet_path_healthy = (
        probes.cloudflare_tcp and probes.google_dns_tcp and probes.http_internet
    )
    modem_path_healthy = probes.modem_ping and probes.modem_http and probes.modem_https

    if not probes.modem_reachable:
        if probes.internet_reachable:
            return "PARTIAL_CONNECTIVITY"
        return "MODEM_LAN_KO"
    if not probes.internet_reachable and not probes.gateway_ping:
        return "WAN_GATEWAY_KO"
    if not probes.internet_reachable:
        return "INTERNET_KO_MODEM_OK"
    if not probes.dns_resolution:
        return "DNS_KO"
    if not probes.gateway_ping:
        if modem_path_healthy and internet_path_healthy:
            return "OK_GATEWAY_ICMP_BLOCKED"
        return "PARTIAL_CONNECTIVITY"
    if not modem_path_healthy or not internet_path_healthy:
        return "PARTIAL_CONNECTIVITY"
    return "OK"
