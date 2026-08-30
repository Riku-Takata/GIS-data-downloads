#!/usr/bin/env python3
"""Export N03 polygons stored in MySQL as a GeoJSON FeatureCollection."""

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

from app.services.japan_boundary_mysql_service import (  # noqa: E402
    iter_boundary_geojson_features,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output")
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--prefecture-code", default=None)
    parser.add_argument(
        "--env-file",
        default=str(PROJECT_ROOT / "infrastructure" / "mysql" / ".env.mysql"),
    )
    args = parser.parse_args(argv)
    load_dotenv(Path(args.env_file).resolve(), override=False)
    import mysql.connector

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial = output_path.with_name(output_path.name + ".part")
    connection = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        database=os.getenv("MYSQL_DATABASE", "gsmap_japan"),
        user=os.getenv("MYSQL_READER_USER", "gsmap_reader"),
        password=os.getenv("MYSQL_READER_PASSWORD", ""),
        connection_timeout=30,
    )
    count = 0
    try:
        with partial.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write('{"type":"FeatureCollection","features":[')
            for feature in iter_boundary_geojson_features(
                connection,
                dataset_key=args.dataset,
                prefecture_code=args.prefecture_code,
            ):
                if count:
                    stream.write(",")
                json.dump(feature, stream, ensure_ascii=False, separators=(",", ":"))
                count += 1
            stream.write("]}")
        os.replace(partial, output_path)
    finally:
        connection.close()
    print(json.dumps({"output": str(output_path), "features": count}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
