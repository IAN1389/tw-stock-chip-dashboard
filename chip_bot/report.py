from __future__ import annotations

import json
import os
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

from .fetch import MarketDataset


def build_report(dataset: MarketDataset, top_n: int = 15) -> str:
    rows = dataset.rows
    top_total_buy = sorted(rows, key=lambda r: r["total_lots"], reverse=True)[:top_n]
    top_total_sell = sorted(rows, key=lambda r: r["total_lots"])[:top_n]
    top_foreign_buy = sorted(rows, key=lambda r: r["foreign_lots"], reverse=True)[:top_n]
    top_trust_buy = sorted(rows, key=lambda r: r["trust_lots"], reverse=True)[:top_n]
    focus = sorted(rows, key=score_focus, reverse=True)[:top_n]

    sections = [
        f"# 台股盤後籌碼分析報告 {dataset.trade_date.isoformat()}",
        "",
        "資料來源：TWSE 臺灣證券交易所、TPEx 櫃買中心盤後公開資料。",
        "",
        "## 今日觀察重點",
        "",
        "- 三大法人合計買超代表法人籌碼偏多，但仍需搭配股價位置、成交量與基本面判斷。",
        "- 投信連續買超通常較有波段參考價值，第一版先列單日排行，後續可加入連買天數。",
        "- 法人買超但股價不漲、或融資同步大增時，要特別注意籌碼分歧風險。",
        "",
        table_section("主力偏多觀察清單", focus),
        table_section("三大法人合計買超排行", top_total_buy),
        table_section("三大法人合計賣超排行", top_total_sell),
        table_section("外資買超排行", top_foreign_buy),
        table_section("投信買超排行", top_trust_buy),
    ]

    ai_summary = maybe_ai_summary(dataset.trade_date, focus, top_total_sell)
    if ai_summary:
        sections.extend(["", "## AI 解讀", "", ai_summary])

    sections.extend(
        [
            "",
            "## 免責聲明",
            "",
            "本報告僅整理公開資訊並提供研究輔助，不構成任何買賣建議。請自行控管風險。",
            "",
        ]
    )
    return "\n".join(sections)


def score_focus(row: dict[str, Any]) -> float:
    score = row["total_lots"]
    if row["trust_lots"] > 0:
        score += row["trust_lots"] * 1.5
    if row["foreign_lots"] > 0:
        score += row["foreign_lots"] * 0.6
    if row["dealer_lots"] > 0:
        score += row["dealer_lots"] * 0.2
    return score


def table_section(title: str, rows: list[dict[str, Any]]) -> str:
    lines = [
        f"## {title}",
        "",
        "| 市場 | 代號 | 名稱 | 外資(張) | 投信(張) | 自營商(張) | 合計(張) |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {market} | {code} | {name} | {foreign_lots:,.0f} | {trust_lots:,.0f} | {dealer_lots:,.0f} | {total_lots:,.0f} |".format(
                **row
            )
        )
    return "\n".join(lines)


def maybe_ai_summary(trade_date: date, focus: list[dict[str, Any]], sells: list[dict[str, Any]]) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return ""

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    prompt = {
        "date": trade_date.isoformat(),
        "focus_top": compact_rows(focus),
        "sell_top": compact_rows(sells),
        "instruction": "請用繁體中文整理盤後籌碼重點，避免直接叫人買賣，語氣偏風險控管。",
    }
    body = json.dumps(
        {
            "model": model,
            "input": [
                {
                    "role": "user",
                    "content": "你是台股盤後籌碼研究助理。根據 JSON 資料產生 5 點以內的精簡解讀：\n"
                    + json.dumps(prompt, ensure_ascii=False),
                }
            ],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return extract_response_text(payload)
    except Exception as exc:
        return f"AI 解讀暫時失敗：{exc}"


def compact_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = ["market", "code", "name", "foreign_lots", "trust_lots", "dealer_lots", "total_lots"]
    return [{key: row[key] for key in keys} for row in rows[:10]]


def extract_response_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks: list[str] = []
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            text = content.get("text")
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip()


def write_report(report: str, output_dir: Path, trade_date: date) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{trade_date.isoformat()}_chip_report.md"
    path.write_text(report, encoding="utf-8")
    return path
