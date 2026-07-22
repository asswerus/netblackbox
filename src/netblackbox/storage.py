from __future__ import annotations

import os
import sys
from pathlib import Path

DATABASE_FILENAME = "netblackbox.sqlite3"
CONFIG_FILENAME = "config.json"


def default_data_dir() -> Path:
    """Return the platform-native directory used for persistent application data."""
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(root) / "NetBlackBox"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "NetBlackBox"
    return Path.home() / ".local" / "share" / "netblackbox"


def default_config_path() -> Path:
    """Return the default configuration file path."""
    return default_data_dir() / CONFIG_FILENAME


def resolve_path(path: str | Path, *, relative_to: Path | None = None) -> Path:
    """Expand and normalize a path, optionally anchoring relative values."""
    expanded = Path(os.path.expandvars(os.path.expanduser(str(path))))
    if not expanded.is_absolute() and relative_to is not None:
        expanded = relative_to / expanded
    return expanded.resolve(strict=False)


def resolve_data_dir(value: str | Path, *, config_path: Path | None = None) -> Path:
    """Resolve a configured data directory relative to its configuration file."""
    anchor = None if config_path is None else resolve_path(config_path).parent
    return resolve_path(value, relative_to=anchor)


def database_path(data_dir: str | Path) -> Path:
    """Return the canonical SQLite database path for a data directory."""
    return resolve_path(data_dir) / DATABASE_FILENAME
