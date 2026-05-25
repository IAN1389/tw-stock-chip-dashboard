# 台股盤後主力大戶籌碼分析 AI 系統

這是一個每天盤後自動執行的台股量化籌碼分析專案。系統會抓取上市櫃價量、三大法人、融資融券、期貨與選擇權擴充資料，產出「主力大戶籌碼分析報告」。

分析風格參考 SLKing 的核心精神：

- 不預設多空，用資料說話
- 重視趨勢、產業族群、資金流向
- 不靠單一指標，多因子交叉驗證
- 找強者恆強、弱者續弱
- 每檔股票附分類、強弱、觸發原因與風險提醒

## 專案結構

```text
data_fetcher.py       多來源資料抓取
indicators.py         均線、量能、突破、W 型態、假突破
chip_analyzer.py      法人、主力 proxy、融資融券、借券整合
sector_analyzer.py    產業族群分類與族群強度
scoring.py            0-100 分股票評分模型
report_generator.py   Markdown / CSV / HTML 報告
main.py               主程式
scripts/send_discord.py
scripts/fubon_check.py
requirements.txt
```

## 快速開始

```bash
cd /Users/ouyangshuoyuan/Documents/股市分析
source .venv/bin/activate
python main.py
```

指定日期：

```bash
python main.py --date 2026-05-22
```

輸出檔案：

```text
reports/index.html
reports/YYYY-MM-DD_slking_chip_report.md
reports/YYYY-MM-DD_slking_chip_report.html
reports/YYYY-MM-DD_slking_chip_scores.csv
```

最方便閱讀的入口是：

```text
reports/index.html
```

這個檔案會永遠覆蓋成最新一次產出的網頁報告，包含摘要卡、族群分類統計、法人籌碼交叉比對、資金流向、最強/最弱股票表格、明日觀察名單，以及可搜尋/篩選的觀察卡片。

所有股票級與族群級分析都會顯示當日成交量，方便同時判斷價格、籌碼與流動性。

## 評分模型

每檔普通股給 0-100 分：

- 價格趨勢：25%
- 成交量動能：20%
- 法人籌碼：25%
- 主力集中度：15%
- 族群強度：15%

主報告只納入 4 碼普通股，ETF / ETN / 權證原始資料會保留在 `data/`，但不進股票強弱排序。

## 篩選項目

報告會標記：

- 主力連續買超股
- 投信連續買超股
- 外資轉買股
- 放量突破股
- 創高股
- W 型態突破股
- 假突破轉弱股
- 可放空弱勢股
- 有期貨的股票
- 有權證的股票
- 外資 / 投信 / 自營商買超 Top 10
- 前日持續走強 Top 10
- 資金族群流入 / 流出 Top 10
- 資金當日主動流入 Top 20
- 資金止跌承接個股
- 量縮漲個股

目前「主力買賣超」使用法人買賣超、融資融券、借券的 proxy 模型。若之後串接券商 API 或付費分點資料，可以在 `chip_analyzer.py` 替換成真正分點主力資料。

## 資料來源

優先使用：

- TWSE 臺灣證券交易所
- TPEx 櫃買中心
- Taiwan Futures Exchange / FinMind 擴充
- yfinance 擴充預留
- 富邦 Neo API 擴充預留

期貨未平倉與選擇權 Put/Call Ratio 若要使用 FinMind，請設定：

```bash
export FINMIND_TOKEN="你的 FinMind token"
python main.py
```

## Discord 發送

```bash
export DISCORD_WEBHOOK_URL="你的 Discord webhook"
python scripts/send_discord.py
```

也可以指定報告：

```bash
python scripts/send_discord.py reports/2026-05-22_slking_chip_report.md
```

## 富邦 Neo API

本專案已下載並安裝富邦官方 Fubon Neo API Python SDK v2.2.8 到 `.venv`。

檢查安裝：

```bash
python scripts/fubon_check.py
```

登入前，先複製 `.env.example` 成 `.env` 並填入 API Key 或憑證資訊：

```bash
set -a
source .env
set +a
python scripts/fubon_check.py --login
```

`.env`、`.pfx`、`.p12` 已列入 `.gitignore`，不要把帳密或憑證寫進程式碼。

## 自動化

Codex automation 已設定為台北時間週一到週五 19:00 執行。盤後資料若延遲，系統會自動往前找最近可用交易日。

## GitHub Pages 部署

專案已內建 `.github/workflows/pages.yml`，推到 GitHub 後會：

- 每次 push 到 `main` 自動部署
- 台北時間週一到週五 17:00 自動產生最新報表並部署
- 也可在 GitHub Actions 手動按 `Run workflow`

第一次使用請到 GitHub repo：

1. `Settings` -> `Pages`
2. `Build and deployment` 選 `GitHub Actions`
3. 到 `Actions` 執行 `Deploy stock report to GitHub Pages`

部署完成後網址通常是：

```text
https://你的GitHub帳號.github.io/你的repo名稱/
```

若要讓期貨與選擇權資料更完整，可在 `Settings` -> `Secrets and variables` -> `Actions` 新增 `FINMIND_TOKEN`。

## 免責聲明

本系統是研究與決策輔助工具，不構成投資建議。任何交易決策都需要依個人資金規模與風險承受度調整。
