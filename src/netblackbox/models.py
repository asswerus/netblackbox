from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ProbeResult:
    modem_ping: bool
    modem_http: bool
    modem_https: bool
    gateway_ping: bool
    cloudflare_tcp: bool
    google_dns_tcp: bool
    http_internet: bool
    dns_resolution: bool
    modem_ping_ms: float | None = None
    modem_http_ms: float | None = None
    modem_https_ms: float | None = None
    gateway_ping_ms: float | None = None
    cloudflare_tcp_ms: float | None = None
    google_dns_tcp_ms: float | None = None
    http_internet_ms: float | None = None
    dns_resolution_ms: float | None = None

    @property
    def modem_reachable(self) -> bool:
        return self.modem_ping or self.modem_http or self.modem_https

    @property
    def internet_reachable(self) -> bool:
        return self.http_internet or self.cloudflare_tcp or self.google_dns_tcp


@dataclass(slots=True)
class Sample:
    timestamp: str
    state: str
    gateway_ip: str
    probes: dict[str, Any]


@dataclass(slots=True)
class EventMetadata:
    event_id: int
    state: str
    severity: str
    detected_at: str
    diagnostics_started_at: str | None = None
    diagnostics_finished_at: str | None = None
