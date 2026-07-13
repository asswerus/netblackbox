from __future__ import annotations

import json
import logging
import logging.handlers
import sqlite3
import threading
import time
from collections import deque
from dataclasses import asdict
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .config import Config
from .models import ProbeResult, Sample
from .platforms import PlatformBackend
from .probes import ProbeRunner, classify

HEALTHY_STATES = {"OK", "OK_GATEWAY_ICMP_BLOCKED"}


def severity_for(state: str, duration_seconds: float = 0) -> str:
    if state in HEALTHY_STATES:
        return "INFO"
    if state == "DNS_KO":
        return "WARNING" if duration_seconds < 60 else "MAJOR"
    if state == "INTERNET_KO_MODEM_OK":
        return "MAJOR" if duration_seconds < 120 else "CRITICAL"
    if state in {"WAN_GATEWAY_KO", "MODEM_LAN_KO"}:
        return "CRITICAL" if duration_seconds >= 30 else "MAJOR"
    return "WARNING"


class NetBlackBoxApp:
    def __init__(self, config: Config, backend: PlatformBackend):
        self.config = config
        self.backend = backend
        self.base_dir = config.base_dir
        self.logs_dir = self.base_dir / "logs"
        self.diagnostics_dir = self.base_dir / "diagnostics"
        self.reports_dir = self.base_dir / "reports"
        self.db_path = self.base_dir / "netblackbox.sqlite3"
        for path in (self.base_dir, self.logs_dir, self.diagnostics_dir, self.reports_dir):
            path.mkdir(parents=True, exist_ok=True)
        self.logger = self._build_logger()
        self.probes = ProbeRunner(config, backend)
        self.snapshot_lock = threading.Lock()
        self.snapshot: dict[str, Any] = {"state": "STARTING", "platform": backend.name}
        max_samples = max(10, int(config.ring_buffer_seconds / max(config.turbo_interval_seconds, 0.1)))
        self.ring: deque[Sample] = deque(maxlen=max_samples)
        self._init_db()
        self._cleanup()

    @staticmethod
    def now() -> datetime:
        return datetime.now().astimezone()

    @staticmethod
    def timestamp(value: datetime | None = None) -> str:
        return (value or datetime.now().astimezone()).isoformat(timespec="milliseconds")

    def _build_logger(self) -> logging.Logger:
        logger = logging.getLogger("NetBlackBox")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%dT%H:%M:%S%z")
        file_handler = logging.handlers.RotatingFileHandler(
            self.logs_dir / "netblackbox.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        return logger

    def db(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self.db() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS samples(
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    state TEXT NOT NULL,
                    probes_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events(
                    id INTEGER PRIMARY KEY,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_seconds REAL,
                    state TEXT NOT NULL,
                    severity TEXT,
                    probes_json TEXT NOT NULL,
                    diagnostics_path TEXT,
                    diagnostics_started_at TEXT,
                    diagnostics_finished_at TEXT
                );
                CREATE TABLE IF NOT EXISTS event_samples(
                    id INTEGER PRIMARY KEY,
                    event_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    state TEXT NOT NULL,
                    gateway_ip TEXT NOT NULL,
                    probes_json TEXT NOT NULL,
                    FOREIGN KEY(event_id) REFERENCES events(id)
                );
                CREATE INDEX IF NOT EXISTS idx_samples_timestamp ON samples(timestamp);
                CREATE INDEX IF NOT EXISTS idx_events_start_time ON events(start_time);
                CREATE INDEX IF NOT EXISTS idx_event_samples_event ON event_samples(event_id, timestamp);
                """
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(events)")}
            migrations = {
                "severity": "ALTER TABLE events ADD COLUMN severity TEXT",
                "diagnostics_started_at": "ALTER TABLE events ADD COLUMN diagnostics_started_at TEXT",
                "diagnostics_finished_at": "ALTER TABLE events ADD COLUMN diagnostics_finished_at TEXT",
            }
            for column, statement in migrations.items():
                if column not in columns:
                    connection.execute(statement)

    def _cleanup(self) -> None:
        cutoff = self.timestamp(self.now() - timedelta(days=self.config.retention_days))
        with self.db() as connection:
            old_ids = [row[0] for row in connection.execute("SELECT id FROM events WHERE start_time < ?", (cutoff,))]
            if old_ids:
                placeholders = ",".join("?" for _ in old_ids)
                connection.execute(f"DELETE FROM event_samples WHERE event_id IN ({placeholders})", old_ids)
            connection.execute("DELETE FROM samples WHERE timestamp < ?", (cutoff,))
            connection.execute("DELETE FROM events WHERE start_time < ?", (cutoff,))

    def save_sample(self, sample: Sample) -> None:
        with self.db() as connection:
            connection.execute(
                "INSERT INTO samples(timestamp, state, probes_json) VALUES(?,?,?)",
                (sample.timestamp, sample.state, json.dumps(sample.probes)),
            )

    def save_event_sample(self, event_id: int, phase: str, sample: Sample) -> None:
        with self.db() as connection:
            connection.execute(
                "INSERT INTO event_samples(event_id,timestamp,phase,state,gateway_ip,probes_json) VALUES(?,?,?,?,?,?)",
                (event_id, sample.timestamp, phase, sample.state, sample.gateway_ip, json.dumps(sample.probes)),
            )

    def open_event(self, state: str, probes: ProbeResult) -> int:
        severity = severity_for(state)
        with self.db() as connection:
            cursor = connection.execute(
                "INSERT INTO events(start_time, state, severity, probes_json) VALUES(?,?,?,?)",
                (self.timestamp(), state, severity, json.dumps(asdict(probes))),
            )
            event_id = int(cursor.lastrowid)
        for sample in list(self.ring):
            self.save_event_sample(event_id, "pre", sample)
        return event_id

    def close_event(self, event_id: int, started_at: datetime, state: str) -> None:
        ended_at = self.now()
        duration = round((ended_at - started_at).total_seconds(), 3)
        with self.db() as connection:
            connection.execute(
                "UPDATE events SET end_time=?, duration_seconds=?, severity=? WHERE id=?",
                (self.timestamp(ended_at), duration, severity_for(state, duration), event_id),
            )

    def collect_diagnostic_snapshot(
        self,
        folder: Path,
        index: int,
        gateway_ip: str,
    ) -> None:
        snapshot_dir = folder / f"snapshot_{index:02d}"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        (snapshot_dir / "captured_at.txt").write_text(self.timestamp(), encoding="utf-8")
        for command in self.backend.diagnostics(self.config.modem_ip, gateway_ip):
            code, output = self.backend.run(command.args, command.timeout)
            (snapshot_dir / f"{command.name}.txt").write_text(
                f"COMMAND: {' '.join(command.args)}\nEXIT CODE: {code}\n\n{output}\n",
                encoding="utf-8",
            )

    def collect_diagnostics(self, event_id: int, state: str, probes: ProbeResult, gateway_ip: str) -> None:
        folder = self.diagnostics_dir / f"{self.now().strftime('%Y%m%d_%H%M%S')}_{state.lower()}_{event_id}"
        folder.mkdir(parents=True, exist_ok=True)
        started = self.timestamp()
        with self.db() as connection:
            connection.execute(
                "UPDATE events SET diagnostics_path=?, diagnostics_started_at=? WHERE id=?",
                (str(folder), started, event_id),
            )
        (folder / "metadata.json").write_text(
            json.dumps(
                {
                    "event_id": event_id,
                    "state": state,
                    "severity": severity_for(state),
                    "platform": self.backend.name,
                    "detected_at": started,
                    "probes": asdict(probes),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        for index in range(self.config.diagnostic_repeat_count):
            self.collect_diagnostic_snapshot(folder, index, gateway_ip)
            if index + 1 < self.config.diagnostic_repeat_count:
                time.sleep(self.config.diagnostic_repeat_interval_seconds)
        finished = self.timestamp()
        with self.db() as connection:
            connection.execute(
                "UPDATE events SET diagnostics_finished_at=? WHERE id=?",
                (finished, event_id),
            )
        self.logger.info("Repeated diagnostics saved to %s", folder)

    def summary(self, days: int = 30) -> dict[str, Any]:
        cutoff = self.timestamp(self.now() - timedelta(days=days))
        with self.db() as connection:
            rows = [dict(row) for row in connection.execute(
                "SELECT * FROM events WHERE start_time >= ? ORDER BY start_time", (cutoff,)
            )]
        completed = [row for row in rows if row["duration_seconds"] is not None]
        by_hour = {str(hour): 0 for hour in range(24)}
        by_state: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for row in rows:
            hour = datetime.fromisoformat(row["start_time"]).hour
            by_hour[str(hour)] += 1
            by_state[row["state"]] = by_state.get(row["state"], 0) + 1
            severity = row.get("severity") or severity_for(row["state"], row.get("duration_seconds") or 0)
            by_severity[severity] = by_severity.get(severity, 0) + 1
        return {
            "generated_at": self.timestamp(),
            "platform": self.backend.name,
            "event_count": len(rows),
            "total_duration_seconds": round(sum(float(row["duration_seconds"]) for row in completed), 3),
            "longest_duration_seconds": max((float(row["duration_seconds"]) for row in completed), default=0),
            "by_hour": by_hour,
            "by_state": by_state,
            "by_severity": by_severity,
            "events": rows[-500:],
        }

    def event_playback(self, event_id: int) -> dict[str, Any]:
        with self.db() as connection:
            event = connection.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
            samples = [dict(row) for row in connection.execute(
                "SELECT timestamp,phase,state,gateway_ip,probes_json FROM event_samples WHERE event_id=? ORDER BY timestamp",
                (event_id,),
            )]
        if event is None:
            raise KeyError(event_id)
        for sample in samples:
            sample["probes"] = json.loads(sample.pop("probes_json"))
        return {"event": dict(event), "samples": samples}

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
                    self.send_body(200, "application/json", json.dumps(app.summary(), indent=2).encode())
                    return
                self.send_body(200, "text/plain; charset=utf-8", b"NetBlackBox is running. Use /status or /api/events.\n")

            def log_message(self, *_: object) -> None:
                return

        ThreadingHTTPServer((self.config.http_host, self.config.http_port), Handler).serve_forever()

    def run(self) -> None:
        threading.Thread(target=self._serve, daemon=True).start()
        previous_state: str | None = None
        candidate_state: str | None = None
        candidate_count = 0
        event_id: int | None = None
        event_state: str | None = None
        event_started_at: datetime | None = None
        post_event_id: int | None = None
        post_capture_until: datetime | None = None
        turbo_until: datetime | None = None
        self.logger.info("NetBlackBox forensic monitor started on %s", self.backend.name)

        while True:
            cycle_started = time.monotonic()
            gateway_ip = self.config.upstream_gateway_ip or self.backend.default_gateway() or "0.0.0.0"
            probes = self.probes.run(gateway_ip)
            observed_state = classify(probes)

            if observed_state == candidate_state:
                candidate_count += 1
            else:
                candidate_state = observed_state
                candidate_count = 1

            needed = (
                self.config.recovery_confirmation_cycles
                if observed_state in HEALTHY_STATES
                else self.config.confirmation_cycles
            )
            confirmed_state = candidate_state if candidate_count >= needed else previous_state
            current_state = confirmed_state or observed_state
            sample = Sample(
                timestamp=self.timestamp(),
                state=current_state,
                gateway_ip=gateway_ip,
                probes=asdict(probes),
            )
            self.ring.append(sample)
            self.save_sample(sample)

            state_changed = confirmed_state is not None and confirmed_state != previous_state
            if state_changed:
                self.logger.info("%s :: %s", confirmed_state, json.dumps(asdict(probes)))
                if event_id is not None and event_started_at is not None and event_state is not None:
                    self.close_event(event_id, event_started_at, event_state)
                    post_event_id = event_id
                    post_capture_until = self.now() + timedelta(seconds=self.config.post_event_capture_seconds)
                    event_id = None
                    event_started_at = None
                    event_state = None

                if confirmed_state not in HEALTHY_STATES:
                    event_started_at = self.now()
                    event_state = confirmed_state
                    event_id = self.open_event(confirmed_state, probes)
                    turbo_until = self.now() + timedelta(seconds=self.config.turbo_duration_seconds)
                    threading.Thread(
                        target=self.collect_diagnostics,
                        args=(event_id, confirmed_state, probes, gateway_ip),
                        daemon=True,
                    ).start()
                previous_state = confirmed_state

            if event_id is not None:
                self.save_event_sample(event_id, "active", sample)
            if post_event_id is not None and post_capture_until is not None:
                if self.now() <= post_capture_until:
                    self.save_event_sample(post_event_id, "post", sample)
                else:
                    post_event_id = None
                    post_capture_until = None

            with self.snapshot_lock:
                self.snapshot = {
                    "timestamp": self.timestamp(),
                    "platform": self.backend.name,
                    "state": current_state,
                    "severity": severity_for(current_state),
                    "gateway_ip": gateway_ip,
                    "modem_reachable": probes.modem_reachable,
                    "internet_reachable": probes.internet_reachable,
                    "active_event_id": event_id,
                    "active_event_started_at": self.timestamp(event_started_at) if event_started_at else None,
                    "turbo_sampling": bool(turbo_until and self.now() <= turbo_until),
                    "probes": asdict(probes),
                }

            interval = self.config.check_interval_seconds
            if turbo_until is not None and self.now() <= turbo_until:
                interval = self.config.turbo_interval_seconds
            elapsed = time.monotonic() - cycle_started
            time.sleep(max(0.05, interval - elapsed))
