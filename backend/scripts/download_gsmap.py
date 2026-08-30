#!/usr/bin/env python3
"""Download a date range of hourly JAXA GSMaP files over read-only FTP."""

from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import date, datetime, timezone
import getpass
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.gsmap_japan_csv_service import (  # noqa: E402
    GsmapCsvResult,
    append_csv_manifest,
    build_daily_csv_path,
    convert_gsmap_day_to_csv,
    load_or_build_japan_grid_mask,
)
from app.services.gsmap_ftp_retry_service import (  # noqa: E402
    close_ftp_quietly,
    run_ftp_operation_with_retry,
)
from app.services.gsmap_ftp_service import (  # noqa: E402
    DATASET_SPECS,
    GsmapFtpConfig,
    append_manifest,
    build_local_path,
    download_remote_file,
    iter_dates,
    list_remote_files,
    normalize_product_path,
    open_ftp,
    parse_date_argument,
)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _default_output_dir() -> Path:
    configured = os.getenv("GSMAP_OUTPUT_DIR", "").strip()
    if not configured:
        return PROJECT_ROOT / "downloads" / "gsmap"
    path = Path(configured).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def _default_csv_output_dir() -> Path:
    configured = os.getenv("GSMAP_JAPAN_CSV_DIR", "").strip()
    if not configured:
        return PROJECT_ROOT / "downloads" / "gsmap-japan-csv"
    path = Path(configured).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def _default_boundary_archive() -> Path:
    configured = os.getenv("GSMAP_JAPAN_BOUNDARY", "").strip()
    if configured:
        path = Path(configured).expanduser()
        return path if path.is_absolute() else PROJECT_ROOT / path
    candidates = sorted((PROJECT_ROOT / "downloads" / "n03-source").glob("N03-*_GML.zip"))
    if candidates:
        return candidates[-1]
    return PROJECT_ROOT / "downloads" / "n03-source" / "N03-20260101_GML.zip"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "JAXA GSMaPの時間雨量データを、指定期間についてFTPから読み取り専用で取得します。"
        )
    )
    parser.add_argument(
        "product",
        help="製品パス（例: standard/v8）",
    )
    parser.add_argument(
        "--start",
        required=True,
        help="開始日（YYYY-MM-DD）",
    )
    parser.add_argument(
        "--end",
        default="today",
        help="終了日（YYYY-MM-DD または today。デフォルト: today、UTC）",
    )
    parser.add_argument(
        "--dataset",
        choices=sorted(DATASET_SPECS),
        default="hourly",
        help="hourly: GSMaP_MVK、hourly-gauge: 雨量計補正済みGSMaP_Gauge",
    )
    parser.add_argument("--host", help="FTPホスト。省略時はGSMAP_FTP_HOST")
    parser.add_argument(
        "--port",
        type=int,
        help="FTPポート。省略時はGSMAP_FTP_PORT（デフォルト21）",
    )
    parser.add_argument("--user", help="FTPユーザー。省略時はGSMAP_FTP_USER")
    parser.add_argument(
        "--tls",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="明示的FTPSを使用する。省略時はGSMAP_FTP_TLS",
    )
    parser.add_argument(
        "--active",
        action="store_true",
        help="アクティブモードを使用する（デフォルトはパッシブ）",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="接続・転送タイムアウト秒。省略時はGSMAP_FTP_TIMEOUT（デフォルト60）",
    )
    parser.add_argument(
        "--ftp-retries",
        type=int,
        default=None,
        help="一時的なFTP障害時の再試行回数。省略時はGSMAP_FTP_RETRIES（デフォルト8）",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=None,
        help="FTP再試行の初期待機秒。省略時はGSMAP_FTP_RETRY_DELAY（デフォルト5）",
    )
    parser.add_argument(
        "--retry-max-delay",
        type=float,
        default=None,
        help="FTP再試行の最大待機秒。省略時はGSMAP_FTP_RETRY_MAX_DELAY（デフォルト120）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="保存先ルート。省略時はGSMAP_OUTPUT_DIRまたはdownloads/gsmap",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="取得記録JSONL。省略時は保存先のmanifest.jsonl",
    )
    parser.add_argument(
        "--japan-csv",
        action="store_true",
        help="取得と並行して、日本国土に重なる元格子を日別CSVへ変換する",
    )
    parser.add_argument(
        "--japan-boundary",
        type=Path,
        default=None,
        help="全国N03 ZIP。省略時はGSMAP_JAPAN_BOUNDARYまたは取得済み最新版を使用",
    )
    parser.add_argument(
        "--japan-csv-dir",
        type=Path,
        default=None,
        help="日本国土CSV保存先。省略時はGSMAP_JAPAN_CSV_DIRまたはdownloads/gsmap-japan-csv",
    )
    parser.add_argument(
        "--csv-compression",
        choices=["gzip", "none"],
        default="gzip",
        help="CSV圧縮。大規模期間向けのgzipがデフォルト",
    )
    parser.add_argument(
        "--csv-workers",
        type=int,
        default=None,
        help="並行CSV変換数。省略時はGSMAP_CSV_WORKERSまたは2",
    )
    parser.add_argument(
        "--rebuild-japan-mask",
        action="store_true",
        help="N03と0.1度格子の交差マスクを再構築する",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="FTP一覧と合計サイズだけ確認し、ダウンロードしない",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="31日を超える大量取得を確認なしで許可する",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="対象ファイル数の上限（接続確認や小規模試験用）",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="既存の.partファイルを再開に使用しない",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="パスワード入力を禁止し、環境変数未設定ならエラーにする",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="進捗表示を抑制する（最終JSONは出力）",
    )
    return parser


