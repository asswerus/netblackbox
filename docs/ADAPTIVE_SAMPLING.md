# Adaptive sampling

NetBlackBox uses three sampling cadences:

- **normal** for healthy, steady-state monitoring;
- **fast** as soon as an unconfirmed suspicious sample appears;
- **turbo** after a fault is confirmed and an event is opened.

The policy is intentionally independent from the application loop and from wall-clock time. Callers provide a monotonic timestamp, making transitions deterministic and easy to test.

A typical progression is:

```text
2.0 s normal
  -> 0.5 s fast on first suspicious sample
  -> 0.25 s turbo on confirmed event
  -> 2.0 s normal after the capture windows expire
```

The policy only selects a mode and interval. Event classification, confirmation cycles, persistence, and sleeping remain responsibilities of the monitor loop.
