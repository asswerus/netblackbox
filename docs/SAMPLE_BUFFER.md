# Forensic sample buffer

NetBlackBox already captures pre-event samples in memory. `SampleBuffer` turns that behavior into a dedicated, testable component instead of leaving retention logic inside the application loop.

The buffer:

- stores `Sample` objects in chronological order;
- derives a bounded capacity from the forensic window and fastest sampling interval;
- removes samples older than the configured time window;
- exposes immutable snapshots;
- returns smaller time slices through `last(seconds)`;
- supports deterministic clearing and bulk insertion.

This abstraction is intentionally independent from SQLite and event classification. It can later support live playback, dashboard previews, tests with synthetic timelines, and alternative storage backends.
