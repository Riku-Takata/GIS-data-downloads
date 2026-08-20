from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.drive_service import (
    DRIVE_SCOPES,
    FOLDER_MIME_TYPE,
    build_drive_service,
    get_or_create_subfolder,
    upsert_file,
    upsert_json_file,
)


@patch("app.services.drive_service.build")
@patch("app.services.drive_service.load_credentials_from_file")
def test_build_drive_service_loads_user_or_service_account_json(
    load_credentials, build
):
    credentials = MagicMock()
    load_credentials.return_value = (credentials, "project-id")
    expected_service = object()
    build.return_value = expected_service

    service = build_drive_service(credentials_path=Path("credentials.json"))

    assert service is expected_service
    load_credentials.assert_called_once_with(
        "credentials.json", scopes=DRIVE_SCOPES
    )
    build.assert_called_once_with(
        "drive", "v3", credentials=credentials, cache_discovery=False
    )


def test_get_or_create_subfolder_returns_existing(tmp_path):
    service = MagicMock()
    files = service.files.return_value
    files.list.return_value.execute.return_value = {
        "files": [{"id": "existing-folder-id", "name": "2026-08-20"}]
    }

    folder_id = get_or_create_subfolder(
        service,
        folder_name="2026-08-20",
        parent_folder_id="parent-folder-id",
        shared_drive_id="shared-drive-id",
    )

    assert folder_id == "existing-folder-id"
    list_kwargs = files.list.call_args.kwargs
    assert list_kwargs["driveId"] == "shared-drive-id"
    assert "name = '2026-08-20'" in list_kwargs["q"]
    assert f"mimeType = '{FOLDER_MIME_TYPE}'" in list_kwargs["q"]
    assert "'parent-folder-id' in parents" in list_kwargs["q"]
    files.create.assert_not_called()


def test_get_or_create_subfolder_creates_when_not_found(tmp_path):
    service = MagicMock()
    files = service.files.return_value
    files.list.return_value.execute.return_value = {"files": []}
    files.create.return_value.execute.return_value = {
        "id": "new-folder-id",
        "name": "2026-08-20",
    }

    folder_id = get_or_create_subfolder(
        service,
        folder_name="2026-08-20",
        parent_folder_id="parent-folder-id",
    )

    assert folder_id == "new-folder-id"
    create_kwargs = files.create.call_args.kwargs
    assert create_kwargs["body"] == {
        "name": "2026-08-20",
        "mimeType": FOLDER_MIME_TYPE,
        "parents": ["parent-folder-id"],
    }


def test_upsert_json_file_creates_when_file_does_not_exist(tmp_path):
    local_path = tmp_path / "metadata.json"
    local_path.write_text('{"dataset_count": 1}\n', encoding="utf-8")
    service = MagicMock()
    files = service.files.return_value
    files.list.return_value.execute.return_value = {"files": []}
    files.create.return_value.execute.return_value = {
        "id": "new-file-id",
        "name": "metadata.json",
        "webViewLink": "https://drive.google.com/file/d/new-file-id/view",
    }

    result = upsert_json_file(
        service,
        local_path=local_path,
        folder_id="folder-id",
        shared_drive_id="shared-drive-id",
    )

    assert result.file_id == "new-file-id"
    assert result.operation == "created"
    list_kwargs = files.list.call_args.kwargs
    assert list_kwargs["driveId"] == "shared-drive-id"
    assert list_kwargs["supportsAllDrives"] is True
    assert "'folder-id' in parents" in list_kwargs["q"]
    create_kwargs = files.create.call_args.kwargs
    assert create_kwargs["body"] == {
        "name": "metadata.json",
        "parents": ["folder-id"],
    }
    assert create_kwargs["supportsAllDrives"] is True
    files.update.assert_not_called()


def test_upsert_json_file_updates_latest_existing_file(tmp_path):
    local_path = tmp_path / "metadata.json"
    local_path.write_text('{"dataset_count": 2}\n', encoding="utf-8")
    service = MagicMock()
    files = service.files.return_value
    files.list.return_value.execute.return_value = {
        "files": [{"id": "existing-file-id", "name": "metadata.json"}]
    }
    files.update.return_value.execute.return_value = {
        "id": "existing-file-id",
        "name": "metadata.json",
        "webViewLink": "https://drive.google.com/file/d/existing-file-id/view",
    }

    result = upsert_json_file(
        service,
        local_path=local_path,
        folder_id="folder-id",
    )

    assert result.file_id == "existing-file-id"
    assert result.operation == "updated"
    update_kwargs = files.update.call_args.kwargs
    assert update_kwargs["fileId"] == "existing-file-id"
    assert update_kwargs["supportsAllDrives"] is True
    files.create.assert_not_called()
