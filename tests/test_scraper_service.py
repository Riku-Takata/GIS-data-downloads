from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.scraper_service import (
    DownloadableItem,
    download_file,
    extract_download_candidates,
    resolve_detail_url,
    select_best_candidate,
)

SAMPLE_DETAIL_HTML = """
<html><body>
<table class="mb30 responsive-table dataTables_e">
  <thead>
    <tr>
      <th>地域</th><th>形式</th><th>測地系</th><th>年度</th><th>ファイル容量</th><th>ファイル名</th><th>ダウンロード</th><th>一括DL</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>全国</td><td>GML形式</td><td>世界測地系</td><td>2025年（令和7年）</td><td>487.38MB</td><td>A33-25_00_GML.zip</td>
      <td><a href="javascript:void(0)" onclick="javascript:DownLd('487.38MB','A33-25_00_GML.zip','../data/A33/A33-25/A33-25_00_GML.zip' ,this);">DL</a></td><td></td>
    </tr>
    <tr>
      <td>全国</td><td>シェープ形式</td><td>世界測地系</td><td>2025年（令和7年）</td><td>640.45MB</td><td>A33-25_00_SHP.zip</td>
      <td><a href="javascript:void(0)" onclick="javascript:DownLd('640.45MB','A33-25_00_SHP.zip','../data/A33/A33-25/A33-25_00_SHP.zip' ,this);">DL</a></td><td></td>
    </tr>
    <tr>
      <td>富山</td><td>GML形式</td><td>世界測地系</td><td>2025年（令和7年）</td><td>6.4MB</td><td>A33-25_16_GML.zip</td>
      <td><a href="javascript:void(0)" onclick="javascript:DownLd('6.4MB','A33-25_16_GML.zip','../data/A33/A33-25/A33-25_16_GML.zip' ,this);">DL</a></td><td></td>
    </tr>
    <tr>
      <td>富山</td><td>シェープ形式</td><td>世界測地系</td><td>2025年（令和7年）</td><td>8.65MB</td><td>A33-25_16_SHP.zip</td>
      <td><a href="javascript:void(0)" onclick="javascript:DownLd('8.65MB','A33-25_16_SHP.zip','../data/A33/A33-25/A33-25_16_SHP.zip' ,this);">DL</a></td><td></td>
    </tr>
    <tr>
      <td>富山</td><td>GEOJSON形式</td><td>世界測地系</td><td>2025年（令和7年）</td><td>6.07MB</td><td>A33-25_16_GEOJSON.zip</td>
      <td><a href="javascript:void(0)" onclick="javascript:DownLd('6.07MB','A33-25_16_GEOJSON.zip','../data/A33/A33-25/A33-25_16_GEOJSON.zip' ,this);">DL</a></td><td></td>
    </tr>
    <tr>
      <td>富山</td><td>シェープ形式</td><td>世界測地系</td><td>2024年（令和6年）</td><td>8.28MB</td><td>A33-24_16_SHP.zip</td>
      <td><a href="javascript:void(0)" onclick="javascript:DownLd('8.28MB','A33-24_16_SHP.zip','../data/A33/A33-24/A33-24_16_SHP.zip' ,this);">DL</a></td><td></td>
    </tr>
  </tbody>
</table>
</body></html>
"""


def test_extract_download_candidates():
    detail_url = "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A33-2025.html"
    candidates = extract_download_candidates(
        SAMPLE_DETAIL_HTML, detail_url=detail_url, data_code="A33"
    )

    assert len(candidates) == 6

    toyama_geojson_2025 = next(
        c for c in candidates if c.file_name == "A33-25_16_GEOJSON.zip"
    )
    assert toyama_geojson_2025.pref_code == "16"
    assert toyama_geojson_2025.region_name == "富山県"
    assert toyama_geojson_2025.year_numeric == 2025
    assert toyama_geojson_2025.format_name == "GeoJSON"
    assert toyama_geojson_2025.file_size_mb == 6.07
    assert (
        toyama_geojson_2025.download_url
        == "https://nlftp.mlit.go.jp/ksj/gml/data/A33/A33-25/A33-25_16_GEOJSON.zip"
    )


def test_select_best_candidate_defaults_to_geojson():
    detail_url = "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A33-2025.html"
    candidates = extract_download_candidates(
        SAMPLE_DETAIL_HTML, detail_url=detail_url, data_code="A33"
    )

    # When format_preference is None, defaults to GeoJSON
    best_default = select_best_candidate(candidates, pref_code="16", year="latest")
    assert best_default is not None
    assert best_default.file_name == "A33-25_16_GEOJSON.zip"
    assert best_default.format_name == "GeoJSON"


def test_select_best_candidate_fallbacks_when_no_geojson():
    detail_url = "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A33-2025.html"
    candidates = extract_download_candidates(
        SAMPLE_DETAIL_HTML, detail_url=detail_url, data_code="A33"
    )

    # Filter out geojson to simulate datasets without GeoJSON (e.g. nationwide or older datasets)
    non_geojson = [c for c in candidates if c.format_name != "GeoJSON"]

    # Should fallback to Shapefile
    best_fallback = select_best_candidate(non_geojson, pref_code="16", year="latest")
    assert best_fallback is not None
    assert best_fallback.file_name == "A33-25_16_SHP.zip"
    assert best_fallback.format_name == "Shapefile"

    # Nationwide has only GML and Shapefile -> falls back to Shapefile
    best_national = select_best_candidate(candidates, pref_code="00", year="latest")
    assert best_national is not None
    assert best_national.file_name == "A33-25_00_SHP.zip"

    # Filter out Shapefile too -> should fallback to GML
    only_gml = [c for c in candidates if c.format_name == "GML"]
    best_gml = select_best_candidate(only_gml, pref_code="16", year="latest")
    assert best_gml is not None
    assert best_gml.file_name == "A33-25_16_GML.zip"
    assert best_gml.format_name == "GML"


def test_select_best_candidate_explicit_format():
    detail_url = "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A33-2025.html"
    candidates = extract_download_candidates(
        SAMPLE_DETAIL_HTML, detail_url=detail_url, data_code="A33"
    )

    # Explicit Shapefile
    best_shp = select_best_candidate(
        candidates, pref_code="16", year="latest", format_preference="Shapefile"
    )
    assert best_shp is not None
    assert best_shp.file_name == "A33-25_16_SHP.zip"

    # Explicit 2024 Shapefile
    best_2024 = select_best_candidate(
        candidates, pref_code="16", year="2024", format_preference="Shapefile"
    )
    assert best_2024 is not None
    assert best_2024.file_name == "A33-24_16_SHP.zip"


def test_resolve_detail_url():
    url_a33 = resolve_detail_url("A33")
    assert url_a33.endswith("KsjTmplt-A33-2025.html")

    url_unknown = resolve_detail_url("XYZ99")
    assert url_unknown == "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-XYZ99.html"


def test_download_file_atomic(tmp_path):
    destination = tmp_path / "downloads" / "test.zip"
    fake_content = b"PK\x03\x04test_zip_payload"

    mock_response = MagicMock()
    mock_response.iter_content.return_value = [fake_content]
    mock_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_response) as mock_get:
        saved_path = download_file("https://example.test/test.zip", destination)
        assert saved_path.is_file()
        assert saved_path.read_bytes() == fake_content
        mock_get.assert_called_once()
