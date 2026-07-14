from __future__ import annotations

from datetime import datetime
from typing import Any

from .incidents import coalesce_events


def build_incident_summary(
    events: list[dict[str, Any]],
    *,
    generated_at: str,
    platform: str,
    merge_window_seconds: float = 15.0,
) -> dict[str, Any]:
    """Build the incident-facing aggregate payload from persisted event rows."""
    incidents = coalesce_events(events, merge_window_seconds=merge_window_seconds)
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
