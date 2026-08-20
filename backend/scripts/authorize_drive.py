#!/usr/bin/env python3
"""Create user OAuth credentials for writing metadata to My Drive."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.drive_service import DRIVE_SCOPES  # noqa: E402
from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Google Drive用のユーザーOAuth認証JSONを作成します。"
    )
    parser.add_argument(
        "--client-secrets",
        type=Path,
        required=True,
        help="Google Cloudで作成したデスクトップアプリのOAuthクライアントJSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("credentials/authorized-user.json"),
        help="認証結果の保存先",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.client_secrets.is_file():
        raise FileNotFoundError(args.client_secrets)

    flow = InstalledAppFlow.from_client_secrets_file(
        str(args.client_secrets), scopes=DRIVE_SCOPES
    )
    credentials = flow.run_local_server(port=0, open_browser=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    credential_data = json.loads(credentials.to_json())
    credential_data["type"] = "authorized_user"
    args.output.write_text(
        json.dumps(credential_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.output.chmod(0o600)
    print(f"Credentials saved to: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
