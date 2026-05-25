from __future__ import annotations

import pandas as pd


def merge_chip_data(
    prices: pd.DataFrame,
    institutional: pd.DataFrame,
    margin: pd.DataFrame,
    borrow: pd.DataFrame,
) -> pd.DataFrame:
    df = prices.copy()
    for extra in (institutional, margin, borrow):
        if not extra.empty and "code" in extra.columns:
            keep = [c for c in extra.columns if c not in {"name"}]
            df = df.merge(extra[keep], on=["market", "code"], how="left") if "market" in extra.columns else df.merge(extra[keep], on="code", how="left")
    numeric_cols = [
        "foreign_buy_lots",
        "trust_buy_lots",
        "dealer_buy_lots",
        "inst_buy_lots",
        "margin_balance_lots",
        "short_balance_lots",
        "margin_change_lots",
        "short_change_lots",
        "borrow_sell_lots",
    ]
    for col in numeric_cols:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = df[col].fillna(0.0)

    df["main_force_lots"] = df["inst_buy_lots"] + df["short_change_lots"] * 0.3 - df["margin_change_lots"] * 0.2
    df["main_force_ratio"] = df.apply(lambda r: r["main_force_lots"] / r["volume"] if r["volume"] else 0.0, axis=1)
    df["inst_flow_million"] = df["inst_buy_lots"] * df["close"] * 1000 / 1_000_000
    if "active_flow_million" not in df.columns:
        df["active_flow_million"] = 0.0
    df["active_flow_million"] = df["active_flow_million"] + df["inst_flow_million"] * 0.35
    df["foreign_turn_buy"] = df["foreign_buy_lots"] > 0
    df["trust_buy"] = df["trust_buy_lots"] > 0
    df["main_force_buy"] = df["main_force_lots"] > 0
    df["bottom_support"] = df.apply(_bottom_support, axis=1)
    df["chip_note"] = df.apply(_chip_note, axis=1)
    return df


def add_continuity_flags(df: pd.DataFrame, institutional_history: pd.DataFrame | None = None) -> pd.DataFrame:
    out = df.copy()
    # Hook for multi-day institutional history. Current official daily fetch keeps a single day,
    # so first generation treats positive net buy as day-1 continuation candidate.
    out["main_force_continuous_buy"] = out["main_force_buy"] & (out["main_force_ratio"] > 0.02)
    out["trust_continuous_buy"] = out["trust_buy"] & (out["trust_buy_lots"] >= 500)
    out["foreign_turn_buy"] = out["foreign_buy_lots"] >= 1000
    return out


def _chip_note(row: pd.Series) -> str:
    notes = []
    if row["inst_buy_lots"] > 1000:
        notes.append("法人偏多")
    if row["trust_buy_lots"] > 500:
        notes.append("投信加碼")
    if row["foreign_buy_lots"] < -1000:
        notes.append("外資提款")
    if row["margin_change_lots"] > 1000:
        notes.append("融資偏熱")
    if row["borrow_sell_lots"] > 1000:
        notes.append("借券賣壓")
    return "、".join(notes) if notes else "籌碼中性"


def _bottom_support(row: pd.Series) -> bool:
    if not row.get("low_20d") or not row.get("ma20"):
        return False
    near_support = row["low"] <= row["low_20d"] * 1.05 or row["close"] < row["ma20"]
    reclaimed = row["close"] > row["open"] and row["pct_change"] > 0
    chip_support = row.get("main_force_lots", 0) > 0 or row.get("inst_buy_lots", 0) > 0
    not_overheated = row.get("volume_ratio", 0) <= 1.6
    return bool(near_support and reclaimed and chip_support and not_overheated)
