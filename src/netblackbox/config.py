from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path


def default_data_dir() -> Path:
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(root) / "NetBlackBox"
    return Path.home() / ".local" / "share" / "netblackbox"


@dataclass(slots=True)
class Config:
    data_dir: str = str(default_data_dir())
    modem_ip: str = "192.168.1.254"
    upstream_gateway_ip: str | None = None
    check_interval_seconds: float = 2.0
    confirmation_cycles: int = 2
    socket_timeout_seconds: float = 1.5
    http_timeout_seconds: float = 3.0
    public_ip_check_interval_seconds: int = 300
    http_host: str = "127.0.0.1"
    http_port: int = 8080
    retention_days: int = 90

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
