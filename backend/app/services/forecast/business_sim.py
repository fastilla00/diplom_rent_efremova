"""Translate profitability forecasts to ruble margin; retro business metrics."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.forecast.metrics import mae, wape


def implied_margin_rub(revenue: float, profitability_pct: float) -> float:
    """Margin = revenue - costs, with profitability = (revenue-costs)/revenue * 100."""
    if revenue <= 0:
        return 0.0
    return float(revenue * profitability_pct / 100.0)


def forecast_path_margin_rub(
    predictions: list[float],
    base_monthly_revenue: float,
) -> list[float]:
    return [implied_margin_rub(base_monthly_revenue, p) for p in predictions]


def retro_margin_from_arrays(
    y_true_pct: np.ndarray,
    y_pred_pct: np.ndarray,
    revenue: np.ndarray,
) -> dict:
    if len(y_true_pct) < 1 or len(y_pred_pct) != len(y_true_pct) or len(revenue) != len(y_true_pct):
        return {}
    rev = np.clip(revenue.astype(float), 0, None)
    act_margin = rev * y_true_pct.astype(float) / 100.0
    pred_margin = rev * y_pred_pct.astype(float) / 100.0
    cum_err = float(np.sum(np.abs(pred_margin - act_margin)))
    sign_wrong = float(np.mean(np.sign(pred_margin) != np.sign(act_margin))) if len(act_margin) else 0.0
    return {
        "retro_margin_mae_rub": mae(act_margin, pred_margin),
        "retro_margin_wape": wape(act_margin, pred_margin),
        "retro_cumulative_abs_margin_error_rub": cum_err,
        "retro_share_months_margin_sign_mismatch": sign_wrong,
        "retro_n_months": int(len(y_true_pct)),
    }


def retro_margin_simulation(
    df: pd.DataFrame,
    predicted_path: list[float],
) -> dict:
    """Compare implied margin vs actual on the last n rows of df (same index order as predicted_path)."""
    if len(predicted_path) < 1 or df.empty or "profitability" not in df.columns:
        return {}
    n = min(len(predicted_path), len(df))
    tail = df.iloc[-n:]
    rev = tail["revenue"].clip(lower=0).astype(float).values
    act = tail["profitability"].astype(float).values
    pred = np.array(predicted_path[-n:], dtype=float)
    return retro_margin_from_arrays(act, pred, rev)
