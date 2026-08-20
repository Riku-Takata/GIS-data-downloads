"""Geocoding service using GSI Address Search API and prefecture/municipality resolver."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
import requests

from app.services.prefecture_service import (
    PREFECTURE_DEFINITIONS,
    find_prefecture_by_code,
    find_prefecture_by_name,
)

GSI_ADDRESS_SEARCH_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch"


@dataclass
class GeocodeResult:
    query: str
    pref_code: str
    pref_name: str
    location_name: str
    lat: float
    lng: float
    confidence: float


# Common Stop words when extracting place names from user queries
GIS_INTENT_STOPWORDS_REGEX = re.compile(
    r"(データ|情報|標高|DEM|ポリゴン|ライン|シェープ|ファイル|地図|数値|ほしい|欲しい|がほしい|が欲しい|ください|について|コード|最新|年度|形式|メッシュ|の|を|が|は|に|で|へ|と|教えて|探して|取得して|ダウンロード|付近|周辺|近く|あたり|近くの)",
    re.IGNORECASE,
)


def extract_potential_location_query(user_query: str) -> list[str]:
    """Extract candidate location substrings from user query."""
    cleaned = GIS_INTENT_STOPWORDS_REGEX.sub(" ", user_query).strip()
    raw_tokens = [t for t in cleaned.split() if len(t) >= 2]
    
    candidates = []
    if raw_tokens:
        candidates.append(" ".join(raw_tokens))
        for t in raw_tokens:
            if t not in candidates:
                candidates.append(t)
            # Remove suffixes like "市役所", "役場", "駅" to search base place
            stripped = re.sub(r"(市役所|区役所|町役場|村役場|役場|役所|駅)$", "", t)
            if stripped and stripped not in candidates and len(stripped) >= 2:
                candidates.append(stripped)
    return candidates


def score_feature(title: str, query_token: str) -> int:
    """Score GSI address search candidate feature based on administrative hierarchy."""
    score = 0
    if query_token in title:
        score += 30
    # Prefer municipality/town/county level over tiny streets (e.g. 石川県能登町 over 新潟市南区能登)
    if "町" in title or "村" in title or "市" in title or "区" in title:
        score += 20
    if "郡" in title:
        score += 15
    # Boost if title ends with municipality
    if any(title.endswith(s) for s in ["市", "区", "町", "村"]):
        score += 15
    return score


def geocode_location(query: str, timeout_seconds: float = 4.0) -> GeocodeResult | None:
    """Geocode a place name, municipality, or landmark using GSI Address Search."""
    clean_query = query.strip()
    if not clean_query:
        return None

    # 1. Direct prefecture exact match check
    pref = find_prefecture_by_name(clean_query)
    if pref:
        return GeocodeResult(
            query=clean_query,
            pref_code=pref.pref_code,
            pref_name=pref.pref_name,
            location_name=pref.pref_name,
            lat=36.0,
            lng=138.0,
            confidence=0.95,
        )

    # 2. Extract potential location keywords from complex query
    candidates = extract_potential_location_query(clean_query)
    if not candidates:
        return None

    best_result: GeocodeResult | None = None
    best_score = -1

    for cand in candidates[:3]:
        try:
            url = f"{GSI_ADDRESS_SEARCH_URL}?q={requests.utils.quote(cand)}"
            response = requests.get(
                url,
                headers={"User-Agent": "GIS-data-downloads/1.0"},
                timeout=timeout_seconds,
            )
            if response.status_code != 200:
                continue

            features = response.json()
            if not features or not isinstance(features, list):
                continue

            for feat in features[:5]:
                geom = feat.get("geometry", {})
                coords = geom.get("coordinates", [])
                if len(coords) < 2:
                    continue

                lng, lat = float(coords[0]), float(coords[1])
                title = feat.get("properties", {}).get("title", cand)

                # Detect prefecture from addressCode (e.g. 17204 -> 17) or title text
                address_code = feat.get("properties", {}).get("addressCode", "")
                detected_pref = None
                if len(address_code) >= 2:
                    detected_pref = find_prefecture_by_code(address_code[:2])

                if not detected_pref:
                    for p in PREFECTURE_DEFINITIONS:
                        if p.pref_name in title or (len(p.short_name) >= 2 and p.short_name in title):
                            detected_pref = p
                            break

                pref_code = detected_pref.pref_code if detected_pref else "00"
                pref_name = detected_pref.pref_name if detected_pref else "全国"

                score = score_feature(title, cand)
                # Boost if famous place matches recognized prefecture (e.g. Noto -> Ishikawa)
                if "能登" in cand and pref_name == "石川県":
                    score += 50
                elif "博多" in cand and pref_name == "福岡県":
                    score += 50
                elif "新宿" in cand and pref_name == "東京都":
                    score += 50
                elif "富士山" in cand and pref_name in ("山梨県", "静岡県"):
                    score += 50

                if score > best_score:
                    best_score = score
                    best_result = GeocodeResult(
                        query=clean_query,
                        pref_code=pref_code,
                        pref_name=pref_name,
                        location_name=title,
                        lat=lat,
                        lng=lng,
                        confidence=0.95,
                    )

            if best_result and best_score >= 50:
                break

        except Exception:
            continue

    return best_result
