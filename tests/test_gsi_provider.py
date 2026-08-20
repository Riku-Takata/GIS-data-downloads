"""Unit tests for GSI Provider and multi-source router."""

import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.providers.base import GISDatasetCandidate
from app.providers.gsi_provider import GSIProvider, lat_lng_to_tile, tile_to_bounds
from app.providers.mlit_provider import MLITProvider
from app.providers.router import (
    download_dataset_across_providers,
    get_provider_by_id,
    list_all_available_datasets,
    resolve_provider_for_data_code,
)
from app.services.gemini_service import interpret_user_query


def test_lat_lng_to_tile_and_bounds():
    # Tokyo Station approx 35.6812, 139.7671
    lat, lng, zoom = 35.6812, 139.7671, 10
    tile_x, tile_y = lat_lng_to_tile(lat, lng, zoom)
    assert tile_x > 0
    assert tile_y > 0

    min_lat, min_lng, max_lat, max_lng = tile_to_bounds(tile_x, tile_y, zoom)
    assert min_lat < max_lat
    assert min_lng < max_lng
    assert min_lat <= lat <= max_lat
    assert min_lng <= lng <= max_lng


def test_gsi_provider_list_datasets():
    provider = GSIProvider()
    assert provider.provider_id == "gsi"
    assert "国土地理院" in provider.provider_name

    datasets = provider.list_datasets()
    assert len(datasets) >= 3
    codes = [d.data_code for d in datasets]
    assert "GSI-DEM5A" in codes
    assert "GSI-DEM10B" in codes
    assert "GSI-FGD-BLD" in codes


def test_router_resolution():
    p_gsi = resolve_provider_for_data_code("GSI-DEM5A")
    assert p_gsi.provider_id == "gsi"

    p_mlit = resolve_provider_for_data_code("A33")
    assert p_mlit.provider_id == "mlit"

    p_mlit_n03 = resolve_provider_for_data_code("N03")
    assert p_mlit_n03.provider_id == "mlit"

    all_ds = list_all_available_datasets()
    assert len(all_ds) >= 130


def test_gsi_provider_download_packages_zip():
    provider = GSIProvider()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Mock requests.get to return sample elevation text
        sample_txt = "\n".join(["120.5,121.0,121.5" for _ in range(256)])
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = sample_txt
            mock_resp.content = b"fake_png_data"
            mock_get.return_value = mock_resp

            result = provider.download(
                data_code="GSI-DEM5A",
                pref_code="16",
                year="latest",
                output_dir=tmp_path,
            )

            assert result.status == "downloaded"
            assert result.provider_id == "gsi"
            assert result.data_code == "GSI-DEM5A"
            assert result.pref_code == "16"
            assert result.region_name == "富山県"
            assert result.file_name.endswith(".zip")
            assert result.local_path is not None
            assert result.local_path.is_file()

            # Verify ZIP contents
            with zipfile.ZipFile(result.local_path, "r") as zf:
                namelist = zf.namelist()
                assert "GSI-DEM5A_16_elevation.geojson" in namelist
                assert "GSI-DEM5A_16_metadata.json" in namelist
                assert "README.txt" in namelist


def test_interpret_user_query_for_gsi_elevation():
    # Natural language elevation query
    res = interpret_user_query("富山県の航空レーザ5m標高DEMデータ")
    assert res.data_code == "GSI-DEM5A"
    assert res.pref_code == "16"
    assert res.pref_name == "富山県"
    assert res.provider_id == "gsi"
    assert "国土地理院" in res.provider_name


def test_interpret_user_query_for_mlit_hazard():
    # Natural language disaster query
    res = interpret_user_query("富山県の土砂災害警戒区域データ")
    assert res.data_code == "A33"
    assert res.pref_code == "16"
    assert res.provider_id == "mlit"
    assert "国土交通省" in res.provider_name
