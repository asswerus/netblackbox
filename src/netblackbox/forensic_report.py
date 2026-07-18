from __future__ import annotations

import html
from typing import Any


def _escape(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _severity_class(value: Any) -> str:
    severity = str(value or "UNKNOWN").casefold()
    return severity if severity in {"info", "warning", "major", "critical"} else "unknown"


def _bars(values: dict[str, Any], *, empty_message: str) -> str:
    if not values:
        return f'<p class="muted">{html.escape(empty_message)}</p>'
    maximum = max((int(value) for value in values.values()), default=0) or 1
    rows = []
    for label, raw_value in sorted(values.items(), key=lambda item: (-int(item[1]), item[0])):
        value = int(raw_value)
        width = max(2, round((value / maximum) * 100)) if value else 0
        rows.append(
            '<div class="bar-row">'
            f'<span class="bar-label">{_escape(label)}</span>'
            f'<span class="bar-track"><span class="bar-fill" style="width:{width}%"></span></span>'
            f"<strong>{value}</strong>"
            "</div>"
        )
    return "".join(rows)


def render_forensic_report(
    summary: dict[str, Any], incidents: dict[str, Any], metadata: dict[str, Any]
) -> str:
    """Render a self-contained, dependency-free forensic bundle report."""
    incident_count = incidents.get("incident_count", len(incidents.get("incidents", [])))
    rows = []
    for event in summary.get("events", []):
        event_id = event.get("id", "")
        severity = event.get("severity") or "UNKNOWN"
        rows.append(
            "<tr>"
            f"<td>{_escape(event_id)}</td>"
            f"<td>{_escape(event.get('start_time'))}</td>"
            f"<td>{_escape(event.get('end_time'))}</td>"
            f"<td>{_escape(event.get('state'))}</td>"
            f'<td><span class="severity {_severity_class(severity)}">{_escape(severity)}</span></td>'
            f"<td>{_escape(event.get('duration_seconds'))}</td>"
            f'<td><a href="playback/{html.escape(str(event_id), quote=True)}.json">Playback</a></td>'
            "</tr>"
        )
    event_rows = (
        "".join(rows)
        or '<tr><td colspan="7" class="muted">No events in this bundle window.</td></tr>'
    )

    by_hour = {
        hour: count for hour, count in incidents.get("by_hour", {}).items() if int(count) > 0
    }
    database = metadata.get("database", {})
    timezone = metadata.get("timezone", {})

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NetBlackBox forensic bundle</title>
<style>
:root{{--bg:#f4f6f8;--panel:#fff;--text:#17202a;--muted:#66717c;--border:#dfe4e8;--accent:#2457d6}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1200px;margin:0 auto;padding:2rem}} h1{{margin:0 0 .25rem}} h2{{margin-top:0}} a{{color:var(--accent)}}
.subtitle,.muted{{color:var(--muted)}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:1rem;margin:1.5rem 0}}
.card,.panel{{background:var(--panel);border:1px solid var(--border);border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.04)}}
.card{{padding:1rem}} .card strong{{display:block;font-size:1.65rem;margin-top:.35rem}} .panel{{padding:1.25rem;margin:1rem 0}}
.split{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:1rem}} table{{width:100%;border-collapse:collapse;font-size:.92rem}}
th,td{{padding:.65rem;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}} th{{background:#f8fafb;position:sticky;top:0}}
.table-wrap{{overflow:auto}} .severity{{display:inline-block;padding:.2rem .5rem;border-radius:999px;font-weight:700;font-size:.78rem}}
.severity.info{{background:#e7f7ed;color:#176b36}} .severity.warning{{background:#fff3cd;color:#805b00}} .severity.major{{background:#ffe5cc;color:#9a4700}}
.severity.critical{{background:#fde2e2;color:#9c1c1c}} .severity.unknown{{background:#eceff1;color:#455a64}}
.bar-row{{display:grid;grid-template-columns:minmax(120px,1fr) minmax(100px,3fr) 3rem;gap:.75rem;align-items:center;margin:.55rem 0}}
.bar-label{{overflow:hidden;text-overflow:ellipsis}} .bar-track{{height:.7rem;background:#e9edf2;border-radius:999px;overflow:hidden}}
.bar-fill{{display:block;height:100%;background:var(--accent);border-radius:999px}} dl{{display:grid;grid-template-columns:max-content 1fr;gap:.5rem 1rem;margin:0}} dt{{font-weight:700}} dd{{margin:0;word-break:break-word}}
@media(max-width:650px){{main{{padding:1rem}} .bar-row{{grid-template-columns:1fr 2fr 2rem}} dl{{grid-template-columns:1fr}}}}
</style>
</head>
<body><main>
<header><h1>NetBlackBox forensic bundle</h1><p class="subtitle">Generated {_escape(summary.get("generated_at"))}</p></header>
<section class="grid" aria-label="Bundle overview">
<div class="card"><span>Events</span><strong>{summary.get("event_count", 0)}</strong></div>
<div class="card"><span>Incidents</span><strong>{incident_count}</strong></div>
<div class="card"><span>Total event duration</span><strong>{summary.get("total_duration_seconds", 0)} s</strong></div>
<div class="card"><span>Longest event</span><strong>{summary.get("longest_duration_seconds", 0)} s</strong></div>
<div class="card"><span>Window</span><strong>{metadata.get("window_days", "")} days</strong></div>
<div class="card"><span>Platform</span><strong>{_escape(metadata.get("platform"))}</strong></div>
</section>
<section class="split">
<div class="panel"><h2>Events by state</h2>{_bars(summary.get("by_state", {}), empty_message="No state data.")}</div>
<div class="panel"><h2>Events by severity</h2>{_bars(summary.get("by_severity", {}), empty_message="No severity data.")}</div>
</section>
<section class="panel"><h2>Incidents by hour</h2>{_bars(by_hour, empty_message="No incidents in this bundle window.")}</section>
<section class="panel"><h2>Events</h2><div class="table-wrap"><table>
<thead><tr><th>ID</th><th>Start</th><th>End</th><th>State</th><th>Severity</th><th>Duration (s)</th><th>Details</th></tr></thead>
<tbody>{event_rows}</tbody></table></div></section>
<section class="panel"><h2>Bundle information</h2><dl>
<dt>NetBlackBox version</dt><dd>{_escape(metadata.get("netblackbox_version"))}</dd>
<dt>Bundle version</dt><dd>{_escape(metadata.get("bundle_version"))}</dd>
<dt>Hostname</dt><dd>{_escape(metadata.get("hostname"))}</dd>
<dt>Timezone</dt><dd>{_escape(timezone.get("name"))} ({_escape(timezone.get("utc_offset"))})</dd>
<dt>Database</dt><dd>{_escape(database.get("filename"))}</dd>
<dt>Database SHA-256</dt><dd><code>{_escape(database.get("sha256"))}</code></dd>
</dl></section>
</main></body></html>"""
