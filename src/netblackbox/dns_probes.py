from __future__ import annotations

import time

import dns.exception
import dns.resolver

from .plugins import Measurement

DNS_TEST_HOST = "example.com"


def resolve_with_nameserver(
    nameserver: str,
    *,
    timeout_seconds: float,
    hostname: str = DNS_TEST_HOST,
) -> Measurement:
    """Resolve an A record through one explicit DNS server."""
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = [nameserver]
    resolver.timeout = timeout_seconds
    resolver.lifetime = timeout_seconds
    started = time.perf_counter()
    try:
        answer = resolver.resolve(hostname, "A", search=False)
        latency = round((time.perf_counter() - started) * 1000, 2)
        addresses = sorted({item.address for item in answer})
        detail = f"resolver={nameserver}; answers={','.join(addresses)}"
        return Measurement(True, latency, detail=detail)
    except (dns.exception.DNSException, OSError) as exc:
        detail = f"resolver={nameserver}; {type(exc).__name__}: {exc}"
        return Measurement(False, detail=detail)
