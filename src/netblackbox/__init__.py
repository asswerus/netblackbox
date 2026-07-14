"""NetBlackBox package."""

from .sqlite_guard import install_sqlite_connection_guard

install_sqlite_connection_guard()

__version__ = "0.2.0"
