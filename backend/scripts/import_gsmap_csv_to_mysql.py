#!/usr/bin/env python3
"""Import completed Japan-only GSMaP daily CSVs into the local MySQL server."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.gsmap_ftp_service import parse_date_argument  # noqa: E402
from app.services.gsmap_mysql_import_service import (  # noqa: E402
    discover_daily_csv_files,
    import_daily_csv_files,
    synchronize_grid_cells,
)


def _path_from_project(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import completed Japan-only GSMaP daily CSVs into MySQL."
    )
    parser.add_argument(
        "--env-file",
        default=str(PROJECT_ROOT / "infrastructure" / "mysql" / ".env.mysql"),
        help="MySQL environment file (default: infrastructure/mysql/.env.mysql)",
    )
    parser.add_argument(
        "--csv-dir",
        default=os.getenv("GSMAP_JAPAN_CSV_DIR", "downloads/gsmap-japan-csv"),
    )
    parser.add_argument("--mask", default=None, help="Grid mask CSV path")
    parser.add_argument("--start", type=parse_date_argument, default=None)
    parser.add_argument("--end", type=parse_date_argument, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--include-incomplete",
        action="store_true",
        help="Include files lacking the normal 24-hour completion metadata",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--database", default=None)
    parser.add_argument("--user", default=None)
    parser.add_argument("--password", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    env_file = Path(args.env_file).expanduser().resolve()
    load_dotenv(env_file, override=False)

    csv_root = _path_from_project(args.csv_dir).resolve()
    mask_path = (
        _path_from_project(args.mask).resolve()
        if args.mask
        else csv_root / "_mask" / "gsmap_japan_grid_mask.csv"
    )
    candidates = discover_daily_csv_files(
        csv_root,
        start_date=args.start,
        end_date=args.end,
        include_incomplete=args.include_incomplete,
        limit=args.limit,
    )
    preview = {
        "status": "dry-run" if args.dry_run else "ready",
        "csv_dir": str(csv_root),
        "mask": str(mask_path),
        "files": len(candidates),
        "expected_rows": sum(item.rows for item in candidates),
        "first_date": candidates[0].observation_date.isoformat() if candidates else None,
        "last_date": candidates[-1].observation_date.isoformat() if candidates else None,
    }
    if args.dry_run:
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0
    if not candidates:
        print(json.dumps({**preview, "status": "no-files"}, ensure_ascii=False, indent=2))
        return 0
    if not mask_path.is_file():
        raise FileNotFoundError(f"GSMaP grid mask not found: {mask_path}")

    try:
        import mysql.connector
    except ImportError as error:
        raise RuntimeError(
            "mysql-connector-python is not installed; run pip install -r backend/requirements.txt"
        ) from error

    config = {
        "host": args.host or os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": args.port or int(os.getenv("MYSQL_PORT", "3306")),
        "database": args.database or os.getenv("MYSQL_DATABASE", "gsmap_japan"),
        "user": args.user or os.getenv("MYSQL_USER", "gsmap_app"),
        "password": args.password or os.getenv("MYSQL_PASSWORD", ""),
        "allow_local_infile": True,
        "autocommit": False,
        "connection_timeout": 20,
    }
    connection = mysql.connector.connect(**config)
    try:
        grid_cells = synchronize_grid_cells(connection, mask_path)
        summary = import_daily_csv_files(connection, candidates, csv_root)
    finally:
        connection.close()

    print(
        json.dumps(
            {
                "status": "completed",
                "grid_cells": grid_cells,
                "candidate_files": len(candidates),
                **summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
