from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass(frozen=True, slots=True)
class Measurement:
    ok: bool
    latency_ms: float | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class ProbeContext:
    modem_ip: str
    gateway_ip: str


class ProbePlugin(Protocol):
    """A named probe that returns one measurement for the current cycle."""

    name: str

    def collect(self, context: ProbeContext) -> Measurement:
        ...


@dataclass(slots=True)
class FunctionProbePlugin:
    """Adapter used by built-in probes and simple third-party extensions."""

    name: str
    collector: Callable[[ProbeContext], Measurement]

    def collect(self, context: ProbeContext) -> Measurement:
        return self.collector(context)


class ProbeRegistry:
    """Ordered registry of probe plugins.

    Duplicate names are rejected because measurement names are persisted and
    form part of the public event format.
    """

    def __init__(self, plugins: list[ProbePlugin] | None = None):
        self._plugins: dict[str, ProbePlugin] = {}
        for plugin in plugins or []:
            self.register(plugin)

    def register(self, plugin: ProbePlugin) -> None:
        if not plugin.name:
            raise ValueError("probe plugin name cannot be empty")
        if plugin.name in self._plugins:
            raise ValueError(f"duplicate probe plugin: {plugin.name}")
        self._plugins[plugin.name] = plugin

    def names(self) -> tuple[str, ...]:
        return tuple(self._plugins)

    def plugins(self) -> tuple[ProbePlugin, ...]:
        return tuple(self._plugins.values())
