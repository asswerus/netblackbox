from nbb.incident_summary import build_incident_summary


def event(
    event_id: int,
    start_time: str,
    end_time: str,
    state: str,
    severity: str,
) -> dict[str, object]:
    return {
        "id": event_id,
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": 1.0,
        "state": state,
        "severity": severity,
    }


def test_builds_incident_aggregates_from_coalesced_events() -> None:
    payload = build_incident_summary(
        [
            event(
                10,
                "2026-07-14T15:12:24+02:00",
                "2026-07-14T15:12:32+02:00",
                "MODEM_LAN_KO",
                "MAJOR",
            ),
            event(
                11,
                "2026-07-14T15:12:32.100+02:00",
                "2026-07-14T15:14:04+02:00",
                "PARTIAL_CONNECTIVITY",
                "WARNING",
            ),
        ],
        generated_at="2026-07-14T16:00:00+02:00",
        platform="macos",
        merge_window_seconds=15,
    )

    assert payload["incident_count"] == 1
    assert payload["source_event_count"] == 2
    assert payload["by_hour"]["15"] == 1
    assert payload["by_state"] == {"MODEM_LAN_KO": 1}
    assert payload["by_severity"] == {"MAJOR": 1}
    assert payload["incidents"][0]["event_ids"] == [10, 11]
    assert payload["total_duration_seconds"] == 100.0
    assert payload["longest_duration_seconds"] == 100.0


def test_keeps_separate_incidents_outside_merge_window() -> None:
    payload = build_incident_summary(
        [
            event(
                1,
                "2026-07-14T15:00:00+02:00",
                "2026-07-14T15:00:01+02:00",
                "PARTIAL_CONNECTIVITY",
                "WARNING",
            ),
            event(
                2,
                "2026-07-14T15:00:20+02:00",
                "2026-07-14T15:00:21+02:00",
                "PARTIAL_CONNECTIVITY",
                "WARNING",
            ),
        ],
        generated_at="2026-07-14T16:00:00+02:00",
        platform="macos",
        merge_window_seconds=15,
    )

    assert payload["incident_count"] == 2
    assert payload["source_event_count"] == 2
    assert payload["total_duration_seconds"] == 2.0
