from __future__ import annotations

import pandas as pd


def add_indicators(prices: pd.DataFrame, history: pd.DataFrame) -> pd.DataFrame:
    if prices.empty:
        return prices
    df = prices.copy()
    defaults = {
        "prev_close": 0.0,
        "prev_pct_change": 0.0,
        "prev_ma5": 0.0,
        "prev_ma20": 0.0,
        "turnover_million": 0.0,
        "ma5": 0.0,
        "ma20": 0.0,
        "vol_ma20": 0.0,
        "volume_ratio": 0.0,
        "high_20d": 0.0,
        "low_20d": 0.0,
        "new_high_20d": False,
        "trend_label": "資料不足",
        "breakout": False,
        "fake_breakout": False,
        "w_breakout": False,
        "short_candidate": False,
    }
    if history.empty:
        for key, value in defaults.items():
            df[key] = value
        return df

    hist = history.copy()
    hist["date"] = pd.to_datetime(hist["date"])
    hist = hist.sort_values(["code", "date"])
    grouped = hist.groupby("code", group_keys=False)
    hist["ma5"] = grouped["close"].transform(lambda x: x.rolling(5, min_periods=3).mean())
    hist["ma20"] = grouped["close"].transform(lambda x: x.rolling(20, min_periods=10).mean())
    hist["vol_ma20"] = grouped["volume"].transform(lambda x: x.rolling(20, min_periods=10).mean())
    hist["high_20d"] = grouped["high"].transform(lambda x: x.rolling(20, min_periods=10).max())
    hist["low_20d"] = grouped["low"].transform(lambda x: x.rolling(20, min_periods=10).min())
    hist["prev_close"] = grouped["close"].shift(1)
    hist["prev_pct_change"] = grouped["pct_change"].shift(1)
    hist["prev_ma5"] = grouped["ma5"].shift(1)
    hist["prev_ma20"] = grouped["ma20"].shift(1)
    latest = hist.sort_values("date").groupby("code").tail(1)
    cols = ["code", "ma5", "ma20", "vol_ma20", "high_20d", "low_20d", "prev_close", "prev_pct_change", "prev_ma5", "prev_ma20"]
    df = df.merge(latest[cols], on="code", how="left")
    for col in cols[1:]:
        df[col] = df[col].fillna(0.0)

    df["turnover_million"] = df["close"] * df["volume"] * 1000 / 1_000_000
    df["volume_ratio"] = df.apply(lambda r: r["volume"] / r["vol_ma20"] if r["vol_ma20"] else 0.0, axis=1)
    df["new_high_20d"] = (df["high_20d"] > 0) & (df["close"] >= df["high_20d"] * 0.995)
    df["breakout"] = (df["close"] > df["ma20"]) & (df["volume_ratio"] >= 1.5) & (df["pct_change"] > 1)
    df["fake_breakout"] = (df["high"] >= df["high_20d"] * 0.995) & (df["close"] < df["ma5"]) & (df["pct_change"] < 0)
    df["w_breakout"] = df.apply(_w_breakout, axis=1)
    df["short_candidate"] = (df["close"] < df["ma20"]) & (df["pct_change"] < -1.5) & (df["volume_ratio"] >= 1.2)
    df["prev_strong"] = (df["prev_close"] > df["prev_ma5"]) & (df["prev_ma5"] > df["prev_ma20"]) & (df["prev_pct_change"] > 0)
    df["continued_strength"] = df["prev_strong"] & (df["pct_change"] > 0) & (df["close"] >= df["ma5"])
    df["active_flow_million"] = df.apply(_active_flow_million, axis=1)
    df["bottom_support"] = df.apply(_bottom_support, axis=1)
    df["up_on_contracting_volume"] = (df["pct_change"] > 0) & (df["volume_ratio"] > 0) & (df["volume_ratio"] < 0.8) & (df["close"] >= df["prev_close"])
    df["trend_label"] = df.apply(_trend_label, axis=1)
    return df


def _trend_label(row: pd.Series) -> str:
    if not row.get("ma20"):
        return "資料不足"
    if row["close"] > row["ma5"] > row["ma20"]:
        return "多頭趨勢"
    if row["close"] < row["ma5"] < row["ma20"]:
        return "空頭趨勢"
    if row["close"] > row["ma20"]:
        return "偏多整理"
    return "偏弱整理"


def _w_breakout(row: pd.Series) -> bool:
    if not row.get("low_20d") or not row.get("high_20d"):
        return False
    range_size = row["high_20d"] - row["low_20d"]
    if range_size <= 0:
        return False
    return bool(row["close"] > row["low_20d"] + range_size * 0.65 and row["volume_ratio"] >= 1.3 and row["pct_change"] > 1)


def _active_flow_million(row: pd.Series) -> float:
    turnover = float(row.get("turnover_million", 0.0) or 0.0)
    pct = float(row.get("pct_change", 0.0) or 0.0)
    volume_ratio = min(float(row.get("volume_ratio", 0.0) or 0.0), 3.0)
    return turnover * (pct / 100.0) * max(volume_ratio, 0.5)


def _bottom_support(row: pd.Series) -> bool:
    if not row.get("low_20d") or not row.get("ma20"):
        return False
    near_support = row["low"] <= row["low_20d"] * 1.05
    reclaimed = row["close"] > row["open"] and row["pct_change"] > 0
    chip_support = row.get("main_force_lots", 0) > 0 or row.get("inst_buy_lots", 0) > 0
    return bool(near_support and reclaimed and chip_support and row.get("volume_ratio", 0) >= 0.8)
