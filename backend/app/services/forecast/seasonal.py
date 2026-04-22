"""Post-process: add historical monthly mean deviation to point forecasts."""
from __future__ import annotations

from typing import Any

import pandas as pd


def seasonal_adjustment_by_month(df: pd.DataFrame) -> dict[int, float]:
    if df.empty or "profitability" not in df.columns:
        return {}
    global_mean = df["profitability"].mean()
    by_month = df.groupby(df["period"].dt.month)["profitability"].mean()
    return {int(m): float(by_month[m] - global_mean) for m in by_month.index}


def apply_seasonal_variation(predictions: list[dict[str, Any]], df: pd.DataFrame) -> None:
    adj = seasonal_adjustment_by_month(df)
    if not adj:
        return
    for row in predictions:
        period_str = row.get("period", "")
        try:
            month = int(period_str.split("-")[1])
            delta = adj.get(month, 0.0)
            row["profitability"] = row["profitability"] + delta * 0.85
        except (IndexError, ValueError):
            pass
