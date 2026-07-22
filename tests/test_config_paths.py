import json
from pathlib import Path

from netblackbox.config import Config


def test_config_resolves_relative_data_dir_from_config_location(tmp_path: Path) -> None:
    config_path = tmp_path / "settings" / "config.json"
    config_path.parent.mkdir()
    config_path.write_text(json.dumps({"data_dir": "../runtime"}), encoding="utf-8")

    config = Config.load(config_path)

    assert config.base_dir == (tmp_path / "runtime").resolve()


def test_new_config_does_not_persist_internal_path(tmp_path: Path) -> None:
    config_path = tmp_path / "settings" / "config.json"

    Config.load(config_path)

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert "_config_path" not in payload
