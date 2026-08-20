#!/usr/bin/env python3
"""Generate the Japan prefecture master catalog and optionally upload it to Google Drive."""

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
from app.services.prefecture_service import (  # noqa: E402
    build_prefecture_document,
    get_prefectures,
    write_prefecture_document,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="都道府県マスターデータを生成し、必要に応じてGoogle Driveへ保存します。"
    )
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
        help="サービスアカウントまたはユーザーOAuth JSON。省略時はADCを使用する",
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

    output_path = args.output or settings.pref_master_output_path
    folder_id = args.drive_folder_id or settings.google_drive_folder_id

    if args.upload_drive and folder_id is None:
        parser.error(
            "--upload-drive requires --drive-folder-id or GOOGLE_DRIVE_FOLDER_ID"
        )

    prefectures = get_prefectures()
    document = build_prefecture_document(prefectures)
    write_prefecture_document(document, output_path)

    result: dict[str, object] = {
        "status": "completed",
        "prefecture_count": len(prefectures),
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
                args.drive_file_name or settings.google_drive_pref_master_filename
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
