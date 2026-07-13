# Architecture decisions

1. Keep one Python core for all operating systems.
2. Isolate OS commands behind a small backend interface.
3. Prefer standard-library probes and persistence.
4. Treat service installation as platform packaging, not monitoring logic.
5. Validate the core on macOS, Linux, and Windows in CI.
