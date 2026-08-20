from datetime import datetime, timezone
import json

from app.services.metadata_service import (
    build_metadata_document,
    parse_catalog_html,
    write_metadata_document,
)


CATALOG_HTML = """
<html><body>
  <ul class="collapsible" id="kokudo">
    <li>
      <div class="collapsible-header"><p class="white-text">1. 国土（水・土地）<i>arrow_drop_down</i></p></div>
      <div class="collapsible-body">
        <div class="row paddingAll"><div class="card-panel"><span class="white-text">土地利用</span></div></div>
        <div class="row"><a href="./datalist/KsjTmplt-L03-a-v1_1.html">土地利用3次メッシュ</a></div>
        <div class="row"><a href="./datalist/KsjTmplt-L03-a-v1_1.html">土地利用3次メッシュ</a></div>
        <div class="row paddingAll"><div class="card-panel"><span class="white-text">災害・防災</span></div></div>
        <div class="row"><a href="./gml/datalist/KsjTmplt-A33-2025.html">土砂災害警戒区域（ポリゴン）</a></div>
      </div>
    </li>
  </ul>
</body></html>
"""


def test_parse_catalog_html_extracts_search_metadata_and_deduplicates():
    datasets = parse_catalog_html(
        CATALOG_HTML,
        source_url="https://nlftp.mlit.go.jp/ksj/",
        detail_base_url="https://nlftp.mlit.go.jp/ksj/gml/datalist/",
    )

    assert [dataset.data_code for dataset in datasets] == ["A33", "L03-a"]
    hazard = datasets[0]
    assert hazard.data_name == "土砂災害警戒区域（ポリゴン）"
    assert hazard.category == "1. 国土（水・土地）"
    assert hazard.subcategory == "災害・防災"
    assert hazard.keywords == [
        "土砂災害警戒区域（ポリゴン）",
        "土砂災害警戒区域",
        "A33",
        "国土（水・土地）",
        "災害・防災",
    ]
    assert hazard.detail_url.endswith("/KsjTmplt-A33-2025.html")


def test_build_and_write_metadata_document(tmp_path):
    datasets = parse_catalog_html(
        CATALOG_HTML,
        source_url="https://example.test/catalog.html",
        detail_base_url="https://example.test/details/",
    )
    document = build_metadata_document(
        datasets,
        source_url="https://example.test/catalog.html",
        retrieved_at=datetime(2026, 8, 20, 0, 0, tzinfo=timezone.utc),
    )
    output_path = tmp_path / "nested" / "metadata.json"

    write_metadata_document(document, output_path)

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["schema_version"] == 1
    assert saved["dataset_count"] == 2
    assert saved["source"]["retrieved_at"] == "2026-08-20T00:00:00Z"
