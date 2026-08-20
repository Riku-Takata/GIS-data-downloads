#!/usr/bin/env python3
"""Generate the MLIT metadata catalog and optionally upload it to Google Drive."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings  # noqa: E402
from app.services.drive_service import (  # noqa: E402
    build_drive_service,
    upsert_json_file,
)
from app.services.metadata_service import (  # noqa: E402
    build_metadata_document,
    fetch_catalog_html,
    parse_catalog_html,
    write_metadata_document,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "国土数値情報のメタデータを生成し、必要に応じてGoogle Driveへ保存します。"
        )
    )
    parser.add_argument("--source-url", help="国土数値情報一覧ページのURL")
    parser.add_argument("--detail-base-url", help="詳細ページのベースURL")
    parser.add_argument("--output", type=Path, help="ローカルJSONの出力先")
    parser.add_argument(
        "--upload-drive",
        action="store_true",
        help="生成したJSONをGoogle Driveへ作成または更新する",
    )
    parser.add_argument("--drive-folder-id", help="保存先のGoogle DriveフォルダID")
    parser.add_argument("--shared-drive-id", help="保存先の共有ドライブID")
    parser.add_argument("--drive-file-name", help="Drive上のファイル名")
    parser.add_argument(
        "--credentials",
        type=Path,
        help="サービスアカウントJSONのパス。省略時はADCを使用する",
    )
    parser.add_argument(
        "--impersonate-user",
        help="ドメイン全体の委任で代理するGoogle Workspaceユーザー",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = Settings.from_env()

    source_url = args.source_url or settings.metadata_source_url
    detail_base_url = args.detail_base_url or settings.detail_base_url
    output_path = args.output or settings.metadata_output_path
    folder_id = args.drive_folder_id or settings.google_drive_folder_id

    if args.upload_drive and folder_id is None:
        parser.error(
            "--upload-drive requires --drive-folder-id or GOOGLE_DRIVE_FOLDER_ID"
        )

    html = fetch_catalog_html(
        source_url, timeout_seconds=settings.http_timeout_seconds
    )
    datasets = parse_catalog_html(
        html,
        source_url=source_url,
        detail_base_url=detail_base_url,
    )
    if not datasets:
        raise RuntimeError("No datasets were found in the MLIT catalog")

    document = build_metadata_document(datasets, source_url=source_url)
    write_metadata_document(document, output_path)

    result: dict[str, object] = {
        "status": "completed",
        "dataset_count": len(datasets),
        "local_path": str(output_path.resolve()),
    }

    if args.upload_drive:
        service = build_drive_service(
            credentials_path=(
                args.credentials or settings.google_application_credentials
            ),
            impersonate_user=(
                args.impersonate_user or settings.google_drive_impersonate_user
            ),
        )
        upload_result = upsert_json_file(
            service,
            local_path=output_path,
            folder_id=folder_id,
            drive_file_name=(
                args.drive_file_name or settings.google_drive_metadata_filename
            ),
            shared_drive_id=(
                args.shared_drive_id or settings.google_drive_shared_drive_id
            ),
        )
        result["google_drive"] = asdict(upload_result)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
