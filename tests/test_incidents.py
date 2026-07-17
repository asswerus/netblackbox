from nbb.incidents import coalesce_events


def event(
    event_id: int,
    start: str,
    end: str,
    state: str,
    severity: str,
) -> dict[str, object]:
    return {
        "id": event_id,
        "start_time": start,
        "end_time": end,
        "duration_seconds": None,
        "state": state,
        "severity": severity,
    }


def test_merges_nearby_partial_connectivity_events() -> None:
    incidents = coalesce_events(
        [
            event(
                8,
                "2026-07-14T15:08:56.664+02:00",
                "2026-07-14T15:08:57.541+02:00",
                "PARTIAL_CONNECTIVITY",
                "WARNING",
            ),
            event(
                9,
                "2026-07-14T15:09:04.850+02:00",
                "2026-07-14T15:09:05.635+02:00",
                "PARTIAL_CONNECTIVITY",
                "WARNING",
            ),
        ]
    )

    assert len(incidents) == 1
    assert incidents[0]["event_ids"] == [8, 9]
    assert len(incidents[0]["phases"]) == 2


def test_merges_outage_and_partial_recovery_into_one_incident() -> None:
    incidents = coalesce_events(
        [
            event(
                10,
                "2026-07-14T15:12:24.286+02:00",
                "2026-07-14T15:12:32.179+02:00",
                "MODEM_LAN_KO",
                "MAJOR",
            ),
            event(
                11,
                "2026-07-14T15:12:32.182+02:00",
                "2026-07-14T15:14:04.600+02:00",
                "PARTIAL_CONNECTIVITY",
                "WARNING",
            ),
        ]
    )

    assert len(incidents) == 1
    assert incidents[0]["primary_state"] == "MODEM_LAN_KO"
    assert incidents[0]["severity"] == "MAJOR"
    assert incidents[0]["event_ids"] == [10, 11]


def test_keeps_distant_events_separate() -> None:
    incidents = coalesce_events(
        [
            event(
                1,
                "2026-07-14T12:18:42.247+02:00",
                "2026-07-14T12:18:45.296+02:00",
                "MODEM_LAN_KO",
                "MAJOR",
            ),
            event(
                2,
                "2026-07-14T12:26:21.415+02:00",
                "2026-07-14T12:26:22.036+02:00",
                "MODEM_LAN_KO",
                "MAJOR",
            ),
        ]
    )

    assert len(incidents) == 2


def test_rejects_negative_merge_window() -> None:
    try:
        coalesce_events([], merge_window_seconds=-1)
    except ValueError as exc:
        assert str(exc) == "merge_window_seconds must be non-negative"
    else:
        raise AssertionError("negative merge window should fail")
