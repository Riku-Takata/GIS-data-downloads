"""Build search metadata from the MLIT National Land Numerical Information catalog."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag
import requests


DATASET_PAGE_PATTERN = re.compile(r"KsjTmplt-(?P<page_id>[^/?#]+)\.html$")
PAGE_VERSION_SUFFIX_PATTERN = re.compile(
    r"(?:-v\d+(?:_\d+)*|-\d{4})$", re.IGNORECASE
)
PARENTHETICAL_PATTERN = re.compile(r"[（(][^）)]*[）)]")
LEADING_CATEGORY_NUMBER_PATTERN = re.compile(r"^\d+[.．]\s*")
MATERIAL_ICON_TEXT = "arrow_drop_down"
USER_AGENT = "GIS-data-downloads/1.0 (metadata catalog updater)"


@dataclass(frozen=True)
class MetadataDataset:
    """One searchable dataset from the official catalog."""

    data_code: str
    data_name: str
    category: str
    subcategory: str | None
    keywords: list[str]
    detail_url: str


def _clean_text(value: str) -> str:
    return " ".join(value.replace(MATERIAL_ICON_TEXT, "").split())


def _find_category(anchor: Tag) -> tuple[str, str | None]:
    container = anchor.find_parent("ul", class_="collapsible")
    if not isinstance(container, Tag):
        return "", None

    header = container.find("div", class_="collapsible-header")
    category = _clean_text(header.get_text(" ", strip=True)) if header else ""

    subcategory = None
    for candidate in anchor.find_all_previous("span", class_="white-text"):
        if candidate.find_parent("ul", class_="collapsible") is container:
            subcategory = _clean_text(candidate.get_text(" ", strip=True))
            break

    return category, subcategory


def _build_keywords(
    *, data_code: str, data_name: str, category: str, subcategory: str | None
) -> list[str]:
    base_name = _clean_text(PARENTHETICAL_PATTERN.sub("", data_name))
    category_name = LEADING_CATEGORY_NUMBER_PATTERN.sub("", category)

    values = [data_name, base_name, data_code, category_name, subcategory]
    keywords: list[str] = []
    for value in values:
        if value and value not in keywords:
            keywords.append(value)
    return keywords


def parse_catalog_html(
    html: str,
    *,
    source_url: str,
    detail_base_url: str,
) -> list[MetadataDataset]:
    """Parse the official catalog HTML into deterministic metadata records."""

    if urlsplit(source_url).scheme not in {"http", "https"}:
        raise ValueError("source_url must use HTTP or HTTPS")
    if urlsplit(detail_base_url).scheme not in {"http", "https"}:
        raise ValueError("detail_base_url must use HTTP or HTTPS")

    soup = BeautifulSoup(html, "html.parser")
    datasets: list[MetadataDataset] = []
    seen: set[tuple[str, str]] = set()

    # The top page also contains promotional and ranking cards. Restrict parsing
    # to the categorized catalog so every record has stable classification data.
    for anchor in soup.select("ul.collapsible a[href]"):
        if not isinstance(anchor, Tag):
            continue

        href = str(anchor["href"])
        match = DATASET_PAGE_PATTERN.search(urlsplit(href).path)
        if match is None:
            continue

        page_id = match.group("page_id")
        data_code = PAGE_VERSION_SUFFIX_PATTERN.sub("", page_id)
        data_name = _clean_text(anchor.get_text(" ", strip=True))
        if not data_name:
            continue

        identity = (data_code, data_name)
        if identity in seen:
            continue
        seen.add(identity)

        category, subcategory = _find_category(anchor)
        detail_filename = f"KsjTmplt-{page_id}.html"
        detail_url = urljoin(detail_base_url.rstrip("/") + "/", detail_filename)

        datasets.append(
            MetadataDataset(
                data_code=data_code,
                data_name=data_name,
                category=category,
                subcategory=subcategory,
                keywords=_build_keywords(
                    data_code=data_code,
                    data_name=data_name,
                    category=category,
                    subcategory=subcategory,
                ),
                detail_url=detail_url,
            )
        )

    datasets.sort(key=lambda item: (item.data_code, item.data_name))
    return datasets


def fetch_catalog_html(source_url: str, *, timeout_seconds: float) -> str:
    """Download the catalog HTML with a bounded timeout."""

    response = requests.get(
        source_url,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def build_metadata_document(
    datasets: list[MetadataDataset],
    *,
    source_url: str,
    retrieved_at: datetime | None = None,
) -> dict[str, Any]:
    """Create the versioned JSON document stored locally and in Drive."""

    timestamp = retrieved_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    timestamp_text = timestamp.astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )

    return {
        "schema_version": 1,
        "source": {
            "name": "国土数値情報ダウンロードサービス",
            "url": source_url,
            "retrieved_at": timestamp_text,
        },
        "dataset_count": len(datasets),
        "datasets": [asdict(dataset) for dataset in datasets],
    }


def write_metadata_document(document: dict[str, Any], output_path: Path) -> None:
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
