import sqlite3

import pytest
from netblackbox.sqlite_guard import install_sqlite_connection_guard


def test_connection_context_closes_database(tmp_path) -> None:
    install_sqlite_connection_guard()
    connection = sqlite3.connect(tmp_path / "guard.sqlite3")

    with connection:
        connection.execute("CREATE TABLE samples(id INTEGER PRIMARY KEY)")

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")


def test_guard_installation_is_idempotent(tmp_path) -> None:
    install_sqlite_connection_guard()
    install_sqlite_connection_guard()

    with sqlite3.connect(tmp_path / "idempotent.sqlite3") as connection:
        connection.execute("SELECT 1")
