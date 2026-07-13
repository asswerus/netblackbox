from __future__ import annotations

import json
import logging
import logging.handlers
import sqlite3
import threading
import time
from dataclasses import asdict
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .config import Config
from .models import ProbeResult
from .platforms import PlatformBackend
from .probes import ProbeRunner, classify

HEALTHY_STATES = {"OK", "OK_GATEWAY_ICMP_BLOCKED"}


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
        self._init_db()
        self._cleanup()

    @staticmethod
    def now() -> datetime:
        return datetime.now().astimezone()

    @staticmethod
    def timestamp(value: datetime | None = None) -> str:
        return (value or datetime.now().astimezone()).isoformat(timespec="seconds")

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
                    probes_json TEXT NOT NULL,
                    diagnostics_path TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_samples_timestamp ON samples(timestamp);
                CREATE INDEX IF NOT EXISTS idx_events_start_time ON events(start_time);
                """
            )

    def _cleanup(self) -> None:
        cutoff = self.timestamp(self.now() - timedelta(days=self.config.retention_days))
        with self.db() as connection:
            connection.execute("DELETE FROM samples WHERE timestamp < ?", (cutoff,))
            connection.execute("DELETE FROM events WHERE start_time < ?", (cutoff,))

    def save_sample(self, state: str, probes: ProbeResult) -> None:
        with self.db() as connection:
            connection.execute(
                "INSERT INTO samples(timestamp, state, probes_json) VALUES(?,?,?)",
                (self.timestamp(), state, json.dumps(asdict(probes))),
            )

    def open_event(self, state: str, probes: ProbeResult) -> int:
        with self.db() as connection:
            cursor = connection.execute(
                "INSERT INTO events(start_time, state, probes_json) VALUES(?,?,?)",
                (self.timestamp(), state, json.dumps(asdict(probes))),
            )
            return int(cursor.lastrowid)

    def close_event(self, event_id: int, started_at: datetime) -> None:
        ended_at = self.now()
        with self.db() as connection:
            connection.execute(
                "UPDATE events SET end_time=?, duration_seconds=? WHERE id=?",
                (self.timestamp(ended_at), round((ended_at - started_at).total_seconds(), 1), event_id),
            )

    def collect_diagnostics(self, event_id: int, state: str, probes: ProbeResult, gateway_ip: str) -> None:
        folder = self.diagnostics_dir / f"{self.now().strftime('%Y%m%d_%H%M%S')}_{state.lower()}_{event_id}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "metadata.json").write_text(
            json.dumps({"state": state, "platform": self.backend.name, "probes": asdict(probes)}, indent=2),
            encoding="utf-8",
        )
        for command in self.backend.diagnostics(self.config.modem_ip, gateway_ip):
            code, output = self.backend.run(command.args, command.timeout)
            (folder / f"{command.name}.txt").write_text(
                f"COMMAND: {' '.join(command.args)}\nEXIT CODE: {code}\n\n{output}\n", encoding="utf-8"
            )
        with self.db() as connection:
            connection.execute("UPDATE events SET diagnostics_path=? WHERE id=?", (str(folder), event_id))
        self.logger.info("Diagnostics saved to %s", folder)

    def summary(self, days: int = 30) -> dict[str, Any]:
        cutoff = self.timestamp(self.now() - timedelta(days=days))
        with self.db() as connection:
            rows = [dict(row) for row in connection.execute(
                "SELECT * FROM events WHERE start_time >= ? ORDER BY start_time", (cutoff,)
            )]
        completed = [row for row in rows if row["duration_seconds"] is not None]
        by_hour = {str(hour): 0 for hour in range(24)}
        by_state: dict[str, int] = {}
        for row in rows:
            hour = datetime.fromisoformat(row["start_time"]).hour
            by_hour[str(hour)] += 1
            by_state[row["state"]] = by_state.get(row["state"], 0) + 1
        return {
            "generated_at": self.timestamp(),
            "platform": self.backend.name,
            "event_count": len(rows),
            "total_duration_seconds": round(sum(float(row["duration_seconds"]) for row in completed), 1),
            "longest_duration_seconds": max((float(row["duration_seconds"]) for row in completed), default=0),
            "by_hour": by_hour,
            "by_state": by_state,
            "events": rows[-500:],
        }

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
                elif self.path.startswith("/api/events"):
                    self.send_body(200, "application/json", json.dumps(app.summary(), indent=2).encode())
                else:
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
        event_started_at: datetime | None = None
        self.logger.info("NetBlackBox started on %s", self.backend.name)

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

            confirmed_state = candidate_state if candidate_count >= self.config.confirmation_cycles else previous_state
            state_changed = confirmed_state is not None and confirmed_state != previous_state

            if state_changed:
                self.logger.info("%s :: %s", confirmed_state, json.dumps(asdict(probes)))
                if event_id is not None and event_started_at is not None:
                    self.close_event(event_id, event_started_at)
                    event_id = None
                    event_started_at = None
                if confirmed_state not in HEALTHY_STATES:
                    event_started_at = self.now()
                    event_id = self.open_event(confirmed_state, probes)
                    threading.Thread(
                        target=self.collect_diagnostics,
                        args=(event_id, confirmed_state, probes, gateway_ip),
                        daemon=True,
                    ).start()
                previous_state = confirmed_state

            current_state = confirmed_state or observed_state
            self.save_sample(current_state, probes)
            with self.snapshot_lock:
                self.snapshot = {
                    "timestamp": self.timestamp(),
                    "platform": self.backend.name,
                    "state": current_state,
                    "gateway_ip": gateway_ip,
                    "modem_reachable": probes.modem_reachable,
                    "internet_reachable": probes.internet_reachable,
                    "active_event_started_at": self.timestamp(event_started_at) if event_started_at else None,
                    "probes": asdict(probes),
                }

            elapsed = time.monotonic() - cycle_started
            time.sleep(max(0.1, self.config.check_interval_seconds - elapsed))
