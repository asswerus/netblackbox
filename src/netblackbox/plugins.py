from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from importlib import metadata
from typing import Callable, Protocol, cast

ENTRY_POINT_GROUP = "netblackbox.probes"


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

    def __init__(self, plugins: Iterable[ProbePlugin] | None = None):
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


def _entry_points() -> tuple[metadata.EntryPoint, ...]:
    discovered = metadata.entry_points()
    if hasattr(discovered, "select"):
        return tuple(discovered.select(group=ENTRY_POINT_GROUP))
    return tuple(discovered.get(ENTRY_POINT_GROUP, ()))  # type: ignore[union-attr]


def _normalise_loaded_plugin(value: object) -> tuple[ProbePlugin, ...]:
    """Accept a plugin instance, a zero-argument factory, or an iterable."""

    if callable(value) and not hasattr(value, "collect"):
        value = value()

    if hasattr(value, "name") and hasattr(value, "collect"):
        return (cast(ProbePlugin, value),)

    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
        plugins = tuple(cast(ProbePlugin, item) for item in value)
        for plugin in plugins:
            if not hasattr(plugin, "name") or not hasattr(plugin, "collect"):
                raise TypeError("entry point returned an invalid probe plugin")
        return plugins

    raise TypeError("entry point must expose a probe plugin, factory, or iterable")


def discover_probe_plugins(enabled: Iterable[str] = ()) -> tuple[ProbePlugin, ...]:
    """Load explicitly enabled third-party probes from Python entry points.

    Entry-point names are package-level identifiers. Use ``*`` to enable every
    installed probe provider. External plugins are opt-in so installing an
    unrelated package cannot silently change monitoring behaviour.
    """

    enabled_names = frozenset(enabled)
    if not enabled_names:
        return ()

    load_all = "*" in enabled_names
    plugins: list[ProbePlugin] = []
    available: set[str] = set()

    for entry_point in _entry_points():
        available.add(entry_point.name)
        if not load_all and entry_point.name not in enabled_names:
            continue
        plugins.extend(_normalise_loaded_plugin(entry_point.load()))

    missing = enabled_names.difference(available).difference({"*"})
    if missing:
        raise ValueError(f"enabled probe providers are not installed: {', '.join(sorted(missing))}")

    return tuple(plugins)
