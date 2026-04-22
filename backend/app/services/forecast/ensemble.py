"""Combine ARIMA and gradient boosting forecasts."""
from __future__ import annotations

import pandas as pd

from app.services.forecast.models_arima import forecast_arima
from app.services.forecast.models_gbdt import forecast_catboost


def forecast_ensemble(
    df: pd.DataFrame,
    horizon: int,
    last_period: pd.Timestamp,
    weight_arima: float = 0.5,
    weight_gbdt: float = 0.5,
) -> tuple[list[float], list[float], list[float]]:
    series = df.set_index("period")["profitability"]
    arima = forecast_arima(series, horizon)
    cat = forecast_catboost(df, horizon, last_period)
    n = max(len(arima), len(cat), horizon)
    if n == 0:
        return [], [], []
    last_val = float(series.iloc[-1])
    arima = (arima + [arima[-1] if arima else last_val] * (n - len(arima)))[:n] if arima else [last_val] * n
    cat = (cat + [cat[-1] if cat else last_val] * (n - len(cat)))[:n] if cat else [last_val] * n
    wa, wb = weight_arima, weight_gbdt
    if wa + wb < 1e-6:
        wa, wb = 1.0, 0.0
    else:
        wa, wb = wa / (wa + wb), wb / (wa + wb)
    ensemble = [wa * arima[i] + wb * cat[i] for i in range(n)]
    return arima, cat, ensemble
