"""Scraper and downloader service for MLIT National Land Numerical Information datasets."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import requests

from app.config import DEFAULT_METADATA_PATH
from app.services.prefecture_service import (
    find_prefecture_by_code,
    find_prefecture_by_name,
)


USER_AGENT = "GIS-data-downloads/1.0 (dataset downloader)"
DOWNLD_CALL_PATTERN = re.compile(
    r"DownLd\s*\(\s*['\"](?P<size>[^'\"]*)['\"]\s*,\s*['\"](?P<filename>[^'\"]*)['\"]\s*,\s*['\"](?P<rel_url>[^'\"]*)['\"]",
    re.IGNORECASE,
)
FOUR_DIGIT_YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")
TWO_DIGIT_YEAR_FILENAME_PATTERN = re.compile(
    r"^[A-Za-z0-9]+-(?P<year_2d>\d{2})(?:_\d{2})?_"
)
ERA_YEAR_PATTERN = re.compile(r"(?:令和|平成|昭和)\s*(?P<era_num>\d+|元)年")


@dataclass(frozen=True)
class DownloadableItem:
    """Represents a downloadable dataset file from a KSJ detail page."""

    data_code: str
    pref_code: str
    region_name: str
    year_text: str
    year_numeric: int | None
    format_name: str
    geodetic_system: str
    file_name: str
    file_size_text: str
    file_size_mb: float | None
    download_url: str


def _parse_size_mb(size_text: str) -> float | None:
    cleaned = size_text.strip().upper().replace(" ", "")
    if not cleaned:
        return None
    try:
        if cleaned.endswith("GB"):
            return round(float(cleaned[:-2]) * 1024.0, 2)
        if cleaned.endswith("MB"):
            return round(float(cleaned[:-2]), 2)
        if cleaned.endswith("KB"):
            return round(float(cleaned[:-2]) / 1024.0, 3)
        if cleaned.endswith("B"):
            return round(float(cleaned[:-1]) / (1024.0 * 1024.0), 4)
        return float(cleaned)
    except ValueError:
        return None


def _normalize_format_name(raw_text: str, filename: str) -> str:
    combined = (raw_text + " " + filename).lower()
    if "シェープ" in combined or "shape" in combined or "_shp" in combined:
        return "Shapefile"
    if "geojson" in combined or "_geojson" in combined:
        return "GeoJSON"
    if "gml" in combined or "_gml" in combined:
        return "GML"
    return "ZIP"


def _extract_year_numeric(
    year_text: str, filename: str
) -> int | None:
    # 1. Check for 4-digit year in text
    four_digit_match = FOUR_DIGIT_YEAR_PATTERN.search(year_text)
    if four_digit_match:
        return int(four_digit_match.group(1))

    # 2. Check for Japanese era in text
    era_match = ERA_YEAR_PATTERN.search(year_text)
    if era_match:
        era_val = era_match.group("era_num")
        era_int = 1 if era_val == "元" else int(era_val)
        if "令和" in year_text:
            return 2018 + era_int
        if "平成" in year_text:
            return 1988 + era_int
        if "昭和" in year_text:
            return 1925 + era_int

    # 3. Check for 2-digit year in filename (e.g. A33-25_16_SHP.zip -> 2025)
    two_digit_match = TWO_DIGIT_YEAR_FILENAME_PATTERN.search(filename)
    if two_digit_match:
        y2 = int(two_digit_match.group("year_2d"))
        return 2000 + y2 if y2 < 70 else 1900 + y2

    # 4. Check for 4-digit year in filename (e.g. N03-20240101_GML.zip -> 2024)
    four_digit_fn_match = FOUR_DIGIT_YEAR_PATTERN.search(filename)
    if four_digit_fn_match:
        return int(four_digit_fn_match.group(1))

    return None


def _detect_pref_code(
    region_text: str, filename: str
) -> tuple[str, str]:
    # Check region text against prefecture definitions
    pref = find_prefecture_by_name(region_text)
    if pref is not None:
        return pref.pref_code, pref.pref_name

    # Check for "全国"
    if "全国" in region_text:
        return "00", "全国"

    # Check filename for pref code pattern (e.g., A33-25_16_SHP.zip -> 16)
    parts = filename.split("_")
    if len(parts) >= 2 and parts[1].isdigit() and len(parts[1]) == 2:
        code = parts[1]
        pref_by_code = find_prefecture_by_code(code)
        if pref_by_code:
            return pref_by_code.pref_code, pref_by_code.pref_name

    return "00", region_text or "全国"


def extract_download_candidates(
    html: str,
    *,
    detail_url: str,
    data_code: str | None = None,
) -> list[DownloadableItem]:
    """Parse detail page HTML and extract all available download items."""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[DownloadableItem] = []
    seen_urls: set[str] = set()

    # Fallback data_code from URL if not given
    derived_code = data_code or ""
    if not derived_code:
        path = urlsplit(detail_url).path
        match = re.search(r"KsjTmplt-([A-Za-z0-9]+)", path)
        if match:
            derived_code = match.group(1)

    for tr in soup.find_all("tr"):
        onclick_link = tr.find("a", onclick=DOWNLD_CALL_PATTERN)
        direct_link = tr.find("a", href=lambda h: bool(h and ".zip" in h.lower()))

        if not onclick_link and not direct_link:
            continue

        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"])]
        full_text = " ".join(cells)

        if onclick_link:
            match = DOWNLD_CALL_PATTERN.search(str(onclick_link.get("onclick", "")))
            if not match:
                continue
            size_str, filename, rel_url = (
                match.group("size"),
                match.group("filename"),
                match.group("rel_url"),
            )
            download_url = urljoin(detail_url, rel_url)
        else:
            filename = str(direct_link.get_text(" ", strip=True)) or os.path.basename(
                urlsplit(str(direct_link.get("href", ""))).path
            )
            rel_url = str(direct_link.get("href", ""))
            download_url = urljoin(detail_url, rel_url)
            size_str = ""

        if download_url in seen_urls:
            continue
        seen_urls.add(download_url)

        # Region extraction
        region_candidate = cells[0] if len(cells) > 0 else ""
        pref_code, region_name = _detect_pref_code(region_candidate, filename)

        # Geodetic system extraction
        geodetic = "世界測地系" if "世界測地系" in full_text else ("日本測地系" if "日本測地系" in full_text else "")

        # Format extraction
        format_name = _normalize_format_name(full_text, filename)

        # Year extraction
        year_numeric = _extract_year_numeric(full_text, filename)

        # Code inference from filename if not derived
        item_code = derived_code
        if not item_code and "-" in filename:
            item_code = filename.split("-")[0]

        candidates.append(
            DownloadableItem(
                data_code=item_code,
                pref_code=pref_code,
                region_name=region_name,
                year_text=full_text,
                year_numeric=year_numeric,
                format_name=format_name,
                geodetic_system=geodetic,
                file_name=filename,
                file_size_text=size_str,
                file_size_mb=_parse_size_mb(size_str),
                download_url=download_url,
            )
        )

    return candidates


def select_best_candidate(
    candidates: list[DownloadableItem],
    *,
    pref_code: str = "00",
    year: str | int = "latest",
    format_preference: str | None = None,
) -> DownloadableItem | None:
    """Select the best matching download item based on prefecture, year, and format preference."""
    if not candidates:
        return None

    target_pref_code = pref_code.strip().zfill(2)

    # 1. Filter candidates by pref_code (with fallback to 00 if no prefecture-specific items exist)
    matching_pref = [c for c in candidates if c.pref_code == target_pref_code]
    if not matching_pref and target_pref_code != "00":
        matching_pref = [c for c in candidates if c.pref_code == "00"]

    if not matching_pref:
        matching_pref = candidates

    # 2. Filter by year if specific year is requested
    if str(year).lower() != "latest" and year is not None:
        target_year_str = str(year).strip()
        target_year_num = int(target_year_str) if target_year_str.isdigit() else None
        by_year = [
            c
            for c in matching_pref
            if (target_year_num is not None and c.year_numeric == target_year_num)
            or target_year_str in c.year_text
            or target_year_str in c.file_name
        ]
        if by_year:
            matching_pref = by_year

    # 3. Sort by format preference, year (descending), exact pref_code match, and filename
    pref_format_normalized = (format_preference or "").lower()

    def sort_key(item: DownloadableItem) -> tuple[int, int, int, str]:
        # Format match score: GeoJSON (highest) > Shapefile > GML > other
        format_match = 0
        if pref_format_normalized:
            if (
                pref_format_normalized in item.format_name.lower()
                or (pref_format_normalized in {"shp", "shapefile"} and item.format_name == "Shapefile")
                or (pref_format_normalized in {"geojson"} and item.format_name == "GeoJSON")
                or (pref_format_normalized in {"gml"} and item.format_name == "GML")
            ):
                format_match = 10

        if format_match == 0:
            if item.format_name == "GeoJSON":
                format_match = 3
            elif item.format_name == "Shapefile":
                format_match = 2
            elif item.format_name == "GML":
                format_match = 1

        # Exact pref match score
        pref_match = 1 if item.pref_code == target_pref_code else 0

        # Year score
        year_score = item.year_numeric if item.year_numeric is not None else 0

        return (format_match, year_score, pref_match, item.file_name)

    matching_pref.sort(key=sort_key, reverse=True)
    return matching_pref[0]


def resolve_detail_url(
    data_code: str, *, metadata_path: Path | None = None
) -> str:
    """Resolve the detail page URL for a given data_code using metadata.json."""
    catalog_path = metadata_path or DEFAULT_METADATA_PATH
    if catalog_path.is_file():
        try:
            document = json.loads(catalog_path.read_text(encoding="utf-8"))
            for dataset in document.get("datasets", []):
                if dataset.get("data_code", "").upper() == data_code.strip().upper():
                    detail_url = dataset.get("detail_url")
                    if detail_url:
                        return detail_url
        except Exception:
            pass

    # Fallback to standard URL convention
    clean_code = data_code.strip().upper()
    return f"https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-{clean_code}.html"


def fetch_detail_page_html(
    detail_url: str, *, timeout_seconds: float = 30.0
) -> str:
    """Download the detail page HTML with bounded timeout."""
    response = requests.get(
        detail_url,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def download_file(
    download_url: str,
    output_path: Path,
    *,
    timeout_seconds: float = 60.0,
    chunk_size: int = 65536,
) -> Path:
    """Download a remote file atomically."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path: Path | None = None
    try:
        response = requests.get(
            download_url,
            headers={"User-Agent": USER_AGENT},
            stream=True,
            timeout=timeout_seconds,
        )
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    temporary_file.write(chunk)
            temporary_path = Path(temporary_file.name)

        os.replace(temporary_path, output_path)
        return output_path
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
