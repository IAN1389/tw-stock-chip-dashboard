from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from chip_bot.fetch import fetch_all_markets


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"


@dataclass
class MarketData:
    trade_date: date
    prices: pd.DataFrame = field(default_factory=pd.DataFrame)
    history: pd.DataFrame = field(default_factory=pd.DataFrame)
    institutional: pd.DataFrame = field(default_factory=pd.DataFrame)
    margin: pd.DataFrame = field(default_factory=pd.DataFrame)
    borrow: pd.DataFrame = field(default_factory=pd.DataFrame)
    futures: pd.DataFrame = field(default_factory=pd.DataFrame)
    options: pd.DataFrame = field(default_factory=pd.DataFrame)
    errors: list[str] = field(default_factory=list)


class DataFetcher:
    def __init__(self, timeout: int = 25) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 slking-chip-ai/0.1",
                "Accept": "application/json,text/plain,*/*",
            }
        )

    def fetch(self, target: date, lookback_days: int = 45) -> MarketData:
        data = MarketData(trade_date=target)
        data.prices = self._safe_frame(data.errors, "上市櫃收盤價", self.fetch_prices, target)
        data.institutional = self._safe_frame(data.errors, "三大法人", self.fetch_institutional, target)
        data.margin = self._safe_frame(data.errors, "融資融券", self.fetch_margin, target)
        data.borrow = self._safe_frame(data.errors, "借券賣出", self.fetch_borrow, target)
        data.futures = self._safe_frame(data.errors, "期貨未平倉", self.fetch_futures, target)
        data.options = self._safe_frame(data.errors, "選擇權 Put/Call Ratio", self.fetch_options, target)
        data.history = self.fetch_price_history(target, lookback_days, data.errors)
        return data

    def fetch_recent_available(self, target: date, lookback_days: int = 45, retry_days: int = 10) -> MarketData:
        last: MarketData | None = None
        for offset in range(retry_days + 1):
            candidate = target - timedelta(days=offset)
            bundle = self.fetch(candidate, lookback_days)
            if not bundle.prices.empty or not bundle.institutional.empty:
                return bundle
            last = bundle
        return last or MarketData(trade_date=target, errors=["找不到可用交易日資料"])

    def fetch_prices(self, target: date) -> pd.DataFrame:
        frames = [self.fetch_twse_prices(target), self.fetch_tpex_prices(target)]
        df = pd.concat([x for x in frames if not x.empty], ignore_index=True)
        self._write_csv(df, target, "prices")
        return df

    def fetch_twse_prices(self, target: date) -> pd.DataFrame:
        ymd = target.strftime("%Y%m%d")
        urls = [
            f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={ymd}&type=ALLBUT0999&response=json",
            f"https://www.twse.com.tw/exchangeReport/MI_INDEX?date={ymd}&type=ALLBUT0999&response=json",
        ]
        payload = self._first_json(urls)
        self._write_raw(payload, target, "twse_prices")
        fields, rows = self._extract_table(payload, required=("證券代號", "收盤價"))
        records = []
        for row in rows:
            item = self._rowdict(fields, row)
            code = clean_text(item.get("證券代號"))
            if not is_stock_like(code):
                continue
            sign = -1 if "-" in clean_text(item.get("漲跌(+/-)")) else 1
            change = parse_float(item.get("漲跌價差")) * sign
            close = parse_float(item.get("收盤價"))
            prev_close = close - change if close and change else 0.0
            records.append(
                {
                    "market": "上市",
                    "code": code,
                    "name": clean_text(item.get("證券名稱")),
                    "close": close,
                    "open": parse_float(item.get("開盤價")),
                    "high": parse_float(item.get("最高價")),
                    "low": parse_float(item.get("最低價")),
                    "volume": parse_int(item.get("成交股數")) // 1000,
                    "change": change,
                    "pct_change": change / prev_close * 100 if prev_close else 0.0,
                    "has_warrant": False,
                    "has_futures": code in FUTURES_STOCKS,
                }
            )
        return pd.DataFrame(records)

    def fetch_tpex_prices(self, target: date) -> pd.DataFrame:
        ad_date = target.strftime("%Y/%m/%d")
        roc_date = f"{target.year - 1911}/{target:%m/%d}"
        urls = [
            "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc?"
            + requests.compat.urlencode({"date": ad_date, "type": "EW", "response": "json"}),
            "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc?"
            + requests.compat.urlencode({"date": roc_date, "type": "EW", "response": "json"}),
            "https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?"
            + requests.compat.urlencode({"d": roc_date, "s": "0,asc,0", "l": "zh-tw", "o": "json"}),
        ]
        payload = self._first_json(urls)
        self._write_raw(payload, target, "tpex_prices")
        fields, rows = self._extract_table(payload, required=("代號", "收盤"))
        records = []
        for row in rows:
            item = self._rowdict(fields, row)
            code = clean_text(item.get("代號") or item.get("股票代號"))
            if not is_stock_like(code):
                continue
            close = parse_float(first_value(item, ["收盤", "收盤價"]))
            change = parse_float(first_value(item, ["漲跌", "漲跌價差"]))
            prev_close = close - change if close and change else 0.0
            volume = parse_int(first_value(item, ["成交股數", "成交仟股", "成交張數"])) // 1000
            records.append(
                {
                    "market": "上櫃",
                    "code": code,
                    "name": clean_text(first_value(item, ["名稱", "股票名稱"])),
                    "close": close,
                    "open": parse_float(first_value(item, ["開盤", "開盤價"])),
                    "high": parse_float(first_value(item, ["最高", "最高價"])),
                    "low": parse_float(first_value(item, ["最低", "最低價"])),
                    "volume": volume,
                    "change": change,
                    "pct_change": change / prev_close * 100 if prev_close else 0.0,
                    "has_warrant": False,
                    "has_futures": code in FUTURES_STOCKS,
                }
            )
        return pd.DataFrame(records)

    def fetch_institutional(self, target: date) -> pd.DataFrame:
        dataset = fetch_all_markets(target)
        df = pd.DataFrame(dataset.rows)
        if not df.empty:
            df = df.rename(
                columns={
                    "foreign_lots": "foreign_buy_lots",
                    "trust_lots": "trust_buy_lots",
                    "dealer_lots": "dealer_buy_lots",
                    "total_lots": "inst_buy_lots",
                }
            )
        return df

    def fetch_margin(self, target: date) -> pd.DataFrame:
        ymd = target.strftime("%Y%m%d")
        urls = [
            f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={ymd}&selectType=ALL&response=json",
            f"https://www.twse.com.tw/exchangeReport/MI_MARGN?date={ymd}&selectType=ALL&response=json",
        ]
        rows = []
        try:
            payload = self._first_json(urls)
            self._write_raw(payload, target, "twse_margin")
            fields, data = self._extract_table(payload, required=("股票代號", "融資"))
            rows.extend(normalize_margin_rows("上市", fields, data))
        except Exception:
            pass
        df = pd.DataFrame(rows)
        self._write_csv(df, target, "margin")
        return df

    def fetch_borrow(self, target: date) -> pd.DataFrame:
        ymd = target.strftime("%Y%m%d")
        urls = [
            f"https://www.twse.com.tw/rwd/zh/SBL/TWT93U?date={ymd}&response=json",
            f"https://www.twse.com.tw/exchangeReport/TWT93U?date={ymd}&response=json",
        ]
        payload = self._first_json(urls)
        self._write_raw(payload, target, "twse_borrow")
        fields, data = self._extract_table(payload, required=("證券代號",))
        rows = []
        for row in data:
            item = self._rowdict(fields, row)
            code = clean_text(first_value(item, ["證券代號", "股票代號", "代號"]))
            if is_stock_like(code):
                rows.append(
                    {
                        "market": "上市",
                        "code": code,
                        "borrow_sell_lots": parse_int(first_value(item, ["借券賣出", "賣出"])) // 1000,
                    }
                )
        df = pd.DataFrame(rows)
        self._write_csv(df, target, "borrow")
        return df

    def fetch_futures(self, target: date) -> pd.DataFrame:
        # TAIFEX public endpoints change more often than TWSE/TPEx. Keep this as a stable
        # extension point; FinMind can backfill if FINMIND_TOKEN is configured.
        token = os.getenv("FINMIND_TOKEN")
        if not token:
            return pd.DataFrame(
                [{"symbol": "TX", "foreign_oi": 0, "net_position": 0, "source_note": "FINMIND_TOKEN 未設定，期貨籌碼暫不評分"}]
            )
        return self._fetch_finmind("TaiwanFuturesInstitutionalInvestors", target, token)

    def fetch_options(self, target: date) -> pd.DataFrame:
        token = os.getenv("FINMIND_TOKEN")
        if not token:
            return pd.DataFrame([{"symbol": "TXO", "put_call_ratio": 0.0, "source_note": "FINMIND_TOKEN 未設定，PCR 暫不評分"}])
        return self._fetch_finmind("TaiwanOptionPutCallRatio", target, token)

    def fetch_price_history(self, target: date, lookback_days: int, errors: list[str]) -> pd.DataFrame:
        frames = []
        for offset in range(lookback_days + 1):
            day = target - timedelta(days=offset)
            try:
                df = self.fetch_prices(day)
            except Exception:
                continue
            if not df.empty:
                df = df.copy()
                df["date"] = day.isoformat()
                frames.append(df)
        if not frames:
            errors.append("歷史價量不足，趨勢與型態分數會降權")
            return pd.DataFrame()
        history = pd.concat(frames, ignore_index=True)
        self._write_csv(history, target, "price_history")
        return history

    def _fetch_finmind(self, dataset: str, target: date, token: str) -> pd.DataFrame:
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {"dataset": dataset, "start_date": target.isoformat(), "end_date": target.isoformat(), "token": token}
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("data"):
            return pd.DataFrame()
        self._write_raw(payload, target, f"finmind_{dataset}")
        return pd.DataFrame(payload["data"])

    def _safe_frame(self, errors: list[str], label: str, func: Any, *args: Any) -> pd.DataFrame:
        try:
            return func(*args)
        except Exception as exc:
            errors.append(f"{label}：{exc}")
            return pd.DataFrame()

    def _first_json(self, urls: list[str]) -> dict[str, Any]:
        problems = []
        for url in urls:
            try:
                resp = self.session.get(url, timeout=self.timeout)
                resp.raise_for_status()
                payload = resp.json()
                self._extract_table(payload)
                return payload
            except Exception as exc:
                problems.append(f"{url} {exc}")
        raise RuntimeError("；".join(problems))

    def _extract_table(self, payload: dict[str, Any], required: tuple[str, ...] = ()) -> tuple[list[str], list[list[Any]]]:
        candidates = []
        if isinstance(payload.get("fields"), list) and isinstance(payload.get("data"), list):
            candidates.append((payload["fields"], payload["data"]))
        for table in payload.get("tables", []) or []:
            fields = table.get("fields") or table.get("columns")
            rows = table.get("data")
            if isinstance(fields, list) and isinstance(rows, list):
                candidates.append((fields, rows))
        if isinstance(payload.get("data"), list) and payload["data"] and isinstance(payload["data"][0], dict):
            fields = list(payload["data"][0].keys())
            candidates.append((fields, [[item.get(field) for field in fields] for item in payload["data"]]))
        for fields, rows in candidates:
            text = " ".join(str(x) for x in fields)
            if rows and all(token in text for token in required):
                return [str(x) for x in fields], rows
            if rows and not required:
                return [str(x) for x in fields], rows
        raise ValueError("沒有可辨識表格")

    def _rowdict(self, fields: list[str], row: list[Any]) -> dict[str, Any]:
        return {fields[i]: row[i] if i < len(row) else "" for i in range(len(fields))}

    def _write_raw(self, payload: dict[str, Any], target: date, name: str) -> None:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        (RAW_DIR / f"{target.isoformat()}_{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_csv(self, df: pd.DataFrame, target: date, name: str) -> None:
        if df.empty:
            return
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(PROCESSED_DIR / f"{target.isoformat()}_{name}.csv", index=False, encoding="utf-8-sig")


def normalize_margin_rows(market: str, fields: list[str], data: list[list[Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in data:
        item = {fields[i]: row[i] if i < len(row) else "" for i in range(len(fields))}
        code = clean_text(first_value(item, ["股票代號", "證券代號", "代號"]))
        if not is_stock_like(code):
            continue
        rows.append(
            {
                "market": market,
                "code": code,
                "margin_balance_lots": parse_int(first_value(item, ["融資今日餘額", "融資餘額"])),
                "short_balance_lots": parse_int(first_value(item, ["融券今日餘額", "融券餘額"])),
                "margin_change_lots": parse_int(first_value(item, ["融資買賣超", "融資增減"])),
                "short_change_lots": parse_int(first_value(item, ["融券買賣超", "融券增減"])),
            }
        )
    return rows


def first_value(item: dict[str, Any], names: list[str]) -> Any:
    for name in names:
        for key, value in item.items():
            if name in key:
                return value
    return ""


def clean_text(value: Any) -> str:
    return str(value or "").replace("\u3000", " ").strip()


def parse_int(value: Any) -> int:
    text = re.sub(r"[^0-9.+-]", "", clean_text(value))
    if text in {"", "+"} or set(text) <= {"-"}:
        return 0
    return int(float(text))


def parse_float(value: Any) -> float:
    text = re.sub(r"[^0-9.+-]", "", clean_text(value))
    if text in {"", "+"} or set(text) <= {"-"}:
        return 0.0
    return float(text)


def is_stock_like(code: str) -> bool:
    return bool(re.match(r"^[0-9A-Z]{4,6}$", code))


FUTURES_STOCKS = {
    "2330",
    "2317",
    "2454",
    "2303",
    "2881",
    "2882",
    "2412",
    "2308",
    "2382",
    "2891",
    "2886",
    "3711",
    "2603",
    "2615",
    "2002",
    "1301",
    "1303",
    "1216",
    "3008",
    "3037",
}
