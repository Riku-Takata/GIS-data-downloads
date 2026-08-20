from unittest.mock import MagicMock

from app.services.drive_service import upsert_json_file


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
