"""Create Japan-only CSV partitions from global GSMaP binary rainfall grids."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import gzip
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile
from typing import Any, Iterable, Iterator, TextIO
import zipfile


GRID_COLUMNS = 3600
GRID_ROWS = 1200
GRID_RESOLUTION = 0.1
GRID_NORTH = 60.0
EXPECTED_BINARY_BYTES = GRID_COLUMNS * GRID_ROWS * 4
MASK_FORMAT_VERSION = 1
CSV_FORMAT_VERSION = 1
_TIMESTAMP_PATTERN = re.compile(r"\.(\d{8})\.(\d{4})\.")


@dataclass(frozen=True)
class GsmapGridCell:
    """One original 0.1-degree GSMaP grid cell that overlaps Japanese land."""

    row: int
    column: int

    @property
    def grid_id(self) -> str:
        return f"r{self.row:04d}c{self.column:04d}"

    @property
    def latitude(self) -> float:
        return round(GRID_NORTH - (self.row + 0.5) * GRID_RESOLUTION, 10)

    @property
    def longitude(self) -> float:
        return round((self.column + 0.5) * GRID_RESOLUTION, 10)

    @property
    def flat_index(self) -> int:
        return self.row * GRID_COLUMNS + self.column


@dataclass(frozen=True)
class GsmapCsvResult:
    status: str
    output_path: Path
    observation_date: date
    source_files: int
    grid_cells: int
    rows: int
    size: int

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["output_path"] = str(self.output_path.resolve())
        data["observation_date"] = self.observation_date.isoformat()
        return data


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    with partial.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(partial, path)


def _boundary_signature(boundary_zip: Path) -> dict[str, Any]:
    stat = boundary_zip.stat()
    return {
        "path": str(boundary_zip.resolve()),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _find_prefecture_shapefile(archive: zipfile.ZipFile) -> tuple[str, dict[str, str]]:
    files = {
        Path(info.filename).name.lower(): info.filename
        for info in archive.infolist()
        if not info.is_dir()
    }
    shp_candidates = [
        original
        for lower_name, original in files.items()
        if lower_name.endswith("_prefecture.shp")
    ]
    if not shp_candidates:
        shp_candidates = [
            original for lower_name, original in files.items() if lower_name.endswith(".shp")
        ]
    if not shp_candidates:
        raise ValueError(f"No shapefile found in boundary archive: {archive.filename}")

    shp_name = sorted(shp_candidates, key=lambda item: ("prefecture" not in item.lower(), item))[0]
    stem = Path(shp_name).stem.lower()
    members: dict[str, str] = {}
    for suffix in (".shp", ".shx", ".dbf"):
        key = f"{stem}{suffix}"
        if key not in files:
            raise ValueError(f"Missing {suffix} member for {shp_name}")
        members[suffix] = files[key]
    return Path(shp_name).stem, members


def _extract_shapefile(archive_path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(archive_path) as archive:
        stem, members = _find_prefecture_shapefile(archive)
        for suffix, member in members.items():
            target = destination / f"{stem}{suffix}"
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
    return destination / f"{stem}.shp"


def _candidate_cells(bounds: tuple[float, float, float, float]) -> Iterator[GsmapGridCell]:
    xmin, ymin, xmax, ymax = bounds
    column_start = max(0, math.floor(xmin / GRID_RESOLUTION) - 1)
    column_end = min(GRID_COLUMNS - 1, math.floor(xmax / GRID_RESOLUTION) + 1)
    row_start = max(0, math.floor((GRID_NORTH - ymax) / GRID_RESOLUTION) - 1)
    row_end = min(GRID_ROWS - 1, math.floor((GRID_NORTH - ymin) / GRID_RESOLUTION) + 1)
    for row in range(row_start, row_end + 1):
        for column in range(column_start, column_end + 1):
            yield GsmapGridCell(row=row, column=column)


def _cell_bounds(cell: GsmapGridCell) -> tuple[float, float, float, float]:
    west = cell.column * GRID_RESOLUTION
    east = west + GRID_RESOLUTION
    north = GRID_NORTH - cell.row * GRID_RESOLUTION
    south = north - GRID_RESOLUTION
    return west, south, east, north


def build_japan_grid_mask(boundary_zip: Path, mask_path: Path) -> list[GsmapGridCell]:
    """Build and cache cells having positive-area overlap with the N03 polygons."""
    try:
        import shapefile
        from shapely import make_valid
        from shapely.geometry import box, shape
        from shapely.prepared import prep
    except ImportError as exc:
        raise RuntimeError(
            "Japan CSV conversion requires pyshp and shapely; install backend/requirements.txt"
        ) from exc

    boundary_zip = boundary_zip.resolve()
    if not boundary_zip.is_file():
        raise FileNotFoundError(f"Japan boundary archive not found: {boundary_zip}")

    selected: set[tuple[int, int]] = set()
    with tempfile.TemporaryDirectory(prefix="gsmap-japan-mask-") as temp_name:
        shp_path = _extract_shapefile(boundary_zip, Path(temp_name))
        reader = shapefile.Reader(str(shp_path))
        try:
            for source_shape in reader.iterShapes():
                geometry = shape(source_shape.__geo_interface__)
                if geometry.is_empty:
                    continue
                if not geometry.is_valid:
                    geometry = make_valid(geometry)
                prepared = prep(geometry)
                for cell in _candidate_cells(geometry.bounds):
                    key = (cell.row, cell.column)
                    if key in selected:
                        continue
                    cell_polygon = box(*_cell_bounds(cell))
                    if not prepared.intersects(cell_polygon):
                        continue
                    if geometry.intersection(cell_polygon).area > 1e-12:
                        selected.add(key)
        finally:
            reader.close()

    cells = [GsmapGridCell(row=row, column=column) for row, column in sorted(selected)]
    if not cells:
        raise RuntimeError("The Japan boundary produced an empty GSMaP grid mask")

    mask_path.parent.mkdir(parents=True, exist_ok=True)
    partial = mask_path.with_name(mask_path.name + ".part")
    with partial.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["grid_id", "row", "column", "latitude", "longitude"])
        for cell in cells:
            writer.writerow(
                [
                    cell.grid_id,
                    cell.row,
                    cell.column,
                    f"{cell.latitude:.2f}",
                    f"{cell.longitude:.2f}",
                ]
            )
    os.replace(partial, mask_path)
    _atomic_write_json(
        mask_path.with_name(mask_path.name + ".meta.json"),
        {
            "format_version": MASK_FORMAT_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "boundary": _boundary_signature(boundary_zip),
            "grid_cells": len(cells),
            "selection": "positive-area intersection with original 0.1-degree GSMaP grid",
        },
    )
    return cells


def load_grid_mask(mask_path: Path) -> list[GsmapGridCell]:
    cells: list[GsmapGridCell] = []
    with mask_path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            cells.append(GsmapGridCell(row=int(row["row"]), column=int(row["column"])))
    if not cells:
        raise ValueError(f"GSMaP Japan mask is empty: {mask_path}")
    return cells


def load_or_build_japan_grid_mask(
    boundary_zip: Path,
    mask_path: Path,
    *,
    rebuild: bool = False,
) -> list[GsmapGridCell]:
    metadata_path = mask_path.with_name(mask_path.name + ".meta.json")
    if not rebuild and mask_path.is_file() and metadata_path.is_file():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if (
                metadata.get("format_version") == MASK_FORMAT_VERSION
                and metadata.get("boundary") == _boundary_signature(boundary_zip)
            ):
                return load_grid_mask(mask_path)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    return build_japan_grid_mask(boundary_zip, mask_path)


def parse_observation_timestamp(path: Path) -> datetime:
    match = _TIMESTAMP_PATTERN.search(path.name)
    if not match:
        raise ValueError(f"Cannot parse GSMaP timestamp from filename: {path.name}")
    return datetime.strptime("".join(match.groups()), "%Y%m%d%H%M").replace(
        tzinfo=timezone.utc
    )


def build_daily_csv_path(
    output_root: Path,
    product: str,
    dataset: str,
    observation_date: date,
    *,
    compression: str,
) -> Path:
    suffix = ".csv.gz" if compression == "gzip" else ".csv"
    return (
        output_root
        / Path(*product.split("/"))
        / dataset
        / observation_date.strftime("%Y")
        / observation_date.strftime("%m")
        / f"{observation_date:%Y%m%d}{suffix}"
    )


def _source_signatures(paths: Iterable[Path]) -> list[dict[str, Any]]:
    signatures = []
    for path in sorted(paths, key=lambda item: item.name):
        stat = path.stat()
        signatures.append(
            {"name": path.name, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
        )
    return signatures


def _open_csv_output(path: Path, compression: str) -> TextIO:
    if compression == "gzip":
        return gzip.open(path, "wt", encoding="utf-8", newline="", compresslevel=6)
    return path.open("w", encoding="utf-8", newline="")


def _read_binary(path: Path) -> bytes:
    opener = gzip.open if path.suffix.lower() == ".gz" else Path.open
    if opener is gzip.open:
        with gzip.open(path, "rb") as stream:
            payload = stream.read()
    else:
        with path.open("rb") as stream:
            payload = stream.read()
    if len(payload) != EXPECTED_BINARY_BYTES:
        raise ValueError(
            f"Unexpected GSMaP binary size for {path}: "
            f"{len(payload):,} bytes (expected {EXPECTED_BINARY_BYTES:,})"
        )
    return payload


def convert_gsmap_day_to_csv(
    source_paths: Iterable[Path],
    output_path: Path,
    cells: list[GsmapGridCell],
    *,
    compression: str = "gzip",
    mask_path: Path | None = None,
) -> GsmapCsvResult:
    """Convert all available hourly files for one UTC day into one atomic CSV."""
    if compression not in {"gzip", "none"}:
        raise ValueError(f"Unsupported CSV compression: {compression}")
    paths = sorted((Path(path) for path in source_paths), key=parse_observation_timestamp)
    if not paths:
        raise ValueError("At least one GSMaP source file is required")

    timestamps = [parse_observation_timestamp(path) for path in paths]
    observation_date = timestamps[0].date()
    if any(timestamp.date() != observation_date for timestamp in timestamps):
        raise ValueError("All source files in a daily CSV must have the same UTC date")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = output_path.with_name(output_path.name + ".meta.json")
    sources = _source_signatures(paths)
    mask_signature = None
    if mask_path is not None:
        mask_stat = mask_path.stat()
        mask_signature = {"size": mask_stat.st_size, "mtime_ns": mask_stat.st_mtime_ns}
    expected_metadata = {
        "format_version": CSV_FORMAT_VERSION,
        "observation_date": observation_date.isoformat(),
        "compression": compression,
        "grid_cells": len(cells),
        "mask": mask_signature,
        "sources": sources,
    }
    if output_path.is_file() and metadata_path.is_file():
        try:
            existing = json.loads(metadata_path.read_text(encoding="utf-8"))
            if all(existing.get(key) == value for key, value in expected_metadata.items()):
                return GsmapCsvResult(
                    status="skipped",
                    output_path=output_path,
                    observation_date=observation_date,
                    source_files=len(paths),
                    grid_cells=len(cells),
                    rows=len(paths) * len(cells),
                    size=output_path.stat().st_size,
                )
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    partial_path = output_path.with_name(output_path.name + ".part")
    try:
        with _open_csv_output(partial_path, compression) as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(
                ["timestamp_utc", "grid_id", "latitude", "longitude", "rain_rate_mm_h"]
            )
            for path, timestamp in zip(paths, timestamps):
                payload = _read_binary(path)
                timestamp_text = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
                for cell in cells:
                    value = struct.unpack_from("<f", payload, cell.flat_index * 4)[0]
                    writer.writerow(
                        [
                            timestamp_text,
                            cell.grid_id,
                            f"{cell.latitude:.2f}",
                            f"{cell.longitude:.2f}",
                            f"{value:.7g}",
                        ]
                    )
        os.replace(partial_path, output_path)
    except Exception:
        partial_path.unlink(missing_ok=True)
        raise

    metadata = {
        **expected_metadata,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rows": len(paths) * len(cells),
        "columns": [
            "timestamp_utc",
            "grid_id",
            "latitude",
            "longitude",
            "rain_rate_mm_h",
        ],
        "rain_rate_unit": "mm/hr",
        "negative_values": "JAXA missing/retrieval codes are preserved (-4, -8, -99)",
    }
    _atomic_write_json(metadata_path, metadata)
    return GsmapCsvResult(
        status="converted",
        output_path=output_path,
        observation_date=observation_date,
        source_files=len(paths),
        grid_cells=len(cells),
        rows=len(paths) * len(cells),
        size=output_path.stat().st_size,
    )


def append_csv_manifest(path: Path, result: GsmapCsvResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"recorded_at": datetime.now(timezone.utc).isoformat(), **result.to_dict()}
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
