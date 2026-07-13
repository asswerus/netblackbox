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

## External discovery

Third-party packages can publish entry points in the `netblackbox.probes` group. Providers remain disabled until explicitly listed in `external_probe_plugins`; `"*"` enables every installed provider.

## Persisted format

Every enabled built-in and external plugin is included under the `measurements` field of each probe result:

```json
{
  "measurements": {
    "example_probe": {
      "ok": true,
      "latency_ms": 4.2,
      "detail": "optional detail"
    }
  }
}
```

Because NetBlackBox already stores the complete probe result, measurements are automatically included in:

- regular SQLite samples;
- event opening snapshots;
- pre-event, active-event and post-event playback samples;
- diagnostic metadata;
- `/status`;
- `/api/events/<id>` playback responses.

External measurements remain observational. They do not alter the built-in outage classification unless a future, explicitly configured classifier consumes them.
