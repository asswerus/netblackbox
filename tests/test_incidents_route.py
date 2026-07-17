from __future__ import annotations

import json

from nbb.incidents_route import incidents_response


def test_incidents_route_returns_json_payload() -> None:
    payload = {
        "incident_count": 1,
        "source_event_count": 2,
        "incidents": [{"id": 1, "event_ids": [10, 11]}],
    }

    response = incidents_response("/api/incidents", lambda: payload)

    assert response is not None
    assert response.status == 200
    assert response.content_type == "application/json"
    assert json.loads(response.body) == payload


def test_incidents_route_accepts_trailing_slash_and_query_string() -> None:
    response = incidents_response(
        "/api/incidents/?days=30",
        lambda: {"incident_count": 0, "incidents": []},
    )

    assert response is not None
    assert response.status == 200


def test_incidents_route_ignores_unrelated_paths() -> None:
    called = False

    def loader() -> dict[str, object]:
        nonlocal called
        called = True
        return {}

    assert incidents_response("/api/events", loader) is None
    assert incidents_response("/api/incidents/1", loader) is None
    assert called is False
