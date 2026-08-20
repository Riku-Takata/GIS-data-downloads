import re
from pathlib import Path

GAS_CODE_PATH = Path(__file__).resolve().parents[1] / "gas" / "Code.gs"
APPSSCRIPT_JSON_PATH = Path(__file__).resolve().parents[1] / "gas" / "appsscript.json"


def test_gas_files_exist():
    assert GAS_CODE_PATH.is_file()
    assert APPSSCRIPT_JSON_PATH.is_file()


def test_gas_code_contains_core_entrypoints():
    content = GAS_CODE_PATH.read_text(encoding="utf-8")
    assert "function doGet(e)" in content
    assert "function doPost(e)" in content
    assert "function loadMetadataFromDrive(" in content
    assert "function loadPrefecturesFromDrive(" in content
    assert "function readTextFileFromDrive(" in content
    assert "function interpretQuery(" in content
    assert "function callGeminiApi(" in content
    assert "function heuristicSearch(" in content
    assert "function parseDownloadCandidates(" in content
    assert "function selectBestCandidate(" in content
    assert "function executeDownloadAndSave(" in content
    # Assert zero hardcoded catalog arrays
    assert "const PREFECTURES_CATALOG = [" not in content
    assert "const DATASETS_CATALOG = [" not in content


def test_gas_download_candidate_regex_matching():
    sample_html = """
    <tr>
      <td>富山</td><td>GEOJSON形式</td><td>世界測地系</td><td>2025年（令和7年）</td><td>6.07MB</td><td>A33-25_16_GEOJSON.zip</td>
      <td><a onclick="DownLd('6.07MB','A33-25_16_GEOJSON.zip','../data/A33/A33-25/A33-25_16_GEOJSON.zip',this)">DL</a></td>
    </tr>
    """
    regex = r"DownLd\(\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*this\s*\)"
    matches = list(re.finditer(regex, sample_html))
    assert len(matches) == 1
    size_str, file_name, rel_url = matches[0].groups()
    assert size_str == "6.07MB"
    assert file_name == "A33-25_16_GEOJSON.zip"
    assert rel_url == "../data/A33/A33-25/A33-25_16_GEOJSON.zip"


def test_appsscript_json_structure():
    import json
    data = json.loads(APPSSCRIPT_JSON_PATH.read_text(encoding="utf-8"))
    assert data["timeZone"] == "Asia/Tokyo"
    assert data["runtimeVersion"] == "V8"
    assert data["webapp"]["access"] == "ANYONE"
