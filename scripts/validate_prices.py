#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate report close prices against raw TWSE/TPEx JSON.")
    parser.add_argument("--date", required=True, help="Report date, e.g. 2026-05-25")
    parser.add_argument("--codes", nargs="*", help="Optional stock codes to validate.")
    args = parser.parse_args()

    report_path = Path(f"reports/{args.date}_slking_chip_scores.csv")
    if not report_path.exists():
        raise SystemExit(f"Missing {report_path}")

    official = {}
    official.update(load_twse(Path(f"data/raw/{args.date}_twse_prices.json")))
    official.update(load_tpex(Path(f"data/raw/{args.date}_tpex_prices.json")))

    report = pd.read_csv(report_path, dtype={"code": str})
    if args.codes:
        report = report[report["code"].isin(args.codes)]

    mismatches = []
    checked = 0
    for row in report.itertuples(index=False):
        source = official.get(row.code)
        if not source:
            continue
        checked += 1
        if abs(float(row.close) - source["close"]) > 0.001:
            mismatches.append((row.code, row.name, float(row.close), source["close"], source["raw"]))

    if mismatches:
        print("Close price mismatches:")
        for code, name, report_close, official_close, raw in mismatches[:50]:
            print(f"{code} {name}: report={report_close} official={official_close} raw={raw}")
        raise SystemExit(1)

    print(f"OK: validated {checked} close prices against raw official JSON.")


def load_twse(path: Path) -> dict[str, dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = {}
    for table in payload.get("tables", []):
        fields = table.get("fields") or []
        if "證券代號" not in fields or "收盤價" not in fields:
            continue
        idx_code = fields.index("證券代號")
        idx_close = fields.index("收盤價")
        for row in table.get("data") or []:
            rows[str(row[idx_code]).strip()] = {"close": parse_number(row[idx_close]), "raw": row}
    return rows


def load_tpex(path: Path) -> dict[str, dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = {}
    for table in payload.get("tables", []):
        fields = [str(x).strip() for x in table.get("fields") or []]
        if "代號" not in fields or "收盤" not in fields:
            continue
        idx_code = fields.index("代號")
        idx_close = fields.index("收盤")
        for row in table.get("data") or []:
            rows[str(row[idx_code]).strip()] = {"close": parse_number(row[idx_close]), "raw": row}
    return rows


def parse_number(value: object) -> float:
    text = str(value).replace(",", "").strip()
    if not text or set(text) <= {"-"}:
        return 0.0
    return float(text)


if __name__ == "__main__":
    main()
