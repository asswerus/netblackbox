from __future__ import annotations

from datetime import datetime
from typing import Any


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _event_end(event: dict[str, Any]) -> datetime:
    return _timestamp(event.get("end_time") or event["start_time"])


def _severity_rank(severity: str | None) -> int:
    return {"INFO": 0, "WARNING": 1, "MAJOR": 2, "CRITICAL": 3}.get(severity or "", 0)


def coalesce_events(
    events: list[dict[str, Any]], merge_window_seconds: float = 15.0
) -> list[dict[str, Any]]:
    """Group nearby event rows into incident envelopes without mutating the input."""
    if merge_window_seconds < 0:
        raise ValueError("merge_window_seconds must be non-negative")
    if not events:
        return []

    ordered = sorted(events, key=lambda event: _timestamp(event["start_time"]))
    incidents: list[dict[str, Any]] = []

    for event in ordered:
        start = _timestamp(event["start_time"])
        end = _event_end(event)
        phase = {
            "event_id": event.get("id"),
            "state": event["state"],
            "severity": event.get("severity"),
            "start_time": event["start_time"],
            "end_time": event.get("end_time"),
            "duration_seconds": event.get("duration_seconds"),
        }

        if incidents:
            previous = incidents[-1]
            gap = (start - _timestamp(previous["end_time"])).total_seconds()
            if gap <= merge_window_seconds:
                previous["end_time"] = end.isoformat(timespec="milliseconds")
                previous["duration_seconds"] = round(
                    (end - _timestamp(previous["start_time"])).total_seconds(), 3
                )
                previous["event_ids"].append(event.get("id"))
                previous["phases"].append(phase)
                if _severity_rank(event.get("severity")) > _severity_rank(previous["severity"]):
                    previous["severity"] = event.get("severity")
                    previous["primary_state"] = event["state"]
                continue

        incidents.append(
            {
                "id": len(incidents) + 1,
                "start_time": event["start_time"],
                "end_time": end.isoformat(timespec="milliseconds"),
                "duration_seconds": round((end - start).total_seconds(), 3),
                "primary_state": event["state"],
                "severity": event.get("severity"),
                "event_ids": [event.get("id")],
                "phases": [phase],
            }
        )

    return incidents
