#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import date, datetime

from chip_analyzer import add_continuity_flags, merge_chip_data
from data_fetcher import DataFetcher
from indicators import add_indicators
from report_generator import ReportGenerator
from scoring import score_stocks
from sector_analyzer import apply_sector_strength, attach_sector, rank_sectors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="台股盤後主力大戶籌碼分析 AI 系統")
    parser.add_argument("--date", help="分析日期 YYYY-MM-DD，預設今天並自動往前找可用交易日")
    parser.add_argument("--lookback-days", type=int, default=45, help="價量歷史回看天數")
    parser.add_argument("--retry-days", type=int, default=10, help="找不到資料時往前尋找幾天")
    parser.add_argument("--output-dir", default="reports", help="報告輸出資料夾")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()

    fetcher = DataFetcher()
    market = fetcher.fetch_recent_available(target, lookback_days=args.lookback_days, retry_days=args.retry_days)
    if market.prices.empty:
        raise SystemExit("沒有取得上市櫃收盤價資料，無法產生評分報告。")

    ordinary_stock = r"[1-9]\d{3}"
    prices = market.prices[market.prices["code"].astype(str).str.fullmatch(ordinary_stock)].copy()
    history = market.history[market.history["code"].astype(str).str.fullmatch(ordinary_stock)].copy() if not market.history.empty else market.history
    if prices.empty:
        raise SystemExit("沒有取得普通股收盤價資料，無法產生股票評分報告。")

    stocks = add_indicators(prices, history)
    stocks = merge_chip_data(stocks, market.institutional, market.margin, market.borrow)
    stocks = add_continuity_flags(stocks)
    stocks = attach_sector(stocks)
    first_pass = score_stocks(stocks)
    sectors = rank_sectors(first_pass)
    stocks = apply_sector_strength(stocks, sectors)
    stocks = score_stocks(stocks)
    sectors = rank_sectors(stocks)

    paths = ReportGenerator(args.output_dir).generate(
        market.trade_date,
        stocks,
        sectors,
        market.futures,
        market.options,
        market.errors,
    )
    print(f"Markdown: {paths.markdown}")
    print(f"CSV: {paths.csv}")
    print(f"HTML: {paths.html}")


if __name__ == "__main__":
    main()
