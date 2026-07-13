#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import shutil
import socket
import sqlite3
import subprocess
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

APP = "NetBlackBox"
VERSION = "0.1.0"
HEALTHY = {"OK", "OK_GATEWAY_ICMP_BLOCKED"}
DEFAULTS = {
    "base_dir": "~/netblackbox",
    "modem_ip": "192.168.1.254",
    "fastweb_gateway_ip": "100.74.248.1",
    "check_interval_seconds": 2,
    "confirmation_cycles": 2,
    "http_host": "127.0.0.1",
    "http_port": 8080,
    "public_ip_check_interval_seconds": 300,
    "retention_days": 90,
}

@dataclass
class Probes:
    modem_ping: bool
    modem_http: bool
    modem_https: bool
    gateway_ping: bool
    cloudflare_tcp: bool
    google_dns_tcp: bool
    http_internet: bool
    dns_resolution: bool

class NetBlackBox:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.cfg = self._load_config()
        self.base = Path(os.path.expanduser(self.cfg["base_dir"]))
        self.logs = self.base / "logs"
        self.diags = self.base / "diagnostics"
        self.reports = self.base / "reports"
        self.db_path = self.base / "netblackbox.sqlite3"
        for path in (self.base, self.logs, self.diags, self.reports):
            path.mkdir(parents=True, exist_ok=True)
        self.log = self._logger()
        self.lock = threading.Lock()
        self.snapshot = {"state": "STARTING", "version": VERSION}
        self._init_db()
        self._cleanup()

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(json.dumps(DEFAULTS, indent=2), encoding="utf-8")
            return dict(DEFAULTS)
        cfg = dict(DEFAULTS)
        cfg.update(json.loads(self.config_path.read_text(encoding="utf-8")))
        return cfg

    def _logger(self) -> logging.Logger:
        logger = logging.getLogger(APP)
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%dT%H:%M:%S%z")
        file_handler = logging.handlers.RotatingFileHandler(
            self.logs / "netblackbox.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        return logger

    @staticmethod
    def now() -> datetime:
        return datetime.now().astimezone()

    @staticmethod
    def ts(value: datetime | None = None) -> str:
        return (value or datetime.now().astimezone()).isoformat(timespec="seconds")

    def db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self.db() as conn:
            conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS samples(
              id INTEGER PRIMARY KEY, timestamp TEXT, state TEXT,
              modem_ok INTEGER, internet_ok INTEGER, public_ip TEXT, probes_json TEXT);
            CREATE TABLE IF NOT EXISTS events(
              id INTEGER PRIMARY KEY, start_time TEXT, end_time TEXT,
              duration_seconds REAL, state TEXT, public_ip TEXT,
              probes_json TEXT, diagnostics_path TEXT);
            CREATE INDEX IF NOT EXISTS idx_samples_time ON samples(timestamp);
            CREATE INDEX IF NOT EXISTS idx_events_time ON events(start_time);
            """)

    def _cleanup(self) -> None:
        cutoff = self.ts(self.now() - timedelta(days=int(self.cfg["retention_days"])))
        with self.db() as conn:
            conn.execute("DELETE FROM samples WHERE timestamp < ?", (cutoff,))
            conn.execute("DELETE FROM events WHERE start_time < ?", (cutoff,))

    @staticmethod
    def command(args: list[str], timeout: float = 10) -> tuple[int, str]:
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
            return proc.returncode, (proc.stdout + ("\nSTDERR:\n" + proc.stderr if proc.stderr else "")).strip()
        except Exception as exc:
            return 125, f"{type(exc).__name__}: {exc}"

    @staticmethod
    def ping(host: str) -> bool:
        try:
            return subprocess.run(
                ["/sbin/ping", "-n", "-c", "1", "-W", "1000", host],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3
            ).returncode == 0
        except Exception:
            return False

    @staticmethod
    def tcp(host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=1.5):
                return True
        except OSError:
            return False

    @staticmethod
    def dns() -> bool:
        try:
            socket.getaddrinfo("example.com", 443, type=socket.SOCK_STREAM)
            return True
        except socket.gaierror:
            return False

    @staticmethod
    def http_test() -> bool:
        try:
            req = Request("https://www.google.com/generate_204", headers={"User-Agent": f"{APP}/{VERSION}"})
            with urlopen(req, timeout=3) as response:
                return 200 <= response.status < 400
        except Exception:
            return False

    @staticmethod
    def public_ip() -> str | None:
        for url in ("https://api.ipify.org", "https://checkip.amazonaws.com"):
            try:
                with urlopen(Request(url, headers={"User-Agent": APP}), timeout=4) as response:
                    return response.read().decode().strip()
            except Exception:
                pass
        return None

    def probe(self) -> Probes:
        modem = self.cfg["modem_ip"]
        gateway = self.cfg["fastweb_gateway_ip"]
        checks = {
            "modem_ping": lambda: self.ping(modem),
            "modem_http": lambda: self.tcp(modem, 80),
            "modem_https": lambda: self.tcp(modem, 443),
            "gateway_ping": lambda: self.ping(gateway),
            "cloudflare_tcp": lambda: self.tcp("1.1.1.1", 443),
            "google_dns_tcp": lambda: self.tcp("8.8.8.8", 53),
            "http_internet": self.http_test,
            "dns_resolution": self.dns,
        }
        with ThreadPoolExecutor(max_workers=len(checks)) as pool:
            values = {name: future.result() for name, future in
                      ((name, pool.submit(fn)) for name, fn in checks.items())}
        return Probes(**values)

    @staticmethod
    def modem_ok(p: Probes) -> bool:
        return p.modem_ping or p.modem_http or p.modem_https

    @staticmethod
    def internet_ok(p: Probes) -> bool:
        return p.http_internet or p.cloudflare_tcp or p.google_dns_tcp

    def classify(self, p: Probes) -> str:
        if not self.modem_ok(p):
            return "MODEM_LAN_KO"
        if not self.internet_ok(p) and not p.gateway_ping:
            return "WAN_GATEWAY_KO"
        if not self.internet_ok(p):
            return "INTERNET_KO_MODEM_OK"
        if not p.dns_resolution:
            return "DNS_KO"
        if not p.gateway_ping:
            return "OK_GATEWAY_ICMP_BLOCKED"
        return "OK"

    def sample(self, state: str, p: Probes, public_ip: str | None) -> None:
        with self.db() as conn:
            conn.execute("INSERT INTO samples(timestamp,state,modem_ok,internet_ok,public_ip,probes_json) VALUES(?,?,?,?,?,?)",
                         (self.ts(), state, self.modem_ok(p), self.internet_ok(p), public_ip, json.dumps(asdict(p))))

    def open_event(self, state: str, p: Probes, public_ip: str | None) -> int:
        with self.db() as conn:
            cur = conn.execute("INSERT INTO events(start_time,state,public_ip,probes_json) VALUES(?,?,?,?)",
                               (self.ts(), state, public_ip, json.dumps(asdict(p))))
            return int(cur.lastrowid)

    def close_event(self, event_id: int, started: datetime) -> None:
        ended = self.now()
        with self.db() as conn:
            conn.execute("UPDATE events SET end_time=?,duration_seconds=? WHERE id=?",
                         (self.ts(ended), round((ended-started).total_seconds(), 1), event_id))

    def diagnostics(self, event_id: int, state: str, p: Probes) -> None:
        stamp = self.now().strftime("%Y%m%d_%H%M%S")
        folder = self.diags / f"{stamp}_{state.lower()}_{event_id}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "metadata.json").write_text(json.dumps({"state": state, "probes": asdict(p)}, indent=2), encoding="utf-8")
        commands = {
            "route": ["/sbin/route", "-n", "get", "default"],
            "routes": ["/usr/sbin/netstat", "-rn"],
            "arp": ["/usr/sbin/arp", "-an"],
            "dns": ["/usr/sbin/scutil", "--dns"],
            "ifconfig": ["/sbin/ifconfig"],
            "traceroute": ["/usr/sbin/traceroute", "-n", "-m", "12", "-w", "1", "1.1.1.1"],
            "curl_modem": ["/usr/bin/curl", "-vk", "--max-time", "6", f"http://{self.cfg['modem_ip']}/"],
            "curl_internet": ["/usr/bin/curl", "-v", "--max-time", "8", "https://www.google.com/generate_204"],
        }
        for name, args in commands.items():
            code, output = self.command(args, 20)
            (folder / f"{name}.txt").write_text(f"EXIT CODE: {code}\n\n{output}\n", encoding="utf-8")
        with self.db() as conn:
            conn.execute("UPDATE events SET diagnostics_path=? WHERE id=?", (str(folder), event_id))
        self.log.info("Diagnostics saved to %s", folder)

    def summary(self, days: int = 30) -> dict:
        cutoff = self.ts(self.now() - timedelta(days=days))
        with self.db() as conn:
            rows = [dict(row) for row in conn.execute("SELECT * FROM events WHERE start_time>=? ORDER BY start_time", (cutoff,))]
        completed = [row for row in rows if row["duration_seconds"] is not None]
        by_hour = {str(i): 0 for i in range(24)}
        by_day: dict[str, int] = {}
        by_state: dict[str, int] = {}
        for row in rows:
            dt = datetime.fromisoformat(row["start_time"])
            by_hour[str(dt.hour)] += 1
            by_day[str(dt.date())] = by_day.get(str(dt.date()), 0) + 1
            by_state[row["state"]] = by_state.get(row["state"], 0) + 1
        return {
            "generated_at": self.ts(), "days": days, "event_count": len(rows),
            "total_duration_seconds": round(sum(float(r["duration_seconds"]) for r in completed), 1),
            "longest_duration_seconds": max((float(r["duration_seconds"]) for r in completed), default=0),
            "by_hour": by_hour, "by_day": by_day, "by_state": by_state, "events": rows[-500:]
        }

    def report_html(self) -> str:
        data = json.dumps(self.summary(30), ensure_ascii=False)
        return f'''<!doctype html><html><head><meta charset="utf-8"><title>{APP}</title>
<style>body{{font-family:system-ui;background:#111;color:#eee;max-width:1200px;margin:auto;padding:24px}}canvas,table{{width:100%;background:#1d1d1f;margin-top:18px}}th,td{{padding:8px;border-bottom:1px solid #333;text-align:left}}</style></head>
<body><h1>{APP}</h1><div id="stats"></div><canvas id="hours" width="1100" height="280"></canvas><table><thead><tr><th>Start</th><th>Duration</th><th>State</th></tr></thead><tbody id="events"></tbody></table>
<script>const D={data};document.getElementById('stats').textContent=`Events: ${{D.event_count}} · Offline: ${{D.total_duration_seconds}}s · Longest: ${{D.longest_duration_seconds}}s`;
const c=document.getElementById('hours'),x=c.getContext('2d'),v=Object.values(D.by_hour),m=Math.max(1,...v),w=c.width/24;x.fillStyle='#1d1d1f';x.fillRect(0,0,c.width,c.height);v.forEach((n,i)=>{{let h=n/m*220;x.fillStyle='#4aa3ff';x.fillRect(i*w+2,250-h,w-4,h);x.fillStyle='#aaa';x.fillText(i,i*w+4,270)}});D.events.slice().reverse().forEach(e=>{{let r=document.createElement('tr');r.innerHTML=`<td>${{e.start_time}}</td><td>${{e.duration_seconds??'-'}}s</td><td>${{e.state}}</td>`;events.appendChild(r)}});</script></body></html>'''

    def export(self) -> Path:
        report = self.reports / "report.html"
        report.write_text(self.report_html(), encoding="utf-8")
        bundle = self.base / f"netblackbox-export-{self.now().strftime('%Y%m%d_%H%M%S')}.zip"
        with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in (self.config_path, self.db_path, report, self.logs / "netblackbox.log"):
                if path.exists(): archive.write(path, path.relative_to(self.base.parent))
            for path in self.diags.rglob("*"):
                if path.is_file(): archive.write(path, path.relative_to(self.base.parent))
        return bundle

    def serve(self) -> None:
        app = self
        class Handler(BaseHTTPRequestHandler):
            def send(self, content_type: str, body: bytes, status: int = 200) -> None:
                self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            def do_GET(self) -> None:
                if self.path in ("/", "/dashboard"):
                    self.send("text/html; charset=utf-8", app.report_html().encode())
                elif self.path == "/status":
                    with app.lock: body = json.dumps(app.snapshot, indent=2).encode()
                    self.send("application/json", body)
                elif self.path.startswith("/api/events"):
                    self.send("application/json", json.dumps(app.summary(), indent=2).encode())
                else: self.send("text/plain", b"Not found", 404)
            def log_message(self, *_: object) -> None: pass
        ThreadingHTTPServer((self.cfg["http_host"], int(self.cfg["http_port"])), Handler).serve_forever()

    def run(self) -> None:
        threading.Thread(target=self.serve, daemon=True).start()
        previous = candidate = None
        candidate_count = 0
        event_id = None
        event_start = None
        public_ip = None
        last_ip_check = 0.0
        self.log.info("%s v%s started", APP, VERSION)
        while True:
            cycle = time.monotonic()
            p = self.probe()
            observed = self.classify(p)
            if observed == candidate: candidate_count += 1
            else: candidate, candidate_count = observed, 1
            confirmed = candidate if candidate_count >= int(self.cfg["confirmation_cycles"]) else previous
            changed = confirmed is not None and confirmed != previous
            if changed:
                self.log.info("%s :: %s", confirmed, json.dumps(asdict(p)))
                if event_id is not None and event_start is not None:
                    self.close_event(event_id, event_start)
                    event_id = event_start = None
                if confirmed not in HEALTHY:
                    event_start = self.now()
                    event_id = self.open_event(confirmed, p, public_ip)
                    threading.Thread(target=self.diagnostics, args=(event_id, confirmed, p), daemon=True).start()
                previous = confirmed
            if confirmed in HEALTHY and time.monotonic() - last_ip_check >= int(self.cfg["public_ip_check_interval_seconds"]):
                new_ip = self.public_ip(); last_ip_check = time.monotonic()
                if new_ip and new_ip != public_ip: self.log.info("Public IP changed: %s -> %s", public_ip or "N/A", new_ip); public_ip = new_ip
            state = confirmed or observed
            self.sample(state, p, public_ip)
            with self.lock:
                self.snapshot = {"timestamp": self.ts(), "version": VERSION, "state": state, "modem_reachable": self.modem_ok(p), "internet_reachable": self.internet_ok(p), "public_ip": public_ip, "active_event_started_at": self.ts(event_start) if event_start else None, "probes": asdict(p)}
            time.sleep(max(0.1, float(self.cfg["check_interval_seconds"]) - (time.monotonic() - cycle)))

def main() -> None:
    parser = argparse.ArgumentParser(description=f"{APP} {VERSION}")
    parser.add_argument("--config", default=str(Path.home() / "netblackbox" / "config.json"))
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args()
    app = NetBlackBox(Path(os.path.expanduser(args.config)))
    if args.report:
        path = app.reports / "report.html"; path.write_text(app.report_html(), encoding="utf-8"); print(path)
    elif args.summary: print(json.dumps(app.summary(), indent=2))
    elif args.export: print(app.export())
    else: app.run()

if __name__ == "__main__":
    main()
