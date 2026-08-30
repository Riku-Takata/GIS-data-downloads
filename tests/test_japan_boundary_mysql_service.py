from datetime import date
from pathlib import Path
import zipfile

import pytest

from app.services.japan_boundary_mysql_service import (
    _find_layer_members,
    _reference_date,
)


def test_reference_date_from_n03_archive_name() -> None:
    assert _reference_date(Path("N03-20260101_GML.zip")) == date(2026, 1, 1)


def test_find_prefecture_layer_members(tmp_path: Path) -> None:
    archive_path = tmp_path / "N03.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for suffix in (".shp", ".shx", ".dbf", ".prj"):
            archive.writestr(f"folder/N03-20260101_prefecture{suffix}", b"test")

    with zipfile.ZipFile(archive_path) as archive:
        layer, members = _find_layer_members(archive)

    assert layer == "N03-20260101_prefecture"
    assert set(members) == {".shp", ".shx", ".dbf", ".prj"}


def test_find_prefecture_layer_rejects_incomplete_archive(tmp_path: Path) -> None:
    archive_path = tmp_path / "N03.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("N03-20260101_prefecture.shp", b"test")

    with zipfile.ZipFile(archive_path) as archive:
        with pytest.raises(ValueError, match="Missing N03 layer member"):
            _find_layer_members(archive)
