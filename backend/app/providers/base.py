"""Provider abstraction layer for multi-source GIS open data."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GISDatasetCandidate:
    """Standardized dataset item from any GIS provider."""

    provider_id: str
    provider_name: str
    data_code: str
    data_name: str
    category: str
    keywords: list[str]
    detail_url: str
    default_format: str = "GeoJSON"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderDownloadResult:
    """Standardized download result across all providers."""

    status: str
    provider_id: str
    provider_name: str
    data_code: str
    pref_code: str
    region_name: str
    year: str | int
    format: str
    file_name: str
    file_size_mb: float | None
    local_path: Path | None = None
    direct_download_url: str = ""
    drive_file_id: str | None = None
    drive_web_view_link: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if self.local_path:
            result["local_path"] = str(self.local_path)
        return result


class BaseGISProvider(ABC):
    """Abstract base class for all GIS open data providers."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier (e.g. 'mlit', 'gsi', 'plateau', 'geospatial_jp')."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name (e.g. '国土交通省（国土数値情報）', '国土地理院（基盤地図情報）')."""
        pass

    @abstractmethod
    def list_datasets(self) -> list[GISDatasetCandidate]:
        """Return available dataset catalog for this provider."""
        pass

    @abstractmethod
    def download(
        self,
        data_code: str,
        pref_code: str,
        year: str = "latest",
        format_preference: str | None = None,
        output_dir: Path | None = None,
    ) -> ProviderDownloadResult:
        """Download dataset and package as ZIP / GeoJSON."""
        pass
