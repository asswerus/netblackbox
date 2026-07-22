from pathlib import Path

from netblackbox.storage import DATABASE_FILENAME, database_path, resolve_data_dir, resolve_path


def test_resolve_path_expands_user_and_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NBB_TEST_ROOT", str(tmp_path))

    assert resolve_path("$NBB_TEST_ROOT/data") == (tmp_path / "data").resolve()


def test_relative_data_dir_is_anchored_to_config_file(tmp_path: Path) -> None:
    config_path = tmp_path / "config" / "config.json"

    resolved = resolve_data_dir("../runtime", config_path=config_path)

    assert resolved == (tmp_path / "runtime").resolve()


def test_database_path_uses_canonical_filename(tmp_path: Path) -> None:
    assert database_path(tmp_path) == tmp_path.resolve() / DATABASE_FILENAME
