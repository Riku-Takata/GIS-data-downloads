import csv
from datetime import date
import gzip
import json
from pathlib import Path
import struct
import zipfile

import shapefile

from app.services import gsmap_japan_csv_service as service
from app.services.gsmap_japan_csv_service import (
    GsmapGridCell,
    build_daily_csv_path,
    build_japan_grid_mask,
    convert_gsmap_day_to_csv,
    parse_observation_timestamp,
)


def test_grid_coordinates_match_official_gsmap_layout():
    first = GsmapGridCell(row=0, column=0)
    last = GsmapGridCell(row=1199, column=3599)

    assert first.latitude == 59.95
    assert first.longitude == 0.05
    assert first.flat_index == 0
    assert last.latitude == -59.95
    assert last.longitude == 359.95
    assert last.flat_index == 4_319_999


def test_build_mask_uses_positive_area_polygon_intersection(tmp_path):
    source_dir = tmp_path / "shape"
    source_dir.mkdir()
    base = source_dir / "sample_prefecture"
    writer = shapefile.Writer(str(base), shapeType=shapefile.POLYGON)
    writer.field("N03_001", "C", size=20)
    writer.poly(
        [
            [
                [139.01, 35.01],
                [139.01, 35.09],
                [139.09, 35.09],
                [139.09, 35.01],
                [139.01, 35.01],
            ]
        ]
    )
    writer.record("test")
    writer.close()

    archive_path = tmp_path / "N03-test_GML.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for suffix in (".shp", ".shx", ".dbf"):
            archive.write(base.with_suffix(suffix), f"sample_prefecture{suffix}")

    mask_path = tmp_path / "mask.csv"
    cells = build_japan_grid_mask(archive_path, mask_path)

    assert cells == [GsmapGridCell(row=249, column=1390)]
    assert mask_path.is_file()
    metadata = json.loads(
        mask_path.with_name("mask.csv.meta.json").read_text(encoding="utf-8")
    )
    assert metadata["grid_cells"] == 1


def test_convert_daily_csv_is_atomic_and_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "EXPECTED_BINARY_BYTES", 8)
    source = tmp_path / "gsmap_mvk.20140101.0000.v8.0000.0.dat.gz"
    with gzip.open(source, "wb") as stream:
        stream.write(struct.pack("<2f", 1.25, -99.0))

    cells = [GsmapGridCell(row=0, column=0), GsmapGridCell(row=0, column=1)]
    output = tmp_path / "20140101.csv.gz"
    result = convert_gsmap_day_to_csv([source], output, cells)

    assert result.status == "converted"
    assert result.observation_date == date(2014, 1, 1)
    assert result.rows == 2
    assert not output.with_name(output.name + ".part").exists()
    with gzip.open(output, "rt", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0] == {
        "timestamp_utc": "2014-01-01T00:00:00Z",
        "grid_id": "r0000c0000",
        "latitude": "59.95",
        "longitude": "0.05",
        "rain_rate_mm_h": "1.25",
    }
    assert rows[1]["rain_rate_mm_h"] == "-99"

    unchanged = convert_gsmap_day_to_csv([source], output, cells)
    assert unchanged.status == "skipped"


def test_timestamp_and_daily_output_path():
    source = Path("gsmap_mvk.20140102.2300.v8.0000.0.dat.gz")
    assert parse_observation_timestamp(source).isoformat() == "2014-01-02T23:00:00+00:00"
    assert build_daily_csv_path(
        Path("csv"),
        "standard/v8",
        "hourly",
        date(2014, 1, 2),
        compression="gzip",
    ) == Path("csv/standard/v8/hourly/2014/01/20140102.csv.gz")
