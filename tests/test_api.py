from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_list_prefectures():
    response = client.get("/api/prefectures")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 48
    assert data[0]["pref_code"] == "00"
    assert data[1]["pref_code"] == "01"


def test_list_datasets():
    response = client.get("/api/datasets")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_search_dataset_endpoint():
    response = client.post(
        "/api/search",
        json={"query": "富山県の土砂災害データ"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    proposal = data["proposal"]
    assert proposal["data_code"] == "A33"
    assert proposal["pref_code"] == "16"
    assert proposal["pref_name"] == "富山県"
    assert proposal["format"] == "GeoJSON"


def test_search_dataset_empty_query():
    response = client.post(
        "/api/search",
        json={"query": "   "},
    )
    assert response.status_code == 400


@patch("app.providers.mlit_provider.download_file")
@patch("app.providers.mlit_provider.fetch_detail_page_html")
def test_download_dataset_endpoint(mock_fetch_html, mock_dl_file, tmp_path):
    mock_fetch_html.return_value = """
    <html><body>
    <table>
      <tr>
        <td>富山</td><td>GEOJSON形式</td><td>世界測地系</td><td>2025年（令和7年）</td><td>6.07MB</td><td>A33-25_16_GEOJSON.zip</td>
        <td><a onclick="DownLd('6.07MB','A33-25_16_GEOJSON.zip','../data/A33/A33-25/A33-25_16_GEOJSON.zip',this)">DL</a></td>
      </tr>
    </table>
    </body></html>
    """
    mock_dl_file.return_value = tmp_path / "A33-25_16_GEOJSON.zip"

    response = client.post(
        "/api/download",
        json={
            "data_code": "A33",
            "pref_code": "16",
            "year": "latest",
            "format": "GeoJSON",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["data_code"] == "A33"
    assert data["pref_code"] == "16"
    assert data["format"] == "GeoJSON"
    assert data["file_name"] == "A33-25_16_GEOJSON.zip"
