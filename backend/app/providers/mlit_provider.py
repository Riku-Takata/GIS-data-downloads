"""MLIT (国土交通省 国土数値情報) GIS Data Provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.providers.base import BaseGISProvider, GISDatasetCandidate, ProviderDownloadResult
from app.services.metadata_service import load_metadata
from app.services.prefecture_service import find_prefecture_by_code
from app.services.scraper_service import (
    download_file,
    extract_download_candidates,
    fetch_detail_page_html,
    resolve_detail_url,
    select_best_candidate,
)


class MLITProvider(BaseGISProvider):
    """Provider for MLIT KSJ (国土交通省 国土数値情報) 133 datasets."""

    @property
    def provider_id(self) -> str:
        return "mlit"

    @property
    def provider_name(self) -> str:
        return "国土交通省（国土数値情報）"

    def list_datasets(self) -> list[GISDatasetCandidate]:
        metadata = load_metadata()
        results: list[GISDatasetCandidate] = []
        for d in metadata.get("datasets", []):
            if d.get("provider_id") == "gsi":
                continue
            results.append(
                GISDatasetCandidate(
                    provider_id=self.provider_id,
                    provider_name=self.provider_name,
                    data_code=d.get("data_code", ""),
                    data_name=d.get("data_name", ""),
                    category=d.get("category", ""),
                    keywords=d.get("keywords", []),
                    detail_url=d.get("detail_url", ""),
                    default_format="GeoJSON",
                )
            )
        return results

    def download(
        self,
        data_code: str,
        pref_code: str,
        year: str = "latest",
        format_preference: str | None = "GeoJSON",
        output_dir: Path | None = None,
    ) -> ProviderDownloadResult:
        detail_url = resolve_detail_url(data_code)
        html = fetch_detail_page_html(detail_url)
        candidates = extract_download_candidates(html, detail_url=detail_url, data_code=data_code)
        if not candidates:
            raise ValueError(f"国土数値情報 {data_code} のダウンロード候補が見つかりませんでした ({detail_url})。")

        target_pref = None if pref_code in ("00", "") else pref_code
        best = select_best_candidate(
            candidates,
            pref_code=target_pref,
            year=year,
            format_preference=format_preference or "GeoJSON",
        )
        if not best:
            raise ValueError(f"指定条件（data_code={data_code}, pref_code={pref_code}）に一致するデータが見つかりませんでした。")

        out_dir = output_dir or (Path(__file__).resolve().parents[2] / "downloads")
        target_path = out_dir / best.file_name
        local_path = download_file(best.download_url, target_path)

        pref_info = find_prefecture_by_code(pref_code)
        region_name = pref_info.pref_name if pref_info else best.region_name

        return ProviderDownloadResult(
            status="downloaded",
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            data_code=best.data_code,
            pref_code=pref_code,
            region_name=region_name,
            year=best.year_numeric or best.year_text or "latest",
            format=best.format_name,
            file_name=best.file_name,
            file_size_mb=best.file_size_mb,
            local_path=local_path,
            direct_download_url=best.download_url,
        )
