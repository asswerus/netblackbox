from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .storage import default_data_dir, resolve_data_dir, resolve_path


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
    _config_path: Path | None = field(default=None, init=False, repr=False, compare=False)

    @property
    def base_dir(self) -> Path:
        return resolve_data_dir(self.data_dir, config_path=self._config_path)

    @classmethod
    def load(cls, path: Path) -> "Config":
        resolved_path = resolve_path(path)
        if not resolved_path.exists():
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            cfg = cls()
            cfg._config_path = resolved_path
            resolved_path.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
            return cfg
        raw = json.loads(resolved_path.read_text(encoding="utf-8"))
        allowed = {
            key
            for key, definition in cls.__dataclass_fields__.items()
            if definition.init
        }
        cfg = cls(**{key: value for key, value in raw.items() if key in allowed})
        cfg._config_path = resolved_path
        return cfg
