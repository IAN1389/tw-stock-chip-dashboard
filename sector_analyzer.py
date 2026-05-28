from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parent
INDUSTRY_CACHE = ROOT / "data" / "processed" / "stock_industries.csv"

COMMON_THEME_BY_CODE = {
    # AI server / cloud hardware
    "2317": "EMS/組裝",
    "2324": "品牌/組裝",
    "2356": "伺服器/AI",
    "2382": "伺服器/AI",
    "3231": "伺服器/AI",
    "6669": "伺服器/AI",
    "3706": "伺服器/AI",
    "2301": "品牌/組裝",
    "2308": "電源/散熱",
    "3017": "伺服器/AI",
    "3324": "電源/散熱",
    "2421": "電源/散熱",
    "3653": "電源/散熱",
    "3338": "電源/散熱",
    "8996": "電源/散熱",
    # PCB / CCL / connectors / passives
    "2313": "PCB/載板",
    "2368": "PCB/載板",
    "2383": "PCB/載板",
    "3037": "PCB/載板",
    "3044": "PCB/載板",
    "3189": "PCB/載板",
    "3321": "PCB/載板",
    "4958": "PCB/載板",
    "5469": "PCB/載板",
    "6153": "PCB/載板",
    "6191": "PCB/載板",
    "6269": "PCB/載板",
    "6274": "PCB/載板",
    "8046": "PCB/載板",
    "8358": "PCB/載板",
    "6213": "PCB/載板",
    "3311": "連接器",
    "6761": "連接器",
    "3533": "連接器",
    "3003": "連接器",
    "6279": "連接器",
    "3665": "連接器",
    "3605": "連接器",
    "6290": "連接器",
    "3021": "連接器",
    "6821": "連接器",
    "6913": "連接器",
    "2327": "被動元件",
    "2492": "被動元件",
    "3042": "被動元件",
    "3026": "被動元件",
    "6173": "被動元件",
    "6207": "被動元件",
    "6449": "被動元件",
    # Semiconductors
    "2330": "晶圓代工",
    "2303": "晶圓代工",
    "6770": "晶圓代工",
    "5347": "晶圓代工",
    "2344": "記憶體",
    "2408": "記憶體",
    "2337": "記憶體",
    "3006": "記憶體",
    "3260": "記憶體",
    "6531": "記憶體",
    "8299": "Flash/儲存IC",
    "2454": "IC設計",
    "3034": "IC設計",
    "2379": "IC設計",
    "3443": "矽智財",
    "5274": "IC設計",
    "6415": "IC設計",
    "4966": "IC設計",
    "4919": "IC設計",
    "3529": "IC設計",
    "3661": "矽智財",
    "6485": "IC設計",
    "3035": "IC設計",
    "3711": "封測",
    "2329": "封測",
    "2449": "封測",
    "6239": "封測",
    "6147": "封測",
    "8150": "封測",
    "2369": "封測",
    "8110": "封測",
    "6548": "封測",
    "3105": "化合物半導體",
    "4991": "化合物半導體",
    "6488": "矽晶圓",
    "6182": "矽晶圓",
    "2481": "功率半導體",
    "6415": "功率半導體",
    "8261": "功率半導體",
    "3131": "檢測/設備服務",
    "3583": "半導體設備",
    "6187": "半導體設備",
    "5443": "半導體設備",
    "6640": "半導體設備",
    "2467": "半導體設備",
    "6196": "半導體設備",
    "3680": "半導體設備",
    "3413": "半導體設備",
    "3402": "半導體設備",
    "2404": "EMS/組裝",
    "6706": "半導體設備",
    "4770": "半導體-其他",
    "4763": "半導體-其他",
    "8028": "半導體-其他",
    # Optical communication / CPO
    "3163": "聲學/RF",
    "3363": "光通訊",
    "4979": "光通訊",
    "3081": "光通訊",
    "4908": "通信網路-其他",
    "6442": "通信網路-其他",
    "3450": "光通訊",
    "3234": "光通訊",
    "2345": "網通設備",
    # Robotics / automation / power grid
    "2049": "機器人/自動化",
    "1590": "機器人/自動化",
    "2359": "機器人/自動化",
    "2464": "機器人/自動化",
    "6125": "機器人/自動化",
    "1504": "重電",
    "1503": "重電",
    "1513": "重電",
    "1514": "重電",
    "1519": "重電",
    "1609": "重電",
    "1618": "重電",
    # Auto / aerospace / defense
    "2201": "汽車",
    "2207": "汽車",
    "2227": "汽車",
    "1536": "車用零組件",
    "1568": "車用零組件",
    "2231": "車用零組件",
    "2233": "車用零組件",
    "3552": "車用零組件",
    "2634": "軍工航太",
    "8033": "軍工航太",
    "8222": "軍工航太",
    "4572": "軍工航太",
    "6753": "軍工航太",
    "2645": "軍工航太",
    "3004": "軍工航太",
    # Finance / transport / tourism leaders
    "2603": "航運",
    "2605": "航運",
    "2606": "航運",
    "2609": "航運",
    "2610": "航運",
    "2615": "航運",
    "2617": "航運",
    "2618": "航運",
    "2637": "航運",
    "2646": "航運",
    "2707": "觀光餐飲",
    "2723": "觀光餐飲",
    "2727": "觀光餐飲",
    "2731": "觀光餐飲",
    "2748": "觀光餐飲",
    "2753": "觀光餐飲",
    "5706": "觀光餐飲",
}

