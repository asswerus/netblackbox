# Probe plugin architecture

NetBlackBox executes network checks through a small plugin contract.

A probe plugin has a stable name and a `collect()` method:

```python
from netblackbox.plugins import Measurement, ProbeContext


class ExampleProbe:
    name = "example_probe"

    def collect(self, context: ProbeContext) -> Measurement:
        return Measurement(ok=True, latency_ms=4.2, detail="optional detail")
```

Plugins are registered in a `ProbeRegistry`. Duplicate names are rejected because probe names are persisted in event data and therefore form part of the public data format.

The first implementation deliberately keeps the existing eight built-in probe names and the current `ProbeResult` model unchanged. This gives NetBlackBox an extension boundary without changing classification, SQLite data, dashboard APIs, or existing installations.

## Current scope

- Built-in probes now run through the registry.
- A plugin can return success, latency and an optional diagnostic detail.
- Collection remains concurrent.
- Required built-in names are validated at startup.

## Follow-up

The next stage will make enabled probes configurable and expose optional third-party plugins through Python entry points. Classification probes will remain explicitly declared so an unrelated extension cannot silently alter outage semantics.
