from __future__ import annotations

import csv
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"


@dataclass
class MarketDataset:
    trade_date: date
    rows: list[dict[str, Any]]


def fetch_all_markets(trade_date: date) -> MarketDataset:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []

    for market, fetcher in (("上市", fetch_twse_institutional), ("上櫃", fetch_tpex_institutional)):
        try:
            rows.extend(fetcher(trade_date))
        except Exception as exc:
            errors.append(f"{market}: {exc}")

    if not rows and errors:
        raise RuntimeError("; ".join(errors))

    write_processed_csv(trade_date, rows)
    return MarketDataset(trade_date=trade_date, rows=rows)


def fetch_twse_institutional(trade_date: date) -> list[dict[str, Any]]:
    ymd = trade_date.strftime("%Y%m%d")
    urls = [
        f"https://www.twse.com.tw/rwd/zh/fund/T86?date={ymd}&selectType=ALLBUT0999&response=json",
        f"https://www.twse.com.tw/fund/T86?date={ymd}&selectType=ALLBUT0999&response=json",
    ]
    payload = first_success_json(urls)
    save_raw("twse_t86", trade_date, payload)
    fields, data = extract_table(payload)
    return normalize_institutional_rows("上市", fields, data)


def fetch_tpex_institutional(trade_date: date) -> list[dict[str, Any]]:
    ad_date = trade_date.strftime("%Y/%m/%d")
    roc_date = f"{trade_date.year - 1911}/{trade_date:%m/%d}"
    urls = [
        "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?"
        + urllib.parse.urlencode({"date": ad_date, "type": "Daily", "response": "json"}),
        "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?"
        + urllib.parse.urlencode({"date": roc_date, "type": "Daily", "response": "json"}),
    ]
    payload = first_success_json(urls)
    save_raw("tpex_insti_dailyTrade", trade_date, payload)
    fields, data = extract_table(payload)
    return normalize_institutional_rows("上櫃", fields, data)


def first_success_json(urls: list[str]) -> dict[str, Any]:
    errors: list[str] = []
    for url in urls:
        try:
            payload = http_get_json(url)
            if has_table_data(payload):
                return payload
            errors.append(f"{url} 無資料")
        except Exception as exc:
            errors.append(f"{url} {exc}")
    raise RuntimeError("；".join(errors))


def http_get_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 chip-ai-bot/0.1",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        body = resp.read().decode("utf-8-sig")
    return json.loads(body)


def has_table_data(payload: dict[str, Any]) -> bool:
    try:
        _, data = extract_table(payload)
    except ValueError:
        return False
    return bool(data)


def extract_table(payload: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    if isinstance(payload.get("fields"), list) and isinstance(payload.get("data"), list):
        return [str(x) for x in payload["fields"]], payload["data"]

    for table in payload.get("tables", []) or []:
        fields = table.get("fields") or table.get("columns")
        data = table.get("data")
        if isinstance(fields, list) and isinstance(data, list) and data:
            return [str(x) for x in fields], data

    for key in ("aaData", "data"):
        data = payload.get(key)
        if isinstance(data, list) and data and isinstance(data[0], dict):
            fields = list(data[0].keys())
            rows = [[item.get(field) for field in fields] for item in data]
            return fields, rows

    raise ValueError("JSON 中沒有可辨識的表格資料")


def normalize_institutional_rows(market: str, fields: list[str], data: list[list[Any]]) -> list[dict[str, Any]]:
    idx = institutional_indexes(market, fields)

    normalized: list[dict[str, Any]] = []
    for row in data:
        if len(row) < 2:
            continue
        code = clean_text(get(row, idx["code"]))
        name = clean_text(get(row, idx["name"]))
        if not code or not re.match(r"^[0-9A-Z]{4,6}$", code):
            continue

        foreign = parse_number(get(row, idx["foreign"])) if idx["foreign"] is not None else 0
        trust = parse_number(get(row, idx["trust"])) if idx["trust"] is not None else 0
        dealer = parse_number(get(row, idx["dealer"])) if idx["dealer"] is not None else 0
        total = parse_number(get(row, idx["total"])) if idx["total"] is not None else foreign + trust + dealer

        normalized.append(
            {
                "market": market,
                "code": code,
                "name": name,
                "foreign_shares": foreign,
                "trust_shares": trust,
                "dealer_shares": dealer,
                "total_shares": total,
                "foreign_lots": round(foreign / 1000, 2),
                "trust_lots": round(trust / 1000, 2),
                "dealer_lots": round(dealer / 1000, 2),
                "total_lots": round(total / 1000, 2),
            }
        )
    return normalized


def institutional_indexes(market: str, fields: list[str]) -> dict[str, int | None]:
    if market == "上櫃" and fields.count("買賣超股數") >= 6:
        return {
            "code": 0,
            "name": 1,
            "foreign": 10,
            "trust": 13,
            "dealer": 22,
            "total": 23,
        }

    return {
        "code": find_field(fields, ["證券", "代號"], fallback=0),
        "name": find_field(fields, ["證券", "名稱"], fallback=1),
        "foreign": find_any_field(fields, [["外陸資", "買賣超"], ["外資", "買賣超"]]),
        "trust": find_field(fields, ["投信", "買賣超"]),
        "dealer": find_field(fields, ["自營商", "買賣超"], exclude=["外資"]),
        "total": find_field(fields, ["三大法人", "買賣超"]),
    }


def find_any_field(fields: list[str], token_sets: list[list[str]]) -> int | None:
    for tokens in token_sets:
        found = find_field(fields, tokens)
        if found is not None:
            return found
    return None


def find_field(fields: list[str], tokens: list[str], exclude: list[str] | None = None, fallback: int | None = None) -> int | None:
    exclude = exclude or []
    for i, field in enumerate(fields):
        text = clean_text(field)
        if all(token in text for token in tokens) and not any(token in text for token in exclude):
            return i
    return fallback


def get(row: list[Any], index: int | None) -> Any:
    if index is None or index >= len(row):
        return ""
    return row[index]


def clean_text(value: Any) -> str:
    return str(value).replace("\u3000", " ").strip()


def parse_number(value: Any) -> int:
    text = clean_text(value)
    if text in {"", "-", "--", "N/A", "nan"}:
        return 0
    text = re.sub(r"[^0-9.+-]", "", text)
    if text in {"", "+", "-"}:
        return 0
    return int(float(text))


def save_raw(prefix: str, trade_date: date, payload: dict[str, Any]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{trade_date.isoformat()}_{prefix}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_processed_csv(trade_date: date, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / f"{trade_date.isoformat()}_institutional.csv"
    fields = [
        "market",
        "code",
        "name",
        "foreign_shares",
        "trust_shares",
        "dealer_shares",
        "total_shares",
        "foreign_lots",
        "trust_lots",
        "dealer_lots",
        "total_lots",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
