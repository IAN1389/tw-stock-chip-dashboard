#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="Send latest chip report to Discord webhook.")
    parser.add_argument("report", nargs="?", help="Markdown report path. Defaults to latest reports/*_slking_chip_report.md")
    args = parser.parse_args()

    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        raise SystemExit("DISCORD_WEBHOOK_URL is not set.")

    report = Path(args.report) if args.report else latest_report()
    text = report.read_text(encoding="utf-8")
    chunks = split_message(text, 1800)
    for i, chunk in enumerate(chunks[:5], start=1):
        title = f"{report.name} ({i}/{min(len(chunks), 5)})"
        resp = requests.post(webhook, json={"content": f"**{title}**\n```md\n{chunk}\n```"}, timeout=20)
        resp.raise_for_status()
    print(f"sent: {report}")


def latest_report() -> Path:
    reports = sorted(Path("reports").glob("*_slking_chip_report.md"))
    if not reports:
        raise SystemExit("No report found.")
    return reports[-1]


def split_message(text: str, size: int) -> list[str]:
    lines = text.splitlines()
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for line in lines:
        if length + len(line) + 1 > size and current:
            chunks.append("\n".join(current))
            current = []
            length = 0
        current.append(line)
        length += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


if __name__ == "__main__":
    main()
