import json
from unittest.mock import MagicMock, patch

from app.models.schemas import Proposal
from app.services.gemini_service import (
    build_system_prompt,
    heuristic_search,
    interpret_user_query,
)
from scripts.search_data import main as search_data_main


def test_heuristic_search_extracts_toyama_hazard_data():
    proposal = heuristic_search("富山県の土砂災害警戒区域データ")
    assert proposal.pref_code == "16"
    assert proposal.pref_name == "富山県"
    assert proposal.data_code == "A33"
    assert proposal.format == "GeoJSON"
    assert proposal.year == "latest"
    assert proposal.confidence >= 0.5


def test_heuristic_search_extracts_format_and_year_and_national():
    proposal = heuristic_search("全国の行政区域 GML 2024")
    assert proposal.pref_code == "00"
    assert proposal.pref_name == "全国"
    assert proposal.data_code == "N03"
    assert proposal.format == "GML"
    assert proposal.year == "2024"


def test_build_system_prompt():
    datasets = [{"data_code": "A33", "data_name": "土砂災害警戒区域", "keywords": ["土砂災害"]}]
    prefectures = [{"pref_code": "16", "pref_name": "富山県"}]
    prompt = build_system_prompt(datasets, prefectures)

    assert "A33: 土砂災害警戒区域" in prompt
    assert "16:富山県" in prompt
    assert "data_code" in prompt


def test_interpret_user_query_with_mocked_gemini_api():
    fake_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "data_code": "A33",
                                    "data_name": "土砂災害警戒区域（ポリゴン）",
                                    "pref_code": "16",
                                    "pref_name": "富山県",
                                    "year": "latest",
                                    "format": "GeoJSON",
                                    "summary": "富山県の土砂災害警戒区域データ（GeoJSON）",
                                    "confidence": 0.98,
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.json.return_value = fake_gemini_response
    mock_resp.raise_for_status.return_value = None

    with patch("requests.post", return_value=mock_resp) as mock_post:
        proposal = interpret_user_query(
            "富山県の土砂災害データがほしい",
            api_key="fake-key",
            model="gemini-2.5-flash",
        )

        assert proposal.data_code == "A33"
        assert proposal.pref_code == "16"
        assert proposal.pref_name == "富山県"
        assert proposal.format == "GeoJSON"
        assert proposal.confidence == 0.98
        mock_post.assert_called_once()


def test_interpret_user_query_falls_back_on_api_error():
    with patch("requests.post", side_effect=Exception("API connection error")):
        proposal = interpret_user_query(
            "富山県の土砂災害データ",
            api_key="fake-key",
        )
        assert proposal.pref_code == "16"
        assert proposal.data_code == "A33"


def test_search_data_cli_script(capsys):
    exit_code = search_data_main(["富山県の土砂災害データ"])
    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "success"
    assert data["proposal"]["pref_code"] == "16"
    assert data["proposal"]["data_code"] == "A33"
