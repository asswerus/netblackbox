from __future__ import annotations

from datetime import datetime
from typing import Any

from .incidents import coalesce_events


def _artifact_references(
    event_ids: list[Any], events_by_id: dict[Any, dict[str, Any]]
) -> dict[str, Any]:
    playback_files: list[str] = []
    diagnostics: list[dict[str, Any]] = []

    for event_id in event_ids:
        if event_id is None:
            continue
        playback_files.append(f"playback/{event_id}.json")
        event = events_by_id.get(event_id, {})
        diagnostics_path = event.get("diagnostics_path")
        if diagnostics_path:
            diagnostics.append(
                {
                    "event_id": event_id,
                    "path": str(diagnostics_path),
                    "started_at": event.get("diagnostics_started_at"),
                    "finished_at": event.get("diagnostics_finished_at"),
                }
            )

    return {
        "playback_files": playback_files,
        "diagnostics": diagnostics,
    }


def build_incident_summary(
    events: list[dict[str, Any]],
    *,
    generated_at: str,
    platform: str,
    merge_window_seconds: float = 15.0,
) -> dict[str, Any]:
    """Build the incident-facing aggregate payload from persisted event rows."""
    incidents = coalesce_events(events, merge_window_seconds=merge_window_seconds)
    events_by_id = {event.get("id"): event for event in events if event.get("id") is not None}
    completed = [incident for incident in incidents if incident["end_time"] is not None]
    by_hour = {str(hour): 0 for hour in range(24)}
    by_state: dict[str, int] = {}
    by_severity: dict[str, int] = {}

    for incident in incidents:
        hour = datetime.fromisoformat(incident["start_time"]).hour
        by_hour[str(hour)] += 1
        state = incident["primary_state"]
        by_state[state] = by_state.get(state, 0) + 1
        severity = incident.get("severity") or "INFO"
        by_severity[severity] = by_severity.get(severity, 0) + 1
        incident["artifacts"] = _artifact_references(incident["event_ids"], events_by_id)

    return {
        "generated_at": generated_at,
        "platform": platform,
        "incident_count": len(incidents),
        "source_event_count": len(events),
        "total_duration_seconds": round(
            sum(float(incident["duration_seconds"]) for incident in completed), 3
        ),
        "longest_duration_seconds": max(
            (float(incident["duration_seconds"]) for incident in completed), default=0
        ),
        "by_hour": by_hour,
        "by_state": by_state,
        "by_severity": by_severity,
        "incidents": incidents[-500:],
    }
