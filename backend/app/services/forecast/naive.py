"""Naive baseline forecast."""
from __future__ import annotations

from typing import Any

import pandas as pd

from app.services.forecast.periods import next_period_str


def naive_forecast(rows: list[dict[str, Any]], horizon: int, last_period: pd.Timestamp) -> list[dict[str, Any]]:
    if not rows:
        avg = 0.0
    else:
        avg = float(sum(r.get("profitability", 0) or 0 for r in rows) / len(rows))
    last = rows[-1].get("profitability") if rows else avg
    val = last if last is not None else avg
    return [
        {"month": i + 1, "period": next_period_str(last_period, i + 1), "profitability": val}
        for i in range(horizon)
    ]


def apply_forecast_periods(
    predictions: list[dict[str, Any]], first_show_ts: pd.Timestamp, horizon: int
) -> None:
    from app.services.forecast.periods import advance_month, period_to_str

    for i in range(min(horizon, len(predictions))):
        predictions[i]["period"] = period_to_str(advance_month(first_show_ts, i))
