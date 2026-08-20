#!/usr/bin/env python3
"""CLI utility to test Gemini-powered search and natural language intent extraction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.schemas import SearchResponse  # noqa: E402
from app.services.gemini_service import interpret_user_query  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="自然言語クエリから国土数値情報のデータ種別・都道府県・年度等を解析・提案します。"
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="検索クエリ（例: 「富山県の土砂災害警戒区域データ」「全国の行政区域 GML」）",
    )
    parser.add_argument("--query", dest="query_opt", help="検索クエリ（オプション指定）")
    parser.add_argument("--api-key", help="Gemini APIキー（省略時は環境変数から取得）")
    parser.add_argument("--model", help="Gemini モデル名（デフォルト: gemini-2.5-flash）")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    search_query = args.query or args.query_opt
    if not search_query:
        parser.error("検索クエリを指定してください（例: python search_data.py '富山県の土砂災害データ'）")

    proposal = interpret_user_query(
        search_query,
        api_key=args.api_key,
        model=args.model,
    )

    response = SearchResponse(status="success", proposal=proposal)
    print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
