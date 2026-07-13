from __future__ import annotations

import argparse
import json
from pathlib import Path

from .app import NetBlackBoxApp
from .config import Config, default_data_dir
from .platforms import current_backend


def main() -> None:
    parser = argparse.ArgumentParser(description="NetBlackBox cross-platform network recorder")
    parser.add_argument(
        "--config",
        type=Path,
        default=default_data_dir() / "config.json",
        help="Path to the JSON configuration file",
    )
    parser.add_argument("--summary", action="store_true", help="Print a 30-day event summary and exit")
    args = parser.parse_args()

    config = Config.load(args.config)
    app = NetBlackBoxApp(config, current_backend())

    if args.summary:
        print(json.dumps(app.summary(), indent=2))
        return

    app.run()


if __name__ == "__main__":
    main()