OFFICIAL_TO_COMMON = {
    "半導體業": "半導體-其他",
    "電腦及週邊設備業": "電腦週邊-其他",
    "光電業": "光電-其他",
    "通信網路業": "通信網路-其他",
    "電子零組件業": "電子零組件-其他",
    "電子通路業": "電子通路",
    "資訊服務業": "軟體服務",
    "其他電子業": "其他電子",
    "數位雲端": "雲端服務",
    "金融保險業": "金控/銀行",
    "航運業": "航運",
    "鋼鐵工業": "鋼鐵",
    "塑膠工業": "塑膠",
    "化學工業": "化工材料",
    "油電燃氣業": "油電燃氣",
    "橡膠工業": "橡膠",
    "水泥工業": "水泥",
    "玻璃陶瓷": "玻璃陶瓷",
    "造紙工業": "造紙",
    "紡織纖維": "紡織纖維",
    "食品工業": "食品",
    "貿易百貨": "百貨通路",
    "觀光餐旅": "觀光餐飲",
    "運動休閒": "運動休閒",
    "居家生活": "居家生活",
    "生技醫療業": "生技醫療-其他",
    "電機機械": "工具機/機械",
    "電器電纜": "電線電纜",
    "汽車工業": "汽車",
    "建材營造": "營建資產",
    "綠能環保": "綠能環保",
    "文化創意業": "文創遊戲",
    "農業科技業": "農業科技",
    "存託憑證": "DR存託憑證",
    "其他": "其他",
}

