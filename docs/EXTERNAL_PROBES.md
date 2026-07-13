# External probe plugins

NetBlackBox discovers optional probe providers through the Python entry-point group:

```text
netblackbox.probes
```

External providers are opt-in. Installing a package does not change monitoring until its entry-point name is added to `external_probe_plugins` in `config.json`.

```json
{
  "external_probe_plugins": ["my-provider"]
}
```

Use `"*"` to enable every installed provider. Explicit names are recommended for predictable deployments.

## Minimal plugin

```python
from dataclasses import dataclass
from netblackbox.plugins import Measurement, ProbeContext

@dataclass
class ExampleProbe:
    name: str = "example_probe"

    def collect(self, context: ProbeContext) -> Measurement:
        return Measurement(
            ok=True,
            latency_ms=1.2,
            detail=f"modem={context.modem_ip}",
        )

probe = ExampleProbe()
```

Register it in the plugin package's `pyproject.toml`:

```toml
[project.entry-points."netblackbox.probes"]
my-provider = "my_package.plugin:probe"
```

An entry point may expose:

- one plugin instance;
- a zero-argument factory returning one plugin;
- a plugin iterable;
- a zero-argument factory returning a plugin iterable.

Probe names must be non-empty and globally unique. A duplicate name aborts startup rather than silently replacing a built-in or another third-party probe.

## Compatibility boundary

External measurements run concurrently with built-ins and are retained by `ProbeRunner.last_measurements`. They do not currently alter outage classification. Classification remains based on the eight built-in probes until an explicit classification extension API is introduced.
