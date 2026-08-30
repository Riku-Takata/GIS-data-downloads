#!/usr/bin/env python3
"""Verify the complete MySQL import, then remove large GSMaP source trees."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.gsmap_ftp_service import parse_date_argument  # noqa: E402
from app.services.gsmap_mysql_import_service import (  # noqa: E402
    discover_daily_csv_files,
)


@dataclass(frozen=True)
class CleanupVerification:
    csv_files: int
    expected_rows: int
    database_manifest_files: int
    database_manifest_rows: int
    database_fact_rows: int
    binary_files: int
    expected_binary_files: int
    boundary_features: int
    targets: tuple[str, ...]


def _assert_safe_target(target: Path, downloads_root: Path) -> Path:
    resolved = target.resolve()
    root = downloads_root.resolve()
    if resolved.parent.parent != root or resolved.name != "standard":
        raise ValueError(f"Refusing unsafe cleanup target: {resolved}")
    return resolved


def _fetch_import_manifest(connection: Any) -> dict[str, tuple[Any, ...]]:
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT file_path, observation_date, file_size, file_mtime_ns,
                   expected_rows, imported_rows, import_status
            FROM gsmap_import_files
            """
        )
        return {str(row[0]): tuple(row[1:]) for row in cursor.fetchall()}
    finally:
        cursor.close()


def verify_cleanup_preconditions(
    connection: Any,
    *,
    csv_root: Path,
    binary_root: Path,
    start_date: date,
    end_date: date,
) -> CleanupVerification:
    candidates = discover_daily_csv_files(
        csv_root, start_date=start_date, end_date=end_date
    )
    all_daily_csvs = sorted(csv_root.rglob("????????.csv"))
    if len(candidates) != len(all_daily_csvs):
        raise RuntimeError(
            "Not every daily CSV has valid 24-hour completion metadata: "
            f"complete={len(candidates)}, all={len(all_daily_csvs)}"
        )
    if not candidates:
        raise RuntimeError("No completed GSMaP CSV files found")

    manifest = _fetch_import_manifest(connection)
    expected_rows = 0
    for candidate in candidates:
        key = candidate.path.resolve().relative_to(csv_root.resolve()).as_posix()
        if key not in manifest:
            raise RuntimeError(f"CSV is missing from DB import manifest: {key}")
        observation_date, size, mtime_ns, manifest_rows, imported_rows, status = manifest[key]
        stat = candidate.path.stat()
        if (
            observation_date != candidate.observation_date
            or int(size) != stat.st_size
            or int(mtime_ns) != stat.st_mtime_ns
            or int(manifest_rows) != candidate.rows
            or int(imported_rows or 0) != candidate.rows
            or status != "completed"
        ):
            raise RuntimeError(f"CSV/DB manifest mismatch: {key}")
        expected_rows += candidate.rows

    completed_rows = sum(
        int(values[4] or 0)
        for values in manifest.values()
        if values[5] == "completed"
    )
    completed_files = sum(1 for values in manifest.values() if values[5] == "completed")
    if completed_files != len(candidates) or completed_rows != expected_rows:
        raise RuntimeError(
            "DB import manifest totals do not match CSV totals: "
            f"files={completed_files}/{len(candidates)}, "
            f"rows={completed_rows}/{expected_rows}"
        )

    cursor = connection.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM gsmap_hourly_rainfall")
        fact_rows = int(cursor.fetchone()[0])
        if fact_rows != expected_rows:
            raise RuntimeError(
                f"Fact table count mismatch: db={fact_rows}, expected={expected_rows}"
            )
        cursor.execute(
            """
            SELECT COALESCE(SUM(imported_feature_count), 0)
            FROM japan_boundary_datasets WHERE import_status='completed'
            """
        )
        boundary_features = int(cursor.fetchone()[0])
        if boundary_features <= 0:
            raise RuntimeError("No completed Japan boundary dataset in MySQL")
    finally:
        cursor.close()

    binary_files = sum(1 for _ in binary_root.rglob("*.dat.gz"))
    expected_binary_files = len(candidates) * 24
    if binary_files != expected_binary_files:
        raise RuntimeError(
            "GSMaP binary count does not match completed CSV hours: "
            f"binary={binary_files}, expected={expected_binary_files}"
        )

    downloads_root = PROJECT_ROOT / "downloads"
    targets = (
        str(_assert_safe_target(binary_root / "standard", downloads_root)),
        str(_assert_safe_target(csv_root / "standard", downloads_root)),
    )
    return CleanupVerification(
        csv_files=len(candidates),
        expected_rows=expected_rows,
        database_manifest_files=completed_files,
        database_manifest_rows=completed_rows,
        database_fact_rows=fact_rows,
        binary_files=binary_files,
        expected_binary_files=expected_binary_files,
        boundary_features=boundary_features,
        targets=targets,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=parse_date_argument, default=date(2014, 1, 1))
    parser.add_argument("--end", type=parse_date_argument, default=parse_date_argument("today"))
    parser.add_argument("--yes", action="store_true", help="Delete after all checks pass")
    parser.add_argument(
        "--env-file",
        default=str(PROJECT_ROOT / "infrastructure" / "mysql" / ".env.mysql"),
    )
    args = parser.parse_args(argv)
    load_dotenv(Path(args.env_file).resolve(), override=False)
    import mysql.connector

    csv_root = (PROJECT_ROOT / "downloads" / "gsmap-japan-csv").resolve()
    binary_root = (PROJECT_ROOT / "downloads" / "gsmap").resolve()
    connection = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        database=os.getenv("MYSQL_DATABASE", "gsmap_japan"),
        user=os.getenv("MYSQL_USER", "gsmap_app"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        connection_timeout=30,
    )
    try:
        result = verify_cleanup_preconditions(
            connection,
            csv_root=csv_root,
            binary_root=binary_root,
            start_date=args.start,
            end_date=args.end,
        )
    finally:
        connection.close()

    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    if not args.yes:
        print("Verification passed; no files deleted. Add --yes to remove listed targets.")
        return 0
    for target_text in result.targets:
        target = Path(target_text)
        if target.is_dir():
            shutil.rmtree(target)
            print(f"[deleted] {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
