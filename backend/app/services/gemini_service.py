"""Gemini-powered intent analysis and natural language query parser for GIS datasets."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any
import requests

from app.config import DEFAULT_METADATA_PATH, DEFAULT_PREF_MASTER_PATH, Settings
from app.models.schemas import Proposal
from app.services.geocoding_service import geocode_location
from app.services.prefecture_service import (
    find_prefecture_by_code,
    find_prefecture_by_name,
    get_prefectures,
    load_prefecture_document,
)


GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _load_catalog_summary(metadata_path: Path | None = None) -> list[dict[str, Any]]:
    path = metadata_path or DEFAULT_METADATA_PATH
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("datasets", [])
    except Exception:
        return []


def _load_prefectures(pref_master_path: Path | None = None) -> list[dict[str, Any]]:
    path = pref_master_path or DEFAULT_PREF_MASTER_PATH
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("prefectures", [])
    except Exception:
        return []


def build_system_prompt(
    datasets: list[dict[str, Any]], prefectures: list[dict[str, Any]]
) -> str:
    """Build compact catalog context for Gemini."""
    catalog_lines = []
    for d in datasets:
        code = d.get("data_code", "")
        name = d.get("data_name", "")
        keywords = ",".join(d.get("keywords", [])[:5])
        catalog_lines.append(f"- {code}: {name} (KW: {keywords})")

    pref_lines = []
    for p in prefectures:
        code = p.get("pref_code", "")
        name = p.get("pref_name", "")
        pref_lines.append(f"{code}:{name}")

    catalog_context = "\n".join(catalog_lines)
    pref_context = ", ".join(pref_lines)

    return f"""あなたは国土交通省の「国土数値情報」ダウンロードサービスを案内するGISデータ専門家アシスタントです。
ユーザーの自然言語による要望から、最適な国土数値情報の「データコード（data_code）」、「都道府県コード（pref_code: 2桁）」、「対象年度（year）」、「希望データ形式（format）」を特定し、提案オブジェクトを生成してください。

【ルール】
1. 利用可能なデータセット一覧から、ユーザーの意図に最も合致する data_code と data_name を選んでください。
2. 地域が指定されている場合、対応する2桁の pref_code と pref_name を特定してください。全国または特定地域が指定されていない場合は pref_code="00", pref_name="全国" としてください。
3. フォーマット指定がない場合は format="GeoJSON" をデフォルトとしてください。ユーザーが明示的に Shapefile/シェープ形式 や GML を要求した場合はそのフォーマットを指定してください。
4. 年度指定がない場合は year="latest" としてください。「2024年」「最新」などの指定があればそれに従ってください。
5. 提案の要約（summary）と 0.0〜1.0 の確信度スコア（confidence）を付与してください。

【都道府県マスター (コード:名称)】
{pref_context}

