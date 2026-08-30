#!/usr/bin/env python3
"""Import the N03 Japan land polygons used by GSMaP masking into MySQL."""

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

from app.services.japan_boundary_mysql_service import import_n03_boundaries  # noqa: E402


def _latest_n03_archive() -> Path:
    candidates = sorted((PROJECT_ROOT / "downloads" / "n03-source").glob("N03-*_GML.zip"))
    if not candidates:
        return PROJECT_ROOT / "downloads" / "n03-source" / "N03-20260101_GML.zip"
    return candidates[-1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", default=str(_latest_n03_archive()))
    parser.add_argument(
        "--env-file",
        default=str(PROJECT_ROOT / "infrastructure" / "mysql" / ".env.mysql"),
    )
    parser.add_argument("--batch-size", type=int, default=250)
    args = parser.parse_args(argv)

    load_dotenv(Path(args.env_file).resolve(), override=False)
    import mysql.connector

    connection = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        database=os.getenv("MYSQL_DATABASE", "gsmap_japan"),
        user=os.getenv("MYSQL_USER", "gsmap_app"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        autocommit=False,
        connection_timeout=30,
    )
    try:
        result = import_n03_boundaries(
            connection, Path(args.archive), batch_size=args.batch_size
        )
    finally:
        connection.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