INDUSTRY_GROUPS = {
    "伺服器/AI": "AI概念",
    "電源/散熱": "AI概念",
    "品牌/組裝": "電子科技",
    "EMS/組裝": "電子科技",
    "工業電腦": "電子科技",
    "PCB/載板": "電子零組件",
    "連接器": "電子零組件",
    "被動元件": "電子零組件",
    "晶圓代工": "半導體",
    "記憶體": "半導體",
    "記憶體模組": "半導體",
    "Flash/儲存IC": "半導體",
    "IC設計": "半導體",
    "矽智財": "半導體",
    "驅動IC": "半導體",
    "CIS/感測": "半導體",
    "封測": "半導體",
    "半導體設備": "半導體",
    "檢測/設備服務": "半導體",
    "化合物半導體": "半導體",
    "矽晶圓": "半導體",
    "功率半導體": "半導體",
    "半導體-其他": "半導體",
    "光通訊": "通信網路",
    "通信網路-其他": "通信網路",
    "網通設備": "通信網路",
    "聲學/RF": "電子科技",
    "機器人/自動化": "機器人",
    "重電": "電力能源",
    "車用零組件": "汽車",
    "軍工航太": "軍工航太",
    "金控/銀行": "金融",
    "電信": "電信",
    "航運": "傳產循環",
    "觀光餐飲": "民生消費",
    "電腦週邊-其他": "電子科技",
    "光電-其他": "光電",
    "面板/顯示": "光電",
    "LED/照明": "光電",
    "太陽能": "綠能環保",
    "電子零組件-其他": "電子零組件",
    "電子通路": "電子科技",
    "軟體服務": "電子科技",
    "其他電子": "電子科技",
    "雲端服務": "電子科技",
    "鋼鐵": "傳產循環",
    "塑膠": "傳產循環",
    "化工材料": "傳產循環",
    "油電燃氣": "傳產循環",
    "橡膠": "傳產循環",
    "水泥": "傳產循環",
    "玻璃陶瓷": "傳產循環",
    "造紙": "傳產循環",
    "紡織纖維": "民生消費",
    "食品": "民生消費",
    "百貨通路": "民生消費",
    "生技醫療-其他": "生技醫療",
    "工具機/機械": "機電設備",
    "電機機械-其他": "機電設備",
    "電線電纜": "機電設備",
    "汽車": "汽車",
    "營建資產": "資產營建",
    "綠能環保": "綠能環保",
    "文創遊戲": "文化內容",
    "農業科技": "其他",
    "DR存託憑證": "其他",
    "半導體業": "半導體",
    "電腦及週邊設備業": "電子科技",
    "光電業": "光電",
    "通信網路業": "通信網路",
    "電子零組件業": "電子零組件",
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
    common = _common_sector_for(row)
    if common:
        return common
    industry = str(row.get("industry_category") or "").strip()
    if industry in {"電子工業", "其他", "創新板股票", "化學生技醫療"}:
        return _fallback_sector(row, industry)
    if industry and industry.lower() != "nan":
        return OFFICIAL_TO_COMMON.get(industry, industry)
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
        return "金控/銀行"
    if original == "化學生技醫療" and code.startswith(("41", "64", "65", "66", "67")):
        return "生技醫療-其他"
    if original == "化學生技醫療":
        return "化工材料"
    if code.startswith(("23", "24", "30", "31", "32", "33", "34", "35", "36", "49", "52", "61", "62", "64", "65", "66", "67", "80", "81", "82")):
        if any(token in name for token in ("封", "測", "頎邦", "南茂", "京元", "力成", "長科")):
            return "封測"
        if any(token in name for token in ("晶", "矽", "半", "積", "創", "芯", "聯電", "華邦", "南亞科", "旺宏", "力積")):
            return "半導體-其他"
        if any(token in name for token in ("面板", "彩晶", "友達", "群創")):
            return "面板/顯示"
        if any(token in name for token in ("光", "LED", "鏡")):
            return "光電-其他"
        if any(token in name for token in ("網", "訊", "通", "電信")):
            return "通信網路-其他"
        if any(token in name for token in ("電腦", "仁寶", "英業達", "廣達", "緯創", "華碩", "宏碁")):
            return "電腦週邊-其他"
        return "電子零組件-其他"
    if code.startswith("20"):
        return "鋼鐵"
    if code.startswith("15"):
        return "電機機械-其他"
    if code.startswith("16"):
        return "電線電纜"
    if code.startswith("17"):
        return "化工材料"
    if code.startswith("18"):
        return "玻璃陶瓷"
    if code.startswith("13"):
        return "塑膠"
    if code.startswith("14"):
        return "紡織纖維"
    if code.startswith("12"):
        return "食品"
    if code.startswith("25"):
        return "營建資產"
    if code.startswith("26"):
        return "航運"
    if code.startswith("27"):
        return "觀光餐飲"
    if code.startswith("41"):
        return "生技醫療-其他"
    if code.startswith("47"):
        return "綠能環保"
    return "其他"


def _common_sector_for(row: pd.Series) -> str:
    code = str(row.get("code") or "")
    name = str(row.get("name") or "")
    if code in COMMON_THEME_BY_CODE:
        return COMMON_THEME_BY_CODE[code]
    if code.startswith("28"):
        return "金控/銀行"
    if any(token in name for token in ("航太", "無人機", "雷虎", "漢翔")):
        return "軍工航太"
    if any(token in name for token in ("機器人", "自動化")):
        return "機器人/自動化"
    if any(token in name for token in ("電纜", "華城", "亞力", "士電", "中興電")):
        return "重電"
    return ""
