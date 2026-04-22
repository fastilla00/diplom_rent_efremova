"""Time-series backtesting (walk-forward one-step where applicable)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.forecast.constants import BACKTEST_HOLDOUT_MONTHS, MIN_HISTORY_FOR_FULL
from app.services.forecast.features import numeric_feature_columns
from app.services.forecast.metrics import mae, wape
from app.services.forecast.models_arima import forecast_arima, forecast_sarimax
from app.services.forecast.models_prophet import forecast_prophet


def _supervised_frame(df: pd.DataFrame) -> pd.DataFrame | None:
    work = df.dropna(subset=["profitability"]).copy()
    work["target"] = work["profitability"].shift(-1)
    work = work.dropna(subset=["target"]).reset_index(drop=True)
    if len(work) < MIN_HISTORY_FOR_FULL:
        return None
    return work


def _gbdt_walk_pairs(df: pd.DataFrame, backend: str, holdout: int) -> list[tuple[float, float]]:
    work = _supervised_frame(df)
    if work is None:
        return []
    feat_cols = numeric_feature_columns(work)
    if not feat_cols:
        return []
    h = min(holdout, len(work) - 6)
    if h < 2:
        return []
    start = len(work) - h
    pairs: list[tuple[float, float]] = []
    for i in range(start, len(work)):
        train = work.iloc[:i]
        if len(train) < 6:
            continue
        try:
            if backend == "catboost":
                import catboost as cb

                model = cb.CatBoostRegressor(
                    iterations=200, depth=5, learning_rate=0.05, random_seed=42, verbose=0
                )
                model.fit(train[feat_cols].fillna(0), train["target"])
            else:
                import lightgbm as lgb

                train_ds = lgb.Dataset(train[feat_cols].fillna(0), label=train["target"])
                model = lgb.train(
                    {"objective": "regression", "verbosity": -1, "learning_rate": 0.05, "num_leaves": 31, "seed": 42},
                    train_ds,
                    num_boost_round=200,
                )
            row = work.iloc[i : i + 1][feat_cols].fillna(0)
            p = float(model.predict(row)[0])
        except Exception:
            continue
        pairs.append((float(work["target"].iloc[i]), p))
    return pairs


def walk_forward_predictions_gbdt(df: pd.DataFrame, backend: str, holdout: int = BACKTEST_HOLDOUT_MONTHS) -> list[float]:
    return [pr for _, pr in _gbdt_walk_pairs(df, backend, holdout)]


def walk_forward_true_pred_gbdt(
    df: pd.DataFrame, backend: str, holdout: int = BACKTEST_HOLDOUT_MONTHS
) -> tuple[list[float], list[float]]:
    pairs = _gbdt_walk_pairs(df, backend, holdout)
    if not pairs:
        return [], []
    yt, yp = zip(*pairs)
    return list(yt), list(yp)


def backtest_gbdt(df: pd.DataFrame, backend: str, holdout: int = BACKTEST_HOLDOUT_MONTHS) -> dict:
    pairs = _gbdt_walk_pairs(df, backend, holdout)
    if len(pairs) < 2:
        return {}
    y_true = [a for a, _ in pairs]
    y_pred = [b for _, b in pairs]
    yt = np.array(y_true)
    yp = np.array(y_pred)
    return {"backtest_mae": mae(yt, yp), "backtest_wape": wape(yt, yp), "backtest_n": len(y_true)}


def walk_forward_true_pred_arima_family(
    series: pd.Series, forecaster, holdout: int = BACKTEST_HOLDOUT_MONTHS
) -> tuple[list[float], list[float]]:
    s = series.dropna()
    if len(s) < holdout + 5:
        return [], []
    h = min(holdout, len(s) - 4)
    y_true: list[float] = []
    y_pred: list[float] = []
    for i in range(len(s) - h, len(s)):
        train = s.iloc[:i]
        if len(train) < 4:
            continue
        pred = forecaster(train, 1)
        if not pred:
            continue
        y_true.append(float(s.iloc[i]))
        y_pred.append(float(pred[0]))
    return y_true, y_pred


def walk_forward_predictions_arima_family(
    series: pd.Series, forecaster, holdout: int = BACKTEST_HOLDOUT_MONTHS
) -> list[float]:
    yt, yp = walk_forward_true_pred_arima_family(series, forecaster, holdout)
    return yp


def backtest_arima_family(
    series: pd.Series, forecaster, holdout: int = BACKTEST_HOLDOUT_MONTHS
) -> dict:
    s = series.dropna()
    if len(s) < holdout + 5:
        return {}
    h = min(holdout, len(s) - 4)
    y_true: list[float] = []
    y_pred: list[float] = []
    for i in range(len(s) - h, len(s)):
        train = s.iloc[:i]
        if len(train) < 4:
            continue
        pred = forecaster(train, 1)
        if not pred:
            continue
        y_true.append(float(s.iloc[i]))
        y_pred.append(float(pred[0]))
    if len(y_true) < 2:
        return {}
    yt = np.array(y_true)
    yp = np.array(y_pred)
    return {"backtest_mae": mae(yt, yp), "backtest_wape": wape(yt, yp), "backtest_n": len(y_true)}


def backtest_prophet(series: pd.Series, holdout: int = BACKTEST_HOLDOUT_MONTHS) -> dict:
    def _prophet_step(ser: pd.Series, h: int) -> list[float]:
        if len(ser) < 1:
            return []
        lp = pd.Timestamp(ser.index[-1])
        return forecast_prophet(ser, h, lp)

    return backtest_arima_family(series, _prophet_step, holdout)


def backtest_rnn_holdout(series: pd.Series, holdout: int = BACKTEST_HOLDOUT_MONTHS) -> dict:
    """Single train on prefix, H one-step predictions with true history windows."""
    try:
        from app.services.forecast.models_rnn import forecast_rnn
    except Exception:
        return {}
    s = series.dropna()
    seq_len = 12
    if len(s) < holdout + seq_len + 6:
        return {}
    # Re-forecast 1 month at a time with growing prefix (true history).
    y_true = [float(s.iloc[-holdout + k]) for k in range(holdout)]
    y_pred: list[float] = []
    for k in range(holdout):
        prefix = s.iloc[: len(s) - holdout + k]
        lp = prefix.index[-1] if len(prefix) else s.index[0]
        if not isinstance(lp, pd.Timestamp):
            lp = pd.Timestamp(lp)
        pred = forecast_rnn(prefix, 1, lp)
        y_pred.append(float(pred[0]) if pred else float("nan"))
    yp = np.array(y_pred, dtype=float)
    yt = np.array(y_true, dtype=float)
    mask = ~np.isnan(yp)
    if mask.sum() < 2:
        return {}
    return {
        "backtest_mae": mae(yt[mask], yp[mask]),
        "backtest_wape": wape(yt[mask], yp[mask]),
        "backtest_n": int(mask.sum()),
    }


def collect_model_scores(df: pd.DataFrame, series: pd.Series) -> dict[str, dict]:
    scores: dict[str, dict] = {}

    def _safe(fn):
        try:
            return fn()
        except Exception:
            return {}

    scores["arima"] = _safe(lambda: backtest_arima_family(series, forecast_arima))
    scores["sarimax"] = _safe(lambda: backtest_arima_family(series, forecast_sarimax))
    scores["catboost"] = _safe(lambda: backtest_gbdt(df, "catboost"))
    scores["lightgbm"] = _safe(lambda: backtest_gbdt(df, "lightgbm"))
    scores["prophet"] = _safe(lambda: backtest_prophet(series))
    scores["rnn"] = _safe(lambda: backtest_rnn_holdout(series))
    return scores


def pick_best_model_id(scores: dict[str, dict], prefer_wape: bool = True) -> str | None:
    best_id, best_val = None, None
    for mid, d in scores.items():
        if not d:
            continue
        w = d.get("backtest_wape")
        m = d.get("backtest_mae")
        val = w if prefer_wape and w is not None else m
        if val is None or (isinstance(val, float) and np.isnan(val)):
            val = m if m is not None else None
        if val is None:
            continue
        if best_val is None or val < best_val:
            best_val = val
            best_id = mid
    return best_id


def holdout_predicted_path(
    model_id: str, df: pd.DataFrame, series: pd.Series, holdout: int = BACKTEST_HOLDOUT_MONTHS
) -> list[float]:
    if model_id == "arima":
        return walk_forward_predictions_arima_family(series, forecast_arima, holdout)
    if model_id == "sarimax":
        return walk_forward_predictions_arima_family(series, forecast_sarimax, holdout)
    if model_id == "prophet":

        def _prophet_step(ser: pd.Series, h: int) -> list[float]:
            if len(ser) < 1:
                return []
            lp = pd.Timestamp(ser.index[-1])
            return forecast_prophet(ser, h, lp)

        return walk_forward_predictions_arima_family(series, _prophet_step, holdout)
    if model_id == "catboost":
        return walk_forward_predictions_gbdt(df, "catboost", holdout)
    if model_id == "lightgbm":
        return walk_forward_predictions_gbdt(df, "lightgbm", holdout)
    if model_id == "rnn":
        from app.services.forecast.models_rnn import forecast_rnn

        s = series.dropna()
        seq_len = 12
        if len(s) < holdout + seq_len + 6:
            return []
        y_pred: list[float] = []
        for k in range(holdout):
            prefix = s.iloc[: len(s) - holdout + k]
            lp = prefix.index[-1]
            if not isinstance(lp, pd.Timestamp):
                lp = pd.Timestamp(lp)
            pred = forecast_rnn(prefix, 1, lp)
            y_pred.append(float(pred[0]) if pred else float("nan"))
        return [p for p in y_pred if not np.isnan(p)]
    return []


def ensemble_weights_from_scores(scores: dict[str, dict], id_a: str, id_b: str) -> tuple[float, float]:
    """Inverse-error weights; default 0.5/0.5 if missing."""
    def err(d: dict | None) -> float | None:
        if not d:
            return None
        w = d.get("backtest_wape")
        if w is not None and w > 1e-9:
            return float(w)
        m = d.get("backtest_mae")
        return float(m) if m is not None else None

    ea, eb = err(scores.get(id_a)), err(scores.get(id_b))
    if ea is None and eb is None:
        return 0.5, 0.5
    if ea is None:
        return 0.0, 1.0
    if eb is None:
        return 1.0, 0.0
    ia, ib = 1.0 / (ea + 1e-6), 1.0 / (eb + 1e-6)
    s = ia + ib
    return ia / s, ib / s
