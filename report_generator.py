from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from html import escape
from pathlib import Path

import pandas as pd


@dataclass
class ReportPaths:
    markdown: Path
    csv: Path
    html: Path


class ReportGenerator:
    MONEY_MILLION_COLUMNS = {"turnover_million", "active_flow_million", "inst_flow_million"}

    def __init__(self, output_dir: str = "reports") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        trade_date: date,
        stocks: pd.DataFrame,
        sectors: pd.DataFrame,
        futures: pd.DataFrame,
        options: pd.DataFrame,
        errors: list[str],
    ) -> ReportPaths:
        strongest = stocks.sort_values("score", ascending=False).head(10)
        weakest = stocks.sort_values("score", ascending=True).head(10)
        watch = self._watchlist(stocks)
        analytics = self._analytics(stocks, sectors)
        csv_path = self.output_dir / f"{trade_date.isoformat()}_slking_chip_scores.csv"
        md_path = self.output_dir / f"{trade_date.isoformat()}_slking_chip_report.md"
        html_path = self.output_dir / f"{trade_date.isoformat()}_slking_chip_report.html"

        csv_stocks = stocks.sort_values("score", ascending=False).drop(
            columns=["entry_price", "stop_loss", "take_profit"],
            errors="ignore",
        )
        csv_stocks.to_csv(csv_path, index=False, encoding="utf-8-sig")
        markdown = self._markdown(trade_date, stocks, sectors, strongest, weakest, watch, futures, options, errors, analytics)
        md_path.write_text(markdown, encoding="utf-8")
        html = self._html(trade_date, stocks, sectors, strongest, weakest, watch, futures, options, errors, analytics)
        html_path.write_text(html, encoding="utf-8")
        (self.output_dir / "index.html").write_text(html, encoding="utf-8")
        return ReportPaths(markdown=md_path, csv=csv_path, html=html_path)

    def _watchlist(self, stocks: pd.DataFrame) -> pd.DataFrame:
        flags = (
            stocks["main_force_continuous_buy"]
            | stocks["trust_continuous_buy"]
            | stocks["foreign_turn_buy"]
            | stocks["breakout"]
            | stocks["new_high_20d"]
            | stocks["w_breakout"]
            | stocks["fake_breakout"]
            | stocks["short_candidate"]
        )
        return stocks[flags].sort_values("score", ascending=False).head(30)

    def _analytics(self, stocks: pd.DataFrame, sectors: pd.DataFrame) -> dict[str, pd.DataFrame]:
        return {
            "foreign_top": stocks.sort_values("foreign_buy_lots", ascending=False).head(10),
            "trust_top": stocks.sort_values("trust_buy_lots", ascending=False).head(10),
            "dealer_top": stocks.sort_values("dealer_buy_lots", ascending=False).head(10),
            "continued_strength": stocks[stocks["continued_strength"]].sort_values(["score", "active_flow_million"], ascending=False).head(10),
            "sector_inflow": sectors.sort_values("total_inst_lots", ascending=False).head(10) if not sectors.empty else pd.DataFrame(),
            "sector_outflow": sectors.sort_values("total_inst_lots", ascending=True).head(10) if not sectors.empty else pd.DataFrame(),
            "active_inflow": stocks[stocks["active_flow_million"] > 0].sort_values("active_flow_million", ascending=False).head(20),
            "bottom_support": stocks[stocks["bottom_support"]].sort_values(["score", "active_flow_million"], ascending=False).head(20),
            "up_contracting_volume": stocks[stocks["up_on_contracting_volume"]].sort_values(["score", "pct_change"], ascending=False).head(20),
        }

    def _markdown(
        self,
        trade_date: date,
        stocks: pd.DataFrame,
        sectors: pd.DataFrame,
        strongest: pd.DataFrame,
        weakest: pd.DataFrame,
        watch: pd.DataFrame,
        futures: pd.DataFrame,
        options: pd.DataFrame,
        errors: list[str],
        analytics: dict[str, pd.DataFrame],
    ) -> str:
        market_line = self._market_conclusion(stocks)
        tx_line = self._tx_conclusion(futures, options)
        parts = [
            f"# 主力大戶籌碼分析報告 {trade_date.isoformat()}",
            "",
            "分析原則：不預設多空，用趨勢、量能、法人、主力集中度、族群強度交叉驗證。分數不是買賣保證，只是排序工具。",
            "",
            "族群分類：以台股常用題材與產業族群為主，例如 AI 伺服器、PCB、散熱、記憶體、IC 設計、金融股、航運股；公開產業別只作備援。",
            "",
            "## 今日大盤結論",
            "",
            market_line,
            "",
            "## 台指期多空方向",
            "",
            tx_line,
            "",
            "## 外資期貨籌碼",
            "",
            self._futures_text(futures),
            "",
            "## 族群分類統計",
            "",
            self._sector_table(sectors.head(10)),
            "",
            "## 法人籌碼交叉比對",
            "",
            "### 外資買超 Top 10",
            "",
            self._flow_stock_table(analytics["foreign_top"], ["foreign_buy_lots", "inst_buy_lots"]),
            "",
            "### 投信買超 Top 10",
            "",
            self._flow_stock_table(analytics["trust_top"], ["trust_buy_lots", "inst_buy_lots"]),
            "",
            "### 自營商買超 Top 10",
            "",
            self._flow_stock_table(analytics["dealer_top"], ["dealer_buy_lots", "inst_buy_lots"]),
            "",
            "## 前日持續走強 Top 10",
            "",
            self._flow_stock_table(analytics["continued_strength"], ["prev_pct_change", "volume_ratio", "active_flow_million"]),
            "",
            "## 資金族群流向",
            "",
            "### 流入 Top 10",
            "",
            self._sector_flow_table(analytics["sector_inflow"]),
            "",
            "### 流出 Top 10",
            "",
            self._sector_flow_table(analytics["sector_outflow"]),
            "",
            "## 資金當日主動流入 Top 20",
            "",
            self._flow_stock_table(analytics["active_inflow"], ["turnover_million", "active_flow_million", "inst_flow_million"]),
            "",
            "## 資金止跌承接個股",
            "",
            self._flow_stock_table(analytics["bottom_support"], ["volume_ratio", "active_flow_million", "inst_buy_lots"]),
            "",
            "## 量縮漲個股",
            "",
            self._flow_stock_table(analytics["up_contracting_volume"], ["volume_ratio", "active_flow_million"]),
            "",
            "## 最強 10 檔股票",
            "",
            self._stock_table(strongest),
            "",
            "## 最弱 10 檔股票",
            "",
            self._stock_table(weakest),
            "",
            "## 明日觀察名單",
            "",
            self._watch_table(watch),
            "",
            "## 篩選條件摘要",
            "",
            self._screen_summary(stocks),
            "",
            "## 風險提醒",
            "",
            "- 放量突破隔日若開高走低，優先視為籌碼鬆動。",
            "- 分數高但融資暴增，倉位要縮小；分數低且反彈無量，弱者續弱機率較高。",
            "- 族群分類以常用台股題材與產業稱呼為主，題材概念仍需搭配公司公告與新聞事件確認。",
            "- 本報告不構成投資建議，請依自身資金與風險承受度決策。",
        ]
        if errors:
            parts.extend(["", "## 資料品質", ""])
            parts.extend([f"- {err}" for err in errors])
        return "\n".join(parts) + "\n"

    def _stock_table(self, df: pd.DataFrame) -> str:
        cols = [
            "market",
            "code",
            "name",
            "sector",
            "close",
            "pct_change",
            "volume",
            "score",
            "trend_label",
            "chip_note",
            "risk_note",
        ]
        return df[[c for c in cols if c in df.columns]].to_markdown(index=False)

    def _watch_table(self, df: pd.DataFrame) -> str:
        if df.empty:
            return "今日沒有符合多因子條件的觀察名單。"
        out = df.copy()
        out["reason"] = out.apply(self._watch_reason, axis=1)
        cols = ["market", "code", "name", "sector", "close", "pct_change", "volume", "score", "reason", "risk_note"]
        return out[[c for c in cols if c in out.columns]].to_markdown(index=False)

    def _flow_stock_table(self, df: pd.DataFrame, extra_cols: list[str]) -> str:
        if df.empty:
            return "沒有符合條件的股票。"
        base = ["market", "code", "name", "sector", "close", "pct_change", "volume", "score"]
        cols = base + extra_cols + ["trend_label", "chip_note", "risk_note"]
        out = df[[c for c in cols if c in df.columns]].copy()
        for col in self.MONEY_MILLION_COLUMNS.intersection(out.columns):
            out[col] = out[col] / 100
        display_names = {
            "market": "市場",
            "code": "代號",
            "name": "名稱",
            "sector": "族群",
            "close": "收盤",
            "pct_change": "漲跌幅",
            "volume": "成交量",
            "score": "分數",
            "prev_pct_change": "前日漲跌幅",
            "volume_ratio": "量比",
            "turnover_million": "成交金額(億)",
            "active_flow_million": "主動流入(億)",
            "inst_flow_million": "法人金額(億)",
            "inst_buy_lots": "法人合計",
            "foreign_buy_lots": "外資",
            "trust_buy_lots": "投信",
            "dealer_buy_lots": "自營商",
            "trend_label": "趨勢",
            "chip_note": "籌碼",
            "risk_note": "風險",
        }
        return out.rename(columns=display_names).round(2).to_markdown(index=False)

    def _sector_flow_table(self, df: pd.DataFrame) -> str:
        if df.empty:
            return "族群資料不足。"
        cols = [
            "sector",
            "industry_group",
            "sector_strength",
            "avg_pct_change",
            "total_volume",
            "total_inst_lots",
            "total_foreign_lots",
            "total_trust_lots",
            "total_dealer_lots",
            "stock_count",
        ]
        return df[[c for c in cols if c in df.columns]].round(2).to_markdown(index=False)

    def _sector_table(self, df: pd.DataFrame) -> str:
        if df.empty:
            return "族群資料不足。"
        cols = [
            "sector",
            "industry_group",
            "sector_strength",
            "avg_score",
            "avg_pct_change",
            "total_volume",
            "total_inst_lots",
            "total_foreign_lots",
            "total_trust_lots",
            "total_margin_change",
            "strong_count",
            "weak_count",
            "stock_count",
        ]
        return df[[c for c in cols if c in df.columns]].round(2).to_markdown(index=False)

    def _screen_summary(self, stocks: pd.DataFrame) -> str:
        screens = {
            "主力連續買超股": "main_force_continuous_buy",
            "投信連續買超股": "trust_continuous_buy",
            "外資轉買股": "foreign_turn_buy",
            "放量突破股": "breakout",
            "創高股": "new_high_20d",
            "W 型態突破股": "w_breakout",
            "假突破轉弱股": "fake_breakout",
            "可放空弱勢股": "short_candidate",
            "有期貨的股票": "has_futures",
            "有權證的股票": "has_warrant",
        }
        lines = []
        for label, col in screens.items():
            count = int(stocks[col].fillna(False).sum()) if col in stocks.columns else 0
            lines.append(f"- {label}：{count} 檔")
        return "\n".join(lines)

    def _market_conclusion(self, stocks: pd.DataFrame) -> str:
        if stocks.empty:
            return "今日股票資料不足，暫不判斷。"
        avg_score = stocks["score"].mean()
        strong = int((stocks["score"] >= 70).sum())
        weak = int((stocks["score"] <= 35).sum())
        up_ratio = (stocks["pct_change"] > 0).mean() * 100
        if avg_score >= 60 and strong > weak:
            tone = "盤面偏多，強勢股續強優先。"
        elif avg_score <= 45 and weak >= strong:
            tone = "盤面偏弱，反彈先看減碼與放空名單。"
        else:
            tone = "盤面分歧，等待主流族群表態。"
        return f"{tone} 全市場平均分數 {avg_score:.1f}，上漲家數比 {up_ratio:.1f}%，強勢股 {strong} 檔，弱勢股 {weak} 檔。"

    def _tx_conclusion(self, futures: pd.DataFrame, options: pd.DataFrame) -> str:
        if futures.empty and options.empty:
            return "期貨與選擇權資料不足，台指期方向暫以現貨族群強弱輔助判斷。"
        pcr = 0.0
        if not options.empty and "put_call_ratio" in options.columns:
            pcr = float(options["put_call_ratio"].iloc[0] or 0)
        if pcr >= 1.2:
            return f"選擇權 PCR {pcr:.2f}，避險需求偏高，台指期不追多。"
        if 0 < pcr <= 0.8:
            return f"選擇權 PCR {pcr:.2f}，市場偏樂觀，留意過熱。"
        return "期權資料未完整，台指期暫以區間看待。"

    def _futures_text(self, futures: pd.DataFrame) -> str:
        if futures.empty:
            return "外資期貨資料不足。"
        return futures.head(5).to_markdown(index=False)

    def _watch_reason(self, row: pd.Series) -> str:
        mapping = [
            ("main_force_continuous_buy", "主力買超"),
            ("trust_continuous_buy", "投信買超"),
            ("foreign_turn_buy", "外資轉買"),
            ("breakout", "放量突破"),
            ("new_high_20d", "創高"),
            ("w_breakout", "W突破"),
            ("fake_breakout", "假突破轉弱"),
            ("short_candidate", "弱勢放空"),
        ]
        return "、".join(label for col, label in mapping if bool(row.get(col, False))) or "觀察"

    def _html(
        self,
        trade_date: date,
        stocks: pd.DataFrame,
        sectors: pd.DataFrame,
        strongest: pd.DataFrame,
        weakest: pd.DataFrame,
        watch: pd.DataFrame,
        futures: pd.DataFrame,
        options: pd.DataFrame,
        errors: list[str],
        analytics: dict[str, pd.DataFrame],
    ) -> str:
        watch_view = watch.copy()
        if not watch_view.empty:
            watch_view["reason"] = watch_view.apply(self._watch_reason, axis=1)

        market_line = self._market_conclusion(stocks)
        tx_line = self._tx_conclusion(futures, options)
        avg_score = float(stocks["score"].mean()) if not stocks.empty else 0.0
        up_ratio = float((stocks["pct_change"] > 0).mean() * 100) if not stocks.empty else 0.0
        strong_count = int((stocks["score"] >= 70).sum()) if not stocks.empty else 0
        weak_count = int((stocks["score"] <= 35).sum()) if not stocks.empty else 0
        best_sector = sectors.iloc[0]["sector"] if not sectors.empty else "資料不足"
        generated = pd.Timestamp.now(tz="Asia/Taipei").strftime("%Y-%m-%d %H:%M")
        stock_payload = self._json_records(
            watch_view,
            ["code", "name", "sector", "score", "close", "pct_change", "volume", "reason", "risk_note"],
        )
        sector_stock_payload = self._json_records(
            self._sector_tab_stocks(stocks),
            ["code", "name", "sector", "score", "close", "pct_change", "volume", "trend_label", "chip_note", "risk_note"],
        )

        return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>主力大戶籌碼分析報告 {trade_date.isoformat()}</title>
  {self._html_css()}
