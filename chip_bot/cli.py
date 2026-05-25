from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path

from .fetch import fetch_all_markets
from .report import build_report, write_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="產生台股盤後籌碼分析報告")
    parser.add_argument("--date", help="查詢日期，格式 YYYY-MM-DD；預設為今天並自動往前找可用交易日")
    parser.add_argument("--top", type=int, default=15, help="每個排行榜顯示幾檔股票")
    parser.add_argument("--lookback-days", type=int, default=10, help="最多往前尋找幾天可用資料")
    parser.add_argument("--output-dir", default="reports", help="報告輸出資料夾")
    return parser.parse_args()


def date_candidates(target: date, lookback_days: int) -> list[date]:
    return [target - timedelta(days=i) for i in range(lookback_days + 1)]


def main() -> None:
    args = parse_args()
    target = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()

    last_error: Exception | None = None
    for candidate in date_candidates(target, args.lookback_days):
        try:
            dataset = fetch_all_markets(candidate)
            if dataset.rows:
                report = build_report(dataset, top_n=args.top)
                output = write_report(report, Path(args.output_dir), dataset.trade_date)
                print(f"完成：{output}")
                return
        except Exception as exc:
            last_error = exc

    if last_error:
        raise SystemExit(f"找不到可用盤後資料，最後錯誤：{last_error}") from last_error
    raise SystemExit("找不到可用盤後資料。")
