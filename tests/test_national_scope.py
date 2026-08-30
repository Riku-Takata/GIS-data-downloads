from pathlib import Path
from unittest.mock import MagicMock, patch

from app.providers.mlit_provider import MLITProvider
from app.services.gemini_service import interpret_user_query


def test_mlit_provider_keeps_national_prefecture_code(tmp_path):
    candidate = MagicMock()
    candidate.data_code = "N03"
    candidate.file_name = "N03-latest_00_GEOJSON.zip"
    candidate.download_url = "https://example.test/N03-latest_00_GEOJSON.zip"
    candidate.year_numeric = 2026
    candidate.year_text = "2026"
    candidate.format_name = "GeoJSON"
    candidate.file_size_mb = 10.0
    candidate.region_name = "全国"
    saved_path = tmp_path / candidate.file_name

    with (
        patch("app.providers.mlit_provider.fetch_detail_page_html", return_value="html"),
        patch("app.providers.mlit_provider.extract_download_candidates", return_value=[candidate]),
        patch("app.providers.mlit_provider.select_best_candidate", return_value=candidate) as select,
        patch("app.providers.mlit_provider.download_file", return_value=saved_path),
    ):
        result = MLITProvider().download(
            data_code="N03",
            pref_code="00",
            year="latest",
            format_preference="GeoJSON",
            output_dir=tmp_path,
        )

    assert result.pref_code == "00"
    assert result.region_name == "全国"
    assert select.call_args.kwargs["pref_code"] == "00"


def test_gemini_national_query_is_not_overwritten_by_geocoder():
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": (
                                '{"data_code":"N03","data_name":"行政区域（ポリゴン）",'
                                '"pref_code":"00","pref_name":"全国","year":"latest",'
                                '"format":"GeoJSON","summary":"全国の行政区域",'
                                '"confidence":1.0}'
                            )
                        }
                    ]
                }
            }
        ]
    }

    with (
        patch("requests.post", return_value=response),
        patch("app.services.gemini_service.geocode_location") as geocode,
    ):
        proposal = interpret_user_query(
            "日本全国の行政区域 GeoJSON 最新",
            api_key="fake-key",
        )

    assert proposal.data_code == "N03"
    assert proposal.pref_code == "00"
    assert proposal.pref_name == "全国"
    geocode.assert_not_called()
