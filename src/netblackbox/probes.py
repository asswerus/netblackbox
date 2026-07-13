from __future__ import annotations

import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

from .config import Config
from .models import ProbeResult
from .platforms import PlatformBackend


class ProbeRunner:
    def __init__(self, config: Config, backend: PlatformBackend):
        self.config = config
        self.backend = backend

    def ping(self, host: str) -> bool:
        try:
            return subprocess.run(
                self.backend.ping_command(host),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                check=False,
            ).returncode == 0
        except Exception:
            return False

    def tcp(self, host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=self.config.socket_timeout_seconds):
                return True
        except OSError:
            return False

    @staticmethod
    def dns() -> bool:
        try:
            socket.getaddrinfo("example.com", 443, type=socket.SOCK_STREAM)
            return True
        except socket.gaierror:
            return False

    def http(self) -> bool:
        try:
            request = Request(
                "https://www.google.com/generate_204",
                headers={"User-Agent": "NetBlackBox/0.2.0", "Cache-Control": "no-cache"},
            )
            with urlopen(request, timeout=self.config.http_timeout_seconds) as response:
                return 200 <= response.status < 400
        except Exception:
            return False

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
            values = {name: future.result() for name, future in futures.items()}
        return ProbeResult(**values)


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
