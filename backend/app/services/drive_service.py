"""Google Drive upload helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


DRIVE_SCOPES = ("https://www.googleapis.com/auth/drive.file",)
JSON_MIME_TYPE = "application/json"


@dataclass(frozen=True)
class DriveUploadResult:
    """Stable subset of the Drive file resource returned to callers."""

    file_id: str
    name: str
    web_view_link: str | None
    operation: str


def build_drive_service(
    *,
    credentials_path: Path | None = None,
    impersonate_user: str | None = None,
) -> Any:
    """Create a Drive v3 client from a service account or ADC credentials."""

    if credentials_path is not None:
        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path), scopes=DRIVE_SCOPES
        )
    else:
        credentials, _ = google.auth.default(scopes=DRIVE_SCOPES)

    if impersonate_user:
        if not hasattr(credentials, "with_subject"):
            raise ValueError(
                "GOOGLE_DRIVE_IMPERSONATE_USER requires service-account credentials"
            )
        credentials = credentials.with_subject(impersonate_user)

    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _escape_query_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def upsert_json_file(
    service: Any,
    *,
    local_path: Path,
    folder_id: str,
    drive_file_name: str = "metadata.json",
    shared_drive_id: str | None = None,
) -> DriveUploadResult:
    """Create or update one JSON file in a Drive folder without duplication."""

    if not local_path.is_file():
        raise FileNotFoundError(local_path)
    if not folder_id.strip():
        raise ValueError("folder_id is required")
    if not drive_file_name.strip():
        raise ValueError("drive_file_name is required")

    escaped_name = _escape_query_literal(drive_file_name)
    escaped_folder_id = _escape_query_literal(folder_id)
    list_arguments: dict[str, Any] = {
        "q": (
            f"name = '{escaped_name}' and "
            f"'{escaped_folder_id}' in parents and trashed = false"
        ),
        "spaces": "drive",
        "orderBy": "modifiedTime desc",
        "pageSize": 1,
        "fields": "files(id,name,webViewLink,modifiedTime)",
        "includeItemsFromAllDrives": True,
    }
    if shared_drive_id:
        list_arguments.update(corpora="drive", driveId=shared_drive_id)

    existing_files = service.files().list(**list_arguments).execute().get("files", [])
    media = MediaFileUpload(
        str(local_path), mimetype=JSON_MIME_TYPE, resumable=False
    )
    fields = "id,name,webViewLink"

    if existing_files:
        response = (
            service.files()
            .update(
                fileId=existing_files[0]["id"],
                body={"name": drive_file_name},
                media_body=media,
                fields=fields,
                supportsAllDrives=True,
            )
            .execute()
        )
        operation = "updated"
    else:
        response = (
            service.files()
            .create(
                body={"name": drive_file_name, "parents": [folder_id]},
                media_body=media,
                fields=fields,
                supportsAllDrives=True,
            )
            .execute()
        )
        operation = "created"

    return DriveUploadResult(
        file_id=response["id"],
        name=response.get("name", drive_file_name),
        web_view_link=response.get("webViewLink"),
        operation=operation,
    )
