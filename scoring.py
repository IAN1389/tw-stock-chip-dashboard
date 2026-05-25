from __future__ import annotations

import pandas as pd


def score_stocks(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["price_trend_score"] = out.apply(price_trend_score, axis=1)
    out["volume_score"] = out.apply(volume_score, axis=1)
    out["institutional_score"] = out.apply(institutional_score, axis=1)
    out["main_force_score"] = out.apply(main_force_score, axis=1)
    if "sector_strength" not in out.columns:
        out["sector_strength"] = 50.0
    out["sector_score"] = out["sector_strength"].clip(0, 100)
    out["score"] = (
        out["price_trend_score"] * 0.25
        + out["volume_score"] * 0.20
        + out["institutional_score"] * 0.25
        + out["main_force_score"] * 0.15
        + out["sector_score"] * 0.15
    ).round(1)
    out["direction"] = out["score"].apply(lambda x: "偏多" if x >= 70 else "偏空" if x <= 35 else "觀察")
    out["entry_price"] = out.apply(entry_price, axis=1)
    out["stop_loss"] = out.apply(stop_loss, axis=1)
    out["take_profit"] = out.apply(take_profit, axis=1)
    out["risk_note"] = out.apply(risk_note, axis=1)
    return out


def price_trend_score(row: pd.Series) -> float:
    score = 45.0
    if row.get("close", 0) > row.get("ma5", 0) > row.get("ma20", 0):
        score += 30
    elif row.get("close", 0) > row.get("ma20", 0):
        score += 15
    elif row.get("close", 0) < row.get("ma5", 0) < row.get("ma20", 0):
        score -= 25
    if bool(row.get("new_high_20d", False)):
        score += 15
    if bool(row.get("fake_breakout", False)):
        score -= 25
    return clamp(score)


def volume_score(row: pd.Series) -> float:
    ratio = row.get("volume_ratio", 0)
    if ratio >= 2.0 and row.get("pct_change", 0) > 0:
        return 90
    if ratio >= 1.5 and row.get("pct_change", 0) > 0:
        return 78
    if ratio >= 1.2:
        return 62
    if ratio and ratio < 0.7:
        return 38
    return 50


def institutional_score(row: pd.Series) -> float:
    volume = row.get("volume", 0) or 1
    inst_ratio = row.get("inst_buy_lots", 0) / volume
    trust_ratio = row.get("trust_buy_lots", 0) / volume
    foreign_ratio = row.get("foreign_buy_lots", 0) / volume
    score = 50 + inst_ratio * 180 + trust_ratio * 150 + foreign_ratio * 80
    if row.get("trust_buy_lots", 0) > 1000:
        score += 10
    if row.get("foreign_buy_lots", 0) < -1000:
        score -= 10
    return clamp(score)


def main_force_score(row: pd.Series) -> float:
    ratio = row.get("main_force_ratio", 0)
    score = 50 + ratio * 240
    if row.get("borrow_sell_lots", 0) > 1000:
        score -= 10
    if row.get("margin_change_lots", 0) > 1500 and row.get("pct_change", 0) > 0:
        score -= 8
    return clamp(score)


def entry_price(row: pd.Series) -> float:
    close = row.get("close", 0.0)
    if row.get("direction") == "偏多":
        return round(close, 2)
    if row.get("direction") == "偏空":
        return round(close * 0.995, 2)
    return round(close, 2)


def stop_loss(row: pd.Series) -> float:
    close = row.get("close", 0.0)
    low = row.get("low", 0.0) or close * 0.94
    ma20 = row.get("ma20", 0.0)
    if row.get("direction") == "偏空":
        return round(max(row.get("high", close) * 1.02, close * 1.04), 2)
    base = max(low * 0.99, ma20 * 0.985 if ma20 else close * 0.93)
    return round(min(base, close * 0.97), 2)


def take_profit(row: pd.Series) -> str:
    close = row.get("close", 0.0)
    if row.get("direction") == "偏空":
        return f"{close * 0.92:.2f} ~ {close * 0.88:.2f}"
    return f"{close * 1.06:.2f} ~ {close * 1.12:.2f}"


def risk_note(row: pd.Series) -> str:
    risks = []
    if row.get("volume_ratio", 0) >= 2.5:
        risks.append("爆量後隔日不可追高")
    if row.get("margin_change_lots", 0) > 1000:
        risks.append("融資同步增加")
    if row.get("foreign_buy_lots", 0) < 0 < row.get("trust_buy_lots", 0):
        risks.append("外資與投信不同步")
    if row.get("fake_breakout", False):
        risks.append("假突破轉弱")
    return "；".join(risks) if risks else "籌碼與量價暫無明顯警訊"


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))
