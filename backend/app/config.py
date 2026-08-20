"""Application settings loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METADATA_PATH = PROJECT_ROOT / "backend" / "app" / "data" / "metadata.json"
DEFAULT_PREF_MASTER_PATH = PROJECT_ROOT / "backend" / "app" / "data" / "pref_master.json"


def _optional_env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the metadata and master update batches."""

    metadata_source_url: str
    detail_base_url: str
    metadata_output_path: Path
    pref_master_output_path: Path
    http_timeout_seconds: float
    gemini_api_key: str | None
    gemini_model: str
    google_application_credentials: Path | None
    google_drive_folder_id: str | None
    google_drive_shared_drive_id: str | None
    google_drive_metadata_filename: str
    google_drive_pref_master_filename: str
    google_drive_impersonate_user: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(PROJECT_ROOT / ".env")

        output_value = os.getenv("METADATA_OUTPUT_PATH", str(DEFAULT_METADATA_PATH))
        output_path = Path(output_value).expanduser()
        if not output_path.is_absolute():
            output_path = PROJECT_ROOT / output_path

        pref_output_value = os.getenv("PREF_MASTER_OUTPUT_PATH", str(DEFAULT_PREF_MASTER_PATH))
        pref_output_path = Path(pref_output_value).expanduser()
        if not pref_output_path.is_absolute():
            pref_output_path = PROJECT_ROOT / pref_output_path

        credentials_value = _optional_env("GOOGLE_APPLICATION_CREDENTIALS")
        credentials_path = (
            Path(credentials_value).expanduser() if credentials_value is not None else None
        )

        timeout = float(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))
        if timeout <= 0:
            raise ValueError("HTTP_TIMEOUT_SECONDS must be greater than zero")

        return cls(
            metadata_source_url=os.getenv(
                "KSJ_METADATA_SOURCE_URL",
                "https://nlftp.mlit.go.jp/ksj/",
            ),
            detail_base_url=os.getenv(
                "KSJ_DETAIL_BASE_URL",
                "https://nlftp.mlit.go.jp/ksj/gml/datalist/",
            ),
            metadata_output_path=output_path,
            pref_master_output_path=pref_output_path,
            http_timeout_seconds=timeout,
            gemini_api_key=_optional_env("GEMINI_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            google_application_credentials=credentials_path,
            google_drive_folder_id=_optional_env("GOOGLE_DRIVE_FOLDER_ID"),
            google_drive_shared_drive_id=_optional_env(
                "GOOGLE_DRIVE_SHARED_DRIVE_ID"
            ),
            google_drive_metadata_filename=os.getenv(
                "GOOGLE_DRIVE_METADATA_FILENAME", "metadata.json"
            ),
            google_drive_pref_master_filename=os.getenv(
                "GOOGLE_DRIVE_PREF_MASTER_FILENAME", "pref_master.json"
            ),
            google_drive_impersonate_user=_optional_env(
                "GOOGLE_DRIVE_IMPERSONATE_USER"
            ),
        )
