"""Resumable bulk import of Japan-only daily GSMaP CSV files into MySQL."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
from typing import Any, Iterable


DAILY_CSV_PATTERN = re.compile(r"^(\d{8})\.csv$")
EXPECTED_HOURS_PER_DAY = 24


@dataclass(frozen=True)
class DailyCsvFile:
    path: Path
    observation_date: date
    rows: int
    grid_cells: int
    source_files: int

    @property
    def complete(self) -> bool:
        return (
            self.source_files == EXPECTED_HOURS_PER_DAY
            and self.rows == self.grid_cells * EXPECTED_HOURS_PER_DAY
        )


def _load_daily_metadata(csv_path: Path) -> dict[str, Any] | None:
    metadata_path = csv_path.with_name(csv_path.name + ".meta.json")
    if not metadata_path.is_file():
        return None
    try:
        value = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def discover_daily_csv_files(
    csv_root: Path,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    include_incomplete: bool = False,
    limit: int | None = None,
) -> list[DailyCsvFile]:
    """Return date-ordered import candidates without modifying source CSV files."""

    candidates: list[DailyCsvFile] = []
    if not csv_root.is_dir():
        return candidates

    for path in csv_root.rglob("*.csv"):
        match = DAILY_CSV_PATTERN.fullmatch(path.name)
        if match is None:
            continue
        observation_date = datetime.strptime(match.group(1), "%Y%m%d").date()
        if start_date is not None and observation_date < start_date:
            continue
        if end_date is not None and observation_date > end_date:
            continue

        metadata = _load_daily_metadata(path)
        if metadata is None:
            if include_incomplete:
                candidates.append(DailyCsvFile(path, observation_date, 0, 0, 0))
            continue

        try:
            rows = int(metadata["rows"])
            grid_cells = int(metadata["grid_cells"])
            source_files = len(metadata["sources"])
            metadata_date = date.fromisoformat(str(metadata["observation_date"]))
        except (KeyError, TypeError, ValueError):
            if include_incomplete:
                candidates.append(DailyCsvFile(path, observation_date, 0, 0, 0))
            continue

        candidate = DailyCsvFile(
            path=path,
            observation_date=observation_date,
            rows=rows,
            grid_cells=grid_cells,
            source_files=source_files,
        )
        if metadata_date != observation_date:
            continue
        if include_incomplete or candidate.complete:
            candidates.append(candidate)

    candidates.sort(key=lambda item: (item.observation_date, str(item.path)))
    if limit is not None:
        candidates = candidates[:limit]
    return candidates


def load_grid_cells(mask_path: Path) -> list[tuple[str, int, int, float, float]]:
    with mask_path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"grid_id", "row", "column", "latitude", "longitude"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"Unexpected GSMaP grid mask header: {mask_path}")
        cells = [
            (
                row["grid_id"],
                int(row["row"]),
                int(row["column"]),
                float(row["latitude"]),
                float(row["longitude"]),
            )
            for row in reader
        ]
    if not cells:
        raise ValueError(f"GSMaP grid mask is empty: {mask_path}")
    return cells


def synchronize_grid_cells(connection: Any, mask_path: Path) -> int:
    """Upsert the small grid master before loading rainfall facts."""

    cells = load_grid_cells(mask_path)
    sql = """
        INSERT INTO gsmap_grid_cells
            (grid_id, grid_row, grid_column, latitude, longitude)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            grid_row = VALUES(grid_row),
            grid_column = VALUES(grid_column),
            latitude = VALUES(latitude),
            longitude = VALUES(longitude)
    """
    cursor = connection.cursor()
    try:
        for offset in range(0, len(cells), 1000):
            cursor.executemany(sql, cells[offset : offset + 1000])
        connection.commit()
    finally:
        cursor.close()
    return len(cells)


def _relative_file_key(csv_path: Path, csv_root: Path) -> str:
    return csv_path.resolve().relative_to(csv_root.resolve()).as_posix()


def _already_imported(
    connection: Any,
    file_key: str,
    file_size: int,
    file_mtime_ns: int,
    expected_rows: int,
) -> bool:
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT import_status, file_size, file_mtime_ns, expected_rows, imported_rows
            FROM gsmap_import_files
            WHERE file_path = %s
            """,
            (file_key,),
        )
        row = cursor.fetchone()
    finally:
        cursor.close()
    return bool(
        row
        and row[0] == "completed"
        and int(row[1]) == file_size
        and int(row[2]) == file_mtime_ns
        and int(row[3]) == expected_rows
        and int(row[4]) == expected_rows
    )


def _mark_loading(
    connection: Any,
    candidate: DailyCsvFile,
    file_key: str,
    file_size: int,
    file_mtime_ns: int,
) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO gsmap_import_files
                (file_path, observation_date, file_size, file_mtime_ns,
                 expected_rows, imported_rows, import_status, started_at,
                 completed_at, error_message)
            VALUES (%s, %s, %s, %s, %s, NULL, 'loading', CURRENT_TIMESTAMP,
                    NULL, NULL)
            ON DUPLICATE KEY UPDATE
                observation_date = VALUES(observation_date),
                file_size = VALUES(file_size),
                file_mtime_ns = VALUES(file_mtime_ns),
                expected_rows = VALUES(expected_rows),
                imported_rows = NULL,
                import_status = 'loading',
                started_at = CURRENT_TIMESTAMP,
                completed_at = NULL,
                error_message = NULL
            """,
            (
                file_key,
                candidate.observation_date,
                file_size,
                file_mtime_ns,
                candidate.rows,
            ),
        )
        connection.commit()
    finally:
        cursor.close()


def _mark_failed(connection: Any, file_key: str, error: BaseException) -> None:
    message = f"{type(error).__name__}: {error}"[:1000]
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            UPDATE gsmap_import_files
            SET import_status = 'failed', error_message = %s,
                completed_at = CURRENT_TIMESTAMP
            WHERE file_path = %s
            """,
            (message, file_key),
        )
        connection.commit()
    finally:
        cursor.close()


