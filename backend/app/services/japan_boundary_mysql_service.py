"""Import the N03 polygons used by GSMaP masking into MySQL spatial tables."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Iterator
import zipfile


_REFERENCE_DATE = re.compile(r"N03-(\d{8})", re.IGNORECASE)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_layer_members(archive: zipfile.ZipFile) -> tuple[str, dict[str, str]]:
    names = {
        Path(info.filename).name.lower(): info.filename
        for info in archive.infolist()
        if not info.is_dir()
    }
    candidates = sorted(
        name[:-4]
        for name in names
        if name.endswith("_prefecture.shp")
    )
    if not candidates:
        raise ValueError(f"N03 prefecture layer not found: {archive.filename}")
    stem = candidates[0]
    members: dict[str, str] = {}
    for suffix in (".shp", ".shx", ".dbf", ".prj"):
        key = stem + suffix
        if key not in names:
            raise ValueError(f"Missing N03 layer member: {key}")
        members[suffix] = names[key]
    return Path(names[stem + ".shp"]).stem, members


def _extract_layer(archive_path: Path, output_dir: Path) -> tuple[Path, str]:
    with zipfile.ZipFile(archive_path) as archive:
        layer_name, members = _find_layer_members(archive)
        for suffix, member in members.items():
            target = output_dir / f"{layer_name}{suffix}"
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output, length=8 * 1024 * 1024)
    return output_dir / f"{layer_name}.shp", layer_name


def _reference_date(archive_path: Path) -> date:
    match = _REFERENCE_DATE.search(archive_path.name)
    if match is None:
        raise ValueError(f"Cannot determine N03 reference date: {archive_path.name}")
    return date.fromisoformat(
        f"{match.group(1)[:4]}-{match.group(1)[4:6]}-{match.group(1)[6:8]}"
    )


def _polygonal_geometry(source_shape: Any) -> Any:
    from shapely import make_valid
    from shapely.geometry import MultiPolygon, shape
    from shapely.ops import unary_union

    geometry = shape(source_shape.__geo_interface__)
    if not geometry.is_valid:
        geometry = make_valid(geometry)
    if geometry.geom_type in {"Polygon", "MultiPolygon"}:
        return geometry
    polygons = [
        part
        for part in getattr(geometry, "geoms", ())
        if part.geom_type in {"Polygon", "MultiPolygon"} and not part.is_empty
    ]
    if not polygons:
        return MultiPolygon()
    return unary_union(polygons)


def import_n03_boundaries(
    connection: Any,
    archive_path: Path,
    *,
    batch_size: int = 250,
) -> dict[str, Any]:
    """Idempotently import the exact N03 prefecture shapes used for the mask."""

    try:
        import shapefile
    except ImportError as error:
        raise RuntimeError("pyshp is required for N03 boundary import") from error

    archive_path = archive_path.resolve()
    archive_sha256 = sha256_file(archive_path)
    reference_date = _reference_date(archive_path)

    with tempfile.TemporaryDirectory(prefix="n03-mysql-") as temp_name:
        shp_path, layer_name = _extract_layer(archive_path, Path(temp_name))
        dataset_key = layer_name
        reader = shapefile.Reader(str(shp_path), encoding="utf-8")
        source_count = len(reader)
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT dataset_id, source_sha256, imported_feature_count, import_status
                FROM japan_boundary_datasets WHERE dataset_key = %s
                """,
                (dataset_key,),
            )
            existing = cursor.fetchone()
            if (
                existing
                and existing[1] == archive_sha256
                and int(existing[2] or 0) == source_count
                and existing[3] == "completed"
            ):
                return {
                    "status": "skipped",
                    "dataset_key": dataset_key,
                    "features": source_count,
                    "sha256": archive_sha256,
                }

            cursor.execute(
                """
                INSERT INTO japan_boundary_datasets
                    (dataset_key, source_archive, source_layer, source_sha256,
                     reference_date, source_feature_count, imported_feature_count,
                     import_status, imported_at, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, NULL, 'loading', NULL, NULL)
                ON DUPLICATE KEY UPDATE
                    source_archive=VALUES(source_archive),
                    source_layer=VALUES(source_layer),
                    source_sha256=VALUES(source_sha256),
                    reference_date=VALUES(reference_date),
                    source_feature_count=VALUES(source_feature_count),
                    imported_feature_count=NULL,
                    import_status='loading', imported_at=NULL, error_message=NULL
                """,
                (
                    dataset_key,
                    archive_path.name,
                    layer_name,
                    archive_sha256,
                    reference_date,
                    source_count,
                ),
            )
            connection.commit()
            cursor.execute(
                "SELECT dataset_id FROM japan_boundary_datasets WHERE dataset_key=%s",
                (dataset_key,),
            )
            dataset_id = int(cursor.fetchone()[0])

            minimum_longitude = minimum_latitude = float("inf")
            maximum_longitude = maximum_latitude = float("-inf")
            imported = 0
            sql = """
                INSERT INTO japan_land_polygons
                    (dataset_id, source_record_number, prefecture_code,
                     prefecture_name, source_attributes, geometry)
                VALUES (%s, %s, %s, %s, %s,
                        ST_GeomFromWKB(%s, 4326, 'axis-order=long-lat'))
                ON DUPLICATE KEY UPDATE
                    prefecture_code=VALUES(prefecture_code),
                    prefecture_name=VALUES(prefecture_name),
                    source_attributes=VALUES(source_attributes),
                    geometry=VALUES(geometry)
            """
            batch: list[tuple[Any, ...]] = []
            for record_number, shape_record in enumerate(
                reader.iterShapeRecords(), start=1
            ):
                attributes = shape_record.record.as_dict()
                geometry = _polygonal_geometry(shape_record.shape)
                if geometry.is_empty:
                    raise ValueError(f"Empty N03 polygon at record {record_number}")
                if not geometry.is_valid:
                    raise ValueError(f"Invalid N03 polygon at record {record_number}")
                xmin, ymin, xmax, ymax = geometry.bounds
                minimum_longitude = min(minimum_longitude, xmin)
                minimum_latitude = min(minimum_latitude, ymin)
                maximum_longitude = max(maximum_longitude, xmax)
                maximum_latitude = max(maximum_latitude, ymax)
                batch.append(
                    (
                        dataset_id,
                        record_number,
                        str(attributes.get("N03_007") or ""),
                        str(attributes.get("N03_001") or ""),
                        json.dumps(attributes, ensure_ascii=False),
                        geometry.wkb,
                    )
                )
                if len(batch) >= batch_size:
                    cursor.executemany(sql, batch)
                    connection.commit()
                    imported += len(batch)
                    print(f"[boundary-imported] {imported:,}/{source_count:,}", flush=True)
                    batch.clear()
            if batch:
                cursor.executemany(sql, batch)
                connection.commit()
                imported += len(batch)
                print(f"[boundary-imported] {imported:,}/{source_count:,}", flush=True)

            cursor.execute(
                "SELECT COUNT(*) FROM japan_land_polygons WHERE dataset_id=%s",
                (dataset_id,),
            )
            stored = int(cursor.fetchone()[0])
            if stored != source_count:
                raise ValueError(
                    f"N03 feature count mismatch: source={source_count}, stored={stored}"
                )
            cursor.execute(
                """
                UPDATE japan_boundary_datasets
                SET imported_feature_count=%s,
                    minimum_longitude=%s, minimum_latitude=%s,
                    maximum_longitude=%s, maximum_latitude=%s,
                    import_status='completed', imported_at=CURRENT_TIMESTAMP,
                    error_message=NULL
                WHERE dataset_id=%s
                """,
                (
                    stored,
                    minimum_longitude,
                    minimum_latitude,
                    maximum_longitude,
                    maximum_latitude,
                    dataset_id,
                ),
            )
            connection.commit()
            return {
                "status": "completed",
                "dataset_key": dataset_key,
                "features": stored,
                "sha256": archive_sha256,
                "bounds": [
                    minimum_longitude,
                    minimum_latitude,
                    maximum_longitude,
                    maximum_latitude,
                ],
            }
        except BaseException as error:
            connection.rollback()
            try:
                cursor.execute(
                    """
                    UPDATE japan_boundary_datasets
                    SET import_status='failed', error_message=%s
                    WHERE dataset_key=%s
                    """,
                    (f"{type(error).__name__}: {error}"[:1000], layer_name),
                )
                connection.commit()
            except BaseException:
                connection.rollback()
            raise
        finally:
            reader.close()
            cursor.close()


