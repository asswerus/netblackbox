from __future__ import annotations

import html
import json
from typing import Any


def _safe_json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")


def render_event_timeline(playback: dict[str, Any]) -> str:
    """Render a self-contained interactive HTML timeline for one event playback."""
    event = playback.get("event") or {}
    samples = playback.get("samples") or []
    event_id = html.escape(str(event.get("id", "unknown")))
    state = html.escape(str(event.get("state", "unknown")))
    payload = _safe_json({"event": event, "samples": samples})

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NetBlackBox event {event_id}</title>
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
    body {{ margin: 0; padding: 1.5rem; max-width: 1200px; margin-inline: auto; }}
    header {{ display: flex; gap: 1rem; align-items: baseline; flex-wrap: wrap; }}
    .toolbar {{ display: flex; gap: .5rem; flex-wrap: wrap; margin: 1rem 0; }}
    button {{ padding: .45rem .75rem; cursor: pointer; }}
    #timeline {{ display: grid; gap: .45rem; }}
    .sample {{ display: grid; grid-template-columns: 10rem 5rem 1fr 6rem; gap: .75rem;
      align-items: center; padding: .55rem .7rem; border: 1px solid currentColor;
      border-radius: .45rem; cursor: pointer; }}
    .sample[data-phase="pre"] {{ opacity: .72; }}
    .sample[data-mode="fast"] {{ border-style: dashed; }}
    .sample[data-mode="turbo"] {{ border-width: 2px; }}
    .state {{ font-weight: 700; }}
    #details {{ white-space: pre-wrap; overflow-wrap: anywhere; padding: 1rem;
      border: 1px solid currentColor; border-radius: .45rem; min-height: 6rem; }}
    .muted {{ opacity: .7; }}
    @media (max-width: 760px) {{
      .sample {{ grid-template-columns: 1fr 4rem; }}
      .sample .timestamp, .sample .mode {{ grid-column: 1 / -1; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Event {event_id}</h1>
    <strong>{state}</strong>
    <span class="muted" id="summary"></span>
  </header>
  <div class="toolbar" aria-label="Timeline filters">
    <button type="button" data-filter="all">All</button>
    <button type="button" data-filter="pre">Pre</button>
    <button type="button" data-filter="active">Active</button>
    <button type="button" data-filter="post">Post</button>
  </div>
  <main id="timeline" aria-live="polite"></main>
  <h2>Sample details</h2>
  <pre id="details">Select a sample.</pre>
  <script id="playback-data" type="application/json">{payload}</script>
  <script>
    const playback = JSON.parse(document.getElementById("playback-data").textContent);
    const timeline = document.getElementById("timeline");
    const details = document.getElementById("details");
    const summary = document.getElementById("summary");

    function render(filter = "all") {{
      timeline.replaceChildren();
      const visible = playback.samples.filter(sample => filter === "all" || sample.phase === filter);
      summary.textContent = `${{playback.samples.length}} samples`;
      for (const sample of visible) {{
        const row = document.createElement("article");
        row.className = "sample";
        row.dataset.phase = sample.phase || "unknown";
        row.dataset.mode = sample.sampling_mode || "normal";
        row.tabIndex = 0;

        const timestamp = document.createElement("time");
        timestamp.className = "timestamp";
        timestamp.textContent = sample.timestamp || "unknown";

        const phase = document.createElement("span");
        phase.textContent = sample.phase || "sample";

        const state = document.createElement("span");
        state.className = "state";
        state.textContent = sample.raw_state || sample.observed_state || sample.state || "unknown";

        const mode = document.createElement("span");
        mode.className = "mode";
        mode.textContent = sample.sampling_mode || "normal";

        row.append(timestamp, phase, state, mode);
        const showDetails = () => {{ details.textContent = JSON.stringify(sample, null, 2); }};
        row.addEventListener("click", showDetails);
        row.addEventListener("keydown", event => {{
          if (event.key === "Enter" || event.key === " ") showDetails();
        }});
        timeline.append(row);
      }}
    }}

    document.querySelectorAll("[data-filter]").forEach(button => {{
      button.addEventListener("click", () => render(button.dataset.filter));
    }});
    render();
  </script>
</body>
</html>
"""
