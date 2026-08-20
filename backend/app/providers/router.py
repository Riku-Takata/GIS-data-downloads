"""Multi-Source Provider Router & Dispatcher."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.providers.base import BaseGISProvider, GISDatasetCandidate, ProviderDownloadResult
from app.providers.gsi_provider import GSIProvider
from app.providers.mlit_provider import MLITProvider

_PROVIDERS: dict[str, BaseGISProvider] = {
    "mlit": MLITProvider(),
    "gsi": GSIProvider(),
}


def get_provider_by_id(provider_id: str) -> BaseGISProvider:
    """Get provider instance by ID ('mlit', 'gsi'). Defaults to MLIT."""
    return _PROVIDERS.get(provider_id.lower(), _PROVIDERS["mlit"])


def resolve_provider_for_data_code(data_code: str) -> BaseGISProvider:
    """Resolve provider by data_code (e.g. 'GSI-DEM5A' -> GSI, 'A33' -> MLIT)."""
    if data_code.upper().startswith("GSI-"):
        return _PROVIDERS["gsi"]
    return _PROVIDERS["mlit"]


def list_all_available_datasets() -> list[GISDatasetCandidate]:
    """Aggregate datasets across all active providers."""
    results: list[GISDatasetCandidate] = []
    for p in _PROVIDERS.values():
        results.extend(p.list_datasets())
    return results


def download_dataset_across_providers(
    data_code: str,
    pref_code: str,
    year: str = "latest",
    format_preference: str | None = "GeoJSON",
    output_dir: Path | None = None,
) -> ProviderDownloadResult:
    """Route download request to the appropriate provider."""
    provider = resolve_provider_for_data_code(data_code)
    return provider.download(
        data_code=data_code,
        pref_code=pref_code,
        year=year,
        format_preference=format_preference,
        output_dir=output_dir,
    )
