from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import sync_symbol


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="session-ai",
        description="Session AI Forecaster data foundation",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync = subparsers.add_parser("sync", help="Download/merge 1m candles and rebuild session summaries")
    sync.add_argument("symbol", help="KuCoin spot USDT symbol, e.g. TUT-USDT")
    sync.add_argument("--days", type=int, default=30, help="Initial lookback in days (default: 30)")
    sync.add_argument("--data-dir", type=Path, default=Path("data"), help="Root data directory")
    sync.add_argument(
        "--storage-format",
        choices=("auto", "parquet", "csv"),
        default="auto",
        help="Storage backend; auto prefers Parquet when available",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "sync":
        if args.days < 1:
            parser.error("--days must be at least 1")
        try:
            result = sync_symbol(
                args.symbol,
                args.data_dir,
                days=args.days,
                storage_format=args.storage_format,
            )
        except Exception as exc:
            print(f"sync failed: {exc}", file=sys.stderr)
            return 1

        print(f"symbol: {result.symbol}")
        print(f"candles: {result.candle_count}")
        print(f"sessions: {result.session_count}")
        print(f"candles_file: {result.candles_path}")
        print(f"sessions_file: {result.sessions_path}")
        print(f"state_file: {result.state_path}")
        return 0

    return 2
