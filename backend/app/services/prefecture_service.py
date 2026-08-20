"""Prefecture master definitions and service operations for GIS data retrieval."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any


@dataclass(frozen=True)
class Prefecture:
    """Prefecture definition conforming to JIS X 0401 with national scope support."""

    pref_code: str
    pref_name: str
    short_name: str
    kana: str
    romaji: str
    region: str
    aliases: list[str]


PREFECTURE_DEFINITIONS: list[Prefecture] = [
    Prefecture("00", "全国", "全国", "ぜんこく", "Zenkoku", "全国", ["全国", "日本", "ぜんこく", "zenkoku", "japan"]),
    Prefecture("01", "北海道", "北海道", "ほっかいどう", "Hokkaido", "北海道", ["北海道", "ほっかいどう", "hokkaido"]),
    Prefecture("02", "青森県", "青森", "あおもり", "Aomori", "東北", ["青森県", "青森", "あおもり", "aomori"]),
    Prefecture("03", "岩手県", "岩手", "いわて", "Iwate", "東北", ["岩手県", "岩手", "いわて", "iwate"]),
    Prefecture("04", "宮城県", "宮城", "みやぎ", "Miyagi", "東北", ["宮城県", "宮城", "みやぎ", "miyagi", "仙台", "せんだい"]),
    Prefecture("05", "秋田県", "秋田", "あきた", "Akita", "東北", ["秋田県", "秋田", "あきた", "akita"]),
    Prefecture("06", "山形県", "山形", "やまがた", "Yamagata", "東北", ["山形県", "山形", "やまがた", "yamagata"]),
    Prefecture("07", "福島県", "福島", "ふくしま", "Fukushima", "東北", ["福島県", "福島", "ふくしま", "fukushima"]),
    Prefecture("08", "茨城県", "茨城", "いばらき", "Ibaraki", "関東", ["茨城県", "茨城", "いばらき", "ibaraki"]),
    Prefecture("09", "栃木県", "栃木", "とちぎ", "Tochigi", "関東", ["栃木県", "栃木", "とちぎ", "tochigi"]),
    Prefecture("10", "群馬県", "群馬", "ぐんま", "Gunma", "関東", ["群馬県", "群馬", "ぐんま", "gunma"]),
    Prefecture("11", "埼玉県", "埼玉", "さいたま", "Saitama", "関東", ["埼玉県", "埼玉", "さいたま", "saitama"]),
    Prefecture("12", "千葉県", "千葉", "ちば", "Chiba", "関東", ["千葉県", "千葉", "ちば", "chiba"]),
    Prefecture("13", "東京都", "東京", "とうきょう", "Tokyo", "関東", ["東京都", "東京", "とうきょう", "tokyo"]),
    Prefecture("14", "神奈川県", "神奈川", "かながわ", "Kanagawa", "関東", ["神奈川県", "神奈川", "かながわ", "kanagawa", "横浜", "よこはま"]),
    Prefecture("15", "新潟県", "新潟", "にいがた", "Niigata", "中部", ["新潟県", "新潟", "にいがた", "niigata"]),
    Prefecture("16", "富山県", "富山", "とやま", "Toyama", "中部", ["富山県", "富山", "とやま", "toyama"]),
    Prefecture("17", "石川県", "石川", "いしかわ", "Ishikawa", "中部", ["石川県", "石川", "いしかわ", "ishikawa", "金沢", "かなざわ"]),
    Prefecture("18", "福井県", "福井", "ふくい", "Fukui", "中部", ["福井県", "福井", "ふくい", "fukui"]),
    Prefecture("19", "山梨県", "山梨", "やまなし", "Yamanashi", "中部", ["山梨県", "山梨", "やまなし", "yamanashi"]),
    Prefecture("20", "長野県", "長野", "ながの", "Nagano", "中部", ["長野県", "長野", "ながの", "nagano"]),
    Prefecture("21", "岐阜県", "岐阜", "ぎふ", "Gifu", "中部", ["岐阜県", "岐阜", "ぎふ", "gifu"]),
    Prefecture("22", "静岡県", "静岡", "しずおか", "Shizuoka", "中部", ["静岡県", "静岡", "しずおか", "shizuoka"]),
    Prefecture("23", "愛知県", "愛知", "あいち", "Aichi", "中部", ["愛知県", "愛知", "あいち", "aichi", "名古屋", "なごや"]),
    Prefecture("24", "三重県", "三重", "みえ", "Mie", "近畿", ["三重県", "三重", "みえ", "mie"]),
    Prefecture("25", "滋賀県", "滋賀", "しが", "Shiga", "近畿", ["滋賀県", "滋賀", "しが", "shiga"]),
    Prefecture("26", "京都府", "京都", "きょうと", "Kyoto", "近畿", ["京都府", "京都", "きょうと", "kyoto"]),
    Prefecture("27", "大阪府", "大阪", "おおさか", "Osaka", "近畿", ["大阪府", "大阪", "おおさか", "osaka"]),
    Prefecture("28", "兵庫県", "兵庫", "ひょうご", "Hyogo", "近畿", ["兵庫県", "兵庫", "ひょうご", "hyogo", "神戸", "こうべ"]),
    Prefecture("29", "奈良県", "奈良", "なら", "Nara", "近畿", ["奈良県", "奈良", "なら", "nara"]),
    Prefecture("30", "和歌山県", "和歌山", "わかやま", "Wakayama", "近畿", ["和歌山県", "和歌山", "わかやま", "wakayama"]),
    Prefecture("31", "鳥取県", "鳥取", "とっとり", "Tottori", "中国", ["鳥取県", "鳥取", "とっとり", "tottori"]),
    Prefecture("32", "島根県", "島根", "しまね", "Shimane", "中国", ["島根県", "島根", "しまね", "shimane"]),
    Prefecture("33", "岡山県", "岡山", "おかやま", "Okayama", "中国", ["岡山県", "岡山", "おかやま", "okayama"]),
    Prefecture("34", "広島県", "広島", "ひろしま", "Hiroshima", "中国", ["広島県", "広島", "ひろしま", "hiroshima"]),
    Prefecture("35", "山口県", "山口", "やまぐち", "Yamaguchi", "中国", ["山口県", "山口", "やまぐち", "yamaguchi"]),
    Prefecture("36", "徳島県", "徳島", "とくしま", "Tokushima", "四国", ["徳島県", "徳島", "とくしま", "tokushima"]),
    Prefecture("37", "香川県", "香川", "かがわ", "Kagawa", "四国", ["香川県", "香川", "かがわ", "kagawa"]),
    Prefecture("38", "愛媛県", "愛媛", "えひめ", "Ehime", "四国", ["愛媛県", "愛媛", "えひめ", "ehime"]),
    Prefecture("39", "高知県", "高知", "こうち", "Kochi", "四国", ["高知県", "高知", "こうち", "kochi"]),
    Prefecture("40", "福岡県", "福岡", "ふくおか", "Fukuoka", "九州", ["福岡県", "福岡", "ふくおか", "fukuoka", "博多", "はかた"]),
    Prefecture("41", "佐賀県", "佐賀", "さが", "Saga", "九州", ["佐賀県", "佐賀", "さが", "saga"]),
    Prefecture("42", "長崎県", "長崎", "ながさき", "Nagasaki", "九州", ["長崎県", "長崎", "ながさき", "nagasaki"]),
    Prefecture("43", "熊本県", "熊本", "くまもと", "Kumamoto", "九州", ["熊本県", "熊本", "くまもと", "kumamoto"]),
    Prefecture("44", "大分県", "大分", "おおいた", "Oita", "九州", ["大分県", "大分", "おおいた", "oita"]),
    Prefecture("45", "宮崎県", "宮崎", "みやざき", "Miyazaki", "九州", ["宮崎県", "宮崎", "みやざき", "miyazaki"]),
    Prefecture("46", "鹿児島県", "鹿児島", "かごしま", "Kagoshima", "九州", ["鹿児島県", "鹿児島", "かごしま", "kagoshima"]),
    Prefecture("47", "沖縄県", "沖縄", "おきなわ", "Okinawa", "九州・沖縄", ["沖縄県", "沖縄", "おきなわ", "okinawa"]),
]


def get_prefectures() -> list[Prefecture]:
    """Return the list of all prefecture definitions including national scope."""
    return list(PREFECTURE_DEFINITIONS)


def build_prefecture_document(
    prefectures: list[Prefecture] | None = None,
    *,
    retrieved_at: datetime | None = None,
) -> dict[str, Any]:
    """Create the versioned JSON document for prefecture master."""
    target_list = prefectures if prefectures is not None else get_prefectures()
    timestamp = retrieved_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    timestamp_text = timestamp.astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )

    return {
        "schema_version": 1,
        "source": {
            "name": "JIS X 0401 都道府県コード / 国土数値情報",
            "retrieved_at": timestamp_text,
        },
        "prefecture_count": len(target_list),
        "prefectures": [asdict(p) for p in target_list],
    }


def write_prefecture_document(document: dict[str, Any], output_path: Path) -> None:
    """Write JSON atomically so readers never observe a partially written file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(document, ensure_ascii=False, indent=2) + "\n"

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(serialized)
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, output_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def load_prefecture_document(path: Path) -> list[Prefecture]:
    """Load prefecture definitions from a saved JSON document."""
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_list = data.get("prefectures", [])
    return [
        Prefecture(
            pref_code=item["pref_code"],
            pref_name=item["pref_name"],
            short_name=item["short_name"],
            kana=item["kana"],
            romaji=item["romaji"],
            region=item["region"],
            aliases=item.get("aliases", []),
        )
        for item in raw_list
    ]


def find_prefecture_by_code(
    code: str, prefectures: list[Prefecture] | None = None
) -> Prefecture | None:
    """Find a prefecture by its 2-digit code (e.g., '16' or '00')."""
    normalized = code.strip().zfill(2)
    target_list = prefectures if prefectures is not None else PREFECTURE_DEFINITIONS
    for p in target_list:
        if p.pref_code == normalized:
            return p
    return None


def find_prefecture_by_name(
    query: str, prefectures: list[Prefecture] | None = None
) -> Prefecture | None:
    """Find a prefecture by exact or alias match."""
    normalized = query.strip().lower()
    if not normalized:
        return None
    target_list = prefectures if prefectures is not None else PREFECTURE_DEFINITIONS
    for p in target_list:
        if (
            normalized == p.pref_name.lower()
            or normalized == p.short_name.lower()
            or normalized == p.kana.lower()
            or normalized == p.romaji.lower()
            or any(normalized == alias.lower() for alias in p.aliases)
        ):
            return p
    return None


get_prefecture_by_code = find_prefecture_by_code
get_prefecture_by_name = find_prefecture_by_name
