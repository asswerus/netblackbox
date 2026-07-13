from netblackbox.timeline_route import event_timeline_response


def playback(event_id: int) -> dict[str, object]:
    if event_id != 42:
        raise KeyError(event_id)
    return {
        "event": {"id": 42, "state": "DNS_KO"},
        "samples": [
            {
                "timestamp": "2026-07-14T00:30:00+02:00",
                "phase": "active",
                "state": "DNS_KO",
                "raw_state": "DNS_KO",
                "sampling_mode": "turbo",
            }
        ],
    }


def test_timeline_route_renders_event_html() -> None:
    response = event_timeline_response("/events/42/timeline?ignored=yes", playback)

    assert response is not None
    assert response.status == 200
    assert response.content_type == "text/html; charset=utf-8"
    assert b"Event 42" in response.body
    assert b"DNS_KO" in response.body


def test_timeline_route_returns_not_found_for_invalid_or_missing_event() -> None:
    invalid = event_timeline_response("/events/nope/timeline", playback)
    missing = event_timeline_response("/events/99/timeline", playback)

    assert invalid is not None and invalid.status == 404
    assert missing is not None and missing.status == 404


def test_unrelated_route_is_not_claimed() -> None:
    assert event_timeline_response("/api/events/42", playback) is None