def import_daily_csv(
    connection: Any,
    candidate: DailyCsvFile,
    csv_root: Path,
) -> tuple[str, int]:
    """Atomically replace one UTC day's facts from a read-only source CSV."""

    stat = candidate.path.stat()
    file_key = _relative_file_key(candidate.path, csv_root)
    if _already_imported(
        connection, file_key, stat.st_size, stat.st_mtime_ns, candidate.rows
    ):
        return "skipped", candidate.rows

    _mark_loading(connection, candidate, file_key, stat.st_size, stat.st_mtime_ns)
    cursor = connection.cursor()
    try:
        cursor.execute("DROP TEMPORARY TABLE IF EXISTS gsmap_rainfall_stage")
        cursor.execute(
            """
            CREATE TEMPORARY TABLE gsmap_rainfall_stage (
                observation_time_utc DATETIME NOT NULL,
                grid_id CHAR(10) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                rain_rate_mm_h FLOAT NOT NULL,
                KEY idx_stage_grid (grid_id),
                KEY idx_stage_time (observation_time_utc)
            ) ENGINE=InnoDB
            """
        )

        infile = candidate.path.resolve().as_posix().replace("'", "''")
        cursor.execute(
            f"""
            LOAD DATA LOCAL INFILE '{infile}'
            INTO TABLE gsmap_rainfall_stage
            CHARACTER SET utf8mb4
            FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
            LINES TERMINATED BY '\n'
            IGNORE 1 LINES
            (@timestamp_utc, @grid_id, @latitude, @longitude, @rain_rate)
            SET observation_time_utc = STR_TO_DATE(
                    REPLACE(REPLACE(TRIM(@timestamp_utc), 'T', ' '), 'Z', ''),
                    '%Y-%m-%d %H:%i:%s'
                ),
                grid_id = TRIM(@grid_id),
                rain_rate_mm_h = CAST(TRIM(@rain_rate) AS FLOAT)
            """
        )

        cursor.execute(
            """
            SELECT COUNT(*),
                   SUM(observation_time_utc < %s OR observation_time_utc >= %s),
                   COUNT(DISTINCT observation_time_utc),
                   COUNT(DISTINCT grid_id)
            FROM gsmap_rainfall_stage
            """,
            (
                candidate.observation_date,
                candidate.observation_date + timedelta(days=1),
            ),
        )
        loaded_rows, outside_day, hours, grids = (
            int(value or 0) for value in cursor.fetchone()
        )
        if loaded_rows != candidate.rows:
            raise ValueError(
                f"CSV row count mismatch: expected {candidate.rows}, loaded {loaded_rows}"
            )
        if outside_day or hours != EXPECTED_HOURS_PER_DAY or grids != candidate.grid_cells:
            raise ValueError(
                "CSV coverage mismatch: "
                f"outside_day={outside_day}, hours={hours}, grids={grids}"
            )

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM gsmap_rainfall_stage AS stage
            LEFT JOIN gsmap_grid_cells AS grid ON grid.grid_id = stage.grid_id
            WHERE grid.grid_cell_id IS NULL
            """
        )
        unmatched = int(cursor.fetchone()[0])
        if unmatched:
            raise ValueError(f"CSV contains {unmatched} rows with unknown grid IDs")

        cursor.execute(
            """
            DELETE FROM gsmap_hourly_rainfall
            WHERE observation_time_utc >= %s AND observation_time_utc < %s
            """,
            (
                candidate.observation_date,
                candidate.observation_date + timedelta(days=1),
            ),
        )
        cursor.execute(
            """
            INSERT INTO gsmap_hourly_rainfall
                (observation_time_utc, observation_time_jst,
                 grid_cell_id, rain_rate_mm_h)
            SELECT stage.observation_time_utc,
                   DATE_ADD(stage.observation_time_utc, INTERVAL 9 HOUR),
                   grid.grid_cell_id,
                   stage.rain_rate_mm_h
            FROM gsmap_rainfall_stage AS stage
            JOIN gsmap_grid_cells AS grid ON grid.grid_id = stage.grid_id
            """
        )
        inserted_rows = int(cursor.rowcount)
        if inserted_rows != candidate.rows:
            raise ValueError(
                f"Inserted row count mismatch: expected {candidate.rows}, inserted {inserted_rows}"
            )
        cursor.execute(
            """
            UPDATE gsmap_import_files
            SET import_status = 'completed', imported_rows = %s,
                completed_at = CURRENT_TIMESTAMP, error_message = NULL
            WHERE file_path = %s
            """,
            (inserted_rows, file_key),
        )
        connection.commit()
        return "imported", inserted_rows
    except BaseException as error:
        connection.rollback()
        _mark_failed(connection, file_key, error)
        raise
    finally:
        cursor.close()


def import_daily_csv_files(
    connection: Any,
    candidates: Iterable[DailyCsvFile],
    csv_root: Path,
) -> dict[str, int]:
    summary = {"files_imported": 0, "files_skipped": 0, "rows_imported": 0}
    for candidate in candidates:
        status, rows = import_daily_csv(connection, candidate, csv_root)
        if status == "skipped":
            summary["files_skipped"] += 1
            print(f"[db-skipped] {candidate.path}")
        else:
            summary["files_imported"] += 1
            summary["rows_imported"] += rows
            print(f"[db-imported] {candidate.path} ({rows:,} rows)")
    return summary
