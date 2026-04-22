"""Orchestrate forecast: load metrics, features, models, validation metrics, business sim."""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.metric import Metric
from app.services.forecast.business_sim import retro_margin_from_arrays
from app.services.forecast.constants import (
    BACKTEST_HOLDOUT_MONTHS,
    MAX_TRAIN_MONTHS,
    MIN_HISTORY_FOR_FULL,
    PROFITABILITY_DISPLAY_CLIP,
)
from app.services.forecast.data import metric_df
from app.services.forecast.ensemble import forecast_ensemble
from app.services.forecast.features import build_features
from app.services.forecast.models_arima import forecast_arima, forecast_sarimax
from app.services.forecast.models_gbdt import forecast_catboost, forecast_lightgbm
from app.services.forecast.models_prophet import forecast_prophet
from app.services.forecast.naive import apply_forecast_periods, naive_forecast
from app.services.forecast.periods import advance_month, first_forecast_period_from_today, period_to_str
from app.services.forecast.seasonal import apply_seasonal_variation
from app.services.forecast.validation import (
    collect_model_scores,
    ensemble_weights_from_scores,
    holdout_predicted_path,
    pick_best_model_id,
    walk_forward_true_pred_arima_family,
    walk_forward_true_pred_gbdt,
)


def _clip(p: float) -> float:
    return max(PROFITABILITY_DISPLAY_CLIP[0], min(PROFITABILITY_DISPLAY_CLIP[1], p))


