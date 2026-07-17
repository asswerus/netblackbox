from __future__ import annotations

from dataclasses import dataclass

import pytest
from netblackbox.plugins import Measurement, ProbeContext, discover_probe_plugins


@dataclass
class FakePlugin:
    name: str = "external_latency"

    def collect(self, context: ProbeContext) -> Measurement:
        return Measurement(True, 1.5, f"{context.modem_ip}->{context.gateway_ip}")


class FakeEntryPoint:
    def __init__(self, name: str, loaded: object):
        self.name = name
        self._loaded = loaded

    def load(self) -> object:
        return self._loaded


def test_external_plugins_are_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "netblackbox.plugins._entry_points",
        lambda: (FakeEntryPoint("demo", FakePlugin()),),
    )
    assert discover_probe_plugins([]) == ()


def test_selected_provider_is_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "netblackbox.plugins._entry_points",
        lambda: (FakeEntryPoint("demo", FakePlugin()),),
    )
    plugins = discover_probe_plugins(["demo"])
    assert [plugin.name for plugin in plugins] == ["external_latency"]


def test_factory_and_iterable_are_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "netblackbox.plugins._entry_points",
        lambda: (FakeEntryPoint("demo", lambda: [FakePlugin("one"), FakePlugin("two")]),),
    )
    assert [plugin.name for plugin in discover_probe_plugins(["*"])] == ["one", "two"]


def test_missing_enabled_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("netblackbox.plugins._entry_points", lambda: ())
    with pytest.raises(ValueError, match="not installed"):
        discover_probe_plugins(["missing"])
