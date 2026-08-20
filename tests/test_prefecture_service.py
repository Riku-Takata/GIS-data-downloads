from datetime import datetime, timezone
import json
import re

from app.services.prefecture_service import (
    PREFECTURE_DEFINITIONS,
    build_prefecture_document,
    find_prefecture_by_code,
    find_prefecture_by_name,
    get_prefectures,
    load_prefecture_document,
    write_prefecture_document,
)
from scripts.generate_pref_master import main as generate_pref_master_main


def test_prefecture_definitions_integrity():
    prefectures = get_prefectures()
    assert len(prefectures) == 48

    codes = [p.pref_code for p in prefectures]
    assert len(set(codes)) == 48

    names = [p.pref_name for p in prefectures]
    assert len(set(names)) == 48

    for p in prefectures:
        assert re.match(r"^\d{2}$", p.pref_code)
        assert len(p.pref_name) > 0
        assert len(p.short_name) > 0
        assert len(p.kana) > 0
        assert len(p.romaji) > 0
        assert len(p.region) > 0
        assert len(p.aliases) > 0

    assert prefectures[0].pref_code == "00"
    assert prefectures[0].pref_name == "全国"

    assert prefectures[1].pref_code == "01"
    assert prefectures[1].pref_name == "北海道"

    assert prefectures[13].pref_code == "13"
    assert prefectures[13].pref_name == "東京都"

    assert prefectures[47].pref_code == "47"
    assert prefectures[47].pref_name == "沖縄県"


def test_build_and_write_and_load_prefecture_document(tmp_path):
    prefectures = get_prefectures()
    retrieved_at = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
    document = build_prefecture_document(prefectures, retrieved_at=retrieved_at)

    assert document["schema_version"] == 1
    assert document["prefecture_count"] == 48
    assert document["source"]["retrieved_at"] == "2026-08-20T12:00:00Z"

    output_path = tmp_path / "subdir" / "pref_master.json"
    write_prefecture_document(document, output_path)

    assert output_path.exists()
    loaded_raw = json.loads(output_path.read_text(encoding="utf-8"))
    assert loaded_raw["prefecture_count"] == 48

    loaded_prefs = load_prefecture_document(output_path)
    assert len(loaded_prefs) == 48
    assert loaded_prefs == prefectures


def test_find_prefecture_by_code():
    pref_toyama = find_prefecture_by_code("16")
    assert pref_toyama is not None
    assert pref_toyama.pref_name == "富山県"

    pref_hokkaido = find_prefecture_by_code("1")  # zfill to '01'
    assert pref_hokkaido is not None
    assert pref_hokkaido.pref_name == "北海道"

    pref_national = find_prefecture_by_code("00")
    assert pref_national is not None
    assert pref_national.pref_name == "全国"

    assert find_prefecture_by_code("99") is None


def test_find_prefecture_by_name():
    # Exact name
    assert find_prefecture_by_name("富山県").pref_code == "16"
    # Short name
    assert find_prefecture_by_name("富山").pref_code == "16"
    # Kana
    assert find_prefecture_by_name("とやま").pref_code == "16"
    # Romaji (case insensitive)
    assert find_prefecture_by_name("TOYAMA").pref_code == "16"
    # Alias / Major City
    assert find_prefecture_by_name("仙台").pref_code == "04"
    assert find_prefecture_by_name("横浜").pref_code == "14"
    assert find_prefecture_by_name("金沢").pref_code == "17"
    assert find_prefecture_by_name("名古屋").pref_code == "23"
    assert find_prefecture_by_name("神戸").pref_code == "28"
    assert find_prefecture_by_name("博多").pref_code == "40"
    # National / Country alias
    assert find_prefecture_by_name("全国").pref_code == "00"
    assert find_prefecture_by_name("日本").pref_code == "00"
    assert find_prefecture_by_name("japan").pref_code == "00"

    # Non-existent
    assert find_prefecture_by_name("架空の県") is None
    assert find_prefecture_by_name("") is None


def test_generate_pref_master_cli_script(tmp_path):
    output_path = tmp_path / "custom_pref_master.json"
    exit_code = generate_pref_master_main(["--output", str(output_path)])
    assert exit_code == 0
    assert output_path.exists()

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["prefecture_count"] == 48
