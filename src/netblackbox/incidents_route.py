from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class IncidentsResponse:
    status: int
    content_type: str
    body: bytes


def incidents_response(
    path: str,
    summary_loader: Callable[[], dict[str, Any]],
) -> IncidentsResponse | None:
    """Return the incident summary JSON response when *path* matches the route."""
    route = urlsplit(path).path.rstrip("/")
    if route != "/api/incidents":
        return None

    body = json.dumps(summary_loader(), indent=2).encode("utf-8")
    return IncidentsResponse(
        status=200,
        content_type="application/json",
        body=body,
    )
