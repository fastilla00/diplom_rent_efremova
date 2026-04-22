"""CatBoost / LightGBM: one-step target, recursive multi-step forecast."""
from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

from app.services.forecast.constants import MIN_HISTORY_FOR_FULL
from app.services.forecast.features import numeric_feature_columns
from app.services.forecast.periods import advance_month

Backend = Literal["catboost", "lightgbm"]


def _norm_ts(ts: pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(ts).normalize()


def _profit_history_map(df: pd.DataFrame) -> dict[pd.Timestamp, float]:
    out: dict[pd.Timestamp, float] = {}
    for _, r in df.iterrows():
        out[_norm_ts(r["period"])] = float(r["profitability"])
    return out


def _fill_row_from_history(
    last: pd.DataFrame,
    period: pd.Timestamp,
    profit_by_period: dict[pd.Timestamp, float],
    feat_cols: list[str],
    base_constants: dict[str, float],
) -> pd.DataFrame:
    """Recompute lags and rolling profitability from known/predicted history; keep revenue-based constants."""
    row = last.iloc[0:1].copy()
    row["period"] = period
    row["month_num"] = period.month
    row["quarter"] = (period.month - 1) // 3 + 1
    row["sin_month"] = np.sin(2 * np.pi * period.month / 12)
    row["cos_month"] = np.cos(2 * np.pi * period.month / 12)
    pnorm = period.normalize()
    for shift_m in (12, 24):
        col = f"profitability_yago_{shift_m}"
        if col in row.columns:
                    prev_p = _norm_ts(advance_month(pnorm, -shift_m))
                    row[col] = profit_by_period.get(prev_p, np.nan)
    for lag in (1, 2, 3, 7, 12):
        col = f"lag_{lag}"
        if col in row.columns:
            prev_p = _norm_ts(advance_month(pnorm, -lag))
            row[col] = profit_by_period.get(prev_p, np.nan)
    for w in (3, 6, 12):
        rcol = f"rolling_{w}"
        if rcol not in row.columns:
            continue
        vals = []
        for k in range(1, w + 1):
            prev_p = _norm_ts(advance_month(pnorm, -k))
            if prev_p in profit_by_period:
                vals.append(profit_by_period[prev_p])
        row[rcol] = float(np.mean(vals)) if vals else np.nan
        std_col = f"rolling_std_{w}"
        if std_col in row.columns:
            row[std_col] = float(np.std(vals)) if len(vals) > 1 else 0.0
    for k, v in base_constants.items():
        if k in row.columns:
            row[k] = v
    return row


def forecast_gbdt(
    df: pd.DataFrame,
    horizon: int,
    last_period: pd.Timestamp,
    backend: Backend = "catboost",
) -> list[float]:
    feat_cols = numeric_feature_columns(df)
    if not feat_cols or len(df) < MIN_HISTORY_FOR_FULL:
        return []
    work = df.dropna(subset=["profitability"]).copy()
    work["target"] = work["profitability"].shift(-1)
    work = work.dropna(subset=["target"])
    if len(work) < 8:
        return []
    n_val = min(6, len(work) // 3)
    train = work.iloc[:-n_val] if n_val else work
    val = work.iloc[-n_val:] if n_val else None
    X_train = train[feat_cols].fillna(0)
    y_train = train["target"]
    X_val = val[feat_cols].fillna(0) if val is not None and len(val) > 0 else None
    y_val = val["target"] if val is not None and len(val) > 0 else None

    try:
        if backend == "catboost":
            import catboost as cb

            model = cb.CatBoostRegressor(
                iterations=400,
                depth=6,
                learning_rate=0.05,
                early_stopping_rounds=25,
                random_seed=42,
                verbose=0,
            )
            eval_set = (X_val, y_val) if X_val is not None else None
            model.fit(X_train, y_train, eval_set=eval_set)
        else:
            import lightgbm as lgb

            params = {
                "objective": "regression",
                "metric": "mae",
                "verbosity": -1,
                "learning_rate": 0.05,
                "num_leaves": 31,
                "seed": 42,
            }
            train_ds = lgb.Dataset(X_train, label=y_train)
            callbacks = []
            if X_val is not None:
                valid_ds = lgb.Dataset(X_val, label=y_val)
                callbacks.append(lgb.early_stopping(25, verbose=False))
                model = lgb.train(
                    params,
                    train_ds,
                    num_boost_round=400,
                    valid_sets=[train_ds, valid_ds],
                    valid_names=["train", "valid"],
                    callbacks=callbacks,
                )
            else:
                model = lgb.train(params, train_ds, num_boost_round=400)
    except Exception:
        return []

    profit_by_period = _profit_history_map(df)
    last_row = df.iloc[-1:].copy()
    base_constants: dict[str, float] = {}
    for c in feat_cols:
        if c.startswith("rolling_rev_") or c.startswith("rolling_cost_"):
            base_constants[c] = float(last_row[c].iloc[0]) if c in last_row.columns else 0.0
        elif c in ("change", "change_rev", "change_cost", "trend_6", "trend_12", "cost_to_revenue"):
            base_constants[c] = float(last_row[c].iloc[0]) if c in last_row.columns and pd.notna(last_row[c].iloc[0]) else 0.0

    preds: list[float] = []
    period = last_period
    for _ in range(horizon):
        period = advance_month(period, 1)
        pnorm = _norm_ts(period)
        cur = _fill_row_from_history(last_row, period, profit_by_period, feat_cols, base_constants)
        X_pred = cur[feat_cols].fillna(0)
        if backend == "catboost":
            p = float(model.predict(X_pred)[0])
        else:
            n_it = getattr(model, "best_iteration", None)
            kwargs = {"num_iteration": n_it} if n_it is not None else {}
            p = float(model.predict(X_pred, **kwargs)[0])
        preds.append(p)
        profit_by_period[_norm_ts(period)] = p
        last_row = cur
        last_row["profitability"] = p
    return preds


def forecast_catboost(df: pd.DataFrame, horizon: int, last_period: pd.Timestamp) -> list[float]:
    return forecast_gbdt(df, horizon, last_period, backend="catboost")


def forecast_lightgbm(df: pd.DataFrame, horizon: int, last_period: pd.Timestamp) -> list[float]:
    return forecast_gbdt(df, horizon, last_period, backend="lightgbm")