</head>
<body>
  <header class="topbar">
    <div>
      <div class="eyebrow">TW After-hours Chip Dashboard</div>
      <h1>主力大戶籌碼分析報告</h1>
      <p>{escape(trade_date.isoformat())}｜產生時間 {escape(generated)}｜台股常用族群分類</p>
    </div>
    <nav>
      <a href="#market">大盤</a>
      <a href="#sectors">族群</a>
      <a href="#category-tabs">分類分頁</a>
      <a href="#strong">強勢</a>
      <a href="#weak">弱勢</a>
      <a href="#watch">觀察</a>
    </nav>
  </header>

  <main>
    <section class="hero-panel">
      <div>
        <div class="eyebrow">After-hours camp classification</div>
        <h2>盤後籌碼陣營總覽</h2>
        <p>{escape(market_line)}</p>
      </div>
      <div class="hero-facts">
        <div><span>交易日</span><strong>{escape(trade_date.isoformat())}</strong></div>
        <div><span>主流族群</span><strong>{escape(str(best_sector))}</strong></div>
        <div><span>分類數</span><strong>{len(set(stocks["sector"].dropna())) if "sector" in stocks.columns else 0}</strong></div>
        <div><span>觀察名單</span><strong>{len(watch_view)}</strong></div>
      </div>
    </section>

    <section id="market" class="summary-grid">
      {self._metric_card("平均分數", f"{avg_score:.1f}", self._score_state(avg_score), "全市場多因子平均")}
      {self._metric_card("上漲家數比", f"{up_ratio:.1f}%", self._ratio_state(up_ratio), "普通股上漲比例")}
      {self._metric_card("強勢 / 弱勢", f"{strong_count} / {weak_count}", "neutral", "分數 >=70 / <=35")}
      {self._metric_card("主流族群", str(best_sector), "neutral", "依族群強度排序")}
    </section>

    <section class="panel two-column">
      <div>
        <h2>今日大盤結論</h2>
        <p class="lead">{escape(market_line)}</p>
      </div>
      <div>
        <h2>台指期多空方向</h2>
        <p class="lead">{escape(tx_line)}</p>
      </div>
    </section>

    <section id="sectors" class="panel">
      <div class="section-head">
        <h2>族群分類統計</h2>
        <span>以台股常用題材與產業稱呼分類，公開產業別作備援</span>
      </div>
      {self._sector_cards(sectors.head(8))}
    </section>

    <section id="category-tabs" class="panel">
      <div class="section-head">
        <h2>分類分頁</h2>
        <span>依族群切成獨立分頁，每頁顯示該分類分數排序</span>
      </div>
      <div class="toolbar">
        <input id="categorySearch" type="search" placeholder="搜尋代號、名稱、族群">
        <span id="categoryMeta" class="toolbar-meta"></span>
      </div>
      <div id="categoryTabs" class="tabs" role="tablist"></div>
      <div id="categoryPane"></div>
    </section>

    <section class="panel">
      <div class="section-head">
        <h2>法人籌碼交叉比對</h2>
        <span>外資、投信、自營商買超 Top 10，皆含當日成交量</span>
      </div>
      <div class="subgrid">
        {self._html_flow_block("外資買超 Top 10", analytics["foreign_top"], ["foreign_buy_lots", "inst_buy_lots"])}
        {self._html_flow_block("投信買超 Top 10", analytics["trust_top"], ["trust_buy_lots", "inst_buy_lots"])}
        {self._html_flow_block("自營商買超 Top 10", analytics["dealer_top"], ["dealer_buy_lots", "inst_buy_lots"])}
      </div>
    </section>

    <section class="panel">
      <div class="section-head">
        <h2>資金流向與延續性</h2>
        <span>資金流以成交金額、漲跌幅、量比與法人買賣超估算 proxy</span>
      </div>
      {self._html_flow_block("前日持續走強 Top 10", analytics["continued_strength"], ["prev_pct_change", "volume_ratio", "active_flow_million"])}
      {self._html_sector_flow("資金族群流入 Top 10", analytics["sector_inflow"])}
      {self._html_sector_flow("資金族群流出 Top 10", analytics["sector_outflow"])}
      {self._html_flow_block("資金當日主動流入 Top 20", analytics["active_inflow"], ["turnover_million", "active_flow_million", "inst_flow_million"])}
      {self._html_flow_block("資金止跌承接個股", analytics["bottom_support"], ["volume_ratio", "active_flow_million", "inst_buy_lots"])}
      {self._html_flow_block("量縮漲個股", analytics["up_contracting_volume"], ["volume_ratio", "active_flow_million"])}
    </section>

    <section id="strong" class="panel">
      <div class="section-head">
        <h2>最強 10 檔股票</h2>
        <span>強者恆強候選，隔日仍需看開盤承接</span>
      </div>
      {self._html_stock_table(strongest, positive=True)}
    </section>

    <section id="weak" class="panel">
      <div class="section-head">
        <h2>最弱 10 檔股票</h2>
        <span>弱者續弱候選，反彈無量偏空看待</span>
      </div>
      {self._html_stock_table(weakest, positive=False)}
    </section>

    <section id="watch" class="panel">
      <div class="section-head">
        <h2>明日觀察名單</h2>
        <span>只保留分類、強弱、觸發原因與風險提醒</span>
      </div>
      <div class="toolbar">
        <input id="stockSearch" type="search" placeholder="搜尋代號、名稱、族群">
        <select id="sectorFilter">
          <option value="">全部族群</option>
        </select>
      </div>
      <div id="watchCards" class="watch-grid"></div>
    </section>

    <section class="panel two-column">
      <div>
        <h2>篩選條件摘要</h2>
        {self._html_screen_summary(stocks)}
      </div>
      <div>
        <h2>資料品質</h2>
        {self._html_errors(errors)}
      </div>
    </section>
  </main>

  <script>
    const watchStocks = {stock_payload};
    const sectorStocks = {sector_stock_payload};
    {self._html_script()}
  </script>
