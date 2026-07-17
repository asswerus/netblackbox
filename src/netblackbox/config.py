from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


def default_data_dir() -> Path:
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(root) / "NetBlackBox"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "NetBlackBox"
    return Path.home() / ".local" / "share" / "netblackbox"


@dataclass(slots=True)
class Config:
    data_dir: str = str(default_data_dir())
    modem_ip: str = "192.168.1.254"
    upstream_gateway_ip: str | None = None
    check_interval_seconds: float = 2.0
    fast_interval_seconds: float = 0.5
    turbo_interval_seconds: float = 0.25
    fast_duration_seconds: float = 10.0
    turbo_duration_seconds: int = 60
    confirmation_cycles: int = 2
    recovery_confirmation_cycles: int = 2
    ring_buffer_seconds: int = 60
    post_event_capture_seconds: int = 30
    diagnostic_repeat_interval_seconds: int = 3
    diagnostic_repeat_count: int = 4
    socket_timeout_seconds: float = 1.5
    http_timeout_seconds: float = 3.0
    public_ip_check_interval_seconds: int = 300
    http_host: str = "127.0.0.1"
    http_port: int = 8080
    retention_days: int = 90
    external_probe_plugins: list[str] = field(default_factory=list)

    @property
    def base_dir(self) -> Path:
        return Path(os.path.expanduser(self.data_dir))

    @classmethod
    def load(cls, path: Path) -> "Config":
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            cfg = cls()
            path.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
            return cfg
        raw = json.loads(path.read_text(encoding="utf-8"))
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in raw.items() if key in allowed})