from __future__ import annotations

from types import SimpleNamespace

import dns.resolver

from netblackbox.dns_probes import resolve_with_nameserver


class FakeResolver:
    def __init__(self, *, fail: Exception | None = None):
        self.nameservers: list[str] = []
        self.timeout = 0.0
        self.lifetime = 0.0
        self.fail = fail

    def resolve(self, hostname: str, record_type: str, *, search: bool) -> list[SimpleNamespace]:
        assert hostname == "example.com"
        assert record_type == "A"
        assert search is False
        if self.fail is not None:
            raise self.fail
        return [SimpleNamespace(address="93.184.216.34")]


def test_explicit_resolver_success(monkeypatch: object) -> None:
    fake = FakeResolver()
    monkeypatch.setattr(dns.resolver, "Resolver", lambda configure: fake)  # type: ignore[attr-defined]

    measurement = resolve_with_nameserver("1.1.1.1", timeout_seconds=1.5)

    assert measurement.ok is True
    assert measurement.latency_ms is not None
    assert measurement.detail == "resolver=1.1.1.1; answers=93.184.216.34"
    assert fake.nameservers == ["1.1.1.1"]
    assert fake.timeout == 1.5
    assert fake.lifetime == 1.5


def test_explicit_resolver_failure_keeps_resolver_context(monkeypatch: object) -> None:
    fake = FakeResolver(fail=dns.resolver.LifetimeTimeout(timeout=1.0, errors=[]))
    monkeypatch.setattr(dns.resolver, "Resolver", lambda configure: fake)  # type: ignore[attr-defined]

    measurement = resolve_with_nameserver("8.8.8.8", timeout_seconds=1.0)

    assert measurement.ok is False
    assert measurement.latency_ms is None
    assert measurement.detail is not None
    assert measurement.detail.startswith("resolver=8.8.8.8; LifetimeTimeout:")
