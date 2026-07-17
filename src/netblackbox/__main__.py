from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import Config, default_data_dir
from .database_backup import create_database_backup
from .forensic_bundle import create_forensic_bundle
from .platforms import current_backend
from .server_app import IncidentApiApp


def main() -> None:
    parser = argparse.ArgumentParser(description="NetBlackBox cross-platform network recorder")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("run", "bundle"),
        default="run",
        help="Run the monitor or create an offline forensic bundle",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=default_data_dir() / "config.json",
        help="Path to the JSON configuration file",
    )
    parser.add_argument(
        "--summary", action="store_true", help="Print a 30-day event summary and exit"
    )
    parser.add_argument("--output", type=Path, help="Bundle ZIP destination")
    parser.add_argument("--days", type=int, default=30, help="Number of days included in a bundle")
    args = parser.parse_args()

    config = Config.load(args.config)
    database_path = config.base_dir / "netblackbox.sqlite3"

    if args.command == "bundle":
        backend = current_backend()
        bundle = create_forensic_bundle(
            config.base_dir,
            output_path=args.output,
            days=args.days,
            platform=backend.name,
        )
        print(bundle)
        return

    create_database_backup(database_path)
    app = IncidentApiApp(config, current_backend())

    if args.summary:
        print(json.dumps(app.summary(), indent=2))
        return

    app.run()


if __name__ == "__main__":
    main()
