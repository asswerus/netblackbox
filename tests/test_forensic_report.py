from __future__ import annotations

from netblackbox.forensic_report import render_forensic_report


def test_report_contains_dashboard_distributions_and_playback_links() -> None:
    summary = {
        "generated_at": "2026-07-17T10:30:00.000+00:00",
        "event_count": 1,
        "total_duration_seconds": 8.0,
        "longest_duration_seconds": 8.0,
        "by_state": {"PARTIAL_CONNECTIVITY": 1},
        "by_severity": {"WARNING": 1},
        "events": [
            {
                "id": 7,
                "start_time": "2026-07-16T12:00:00+00:00",
                "end_time": "2026-07-16T12:00:08+00:00",
                "state": "PARTIAL_CONNECTIVITY",
                "severity": "WARNING",
                "duration_seconds": 8.0,
            }
        ],
    }
    incidents = {
        "incident_count": 1,
        "by_hour": {str(hour): 1 if hour == 12 else 0 for hour in range(24)},
        "incidents": [],
    }
    metadata = {
        "window_days": 30,
        "platform": "test-platform",
        "netblackbox_version": "1.2.3",
        "bundle_version": 1,
        "hostname": "test-host",
        "timezone": {"name": "UTC", "utc_offset": "+00:00"},
        "database": {
            "filename": "database.sqlite3",
            "sha256": "a" * 64,
        },
    }

    report = render_forensic_report(summary, incidents, metadata)

    assert "Bundle overview" in report
    assert "Events by state" in report
    assert "Events by severity" in report
    assert "Incidents by hour" in report
    assert "PARTIAL_CONNECTIVITY" in report
    assert 'class="severity warning"' in report
    assert 'href="playback/7.json"' in report
    assert "test-platform" in report
    assert "test-host" in report
    assert "a" * 64 in report


def test_report_escapes_event_and_metadata_values() -> None:
    report = render_forensic_report(
        {
            "generated_at": "now",
            "event_count": 1,
            "total_duration_seconds": 0,
            "longest_duration_seconds": 0,
            "by_state": {"<script>": 1},
            "by_severity": {},
            "events": [
                {
                    "id": "7&8",
                    "state": "<script>alert(1)</script>",
                    "severity": "UNKNOWN",
                }
            ],
        },
        {"incident_count": 0, "by_hour": {}},
        {
            "window_days": 1,
            "platform": "<unsafe>",
            "timezone": {},
            "database": {},
        },
    )

    assert "<script>" not in report
    assert "&lt;script&gt;" in report
    assert 'href="playback/7&amp;8.json"' in report
