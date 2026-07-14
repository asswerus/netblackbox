from __future__ import annotations

import sqlite3
from types import TracebackType
from typing import Any, Literal, cast

_original_connect = sqlite3.connect
_installed = False


class ClosingConnection(sqlite3.Connection):
    """SQLite connection that also closes when its transaction context exits."""

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def _connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
    kwargs.setdefault("factory", ClosingConnection)
    return cast(sqlite3.Connection, _original_connect(*args, **kwargs))


def install_sqlite_connection_guard() -> None:
    """Make ``with sqlite3.connect(...)`` close connections after commit/rollback."""
    global _installed
    if _installed:
        return
    sqlite3.connect = _connect  # type: ignore[assignment]
    _installed = True
