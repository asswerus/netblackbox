from __future__ import annotations

import argparse
import json
from pathlib import Path

from .bundle_analysis import analyze_bundle
from .bundle_verifier import render_verification, verify_bundle
from .config import Config
from .database_backup import create_database_backup
from .forensic_bundle import create_forensic_bundle
from .platforms import current_backend
from .server_app import IncidentApiApp
from .storage import database_path, default_config_path, resolve_path


def main() -> None:
    parser = argparse.ArgumentParser(description="NetBlackBox cross-platform network recorder")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("run", "bundle", "analyze", "verify"),
        default="run",
        help="Run the monitor, create a forensic bundle, analyze one, or verify its integrity",
    )
    parser.add_argument(
        "bundle_path",
        nargs="?",
        type=Path,
        help="Forensic bundle ZIP to analyze or verify",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=default_config_path(),
        help="Path to the JSON configuration file",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        help="Override the persistent data directory from the configuration file",
    )
    parser.add_argument(
        "--summary", action="store_true", help="Print a 30-day event summary and exit"
    )
    parser.add_argument("--output", type=Path, help="Bundle ZIP destination")
    parser.add_argument("--days", type=int, default=30, help="Number of days included in a bundle")
    args = parser.parse_args()

    if args.command in {"analyze", "verify"}:
        if args.bundle_path is None:
            parser.error(f"{args.command} requires a bundle ZIP path")
        try:
            bundle_path = resolve_path(args.bundle_path)
            if args.command == "verify":
                result = verify_bundle(bundle_path)
                print(render_verification(result))
                if not result.is_valid:
                    raise SystemExit(1)
            else:
                print(analyze_bundle(bundle_path))
        except (FileNotFoundError, ValueError) as error:
            parser.exit(2, f"error: {error}\n")
        return

    if args.bundle_path is not None:
        parser.error("bundle_path is only valid with the analyze or verify command")

    config = Config.load(args.config)
    if args.data_dir is not None:
        config.data_dir = str(resolve_path(args.data_dir))
    db_path = database_path(config.base_dir)

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

    create_database_backup(db_path)
    app = IncidentApiApp(config, current_backend())

    if args.summary:
        print(json.dumps(app.summary(), indent=2))
        return

    app.run()


if __name__ == "__main__":
    main()