def _resolve_path(path: Path) -> Path:
    expanded = path.expanduser()
    return expanded if expanded.is_absolute() else PROJECT_ROOT / expanded


def _print_progress(message: str, *, quiet: bool) -> None:
    if not quiet:
        print(message, file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        product = normalize_product_path(args.product)
        start_date = parse_date_argument(args.start)
        end_date = parse_date_argument(args.end)
        date_count = len(list(iter_dates(start_date, end_date)))
    except ValueError as exc:
        parser.error(str(exc))

    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be greater than zero")
    if args.japan_csv:
        try:
            csv_workers = args.csv_workers or int(os.getenv("GSMAP_CSV_WORKERS", "2"))
        except ValueError:
            parser.error("GSMAP_CSV_WORKERS must be an integer")
        if csv_workers <= 0:
            parser.error("--csv-workers must be greater than zero")
    else:
        csv_workers = 0
    if not args.dry_run and date_count > 31 and not args.yes:
        parser.error(
            f"The requested range covers {date_count} days (up to {date_count * 24:,} files). "
            "Run once with --dry-run, then add --yes to execute the large download."
        )

    host = args.host or os.getenv("GSMAP_FTP_HOST", "").strip()
    username = args.user or os.getenv("GSMAP_FTP_USER", "").strip()
    if not host:
        parser.error("--host or GSMAP_FTP_HOST is required")
    if not username:
        parser.error("--user or GSMAP_FTP_USER is required")

    password = os.getenv("GSMAP_FTP_PASSWORD", "")
    if not password:
        if args.non_interactive or not sys.stdin.isatty():
            parser.error("GSMAP_FTP_PASSWORD is required in non-interactive mode")
        password = getpass.getpass("GSMaP FTP password: ")

    port = args.port or int(os.getenv("GSMAP_FTP_PORT", "21"))
    timeout = args.timeout or float(os.getenv("GSMAP_FTP_TIMEOUT", "60"))
    try:
        ftp_retries = (
            args.ftp_retries
            if args.ftp_retries is not None
            else int(os.getenv("GSMAP_FTP_RETRIES", "8"))
        )
        retry_delay = (
            args.retry_delay
            if args.retry_delay is not None
            else float(os.getenv("GSMAP_FTP_RETRY_DELAY", "5"))
        )
        retry_max_delay = (
            args.retry_max_delay
            if args.retry_max_delay is not None
            else float(os.getenv("GSMAP_FTP_RETRY_MAX_DELAY", "120"))
        )
    except ValueError:
        parser.error("FTP retry environment values must be numeric")
    if ftp_retries < 0:
        parser.error("--ftp-retries must be zero or greater")
    if retry_delay < 0 or retry_max_delay < 0:
        parser.error("retry delays must be zero or greater")
    use_tls = _env_bool("GSMAP_FTP_TLS") if args.tls is None else args.tls
    output_root = _resolve_path(args.output_dir or _default_output_dir())
    manifest_path = _resolve_path(args.manifest or output_root / "manifest.jsonl")
    csv_output_root = _resolve_path(args.japan_csv_dir or _default_csv_output_dir())
    boundary_path = _resolve_path(args.japan_boundary or _default_boundary_archive())
    mask_path = csv_output_root / "_mask" / "gsmap_japan_grid_mask.csv"
    csv_manifest_path = csv_output_root / "manifest.jsonl"
    japan_cells = []
    if args.japan_csv and not args.dry_run:
        _print_progress(
            f"Preparing Japan grid mask from {boundary_path}",
            quiet=args.quiet,
        )
        try:
            japan_cells = load_or_build_japan_grid_mask(
                boundary_path,
                mask_path,
                rebuild=args.rebuild_japan_mask,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        _print_progress(
            f"Japan grid mask ready: {len(japan_cells):,} cells",
            quiet=args.quiet,
        )

    config = GsmapFtpConfig(
        host=host,
        port=port,
        username=username,
        password=password,
        use_tls=use_tls,
        passive=not args.active,
        timeout_seconds=timeout,
    )

    theoretical_max = date_count * 24
    _print_progress(
        f"Connecting to {host}:{port}; product={product}; dataset={args.dataset}; "
        f"range={start_date}..{end_date}; theoretical_max={theoretical_max:,}",
        quiet=args.quiet,
    )

    found = 0
    downloaded = 0
    skipped = 0
    total_remote_bytes = 0
    missing_days = 0
    limited = False
    ftp_retry_count = 0
    csv_converted = 0
    csv_unchanged = 0
    csv_failed = 0
    csv_rows = 0
    pending_csv: dict[Future[GsmapCsvResult], Path] = {}
    csv_executor = (
        ThreadPoolExecutor(max_workers=csv_workers)
        if args.japan_csv and not args.dry_run
        else None
    )

    def _collect_csv_results(done: set[Future[GsmapCsvResult]]) -> None:
        nonlocal csv_converted, csv_unchanged, csv_failed, csv_rows
        for future in done:
            target = pending_csv.pop(future)
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 - record each failed day and continue
                csv_failed += 1
                csv_manifest_path.parent.mkdir(parents=True, exist_ok=True)
                with csv_manifest_path.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(
                        json.dumps(
                            {
                                "recorded_at": datetime.now(timezone.utc).isoformat(),
                                "status": "failed",
                                "output_path": str(target.resolve()),
                                "error": str(exc),
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                _print_progress(
                    f"[csv-failed] {target}: {exc}",
                    quiet=args.quiet,
                )
                continue
            append_csv_manifest(csv_manifest_path, result)
            if result.status == "converted":
                csv_converted += 1
            else:
                csv_unchanged += 1
            csv_rows += result.rows
            _print_progress(
                f"[csv-{result.status}] {result.output_path} ({result.rows:,} rows)",
                quiet=args.quiet,
            )

    def _retry_notice(operation: str):
        def callback(
            retry_number: int,
            total_retries: int,
            delay: float,
            exc: BaseException,
        ) -> None:
            nonlocal ftp_retry_count
            ftp_retry_count += 1
            _print_progress(
                f"[ftp-retry] {operation}; retry={retry_number}/{total_retries}; "
                f"wait={delay:g}s; {type(exc).__name__}: {exc}",
                quiet=args.quiet,
            )

        return callback

    ftp = None
    try:
        for target_date in iter_dates(start_date, end_date):
            day_files, ftp = run_ftp_operation_with_retry(
                ftp,
                config,
                lambda client: list_remote_files(
                    client,
                    product=product,
                    dataset=args.dataset,
                    target_date=target_date,
                ),
                retries=ftp_retries,
                base_delay_seconds=retry_delay,
                max_delay_seconds=retry_max_delay,
                on_retry=_retry_notice(f"list {target_date}"),
                connect=open_ftp,
            )
            if not day_files:
                missing_days += 1
                continue

            day_local_paths: list[Path] = []
            for remote_file in day_files:
                if args.limit is not None and found >= args.limit:
                    limited = True
                    break
                found += 1
                total_remote_bytes += remote_file.size or 0

                if args.dry_run:
                    continue

                destination = build_local_path(
                    output_root,
                    product,
                    args.dataset,
                    remote_file,
                )
                result, ftp = run_ftp_operation_with_retry(
                    ftp,
                    config,
                    lambda client: download_remote_file(
                        client,
                        remote_file=remote_file,
                        destination=destination,
                        resume=not args.no_resume,
                    ),
                    retries=ftp_retries,
                    base_delay_seconds=retry_delay,
                    max_delay_seconds=retry_max_delay,
                    on_retry=_retry_notice(f"download {remote_file.file_name}"),
                    connect=open_ftp,
                )
                append_manifest(manifest_path, result)
                if result.status == "downloaded":
                    downloaded += 1
                else:
                    skipped += 1
                day_local_paths.append(destination)
                _print_progress(
                    f"[{result.status}] {remote_file.remote_path} -> {destination}",
                    quiet=args.quiet,
                )
            if csv_executor is not None and day_local_paths:
                csv_target = build_daily_csv_path(
                    csv_output_root,
                    product,
                    args.dataset,
                    target_date,
                    compression=args.csv_compression,
                )
                future = csv_executor.submit(
                    convert_gsmap_day_to_csv,
                    day_local_paths,
                    csv_target,
                    japan_cells,
                    compression=args.csv_compression,
                    mask_path=mask_path,
                )
                pending_csv[future] = csv_target
                _print_progress(f"[csv-queued] {csv_target}", quiet=args.quiet)
                if len(pending_csv) >= csv_workers * 2:
                    done, _ = wait(set(pending_csv), return_when=FIRST_COMPLETED)
                    _collect_csv_results(set(done))
            if limited:
                break
    finally:
        close_ftp_quietly(ftp)
        if csv_executor is not None:
            csv_executor.shutdown(wait=True)
            _collect_csv_results(set(pending_csv))

    summary = {
        "status": (
            "dry-run"
            if args.dry_run
            else "completed-with-csv-errors" if csv_failed else "completed"
        ),
        "product": product,
        "dataset": args.dataset,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "days": date_count,
        "missing_days": missing_days,
        "ftp_retries": ftp_retry_count,
        "files_found": found,
        "remote_bytes_known": total_remote_bytes,
        "remote_gib_known": round(total_remote_bytes / (1024**3), 3),
        "downloaded": downloaded,
        "skipped": skipped,
        "limited": limited,
        "output_dir": str(output_root.resolve()),
        "manifest": None if args.dry_run else str(manifest_path.resolve()),
        "japan_csv": {
            "enabled": args.japan_csv,
            "compression": args.csv_compression if args.japan_csv else None,
            "workers": csv_workers if args.japan_csv else 0,
            "grid_cells": len(japan_cells) if japan_cells else None,
            "days_converted": csv_converted,
            "days_unchanged": csv_unchanged,
            "days_failed": csv_failed,
            "rows": csv_rows,
            "output_dir": str(csv_output_root.resolve()) if args.japan_csv else None,
            "manifest": (
                str(csv_manifest_path.resolve())
                if args.japan_csv and not args.dry_run
                else None
            ),
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if csv_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
