from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from .timeline import render_event_timeline


@dataclass(frozen=True, slots=True)
class TimelineResponse:
    status: int
    content_type: str
    body: bytes


def event_timeline_response(
    path: str,
    playback_loader: Callable[[int], dict[str, Any]],
) -> TimelineResponse | None:
    """Return an HTML timeline response when *path* matches an event timeline route."""
    route = urlsplit(path).path
    parts = route.strip("/").split("/")
    if len(parts) != 3 or parts[0] != "events" or parts[2] != "timeline":
        return None

    try:
        event_id = int(parts[1])
        playback = playback_loader(event_id)
    except (ValueError, KeyError):
        return TimelineResponse(
            status=404,
            content_type="text/plain; charset=utf-8",
            body=b"Event not found.\n",
        )

    return TimelineResponse(
        status=200,
        content_type="text/html; charset=utf-8",
        body=render_event_timeline(playback).encode("utf-8"),
    )