def iter_boundary_geojson_features(
    connection: Any,
    *,
    dataset_key: str | None = None,
    prefecture_code: str | None = None,
) -> Iterator[dict[str, Any]]:
    conditions = ["dataset.import_status='completed'"]
    parameters: list[Any] = []
    if dataset_key:
        conditions.append("dataset.dataset_key=%s")
        parameters.append(dataset_key)
    if prefecture_code:
        conditions.append("polygon.prefecture_code=%s")
        parameters.append(prefecture_code)
    cursor = connection.cursor(buffered=False)
    cursor.execute(
        f"""
        SELECT polygon.polygon_id, dataset.dataset_key,
               polygon.source_record_number, polygon.prefecture_code,
               polygon.prefecture_name, polygon.source_attributes,
               ST_AsGeoJSON(polygon.geometry, 8, 0)
        FROM japan_land_polygons AS polygon
        JOIN japan_boundary_datasets AS dataset
          ON dataset.dataset_id=polygon.dataset_id
        WHERE {' AND '.join(conditions)}
        """,
        tuple(parameters),
    )
    try:
        for row in cursor:
            attributes = row[5]
            if isinstance(attributes, str):
                attributes = json.loads(attributes)
            yield {
                "type": "Feature",
                "id": int(row[0]),
                "properties": {
                    **attributes,
                    "dataset_key": row[1],
                    "source_record_number": int(row[2]),
                    "prefecture_code": row[3],
                    "prefecture_name": row[4],
                },
                "geometry": json.loads(row[6]),
            }
    finally:
        cursor.close()
