"""Feature engineering for monthly profitability forecasting.

Лаги по месяцам: ``lag_1`` — предыдущий месяц, ``lag_7`` — семь месяцев назад,
``lag_12`` — год назад (дублирует смысл ``profitability_yago_12``, но явно в признаках GBDT).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 3:
        return pd.DataFrame()
    target = "profitability"
    df = df.copy()
    for lag in (1, 2, 3, 7, 12):
        df[f"lag_{lag}"] = df[target].shift(lag)
    for w in (3, 6, 12):
        df[f"rolling_{w}"] = df[target].rolling(w, min_periods=1).mean()
        df[f"rolling_std_{w}"] = df[target].rolling(w, min_periods=1).std().fillna(0)
        df[f"rolling_rev_{w}"] = df["revenue"].rolling(w, min_periods=1).mean()
        df[f"rolling_cost_{w}"] = df["costs"].rolling(w, min_periods=1).mean()

    def _trend(x):
        if len(x) < 2:
            return 0.0
        try:
            return float(np.polyfit(range(len(x)), x, 1)[0])
        except Exception:
            return 0.0

    df["trend_6"] = df[target].rolling(6, min_periods=2).apply(_trend, raw=True)
    df["trend_12"] = df[target].rolling(12, min_periods=2).apply(_trend, raw=True)
    df["change"] = df[target].diff(1)
    df["change_rev"] = df["revenue"].diff(1)
    df["change_cost"] = df["costs"].diff(1)
    df["cost_to_revenue"] = np.where(df["revenue"] > 0, df["costs"] / df["revenue"], 0)
    df["month_num"] = df["period"].dt.month
    df["quarter"] = df["period"].dt.quarter
    df["sin_month"] = np.sin(2 * np.pi * df["month_num"] / 12)
    df["cos_month"] = np.cos(2 * np.pi * df["month_num"] / 12)
    df = df.sort_values("period").reset_index(drop=True)
    for shift_months in (12, 24):
        df[f"profitability_yago_{shift_months}"] = df[target].shift(shift_months)
    return df


def numeric_feature_columns(df: pd.DataFrame) -> list[str]:
    """Columns suitable for tree models (numeric only)."""
    exclude = {"period", "year", "month", "profitability", "revenue", "costs"}
    cols: list[str] = []
    for c in df.columns:
        if c in exclude:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            cols.append(c)
    return cols
