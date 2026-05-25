from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parent
INDUSTRY_CACHE = ROOT / "data" / "processed" / "stock_industries.csv"

INDUSTRY_GROUPS = {
    "半導體業": "電子科技",
    "電腦及週邊設備業": "電子科技",
    "光電業": "電子科技",
    "通信網路業": "電子科技",
    "電子零組件業": "電子科技",
    "電子通路業": "電子科技",
    "資訊服務業": "電子科技",
    "電子工業": "電子科技",
    "其他電子類": "電子科技",
    "數位雲端類": "電子科技",
    "其他電子業": "電子科技",
    "數位雲端": "電子科技",
    "金融保險業": "金融",
    "金融保險": "金融",
    "金融業": "金融",
    "航運業": "傳產循環",
    "鋼鐵工業": "傳產循環",
    "塑膠工業": "傳產循環",
    "化學工業": "傳產循環",
    "油電燃氣業": "傳產循環",
    "橡膠工業": "傳產循環",
    "水泥工業": "傳產循環",
    "玻璃陶瓷": "傳產循環",
    "造紙工業": "傳產循環",
    "紡織纖維": "民生消費",
    "食品工業": "民生消費",
    "貿易百貨": "民生消費",
    "觀光餐旅": "民生消費",
    "運動休閒": "民生消費",
    "居家生活": "民生消費",
    "居家生活類": "民生消費",
    "生技醫療業": "生技醫療",
    "化學生技醫療": "生技醫療",
    "電機機械": "機電設備",
    "電器電纜": "機電設備",
    "汽車工業": "機電設備",
    "建材營造": "資產營建",
    "綠能環保": "綠能環保",
    "綠能環保類": "綠能環保",
    "文化創意業": "文化內容",
    "農業科技業": "其他",
    "運動休閒類": "民生消費",
    "創新板股票": "其他",
    "存託憑證": "其他",
    "其他": "其他",
}


