"""FastAPI application entrypoint for GIS Data Downloads."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import DEFAULT_METADATA_PATH, Settings
from app.models.schemas import (
    DownloadRequest as DownloadRequestData,
    DownloadResponse as DownloadResponseData,
    Proposal as ProposalData,
    SearchRequest as SearchRequestData,
    SearchResponse as SearchResponseData,
)
from app.services.drive_service import (
    ZIP_MIME_TYPE,
    build_drive_service,
    get_or_create_subfolder,
    upsert_file,
)
from app.providers.router import download_dataset_across_providers
from app.services.gemini_service import interpret_user_query
from app.services.prefecture_service import get_prefectures
from app.services.scraper_service import (
    download_file,
    extract_download_candidates,
    fetch_detail_page_html,
    resolve_detail_url,
    select_best_candidate,
)


app = FastAPI(
    title="GIS Data Downloads API",
    description="Natural language GIS dataset search and download service for MLIT National Land Numerical Information.",
    version="1.0.0",
)

# Enable CORS for local Next.js development and Vercel deployments
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequestBody(BaseModel):
    query: str = Field(..., description="自然言語による検索クエリ", examples=["富山県の土砂災害データ"])


class DownloadRequestBody(BaseModel):
    data_code: str = Field(..., description="国土数値情報データコード", examples=["A33"])
    pref_code: str = Field("00", description="都道府県コード (例: 16, 00)", examples=["16"])
    year: str = Field("latest", description="対象年度", examples=["latest"])
    format: str | None = Field(None, description="希望フォーマット (例: GeoJSON, Shapefile, GML)", examples=["GeoJSON"])


@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "message": "GIS Data Downloads API is running"}


@app.get("/api/prefectures", tags=["Master"])
def list_prefectures() -> list[dict[str, Any]]:
    """Return all prefecture definitions."""
    return [asdict(p) for p in get_prefectures()]


@app.get("/api/datasets", tags=["Master"])
def list_datasets() -> list[dict[str, Any]]:
    """Return the list of available datasets from metadata catalog."""
    if not DEFAULT_METADATA_PATH.is_file():
        return []
    try:
        data = json.loads(DEFAULT_METADATA_PATH.read_text(encoding="utf-8"))
        return data.get("datasets", [])
    except Exception:
        return []


@app.post("/api/search", tags=["Search"])
def search_dataset(body: SearchRequestBody) -> dict[str, Any]:
    """Analyze natural language query and propose matching GIS dataset."""
    if not body.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="検索クエリを入力してください。",
        )

    try:
        proposal = interpret_user_query(body.query.strip())
        return {
            "status": "success",
            "proposal": proposal.to_dict(),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"検索処理中にエラーが発生しました: {str(exc)}",
        )


@app.post("/api/download", tags=["Download"])
def download_dataset(body: DownloadRequestBody) -> dict[str, Any]:
    settings = Settings.from_env()
    try:
        # Local destination with date subfolder
        date_folder = datetime.now().strftime("%Y-%m-%d")
        output_dir = Path(__file__).resolve().parents[1] / "downloads" / date_folder

        result = download_dataset_across_providers(
            data_code=body.data_code,
            pref_code=body.pref_code,
            year=body.year,
            format_preference=body.format,
            output_dir=output_dir,
        )

        response_data: dict[str, Any] = {
            "status": "completed",
            "provider_id": result.provider_id,
            "provider_name": result.provider_name,
            "data_code": result.data_code,
            "pref_code": result.pref_code,
            "region_name": result.region_name,
            "year": result.year,
            "format": result.format,
            "file_name": result.file_name,
            "file_size_mb": result.file_size_mb,
            "direct_download_url": result.direct_download_url,
            "drive_file_id": None,
            "drive_web_view_link": None,
        }

        # Google Drive upload if folder configured
        if settings.google_drive_folder_id and result.local_path and result.local_path.is_file():
            try:
                service = build_drive_service(
                    credentials_path=settings.google_application_credentials,
                    impersonate_user=settings.google_drive_impersonate_user,
                )
                target_drive_folder_id = get_or_create_subfolder(
                    service,
                    folder_name=date_folder,
                    parent_folder_id=settings.google_drive_folder_id,
                    shared_drive_id=settings.google_drive_shared_drive_id,
                )
                upload_result = upsert_file(
                    service,
                    local_path=downloaded_path,
                    folder_id=target_drive_folder_id,
                    mime_type=ZIP_MIME_TYPE,
                    shared_drive_id=settings.google_drive_shared_drive_id,
                )
                response_data["drive_file_id"] = upload_result.file_id
                response_data["drive_web_view_link"] = upload_result.web_view_link
                response_data["google_drive"] = asdict(upload_result)
            except Exception as drive_error:
                response_data["drive_upload_error"] = str(drive_error)

        return response_data

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ダウンロード処理中にエラーが発生しました: {str(exc)}",
        )
