"""Google Drive upload helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import google.auth
from google.auth import load_credentials_from_file
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


# The configured folder can be an existing My Drive folder. The narrower
# drive.file scope cannot discover arbitrary folders that were not opened with
# this application, so user OAuth requires full Drive access.
DRIVE_SCOPES = ("https://www.googleapis.com/auth/drive",)
JSON_MIME_TYPE = "application/json"
ZIP_MIME_TYPE = "application/zip"
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


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
    """Create a Drive v3 client from a service account, user OAuth, or ADC."""

    if credentials_path is not None:
        credentials, _ = load_credentials_from_file(
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


def get_or_create_subfolder(
    service: Any,
    *,
    folder_name: str,
    parent_folder_id: str,
    shared_drive_id: str | None = None,
) -> str:
    """Find existing subfolder by name under parent or create it. Returns the folder ID."""

    if not folder_name.strip():
        raise ValueError("folder_name is required")
    if not parent_folder_id.strip():
        raise ValueError("parent_folder_id is required")

    escaped_name = _escape_query_literal(folder_name)
    escaped_parent = _escape_query_literal(parent_folder_id)
    list_arguments: dict[str, Any] = {
        "q": (
            f"name = '{escaped_name}' and "
            f"mimeType = '{FOLDER_MIME_TYPE}' and "
            f"'{escaped_parent}' in parents and trashed = false"
        ),
        "spaces": "drive",
        "pageSize": 1,
        "fields": "files(id,name)",
        "includeItemsFromAllDrives": True,
        "supportsAllDrives": True,
    }
    if shared_drive_id:
        list_arguments.update(corpora="drive", driveId=shared_drive_id)

    existing_folders = (
        service.files().list(**list_arguments).execute().get("files", [])
    )
    if existing_folders:
        return existing_folders[0]["id"]

    response = (
        service.files()
        .create(
            body={
                "name": folder_name,
                "mimeType": FOLDER_MIME_TYPE,
                "parents": [parent_folder_id],
            },
            fields="id,name",
            supportsAllDrives=True,
        )
        .execute()
    )
    return response["id"]


def upsert_file(
    service: Any,
    *,
    local_path: Path,
    folder_id: str,
    drive_file_name: str | None = None,
    mime_type: str = "application/octet-stream",
    shared_drive_id: str | None = None,
) -> DriveUploadResult:
    """Create or update a file in a Drive folder without duplication."""

    if not local_path.is_file():
        raise FileNotFoundError(local_path)
    if not folder_id.strip():
        raise ValueError("folder_id is required")

    target_file_name = drive_file_name or local_path.name
    if not target_file_name.strip():
        raise ValueError("drive_file_name is required")

    escaped_name = _escape_query_literal(target_file_name)
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
        "supportsAllDrives": True,
    }
    if shared_drive_id:
        list_arguments.update(corpora="drive", driveId=shared_drive_id)

    existing_files = service.files().list(**list_arguments).execute().get("files", [])
    media = MediaFileUpload(
        str(local_path), mimetype=mime_type, resumable=True
    )
    fields = "id,name,webViewLink"

    if existing_files:
        response = (
            service.files()
            .update(
                fileId=existing_files[0]["id"],
                body={"name": target_file_name},
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
                body={"name": target_file_name, "parents": [folder_id]},
                media_body=media,
                fields=fields,
                supportsAllDrives=True,
            )
            .execute()
        )
        operation = "created"

    return DriveUploadResult(
        file_id=response["id"],
        name=response.get("name", target_file_name),
        web_view_link=response.get("webViewLink"),
        operation=operation,
    )


def upsert_json_file(
    service: Any,
    *,
    local_path: Path,
    folder_id: str,
    drive_file_name: str = "metadata.json",
    shared_drive_id: str | None = None,
) -> DriveUploadResult:
    """Create or update one JSON file in a Drive folder without duplication."""
    return upsert_file(
        service,
        local_path=local_path,
        folder_id=folder_id,
        drive_file_name=drive_file_name,
        mime_type=JSON_MIME_TYPE,
        shared_drive_id=shared_drive_id,
    )