def attach_sector(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    industry = _load_industry_info()
    if not industry.empty:
        out = out.merge(industry, on="code", how="left", suffixes=("", "_industry"))
    else:
        out["industry_category"] = ""
        out["industry_group"] = ""
        out["industry_source"] = ""

    out["sector"] = out.apply(_sector_for, axis=1)
    out["industry_group"] = out.apply(_industry_group_for, axis=1)
    out["industry_source"] = out["industry_source"].fillna("").replace("", "name/code fallback")
    return out


def rank_sectors(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "sector" not in df.columns:
        return pd.DataFrame()
    grouped = df.groupby(["sector", "industry_group"], dropna=False).agg(
        avg_score=("score", "mean"),
        avg_pct_change=("pct_change", "mean"),
        total_inst_lots=("inst_buy_lots", "sum"),
        total_foreign_lots=("foreign_buy_lots", "sum"),
        total_trust_lots=("trust_buy_lots", "sum"),
        total_dealer_lots=("dealer_buy_lots", "sum"),
        total_margin_change=("margin_change_lots", "sum"),
        total_volume=("volume", "sum"),
        strong_count=("score", lambda x: int((x >= 70).sum())),
        weak_count=("score", lambda x: int((x <= 35).sum())),
        stock_count=("code", "count"),
    )
    grouped["sector_strength"] = (
        grouped["avg_score"] * 0.45
        + grouped["avg_pct_change"].clip(-5, 5) * 5
        + grouped["strong_count"] / grouped["stock_count"].clip(lower=1) * 30
        - grouped["weak_count"] / grouped["stock_count"].clip(lower=1) * 12
    )
    return grouped.reset_index().sort_values("sector_strength", ascending=False)


def apply_sector_strength(df: pd.DataFrame, sectors: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if sectors.empty:
        out["sector_strength"] = 50.0
        return out
    sector_strength = (
        sectors.sort_values("sector_strength", ascending=False)
        .drop_duplicates("sector", keep="first")[["sector", "sector_strength"]]
    )
    out = out.merge(sector_strength, on="sector", how="left")
    out["sector_strength"] = out["sector_strength"].fillna(50.0)
    return out


def _load_industry_info() -> pd.DataFrame:
    cached = _read_industry_cache()
    if not cached.empty:
        return cached

    url = "https://api.finmindtrade.com/api/v4/data"
    try:
        response = requests.get(url, params={"dataset": "TaiwanStockInfo"}, timeout=25)
        response.raise_for_status()
        payload = response.json()
        records = payload.get("data", [])
        df = pd.DataFrame(records)
    except Exception:
        return pd.DataFrame(columns=["code", "industry_category", "industry_group", "industry_source"])

    if df.empty or "stock_id" not in df.columns:
        return pd.DataFrame(columns=["code", "industry_category", "industry_group", "industry_source"])

    df = df.rename(columns={"stock_id": "code", "stock_name": "industry_name"})
    df["code"] = df["code"].astype(str).str.strip()
    df = df[df["code"].str.fullmatch(r"[1-9]\d{3}", na=False)].copy()
    df["industry_category"] = df["industry_category"].fillna("").astype(str).str.strip()
    df["industry_category"] = df["industry_category"].map(_normalize_industry_name)
    df["industry_group"] = df["industry_category"].map(lambda x: INDUSTRY_GROUPS.get(x, "其他"))
    df["industry_source"] = "FinMind TaiwanStockInfo"
    out = df[["code", "industry_category", "industry_group", "industry_source"]].drop_duplicates("code", keep="last")
    INDUSTRY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(INDUSTRY_CACHE, index=False, encoding="utf-8-sig")
    return out


def _read_industry_cache() -> pd.DataFrame:
    if not INDUSTRY_CACHE.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(INDUSTRY_CACHE, dtype={"code": str})
    except Exception:
        return pd.DataFrame()
    required = {"code", "industry_category", "industry_group", "industry_source"}
    if df.empty or not required.issubset(df.columns):
        return pd.DataFrame()
    out = df[["code", "industry_category", "industry_group", "industry_source"]].copy()
    out["industry_category"] = out["industry_category"].fillna("").astype(str).map(_normalize_industry_name)
    out["industry_group"] = out["industry_category"].map(lambda x: INDUSTRY_GROUPS.get(x, "其他"))
    return out.drop_duplicates("code", keep="last")


def _normalize_industry_name(value: object) -> str:
    name = str(value or "").strip()
    aliases = {
        "金融保險": "金融保險業",
        "金融業": "金融保險業",
        "其他電子類": "其他電子業",
        "數位雲端類": "數位雲端",
        "綠能環保類": "綠能環保",
        "居家生活類": "居家生活",
        "運動休閒類": "運動休閒",
    }
    return aliases.get(name, name)


def _sector_for(row: pd.Series) -> str:
    industry = str(row.get("industry_category") or "").strip()
    if industry in {"電子工業", "其他", "創新板股票", "化學生技醫療"}:
        return _fallback_sector(row, industry)
    if industry and industry.lower() != "nan":
        return industry
    return _fallback_sector(row, industry)


def _industry_group_for(row: pd.Series) -> str:
    sector = str(row.get("sector") or "").strip()
    if sector in INDUSTRY_GROUPS:
        return INDUSTRY_GROUPS[sector]
    group = str(row.get("industry_group") or "").strip()
    if group and group.lower() != "nan":
        return group
    return INDUSTRY_GROUPS.get(sector, "其他")


def _fallback_sector(row: pd.Series, original: str = "") -> str:
    code = str(row.get("code") or "")
    name = str(row.get("name") or "")
    if code.startswith("28"):
        return "金融保險業"
    if original == "化學生技醫療" and code.startswith(("41", "64", "65", "66", "67")):
        return "生技醫療業"
    if original == "化學生技醫療":
        return "化學工業"
    if code.startswith(("23", "24", "30", "31", "32", "33", "34", "35", "36", "49", "52", "61", "62", "64", "65", "66", "67", "80", "81", "82")):
        if any(token in name for token in ("晶", "矽", "半", "積", "創", "芯", "封", "測", "聯電", "華邦", "南亞科", "旺宏", "力積")):
            return "半導體業"
        if any(token in name for token in ("光", "面板", "LED", "鏡", "彩晶", "友達", "群創")):
            return "光電業"
        if any(token in name for token in ("網", "訊", "通", "電信")):
            return "通信網路業"
        if any(token in name for token in ("電腦", "仁寶", "英業達", "廣達", "緯創", "華碩", "宏碁")):
            return "電腦及週邊設備業"
        return "電子零組件業"
    if code.startswith("20"):
        return "鋼鐵工業"
    if code.startswith("15"):
        return "電機機械"
    if code.startswith("16"):
        return "電器電纜"
    if code.startswith("17"):
        return "化學工業"
    if code.startswith("18"):
        return "玻璃陶瓷"
    if code.startswith("13"):
        return "塑膠工業"
    if code.startswith("14"):
        return "紡織纖維"
    if code.startswith("12"):
        return "食品工業"
    if code.startswith("25"):
        return "建材營造"
    if code.startswith("26"):
        return "航運業"
    if code.startswith("27"):
        return "觀光餐旅"
    if code.startswith("41"):
        return "生技醫療業"
    if code.startswith("47"):
        return "綠能環保"
    return "其他"
