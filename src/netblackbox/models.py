from __future__ import annotations

from dataclasses import dataclass


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

    @property
    def modem_reachable(self) -> bool:
        return self.modem_ping or self.modem_http or self.modem_https

    @property
    def internet_reachable(self) -> bool:
        return self.http_internet or self.cloudflare_tcp or self.google_dns_tcp
