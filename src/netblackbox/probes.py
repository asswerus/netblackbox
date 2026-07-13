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


class ProbeRunner:
    def __init__(self, config: Config, backend: PlatformBackend):
        self.config = config
        self.backend = backend

    def ping(self, host: str) -> tuple[bool, float | None]:
        try:
            result = subprocess.run(
                self.backend.ping_command(host),
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            output = f"{result.stdout}\n{result.stderr}"
            match = re.search(r"time[=<]\s*([0-9]+(?:\.[0-9]+)?)\s*ms", output, re.IGNORECASE)
            latency = float(match.group(1)) if match else None
            return result.returncode == 0, latency
        except Exception:
            return False, None

    def tcp(self, host: str, port: int) -> tuple[bool, float | None]:
        started = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=self.config.socket_timeout_seconds):
                return True, round((time.perf_counter() - started) * 1000, 2)
        except OSError:
            return False, None

    @staticmethod
    def dns() -> tuple[bool, float | None]:
        started = time.perf_counter()
        try:
            socket.getaddrinfo("example.com", 443, type=socket.SOCK_STREAM)
            return True, round((time.perf_counter() - started) * 1000, 2)
        except socket.gaierror:
            return False, None

    def http(self) -> tuple[bool, float | None]:
        started = time.perf_counter()
        try:
            request = Request(
                "https://www.google.com/generate_204",
                headers={"User-Agent": "NetBlackBox/0.2.0", "Cache-Control": "no-cache"},
            )
            with urlopen(request, timeout=self.config.http_timeout_seconds) as response:
                ok = 200 <= response.status < 400
                return ok, round((time.perf_counter() - started) * 1000, 2) if ok else None
        except Exception:
            return False, None

    def run(self, gateway_ip: str) -> ProbeResult:
        modem = self.config.modem_ip
        checks = {
            "modem_ping": lambda: self.ping(modem),
            "modem_http": lambda: self.tcp(modem, 80),
            "modem_https": lambda: self.tcp(modem, 443),
            "gateway_ping": lambda: self.ping(gateway_ip),
            "cloudflare_tcp": lambda: self.tcp("1.1.1.1", 443),
            "google_dns_tcp": lambda: self.tcp("8.8.8.8", 53),
            "http_internet": self.http,
            "dns_resolution": self.dns,
        }
        with ThreadPoolExecutor(max_workers=len(checks)) as pool:
            futures = {name: pool.submit(function) for name, function in checks.items()}
            measurements = {name: future.result() for name, future in futures.items()}

        return ProbeResult(
            modem_ping=measurements["modem_ping"][0],
            modem_http=measurements["modem_http"][0],
            modem_https=measurements["modem_https"][0],
            gateway_ping=measurements["gateway_ping"][0],
            cloudflare_tcp=measurements["cloudflare_tcp"][0],
            google_dns_tcp=measurements["google_dns_tcp"][0],
            http_internet=measurements["http_internet"][0],
            dns_resolution=measurements["dns_resolution"][0],
            modem_ping_ms=measurements["modem_ping"][1],
            modem_http_ms=measurements["modem_http"][1],
            modem_https_ms=measurements["modem_https"][1],
            gateway_ping_ms=measurements["gateway_ping"][1],
            cloudflare_tcp_ms=measurements["cloudflare_tcp"][1],
            google_dns_tcp_ms=measurements["google_dns_tcp"][1],
            http_internet_ms=measurements["http_internet"][1],
            dns_resolution_ms=measurements["dns_resolution"][1],
        )


def classify(probes: ProbeResult) -> str:
    if not probes.modem_reachable:
        return "MODEM_LAN_KO"
    if not probes.internet_reachable and not probes.gateway_ping:
        return "WAN_GATEWAY_KO"
    if not probes.internet_reachable:
        return "INTERNET_KO_MODEM_OK"
    if not probes.dns_resolution:
        return "DNS_KO"
    if not probes.gateway_ping:
        return "OK_GATEWAY_ICMP_BLOCKED"
    return "OK"
