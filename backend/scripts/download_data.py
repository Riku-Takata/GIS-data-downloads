#!/usr/bin/env python3
"""Download MLIT National Land Numerical Information datasets and optionally upload to Google Drive."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings  # noqa: E402
from app.services.drive_service import (  # noqa: E402
    ZIP_MIME_TYPE,
    build_drive_service,
    get_or_create_subfolder,
    upsert_file,
)
from app.providers.router import download_dataset_across_providers  # noqa: E402
from app.services.scraper_service import (  # noqa: E402
    download_file,
    extract_download_candidates,
    fetch_detail_page_html,
    resolve_detail_url,
    select_best_candidate,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="国土数値情報データをスクレイピングしてダウンロードし、日付別フォルダおよびGoogle Driveへ保存します。"
    )
    parser.add_argument(
        "--data-code",
        required=True,
        help="対象の国土数値情報データコード（例: A33, N03, L01）",
    )
    parser.add_argument(
        "--pref-code",
        default="00",
        help="対象の都道府県コード（例: 16 (富山県), 00 (全国)）",
    )
    parser.add_argument(
        "--year",
        default="latest",
        help="対象年度（例: latest, 2025, 2024）",
    )
    parser.add_argument(
        "--format",
        default=None,
        help="希望フォーマット（例: GeoJSON, Shapefile, GML。省略時はGeoJSON優先）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=BACKEND_ROOT / "downloads",
        help="ローカル保存先ベースディレクトリ",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="日付フォルダ名（デフォルト: 今日の日付 YYYY-MM-DD）",
    )
    parser.add_argument(
        "--no-date-folder",
        action="store_true",
        help="日付別サブフォルダを作成せず直接出力先へ保存する",
    )
    parser.add_argument(
        "--upload-drive",
        action="store_true",
        help="ダウンロードしたZIPファイルをGoogle Driveの日付フォルダへ保存する",
    )
    parser.add_argument("--drive-folder-id", help="保存先のGoogle Drive親フォルダID")
    parser.add_argument("--shared-drive-id", help="保存先の共有ドライブID")
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

    parent_folder_id = args.drive_folder_id or settings.google_drive_folder_id
    if args.upload_drive and parent_folder_id is None:
        parser.error(
            "--upload-drive requires --drive-folder-id or GOOGLE_DRIVE_FOLDER_ID"
        )

    date_folder_name = args.date or datetime.now().strftime("%Y-%m-%d")

    target_local_dir = (
        args.output_dir if args.no_date_folder else args.output_dir / date_folder_name
    )

    download_res = download_dataset_across_providers(
        data_code=args.data_code,
        pref_code=args.pref_code,
        year=args.year,
        format_preference=args.format,
        output_dir=target_local_dir,
    )

    downloaded_path = download_res.local_path
    if not downloaded_path or not downloaded_path.is_file():
        raise RuntimeError(f"Download failed for data_code={args.data_code}, pref_code={args.pref_code}")

    result: dict[str, Any] = {
        "status": "completed",
        "provider_id": download_res.provider_id,
        "provider_name": download_res.provider_name,
        "data_code": download_res.data_code,
        "pref_code": download_res.pref_code,
        "region_name": download_res.region_name,
        "year": download_res.year,
        "format": download_res.format,
        "file_name": download_res.file_name,
        "file_size_mb": download_res.file_size_mb,
        "local_path": str(downloaded_path.resolve()),
        "direct_download_url": download_res.direct_download_url,
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

        target_drive_folder_id = parent_folder_id
        if not args.no_date_folder and parent_folder_id:
            target_drive_folder_id = get_or_create_subfolder(
                service,
                folder_name=date_folder_name,
                parent_folder_id=parent_folder_id,
                shared_drive_id=(
                    args.shared_drive_id or settings.google_drive_shared_drive_id
                ),
            )

        upload_result = upsert_file(
            service,
            local_path=downloaded_path,
            folder_id=target_drive_folder_id,
            mime_type=ZIP_MIME_TYPE,
            shared_drive_id=(
                args.shared_drive_id or settings.google_drive_shared_drive_id
            ),
        )
        drive_data = asdict(upload_result)
        drive_data["folder_id"] = target_drive_folder_id
        if not args.no_date_folder:
            drive_data["date_folder"] = date_folder_name
        result["google_drive"] = drive_data

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
