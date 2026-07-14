from __future__ import annotations

import json
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .app import NetBlackBoxApp
from .incident_summary import build_incident_summary
from .incidents_route import incidents_response


class IncidentApiApp(NetBlackBoxApp):
    """NetBlackBox application with the incident summary HTTP endpoint enabled."""

    def incident_summary(self, days: int = 30) -> dict[str, Any]:
        cutoff = self.timestamp(self.now() - timedelta(days=days))
        with self.db() as connection:
            events = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM events WHERE start_time >= ? ORDER BY start_time",
                    (cutoff,),
                )
            ]
        return build_incident_summary(
            events,
            generated_at=self.timestamp(),
            platform=self.backend.name,
        )

    def _serve(self) -> None:
        app = self

        class Handler(BaseHTTPRequestHandler):
            def send_body(self, status: int, content_type: str, body: bytes) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                incident = incidents_response(self.path, app.incident_summary)
                if incident is not None:
                    self.send_body(incident.status, incident.content_type, incident.body)
                    return
                if self.path == "/status":
                    with app.snapshot_lock:
                        body = json.dumps(app.snapshot, indent=2).encode()
                    self.send_body(200, "application/json", body)
                    return
                if self.path.startswith("/api/events/"):
                    try:
                        event_id = int(self.path.rsplit("/", 1)[1])
                        body = json.dumps(app.event_playback(event_id), indent=2).encode()
                        self.send_body(200, "application/json", body)
                    except (ValueError, KeyError):
                        self.send_body(404, "application/json", b'{"error":"event not found"}')
                    return
                if self.path.startswith("/api/events"):
                    body = json.dumps(app.summary(), indent=2).encode()
                    self.send_body(200, "application/json", body)
                    return
                self.send_body(
                    200,
                    "text/plain; charset=utf-8",
                    b"NetBlackBox is running. Use /status, /api/events or /api/incidents.\n",
                )

            def log_message(self, *_: object) -> None:
                return

        ThreadingHTTPServer((self.config.http_host, self.config.http_port), Handler).serve_forever()