async def run_forecast(
    session: AsyncSession,
    project_id: int,
    horizon_months: int,
    model_type: str = "ensemble",
) -> dict[str, Any]:
    settings = get_settings()
    res = await session.execute(
        select(Metric).where(Metric.project_id == project_id).order_by(Metric.year, Metric.month)
    )
    rows = res.scalars().all()
    df0 = metric_df(rows)
    horizon = min(horizon_months, 12)

    if len(df0) == 0:
        today = date.today()
        last_ts = pd.Timestamp(year=today.year, month=today.month, day=1)
        naive = naive_forecast([], horizon, last_ts)
        return {
            "model": "naive",
            "predictions": naive,
            "metrics": {},
            "note": "Нет метрик. Синхронизируйте проект и подождите данные за несколько месяцев.",
        }

    first_show_ts = first_forecast_period_from_today()
    last_period = df0["period"].iloc[-1]
    first_pred_ts = advance_month(last_period, 1)
    df = df0
    if first_pred_ts > first_show_ts:
        cut = df["period"] <= advance_month(first_show_ts, -2)
        df_cut = df[cut].copy()
        if len(df_cut) >= 3:
            df = df_cut
            last_period = df["period"].iloc[-1]
            first_pred_ts = advance_month(last_period, 1)
    offset = max(0, (first_show_ts.year - first_pred_ts.year) * 12 + (first_show_ts.month - first_pred_ts.month))
    total_steps = offset + horizon

    rows_list = [{"profitability": float(df["profitability"].iloc[i])} for i in range(len(df))]

    if len(df) < settings.forecast_min_months_history:
        naive = naive_forecast(rows_list, horizon, last_period)
        apply_forecast_periods(naive, first_show_ts, horizon)
        return {
            "model": "naive",
            "predictions": naive,
            "metrics": {},
            "note": f"Мало данных ({len(df)} мес.). Прогноз упрощён.",
        }

    df = df.tail(MAX_TRAIN_MONTHS).reset_index(drop=True)
    df_feat = build_features(df)
    df_feat = df_feat.dropna(subset=["lag_1"]).reset_index(drop=True)
    if len(df_feat) < 4:
        naive = naive_forecast(rows_list, horizon, last_period)
        apply_forecast_periods(naive, first_show_ts, horizon)
        return {"model": "naive", "predictions": naive, "metrics": {}}

    series = df_feat.set_index("period")["profitability"]
    scores = collect_model_scores(df_feat, series)

    allowed = (
        "arima",
        "sarimax",
        "catboost",
        "lightgbm",
        "prophet",
        "rnn",
        "ensemble",
        "auto",
    )
    if model_type not in allowed:
        model_type = "ensemble"

    metrics: dict[str, Any] = {
        "validation_scheme": "walk_forward_one_step",
        "holdout_months": BACKTEST_HOLDOUT_MONTHS,
        "model_comparison": {
            k: {kk: vv for kk, vv in v.items() if vv is not None} for k, v in scores.items() if v
        },
    }

    def _attach_selected_backtest(mid: str) -> None:
        sc = scores.get(mid, {})
        if sc:
            metrics["backtest_mae"] = sc.get("backtest_mae")
            metrics["backtest_wape"] = sc.get("backtest_wape")
            metrics["backtest_n"] = sc.get("backtest_n")

    def _business_for_model(model_id: str) -> None:
        """Retro margin in rubles using mean revenue over last 12 months (stable proxy)."""
        avg_rev = float(df_feat["revenue"].tail(12).mean()) if "revenue" in df_feat.columns else 0.0
        s = series.dropna()
        yt: list[float] = []
        yp: list[float] = []
        if model_id == "arima":
            yt, yp = walk_forward_true_pred_arima_family(s, forecast_arima)
        elif model_id == "sarimax":
            yt, yp = walk_forward_true_pred_arima_family(s, forecast_sarimax)
        elif model_id == "prophet":

            def _prophet_step(ser: pd.Series, h: int) -> list[float]:
                if len(ser) < 1:
                    return []
                lp = pd.Timestamp(ser.index[-1])
                return forecast_prophet(ser, h, lp)

            yt, yp = walk_forward_true_pred_arima_family(s, _prophet_step)
        elif model_id == "catboost":
            yt, yp = walk_forward_true_pred_gbdt(df_feat, "catboost")
        elif model_id == "lightgbm":
            yt, yp = walk_forward_true_pred_gbdt(df_feat, "lightgbm")
        elif model_id == "rnn":
            from app.services.forecast.models_rnn import forecast_rnn

            holdout = BACKTEST_HOLDOUT_MONTHS
            yt, yp = [], []
            if len(s) >= holdout + 18:
                for k in range(holdout):
                    prefix = s.iloc[: len(s) - holdout + k]
                    lp = pd.Timestamp(prefix.index[-1])
                    pred = forecast_rnn(prefix, 1, lp)
                    yp.append(float(pred[0]) if pred else float("nan"))
                    yt.append(float(s.iloc[len(s) - holdout + k]))
                mask = [not np.isnan(p) for p in yp]
                yt = [t for t, ok in zip(yt, mask) if ok]
                yp = [p for p, ok in zip(yp, mask) if ok]
        if len(yt) >= 2 and len(yp) == len(yt):
            rev = np.full(len(yt), max(avg_rev, 0.0))
            b = retro_margin_from_arrays(np.array(yt), np.array(yp), rev)
            if b:
                metrics["business_retro"] = b

    def _build_result(
        preds: list[float],
        with_components: bool = False,
        arima_p: list | None = None,
        cat_p: list | None = None,
    ) -> list[dict]:
        preds = (preds + [preds[-1]] * (total_steps - len(preds)))[:total_steps]
        result = []
        for i in range(horizon):
            p = _clip(preds[offset + i]) if offset + i < len(preds) else _clip(preds[-1])
            row = {"month": i + 1, "period": period_to_str(advance_month(first_show_ts, i)), "profitability": p}
            if with_components and arima_p is not None and cat_p is not None:
                row["profitability_arima"] = _clip(arima_p[offset + i]) if offset + i < len(arima_p) else None
                row["profitability_catboost"] = _clip(cat_p[offset + i]) if offset + i < len(cat_p) else None
            result.append(row)
        apply_seasonal_variation(result, df_feat)
        for r in result:
            r["profitability"] = _clip(r["profitability"])
            if "profitability_arima" in r and r["profitability_arima"] is not None:
                r["profitability_arima"] = _clip(r["profitability_arima"])
            if "profitability_catboost" in r and r["profitability_catboost"] is not None:
                r["profitability_catboost"] = _clip(r["profitability_catboost"])
        return result

    try:
        if model_type == "auto":
            best = pick_best_model_id(scores)
            if not best:
                best = "arima"
            metrics["auto_selected"] = best
            model_type = best

        if model_type == "arima":
            preds = forecast_arima(series, total_steps)
            if not preds:
                preds = [float(df_feat["profitability"].iloc[-1])] * total_steps
            _attach_selected_backtest("arima")
            _business_for_model("arima")
            return {"model": "arima", "predictions": _build_result(preds), "metrics": metrics}

        if model_type == "sarimax":
            preds = forecast_sarimax(series, total_steps)
            if not preds:
                preds = [float(df_feat["profitability"].iloc[-1])] * total_steps
            _attach_selected_backtest("sarimax")
            _business_for_model("sarimax")
            return {"model": "sarimax", "predictions": _build_result(preds), "metrics": metrics}

        if model_type == "prophet":
            preds = forecast_prophet(series, total_steps, last_period)
            if not preds:
                preds = [float(df_feat["profitability"].iloc[-1])] * total_steps
            _attach_selected_backtest("prophet")
            _business_for_model("prophet")
            return {"model": "prophet", "predictions": _build_result(preds), "metrics": metrics}

        if model_type == "rnn":
            from app.services.forecast.models_rnn import forecast_rnn as _forecast_rnn

            preds = _forecast_rnn(series, total_steps, last_period)
            if not preds:
                preds = [float(df_feat["profitability"].iloc[-1])] * total_steps
            _attach_selected_backtest("rnn")
            _business_for_model("rnn")
            return {"model": "rnn", "predictions": _build_result(preds), "metrics": metrics}

        if model_type == "lightgbm":
            preds = forecast_lightgbm(df_feat, total_steps, last_period)
            if not preds:
                preds = [float(df_feat["profitability"].iloc[-1])] * total_steps
            _attach_selected_backtest("lightgbm")
            _business_for_model("lightgbm")
            return {"model": "lightgbm", "predictions": _build_result(preds), "metrics": metrics}

        if model_type == "catboost":
            preds = forecast_catboost(df_feat, total_steps, last_period)
            if not preds:
                preds = [float(df_feat["profitability"].iloc[-1])] * total_steps
            _attach_selected_backtest("catboost")
            _business_for_model("catboost")
            return {"model": "catboost", "predictions": _build_result(preds), "metrics": metrics}

        # ensemble: dynamic weights from backtest WAPE
        wa, wb = ensemble_weights_from_scores(scores, "arima", "catboost")
        metrics["ensemble_weight_arima"] = wa
        metrics["ensemble_weight_catboost"] = wb
        arima, cat, ensemble = forecast_ensemble(df_feat, total_steps, last_period, wa, wb)
        n = total_steps
        last_val = float(series.iloc[-1])
        arima = (arima + [arima[-1] if arima else last_val] * (n - len(arima)))[:n] if arima else [last_val] * n
        cat = (cat + [cat[-1] if cat else last_val] * (n - len(cat)))[:n] if cat else [last_val] * n
        if len(ensemble) < n:
            ensemble = (ensemble + [ensemble[-1] if ensemble else last_val] * (n - len(ensemble)))[:n]
        # backtest for ensemble: combine holdout paths
        pa = holdout_predicted_path("arima", df_feat, series)
        pb = holdout_predicted_path("catboost", df_feat, series)
        m = min(len(pa), len(pb))
        if m >= 2:
            comb = [wa * pa[i] + wb * pb[i] for i in range(m)]
            vals = series.values.astype(float)
            yt = np.array(vals[-m:])
            from app.services.forecast.metrics import mae as mae_fn
            from app.services.forecast.metrics import wape as wape_fn

            metrics["ensemble_holdout_mae"] = mae_fn(yt, np.array(comb))
            metrics["ensemble_holdout_wape"] = wape_fn(yt, np.array(comb))
            avg_rev = float(df_feat["revenue"].tail(12).mean()) if "revenue" in df_feat.columns else 0.0
            br = retro_margin_from_arrays(yt, np.array(comb), np.full(m, max(avg_rev, 0.0)))
            if br:
                metrics["business_retro"] = br
        return {
            "model": "ensemble",
            "predictions": _build_result(ensemble, with_components=True, arima_p=arima, cat_p=cat),
            "metrics": metrics,
        }
    except Exception:
        naive = naive_forecast(rows_list, horizon, last_period)
        apply_forecast_periods(naive, first_show_ts, horizon)
        return {
            "model": "naive",
            "predictions": naive,
            "metrics": metrics,
            "note": "Ошибка модели — выдан упрощённый прогноз.",
        }
