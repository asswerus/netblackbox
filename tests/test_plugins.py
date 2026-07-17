import pytest

from netblackbox.plugins import (
    FunctionProbePlugin,
    Measurement,
    ProbeContext,
    ProbeRegistry,
)


def test_registry_preserves_order_and_executes_plugin() -> None:
    plugin = FunctionProbePlugin(
        "example",
        lambda context: Measurement(context.gateway_ip == "192.0.2.1", 12.5),
    )
    registry = ProbeRegistry([plugin])

    assert registry.names() == ("example",)
    result = registry.plugins()[0].collect(
        ProbeContext(modem_ip="192.168.1.1", gateway_ip="192.0.2.1")
    )
    assert result == Measurement(True, 12.5)


def test_registry_rejects_duplicate_names() -> None:
    registry = ProbeRegistry([FunctionProbePlugin("duplicate", lambda _ctx: Measurement(True))])

    with pytest.raises(ValueError, match="duplicate probe plugin"):
        registry.register(FunctionProbePlugin("duplicate", lambda _ctx: Measurement(False)))


def test_registry_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        ProbeRegistry([FunctionProbePlugin("", lambda _ctx: Measurement(True))])