</body>
</html>"""

    def _sector_tab_stocks(self, stocks: pd.DataFrame) -> pd.DataFrame:
        if stocks.empty or "sector" not in stocks.columns:
            return pd.DataFrame()
        cols = [
            "code",
            "name",
            "sector",
            "score",
            "close",
            "pct_change",
            "volume",
            "trend_label",
            "chip_note",
            "risk_note",
        ]
        out = stocks[[c for c in cols if c in stocks.columns]].copy()
        out["sector"] = out["sector"].fillna("其他").astype(str)
        out = out.sort_values(["sector", "score", "volume"], ascending=[True, False, False])
        return out.groupby("sector", group_keys=False).head(20)

    def _html_css(self) -> str:
        return """<style>
:root{--bg:#eef2ef;--panel:#fff;--panel-soft:#f8faf8;--ink:#111815;--muted:#66736d;--line:#d8e1dc;--line-strong:#c4d0ca;--green:#0f7a58;--green-2:#6fa342;--red:#b54545;--amber:#a86b13;--blue:#276a8d;--navy:#173b31;--shadow:0 18px 42px rgba(31,49,42,.08)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(circle at 18% -10%,rgba(15,122,88,.16),transparent 32%),linear-gradient(180deg,#f8faf8 0%,var(--bg) 44%,#e8eeeb 100%);color:var(--ink);font-family:"Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif;line-height:1.5}
.topbar{position:sticky;top:0;z-index:10;display:flex;align-items:center;justify-content:space-between;gap:24px;padding:16px 28px;background:rgba(248,250,248,.92);border-bottom:1px solid var(--line);backdrop-filter:blur(18px)}
.eyebrow{font-size:12px;color:var(--green);font-weight:800;text-transform:uppercase;letter-spacing:.08em}.topbar h1{margin:2px 0 4px;font-size:23px;letter-spacing:0}.topbar p{margin:0;color:var(--muted);font-size:13px}
nav{display:flex;gap:8px;flex-wrap:wrap}nav a{color:#20372f;text-decoration:none;font-size:14px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:#fff;transition:background .18s ease,border-color .18s ease,transform .18s ease}nav a:hover{background:#eef6f2;border-color:#a9c7ba;transform:translateY(-1px)}
main{max-width:1480px;margin:0 auto;padding:24px}.hero-panel{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(360px,.8fr);gap:22px;margin:4px 0 18px;padding:26px;background:linear-gradient(135deg,#113a31 0%,#1e5d4e 52%,#f4f7f3 52%);border:1px solid rgba(17,58,49,.18);border-radius:8px;box-shadow:var(--shadow);overflow:hidden}.hero-panel h2{color:#fff;font-size:34px;margin:4px 0 10px}.hero-panel p{max-width:760px;margin:0;color:#dcebe5;font-size:17px}.hero-facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.hero-facts div{background:rgba(255,255,255,.9);border:1px solid rgba(255,255,255,.55);border-radius:8px;padding:13px 14px}.hero-facts span{display:block;color:var(--muted);font-size:12px}.hero-facts strong{display:block;margin-top:4px;font-size:20px;color:#173b31;line-height:1.2}
.summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:18px}.metric{position:relative;overflow:hidden;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:16px;box-shadow:0 10px 28px rgba(25,42,35,.05)}.metric:before{content:"";position:absolute;inset:0 0 auto;height:3px;background:var(--blue)}.metric.positive:before{background:var(--green)}.metric.negative:before{background:var(--red)}.metric span{display:block;color:var(--muted);font-size:13px}.metric strong{display:block;margin:6px 0;font-size:30px;line-height:1.1}.metric.positive strong{color:var(--green)}.metric.negative strong{color:var(--red)}.metric.neutral strong{color:var(--blue)}
.panel{background:rgba(255,255,255,.96);border:1px solid var(--line);border-radius:8px;margin:18px 0;padding:20px;box-shadow:0 12px 30px rgba(31,49,42,.05)}.two-column{display:grid;grid-template-columns:1fr 1fr;gap:22px}.subgrid{display:grid;grid-template-columns:1fr;gap:18px}.mini-section{margin:18px 0}.mini-section h3{margin:0 0 10px;font-size:17px}.section-head{display:flex;justify-content:space-between;gap:16px;align-items:end;margin-bottom:14px}h2{margin:0 0 8px;font-size:20px;letter-spacing:0}.section-head h2{margin:0}.section-head span,.lead{color:var(--muted)}.lead{font-size:17px;margin:0}
.sector-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.sector{border:1px solid var(--line);border-radius:8px;padding:14px;background:linear-gradient(180deg,#fff,#f8fbf9);transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease}.sector:hover{transform:translateY(-2px);border-color:#a9c7ba;box-shadow:0 12px 28px rgba(31,49,42,.08)}.sector-top{display:flex;justify-content:space-between;align-items:center;gap:10px}.sector h3{margin:0;font-size:17px}.bar{height:8px;background:#e7eeea;border-radius:99px;overflow:hidden;margin:12px 0}.bar i{display:block;height:100%;background:linear-gradient(90deg,var(--green),var(--green-2))}.sector dl{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:0}.sector dt{color:var(--muted);font-size:12px}.sector dd{margin:0;font-weight:800}
.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:8px;background:#fff;box-shadow:inset 0 1px 0 rgba(255,255,255,.7)}table{width:100%;border-collapse:separate;border-spacing:0;min-width:1080px}th,td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:right;vertical-align:top;font-size:14px}tbody tr:nth-child(even){background:#fbfdfb}tbody tr:hover{background:#eef6f2}th{position:sticky;top:0;background:#e8f1ed;color:#243a33;font-weight:800;z-index:1}td:first-child,td:nth-child(2),td:nth-child(3),td:nth-child(4),td:last-child{text-align:left}.positive{color:var(--green);font-weight:800}.negative{color:var(--red);font-weight:800}.neutral{color:var(--blue)}.code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-weight:800}.score-pill{display:inline-flex;min-width:48px;justify-content:center;padding:3px 8px;border-radius:99px;color:white;font-weight:800}.score-high{background:var(--green)}.score-mid{background:var(--amber)}.score-low{background:var(--red)}.tag{display:inline-block;margin:0 4px 4px 0;padding:3px 7px;border-radius:99px;background:#eef5f3;color:#244139;font-size:12px}
.toolbar{display:flex;gap:10px;margin-bottom:14px;align-items:center}input,select{height:40px;border:1px solid var(--line);border-radius:8px;background:#fff;padding:0 12px;font-size:15px}input{flex:1}input:focus,select:focus,.tab-button:focus{outline:2px solid rgba(15,122,88,.22);outline-offset:2px;border-color:#78aa95}.toolbar-meta{color:var(--muted);font-size:13px;white-space:nowrap}.tabs{display:flex;gap:8px;overflow:auto;padding:2px 0 12px;margin-bottom:14px}.tab-button{border:1px solid var(--line);border-radius:8px;background:#fff;color:#243a33;cursor:pointer;flex:0 0 auto;padding:8px 11px;font-size:14px;transition:background .16s ease,color .16s ease,border-color .16s ease,transform .16s ease}.tab-button:hover{transform:translateY(-1px);border-color:#a9c7ba}.tab-button[aria-selected="true"]{background:var(--navy);color:#fff;border-color:var(--navy)}.tab-count{opacity:.72;margin-left:4px}.category-head{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:10px}.category-head h3{margin:0;font-size:18px}.category-head span{color:var(--muted);font-size:13px}
.watch-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.watch-card{border:1px solid var(--line);border-radius:8px;padding:14px;background:#fff;transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease}.watch-card:hover{transform:translateY(-2px);border-color:#a9c7ba;box-shadow:0 12px 28px rgba(31,49,42,.08)}.watch-card header{display:flex;justify-content:space-between;gap:10px;align-items:start}.watch-card h3{margin:0;font-size:17px}.watch-card p{margin:6px 0;color:var(--muted);font-size:13px}.watch-card .risk-text{border-top:1px solid var(--line);margin-top:12px;padding-top:10px;color:#36443f}.price-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px}.price-grid div{background:#f1f5f3;border-radius:8px;padding:8px}.price-grid span{display:block;color:var(--muted);font-size:12px}.price-grid b{font-size:15px}.summary-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:0;padding:0;list-style:none}.summary-list li{display:flex;justify-content:space-between;border:1px solid var(--line);border-radius:8px;padding:9px 10px;background:#fff}.warnings{margin:0;padding-left:18px;color:var(--muted)}
@media (max-width:1000px){main{padding:18px}.hero-panel{grid-template-columns:1fr;background:linear-gradient(180deg,#113a31 0%,#1e5d4e 58%,#f4f7f3 58%)}.summary-grid,.sector-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.two-column,.watch-grid{grid-template-columns:1fr}.topbar{position:static;align-items:flex-start;flex-direction:column}.section-head{align-items:flex-start;flex-direction:column}.toolbar{align-items:stretch;flex-direction:column}.toolbar-meta{white-space:normal}}
@media (max-width:620px){main{padding:14px}.hero-panel{padding:18px}.hero-panel h2{font-size:27px}.hero-panel p{font-size:15px}.hero-facts,.summary-grid,.sector-grid{grid-template-columns:1fr}.topbar{padding:16px}.topbar h1{font-size:21px}.metric strong{font-size:26px}.panel{padding:14px}.summary-list{grid-template-columns:1fr}.price-grid{grid-template-columns:1fr}nav a{font-size:13px;padding:7px 8px}th,td{font-size:13px;padding:9px 10px}}
</style>"""

    def _metric_card(self, title: str, value: str, state: str, note: str) -> str:
        return f'<article class="metric {state}"><span>{escape(title)}</span><strong>{escape(value)}</strong><span>{escape(note)}</span></article>'

    def _sector_cards(self, df: pd.DataFrame) -> str:
        if df.empty:
            return '<p class="lead">族群資料不足。</p>'
        cards = []
        for _, row in df.iterrows():
            strength = float(row.get("sector_strength", 0))
            width = max(0, min(100, strength))
            cards.append(
                f"""<article class="sector">
  <div class="sector-top"><h3>{escape(str(row.get("sector", "")))}</h3><span class="score-pill {self._score_class(strength)}">{strength:.1f}</span></div>
  <div class="bar"><i style="width:{width:.0f}%"></i></div>
  <dl>
    <div><dt>族群大類</dt><dd>{escape(str(row.get("industry_group", ""))[:8])}</dd></div>
    <div><dt>平均分</dt><dd>{float(row.get("avg_score", 0)):.1f}</dd></div>
    <div><dt>成交量</dt><dd>{float(row.get("total_volume", 0)):,.0f} 張</dd></div>
    <div><dt>法人</dt><dd>{float(row.get("total_inst_lots", 0)):,.0f} 張</dd></div>
    <div><dt>強/弱</dt><dd>{int(row.get("strong_count", 0))}/{int(row.get("weak_count", 0))}</dd></div>
  </dl>
</article>"""
            )
        return '<div class="sector-grid">' + "\n".join(cards) + "</div>"

    def _html_flow_block(self, title: str, df: pd.DataFrame, extra_cols: list[str]) -> str:
        return f'<div class="mini-section"><h3>{escape(title)}</h3>{self._html_stock_table(df, positive=True, extra_cols=extra_cols)}</div>'

    def _html_sector_flow(self, title: str, df: pd.DataFrame) -> str:
        if df.empty:
            table = '<p class="lead">族群資料不足。</p>'
        else:
            headers = ["族群", "族群大類", "強度", "漲跌幅", "成交量", "法人", "外資", "投信", "自營商", "檔數"]
            rows = []
            for _, row in df.iterrows():
                rows.append(
                    "<tr>"
                    f"<td>{escape(str(row.get('sector', '')))}</td>"
                    f"<td>{escape(str(row.get('industry_group', '')))}</td>"
                    f"<td>{float(row.get('sector_strength', 0)):.1f}</td>"
                    f"<td class='{self._pct_class(float(row.get('avg_pct_change', 0)))}'>{float(row.get('avg_pct_change', 0)):.2f}%</td>"
                    f"<td>{float(row.get('total_volume', 0)):,.0f}</td>"
                    f"<td>{float(row.get('total_inst_lots', 0)):,.0f}</td>"
                    f"<td>{float(row.get('total_foreign_lots', 0)):,.0f}</td>"
                    f"<td>{float(row.get('total_trust_lots', 0)):,.0f}</td>"
                    f"<td>{float(row.get('total_dealer_lots', 0)):,.0f}</td>"
                    f"<td>{int(row.get('stock_count', 0))}</td>"
                    "</tr>"
                )
            table = "<div class='table-wrap'><table><thead><tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr></thead><tbody>" + "\n".join(rows) + "</tbody></table></div>"
        return f'<div class="mini-section"><h3>{escape(title)}</h3>{table}</div>'

    def _html_stock_table(self, df: pd.DataFrame, positive: bool, extra_cols: list[str] | None = None) -> str:
        if df.empty:
            return '<p class="lead">資料不足。</p>'
        extra_cols = extra_cols or []
        header_map = {
            "foreign_buy_lots": "外資",
            "trust_buy_lots": "投信",
            "dealer_buy_lots": "自營商",
            "inst_buy_lots": "法人合計",
            "prev_pct_change": "前日漲跌幅",
            "volume_ratio": "量比",
            "turnover_million": "成交金額(億)",
            "active_flow_million": "主動流入(億)",
            "inst_flow_million": "法人金額(億)",
        }
        headers = ["市場", "代號", "名稱", "族群", "收盤", "漲跌幅", "成交量", "分數"] + [header_map.get(c, c) for c in extra_cols] + ["趨勢", "籌碼", "風險"]
        rows = []
        for _, row in df.iterrows():
            score = float(row.get("score", 0))
            tags = "".join(f'<span class="tag">{escape(x)}</span>' for x in str(row.get("chip_note", "")).split("、") if x)
            extra_tds = "".join(f"<td>{self._format_extra(row.get(col, 0), col)}</td>" for col in extra_cols)
            rows.append(
                "<tr>"
                f"<td>{escape(str(row.get('market', '')))}</td>"
                f"<td><span class='code'>{escape(str(row.get('code', '')))}</span></td>"
                f"<td>{escape(str(row.get('name', '')))}</td>"
                f"<td>{escape(str(row.get('sector', '')))}</td>"
                f"<td>{float(row.get('close', 0)):.2f}</td>"
                f"<td class='{self._pct_class(float(row.get('pct_change', 0)))}'>{float(row.get('pct_change', 0)):.2f}%</td>"
                f"<td>{float(row.get('volume', 0)):,.0f}</td>"
                f"<td><span class='score-pill {self._score_class(score)}'>{score:.1f}</span></td>"
                f"{extra_tds}"
                f"<td>{escape(str(row.get('trend_label', '')))}</td>"
                f"<td>{tags}</td>"
                f"<td>{escape(str(row.get('risk_note', '')))}</td>"
                "</tr>"
            )
        return "<div class='table-wrap'><table><thead><tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr></thead><tbody>" + "\n".join(rows) + "</tbody></table></div>"

    def _format_extra(self, value: object, col: str) -> str:
        number = float(value or 0)
        if col in {"prev_pct_change"}:
            return f"{number:.2f}%"
        if col in {"volume_ratio"}:
            return f"{number:.2f}"
        if col in self.MONEY_MILLION_COLUMNS:
            return f"{number / 100:,.2f}"
        return f"{number:,.0f}"

    def _html_screen_summary(self, stocks: pd.DataFrame) -> str:
        screens = {
            "主力連續買超股": "main_force_continuous_buy",
            "投信連續買超股": "trust_continuous_buy",
            "外資轉買股": "foreign_turn_buy",
            "放量突破股": "breakout",
            "創高股": "new_high_20d",
            "W 型態突破股": "w_breakout",
            "假突破轉弱股": "fake_breakout",
            "可放空弱勢股": "short_candidate",
            "有期貨的股票": "has_futures",
            "有權證的股票": "has_warrant",
        }
        items = []
        for label, col in screens.items():
            count = int(stocks[col].fillna(False).sum()) if col in stocks.columns else 0
            items.append(f"<li><span>{escape(label)}</span><strong>{count}</strong></li>")
        return '<ul class="summary-list">' + "\n".join(items) + "</ul>"

    def _html_errors(self, errors: list[str]) -> str:
        if not errors:
            return '<p class="lead">資料源正常。</p>'
        return '<ul class="warnings">' + "\n".join(f"<li>{escape(err)}</li>" for err in errors) + "</ul>"

    def _json_records(self, df: pd.DataFrame, cols: list[str]) -> str:
        if df.empty:
            return "[]"
        records = df[[c for c in cols if c in df.columns]].copy()
        return json.dumps(records.to_dict(orient="records"), ensure_ascii=False)

    def _html_script(self) -> str:
        return """
const container = document.getElementById('watchCards');
const search = document.getElementById('stockSearch');
const sectorFilter = document.getElementById('sectorFilter');
const categorySearch = document.getElementById('categorySearch');
const categoryTabs = document.getElementById('categoryTabs');
const categoryPane = document.getElementById('categoryPane');
const categoryMeta = document.getElementById('categoryMeta');
const sectors = [...new Set(watchStocks.map(s => s.sector).filter(Boolean))].sort();
const categoryNames = [...new Set(sectorStocks.map(s => s.sector).filter(Boolean))].sort();
let activeCategory = categoryNames[0] || '';
for (const sector of sectors) {
  const option = document.createElement('option');
  option.value = sector;
  option.textContent = sector;
  sectorFilter.appendChild(option);
}
function scoreClass(score) {
  if (score >= 70) return 'score-high';
  if (score <= 35) return 'score-low';
  return 'score-mid';
}
function pctClass(pct) {
  if (pct > 0) return 'positive';
  if (pct < 0) return 'negative';
  return 'neutral';
}
function renderCategoryTabs() {
  const q = categorySearch.value.trim().toLowerCase();
  const visibleNames = categoryNames.filter(name => {
    if (!q) return true;
    return sectorStocks.some(s => {
      const text = `${s.code || ''} ${s.name || ''} ${s.sector || ''}`.toLowerCase();
      return s.sector === name && text.includes(q);
    });
  });
  if (!visibleNames.includes(activeCategory)) {
    activeCategory = visibleNames[0] || '';
  }
  categoryMeta.textContent = `${visibleNames.length} 個分類｜${sectorStocks.length} 筆候選`;
  categoryTabs.innerHTML = visibleNames.map(name => {
    const count = sectorStocks.filter(s => s.sector === name).length;
    return `<button class="tab-button" type="button" role="tab" aria-selected="${name === activeCategory}" data-sector="${name}">${name}<span class="tab-count">${count}</span></button>`;
  }).join('');
  for (const button of categoryTabs.querySelectorAll('button')) {
    button.addEventListener('click', () => {
      activeCategory = button.dataset.sector;
      renderCategoryTabs();
      renderCategoryPane();
    });
  }
  renderCategoryPane();
}
function renderCategoryPane() {
  const q = categorySearch.value.trim().toLowerCase();
  const rows = sectorStocks.filter(s => {
    const text = `${s.code || ''} ${s.name || ''} ${s.sector || ''}`.toLowerCase();
    return s.sector === activeCategory && (!q || text.includes(q));
  });
  if (!activeCategory || rows.length === 0) {
    categoryPane.innerHTML = '<p class="lead">沒有符合搜尋條件的分類資料。</p>';
    return;
  }
  categoryPane.innerHTML = `
    <div class="category-head">
      <h3>${activeCategory}</h3>
      <span>${rows.length} 檔｜依分數排序</span>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>代號</th><th>名稱</th><th>收盤</th><th>漲跌幅</th><th>成交量</th><th>分數</th><th>趨勢</th><th>籌碼</th><th>風險</th></tr></thead>
        <tbody>
          ${rows.map(s => `
            <tr>
              <td><span class="code">${s.code || ''}</span></td>
              <td>${s.name || ''}</td>
              <td>${Number(s.close || 0).toFixed(2)}</td>
              <td class="${pctClass(Number(s.pct_change || 0))}">${Number(s.pct_change || 0).toFixed(2)}%</td>
              <td>${Number(s.volume || 0).toLocaleString()}</td>
              <td><span class="score-pill ${scoreClass(Number(s.score || 0))}">${Number(s.score || 0).toFixed(1)}</span></td>
              <td>${s.trend_label || ''}</td>
              <td>${s.chip_note || ''}</td>
              <td>${s.risk_note || ''}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}
function render() {
  const q = search.value.trim().toLowerCase();
  const sector = sectorFilter.value;
  const filtered = watchStocks.filter(s => {
    const text = `${s.code || ''} ${s.name || ''} ${s.sector || ''}`.toLowerCase();
    return (!q || text.includes(q)) && (!sector || s.sector === sector);
  });
  container.innerHTML = filtered.map(s => `
    <article class="watch-card">
      <header>
        <div>
          <h3><span class="code">${s.code}</span> ${s.name}</h3>
          <p>${s.sector || '其他'}｜成交量 ${Number(s.volume || 0).toLocaleString()} 張｜${s.reason || '觀察'}</p>
        </div>
        <span class="score-pill ${scoreClass(Number(s.score || 0))}">${Number(s.score || 0).toFixed(1)}</span>
      </header>
      <p class="risk-text">${s.risk_note || '依籌碼與量價變化追蹤'}</p>
    </article>
  `).join('') || '<p class="lead">沒有符合搜尋條件的股票。</p>';
}
search.addEventListener('input', render);
sectorFilter.addEventListener('change', render);
categorySearch.addEventListener('input', renderCategoryTabs);
renderCategoryTabs();
render();
"""

    def _score_state(self, score: float) -> str:
        if score >= 60:
            return "positive"
        if score <= 45:
            return "negative"
        return "neutral"

    def _ratio_state(self, ratio: float) -> str:
        if ratio >= 55:
            return "positive"
        if ratio <= 45:
            return "negative"
        return "neutral"

    def _score_class(self, score: float) -> str:
        if score >= 70:
            return "score-high"
        if score <= 35:
            return "score-low"
        return "score-mid"

    def _pct_class(self, pct: float) -> str:
        if pct > 0:
            return "positive"
        if pct < 0:
            return "negative"
        return "neutral"