【国土数値情報データセット一覧 (コード: 名称 (KW: キーワード))】
{catalog_context}
"""


def heuristic_search(
    query: str,
    *,
    metadata_path: Path | None = None,
    pref_master_path: Path | None = None,
) -> Proposal:
    """Fallback keyword-based query parser with nationwide GSI geocoding when Gemini API is offline."""
    cleaned_query = query.strip()
    query_lower = cleaned_query.lower()

    # 1. Detect prefecture & location (using GSI address geocoding + prefecture matcher)
    pref_match = None
    all_prefs = get_prefectures()
    target_lat: float | None = None
    target_lng: float | None = None
    location_name: str | None = None

    # Check direct prefecture match first
    for p in all_prefs:
        if p.pref_code == "00":
            continue
        if (
            p.pref_name in cleaned_query
            or p.short_name in cleaned_query
            or p.kana in cleaned_query
            or any(alias in cleaned_query for alias in p.aliases)
            or p.romaji.lower() in query_lower
        ):
            pref_match = p
            break

    national_pref = next((p for p in all_prefs if p.pref_code == "00"), None)
    has_national_scope = national_pref is not None and any(
        alias in cleaned_query or alias.lower() in query_lower
        for alias in national_pref.aliases
    )

    if has_national_scope:
        pref_code, pref_name = "00", "全国"
    elif pref_match is not None:
        pref_code, pref_name = pref_match.pref_code, pref_match.pref_name
    else:
        # Try GSI nationwide geocoder for cities, towns, landmarks (e.g. 能登, 輪島市役所, 博多駅)
        geo_res = geocode_location(cleaned_query)
        if geo_res and geo_res.pref_code != "00":
            pref_code = geo_res.pref_code
            pref_name = geo_res.pref_name
            target_lat = geo_res.lat
            target_lng = geo_res.lng
            location_name = geo_res.location_name
        else:
            # Check for national keywords
            pref_code, pref_name = "00", "全国"

    # 2. Detect format
    if "shape" in query_lower or "shp" in query_lower or "シェープ" in cleaned_query:
        target_format = "Shapefile"
    elif "gml" in query_lower:
        target_format = "GML"
    else:
        target_format = "GeoJSON"

    # 3. Detect year
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", cleaned_query)
    if year_match:
        target_year = year_match.group(1)
    else:
        target_year = "latest"

    # 4. Score datasets
    datasets = _load_catalog_summary(metadata_path)
    best_dataset = None
    best_score = -1

    stop_words_pattern = r"(データ|情報|ポリゴン|シェープ|ファイル|ほしい|欲しい|がほしい|が欲しい|ください|について|コード|最新|年度|形式|メッシュ|の|を|が|は|に|で|へ|と|付近|周辺|近く|あたり|近くの|教えて|探して|取得して|ダウンロード)"
    clean_topic = cleaned_query
    if pref_name != "全国":
        clean_topic = clean_topic.replace(pref_name, "").replace(pref_name.rstrip("県府東京都道"), "")
    if location_name:
        clean_topic = clean_topic.replace(location_name, "")
    clean_topic = re.sub(stop_words_pattern, " ", clean_topic)

    raw_tokens = re.findall(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ffa-zA-Z0-9]+", clean_topic)
    topic_tokens = []
    for chunk in raw_tokens:
        if len(chunk) >= 2:
            topic_tokens.append(chunk)
            if len(chunk) >= 4:
                for i in range(len(chunk) - 1):
                    sub = chunk[i : i + 2]
                    topic_tokens.append(sub)
    topic_tokens = list(dict.fromkeys(topic_tokens))

    for d in datasets:
        score = 0
        code = d.get("data_code", "")
        name = d.get("data_name", "")
        keywords = d.get("keywords", [])

        # Exact code match in query
        if code and code.lower() in query_lower:
            score += 50

        # Exact name match in query
        if name and name in cleaned_query:
            score += 40

        # Topic tokens contained in name or keywords
        for tok in topic_tokens:
            if tok in name:
                score += 20 * len(tok)
            for kw in keywords:
                if tok in kw:
                    score += 10 * len(tok)

        # Keyword substring in query
        for kw in keywords:
            if kw and len(kw) >= 2 and kw in cleaned_query:
                score += 15

        if score > best_score:
            best_score = score
            best_dataset = d

    if best_dataset is None and datasets:
        best_dataset = datasets[0]

    if best_dataset:
        data_code = best_dataset.get("data_code", "A33")
        data_name = best_dataset.get("data_name", "国土数値情報")
        provider_id = best_dataset.get("provider_id", "gsi" if data_code.startswith("GSI-") else "mlit")
        provider_name = best_dataset.get("provider_name", "国土地理院（基盤地図情報）" if provider_id == "gsi" else "国土交通省（国土数値情報）")
        confidence = min(0.95, max(0.5, best_score / 50.0)) if best_score > 0 else 0.5
    else:
        data_code = "A33"
        data_name = "土砂災害警戒区域データ"
        provider_id = "mlit"
        provider_name = "国土交通省（国土数値情報）"
        confidence = 0.5

    loc_label = f"{location_name}（{pref_name}）" if location_name and location_name != pref_name else pref_name
    summary = f"{loc_label}の「{data_name}」（{data_code}、{target_year}版、{target_format}形式）"

    return Proposal(
        data_code=data_code,
        data_name=data_name,
        pref_code=pref_code,
        pref_name=pref_name,
        provider_id=provider_id,
        provider_name=provider_name,
        year=target_year,
        format=target_format,
        summary=summary,
        confidence=round(confidence, 2),
        location_name=location_name,
        target_lat=target_lat,
        target_lng=target_lng,
    )


def interpret_user_query(
    query: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    metadata_path: Path | None = None,
    pref_master_path: Path | None = None,
    timeout_seconds: float = 20.0,
) -> Proposal:
    """Analyze a user query using Gemini Structured Outputs with fallback to heuristic search."""
    settings = Settings.from_env()
    effective_api_key = api_key or settings.gemini_api_key
    effective_model = model or settings.gemini_model or "gemini-2.5-flash"

    if not effective_api_key:
        return heuristic_search(
            query,
            metadata_path=metadata_path,
            pref_master_path=pref_master_path,
        )

    datasets = _load_catalog_summary(metadata_path)
    prefectures = _load_prefectures(pref_master_path)
    system_prompt = build_system_prompt(datasets, prefectures)

    endpoint = f"{GEMINI_API_BASE_URL}/{effective_model}:generateContent?key={effective_api_key}"

    payload = {
        "systemInstruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": query}]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "data_code": {"type": "STRING"},
                    "data_name": {"type": "STRING"},
                    "pref_code": {"type": "STRING"},
                    "pref_name": {"type": "STRING"},
                    "year": {"type": "STRING"},
                    "format": {"type": "STRING"},
                    "summary": {"type": "STRING"},
                    "confidence": {"type": "NUMBER"},
                },
                "required": [
                    "data_code",
                    "data_name",
                    "pref_code",
                    "pref_name",
                    "year",
                    "format",
                    "summary",
                    "confidence",
                ],
            },
        },
    }

    try:
        response = requests.post(
            endpoint,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()

        candidates = data.get("candidates", [])
        if not candidates:
            return heuristic_search(
                query,
                metadata_path=metadata_path,
                pref_master_path=pref_master_path,
            )

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return heuristic_search(
                query,
                metadata_path=metadata_path,
                pref_master_path=pref_master_path,
            )

        raw_json = parts[0].get("text", "{}")
        parsed = json.loads(raw_json)

        # Normalize and validate returned fields
        data_code = parsed.get("data_code", "").strip()
        pref_code = parsed.get("pref_code", "00").strip().zfill(2)

        # Validate against prefectures
        pref_item = find_prefecture_by_code(pref_code)
        pref_name = pref_item.pref_name if pref_item else parsed.get("pref_name", "全国")

        data_name = parsed.get("data_name", "")
        provider_id = "gsi" if data_code.upper().startswith("GSI-") else "mlit"
        provider_name = "国土地理院（基盤地図情報）" if provider_id == "gsi" else "国土交通省（国土数値情報）"
        for d in datasets:
            if d.get("data_code", "").upper() == data_code.upper():
                data_code = d.get("data_code", data_code)
                provider_id = d.get("provider_id", provider_id)
                provider_name = d.get("provider_name", provider_name)
                if not data_name:
                    data_name = d.get("data_name", "")
                break

        target_lat: float | None = None
        target_lng: float | None = None
        location_name: str | None = None

        national_pref = next(
            (p for p in prefectures if p.get("pref_code") == "00"),
            {},
        )
        national_aliases = national_pref.get("aliases", ["全国", "日本"])
        has_national_scope = any(
            alias and alias.lower() in query.lower() for alias in national_aliases
        )
        if has_national_scope:
            pref_code, pref_name = "00", "全国"
        else:
            geo_res = geocode_location(query)
            if geo_res and geo_res.pref_code != "00":
                if pref_code == "00" or pref_code == geo_res.pref_code:
                    pref_code = geo_res.pref_code
                    pref_name = geo_res.pref_name
                target_lat = geo_res.lat
                target_lng = geo_res.lng
                location_name = geo_res.location_name

        summary = parsed.get("summary", "")
        if location_name and location_name != pref_name:
            summary = f"{location_name}（{pref_name}）の「{data_name}」（{data_code}、{parsed.get('year', 'latest')}版、{parsed.get('format', 'GeoJSON')}形式）"

        return Proposal(
            data_code=data_code,
            data_name=data_name or data_code,
            pref_code=pref_code,
            pref_name=pref_name,
            provider_id=provider_id,
            provider_name=provider_name,
            year=parsed.get("year", "latest"),
            format=parsed.get("format", "GeoJSON"),
            summary=summary or parsed.get("summary", ""),
            confidence=float(parsed.get("confidence", 0.9)),
            location_name=location_name,
            target_lat=target_lat,
            target_lng=target_lng,
        )

    except Exception:
        # Gracefully fallback to heuristic search if API fails
        return heuristic_search(
            query,
            metadata_path=metadata_path,
            pref_master_path=pref_master_path,
        )
