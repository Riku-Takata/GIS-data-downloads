from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from app.services.gsmap_mysql_import_service import (
    discover_daily_csv_files,
    load_grid_cells,
)


def _write_day(root: Path, day: str, *, hours: int = 24, rows: int = 48) -> Path:
    path = root / day[:4] / day[4:6] / f"{day}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "timestamp_utc,grid_id,latitude,longitude,rain_rate_mm_h\n",
        encoding="utf-8",
    )
    metadata = {
        "observation_date": date(
            int(day[:4]), int(day[4:6]), int(day[6:8])
        ).isoformat(),
        "grid_cells": 2,
        "sources": [{"name": str(index)} for index in range(hours)],
        "rows": rows,
    }
    path.with_name(path.name + ".meta.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    return path


def test_discover_only_complete_daily_csvs(tmp_path: Path) -> None:
    complete = _write_day(tmp_path, "20140101")
    _write_day(tmp_path, "20140102", hours=23, rows=46)
    (tmp_path / "_mask").mkdir()
    (tmp_path / "_mask" / "gsmap_japan_grid_mask.csv").write_text(
        "grid_id,row,column,latitude,longitude\n", encoding="utf-8"
    )

    candidates = discover_daily_csv_files(tmp_path)

    assert [candidate.path for candidate in candidates] == [complete]
    assert candidates[0].complete


def test_discover_applies_date_range_and_limit(tmp_path: Path) -> None:
    _write_day(tmp_path, "20140101")
    second = _write_day(tmp_path, "20140102")
    _write_day(tmp_path, "20140103")

    candidates = discover_daily_csv_files(
        tmp_path,
        start_date=date(2014, 1, 2),
        end_date=date(2014, 1, 3),
        limit=1,
    )

    assert [candidate.path for candidate in candidates] == [second]


def test_load_grid_cells(tmp_path: Path) -> None:
    mask = tmp_path / "mask.csv"
    mask.write_text(
        "grid_id,row,column,latitude,longitude\n"
        "r0144c1409,144,1409,45.55,140.95\n",
        encoding="utf-8",
    )

    assert load_grid_cells(mask) == [("r0144c1409", 144, 1409, 45.55, 140.95)]
