# EcomProfit Guard — ML forecasting: ARIMA, CatBoost, ensemble
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Any
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.metric import Metric
from app.config import get_settings

# Ограничение выбросов: винзоризация по перцентилям (сохраняет форму ряда), итоговый прогноз — в [-100, 100]
PROFITABILITY_DISPLAY_CLIP = (-100.0, 100.0)
WINSORIZE_LOW, WINSORIZE_HIGH = 0.05, 0.95  # перцентили для обрезки выбросов при обучении
MAX_TRAIN_MONTHS = 36  # обучаем на последних N месяцах (свежие данные после TL)
MIN_HISTORY_FOR_FULL = 12


def _metric_df(rows: list) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    data = []
    for r in rows:
        pct = None
        if r.revenue and r.costs is not None and r.revenue > 0:
            pct = float((r.revenue - r.costs) / r.revenue * 100)
        elif r.profitability_pct is not None:
            pct = float(r.profitability_pct)
        if pct is None:
            continue
        rev = float(r.revenue or 0)
        cost = float(r.costs or 0)
        data.append({"year": r.year, "month": r.month, "revenue": rev, "costs": cost, "profitability": pct})
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["period"] = pd.to_datetime(df[["year", "month"]].assign(day=1))
    df = df.sort_values("period").reset_index(drop=True)
    # Винзоризация выбросов по перцентилям (не загоняем всё в -100)
    if len(df) >= 4:
        lo = df["profitability"].quantile(WINSORIZE_LOW)
        hi = df["profitability"].quantile(WINSORIZE_HIGH)
        df["profitability"] = df["profitability"].clip(lo, hi)
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 3:
        return pd.DataFrame()
    target = "profitability"
    df = df.copy()
    for lag in [1, 2, 3]:
        df[f"lag_{lag}"] = df[target].shift(lag)
    for w in [3, 6, 12]:
        df[f"rolling_{w}"] = df[target].rolling(w, min_periods=1).mean()
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
    # Сезонность: рентабельность того же месяца в прошлых годах
    df = df.sort_values("period").reset_index(drop=True)
    for shift_months in [12, 24]:
        df[f"profitability_yago_{shift_months}"] = df[target].shift(shift_months)
    return df


def forecast_arima(series: pd.Series, horizon: int) -> list[float]:
    if len(series) < 4 or horizon < 1:
        return []
    try:
        import warnings
        from statsmodels.tools.sm_exceptions import ConvergenceWarning
        from statsmodels.tsa.arima.model import ARIMA
        from statsmodels.tsa.stattools import adfuller
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            warnings.simplefilter("ignore", UserWarning)
            s = series.dropna()
            if len(s) < 4:
                return []
            d = 0
            try:
                if adfuller(s)[1] > 0.05:
                    d = 1
            except Exception:
                pass
            best_aic, best_pred = None, None
            for order in [(1, d, 0), (1, d, 1), (2, d, 0), (2, d, 1)]:
                if len(s) <= 6 and order[0] + order[2] > 1:
                    continue
                try:
                    model = ARIMA(s, order=order)
                    fit = model.fit()
                    aic = fit.aic
                    if best_aic is None or aic < best_aic:
                        best_aic = aic
                        best_pred = list(fit.forecast(steps=horizon))
                except Exception:
                    continue
            if best_pred:
                return best_pred
    except Exception:
        pass
    return []


def _advance_month(ts: pd.Timestamp, delta: int) -> pd.Timestamp:
    m = ts.month + delta
    y = ts.year
    while m > 12:
        m -= 12
        y += 1
    while m < 1:
        m += 12
        y -= 1
    return pd.Timestamp(year=y, month=m, day=1)


def forecast_catboost(df: pd.DataFrame, horizon: int, last_period: pd.Timestamp) -> list[float]:
    exclude = {"period", "year", "month", "profitability", "revenue", "costs"}
    feat_cols = [c for c in df.columns if c not in exclude and df[c].dtype in (np.float64, np.int64)]
    if not feat_cols or len(df) < MIN_HISTORY_FOR_FULL:
        return []
    try:
        import catboost as cb
        work = df.dropna(subset=["profitability"]).copy()
        work["target"] = work["profitability"].shift(-1)
        work = work.dropna(subset=["target"])
        if len(work) < 8:
            return []
        n_val = min(6, len(work) // 3)
        train = work.iloc[: -n_val] if n_val else work
        val = work.iloc[-n_val:] if n_val else None
        X_train = train[feat_cols].fillna(0)
        y_train = train["target"]
        eval_set = (val[feat_cols].fillna(0), val["target"]) if val is not None and len(val) > 0 else None
        model = cb.CatBoostRegressor(
            iterations=400,
            depth=6,
            learning_rate=0.05,
            early_stopping_rounds=25,
            random_seed=42,
            verbose=0,
        )
        model.fit(X_train, y_train, eval_set=eval_set)
        preds = []
        last = df.iloc[-1:].copy()
        period = last_period  # первый прогноз — для (last_period + 1 месяц)
        series_by_period = df.set_index("period")["profitability"]
        for step in range(horizon):
            period = _advance_month(period, 1)
            # Для каждого прогнозного месяца обновляем календарные признаки (сезонность)
            last = last.copy()
            last["period"] = period
            last["month_num"] = period.month
            last["quarter"] = (period.month - 1) // 3 + 1
            last["sin_month"] = np.sin(2 * np.pi * period.month / 12)
            last["cos_month"] = np.cos(2 * np.pi * period.month / 12)
            for shift_m in [12, 24]:
                col = f"profitability_yago_{shift_m}"
                if col in last.columns:
                    prev_period = _advance_month(period, -shift_m)
                    last[col] = series_by_period.get(prev_period, np.nan)
            X_pred = last[feat_cols].fillna(0)
            p = float(model.predict(X_pred)[0])
            preds.append(p)
            new_row = last.copy()
            new_row["profitability"] = p
            new_row["lag_1"] = last["profitability"].values[0]
            new_row["lag_2"] = last["lag_1"].values[0] if "lag_1" in last.columns else p
            new_row["lag_3"] = last["lag_2"].values[0] if "lag_2" in last.columns else p
            for w in [3, 6, 12]:
                r = f"rolling_{w}"
                if r in new_row.columns:
                    new_row[r] = (last[r].values[0] * (w - 1) + p) / w
            last = new_row
        return preds
    except Exception:
        return []


def forecast_ensemble(df: pd.DataFrame, horizon: int, last_period: pd.Timestamp) -> tuple[list[float], list[float], list[float]]:
    series = df.set_index("period")["profitability"]
    arima = forecast_arima(series, horizon)
    cat = forecast_catboost(df, horizon, last_period)
    n = max(len(arima), len(cat), horizon)
    if n == 0:
        return [], [], []
    last_val = float(series.iloc[-1])
    arima = (arima + [arima[-1] if arima else last_val] * (n - len(arima)))[:n] if arima else [last_val] * n
    cat = (cat + [cat[-1] if cat else last_val] * (n - len(cat)))[:n] if cat else [last_val] * n
    # Взвешенный ансамбль: если оба есть — 0.5/0.5, иначе один источник
    w_arima = 0.5 if arima else 0.0
    w_cat = 0.5 if cat else 0.0
    if w_arima + w_cat < 1e-6:
        w_arima, w_cat = 1.0, 0.0
    else:
        w_arima, w_cat = w_arima / (w_arima + w_cat), w_cat / (w_arima + w_cat)
    ensemble = [w_arima * arima[i] + w_cat * cat[i] for i in range(n)]
    return arima, cat, ensemble


def _naive_forecast(rows: list, horizon: int, last_period: pd.Timestamp) -> list[dict]:
    """Простой прогноз: повтор последнего значения или среднего."""
    if not rows:
        avg = 0.0
    else:
        avg = float(sum(r.get("profitability", 0) or 0 for r in rows) / len(rows))
    last = rows[-1].get("profitability") if rows else avg
    val = last if last is not None else avg
    return [
        {"month": i + 1, "period": _next_period(last_period, i + 1), "profitability": val}
        for i in range(horizon)
    ]


def _apply_forecast_periods(predictions: list[dict], first_show_ts: pd.Timestamp, horizon: int) -> None:
    """Подменяет периоды в predictions на первые horizon месяцев начиная с first_show_ts."""
    for i in range(min(horizon, len(predictions))):
        predictions[i]["period"] = _period_to_str(_advance_month(first_show_ts, i))


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
    df = _metric_df(rows)
    horizon = min(horizon_months, 12)

    if len(df) == 0:
        from datetime import date
        today = date.today()
        last_ts = pd.Timestamp(year=today.year, month=today.month, day=1)
        naive = _naive_forecast([], horizon, last_ts)
        return {"model": "naive", "predictions": naive, "metrics": {}, "note": "Нет метрик. Синхронизируйте проект и подождите данные за несколько месяцев."}

    # Всегда показываем прогноз с следующего месяца от сегодня
    first_show_ts = _first_forecast_period_from_today()
    last_period = df["period"].iloc[-1]
    first_pred_ts = _advance_month(last_period, 1)
    # Если данные «в будущем» (последний месяц в данных > первый показ), обрезаем историю до (first_show_ts - 2), чтобы первый месяц прогноза = first_show_ts
    if first_pred_ts > first_show_ts:
        cut = df["period"] <= _advance_month(first_show_ts, -2)
        df_cut = df[cut].copy()
        if len(df_cut) >= 3:  # оставляем обрезку даже при 3 месяцах — дальше может сработать naive с правильными периодами
            df = df_cut
            last_period = df["period"].iloc[-1]
            first_pred_ts = _advance_month(last_period, 1)
    offset = max(0, (first_show_ts.year - first_pred_ts.year) * 12 + (first_show_ts.month - first_pred_ts.month))
    total_steps = offset + horizon

    rows_list = [{"profitability": float(df["profitability"].iloc[i])} for i in range(len(df))]

    if len(df) < settings.forecast_min_months_history:
        naive = _naive_forecast(rows_list, horizon, last_period)
        _apply_forecast_periods(naive, first_show_ts, horizon)
        return {"model": "naive", "predictions": naive, "metrics": {}, "note": f"Мало данных ({len(df)} мес.). Прогноз упрощён."}

    df = df.tail(MAX_TRAIN_MONTHS).reset_index(drop=True)
    df = build_features(df)
    df = df.dropna(subset=["lag_1"]).reset_index(drop=True)
    if len(df) < 4:
        naive = _naive_forecast(rows_list, horizon, last_period)
        _apply_forecast_periods(naive, first_show_ts, horizon)
        return {"model": "naive", "predictions": naive, "metrics": {}}

    def _clip(p: float) -> float:
        return max(PROFITABILITY_DISPLAY_CLIP[0], min(PROFITABILITY_DISPLAY_CLIP[1], p))

    try:
        def _build_result(preds: list[float], with_components: bool = False, arima_p: list | None = None, cat_p: list | None = None) -> list[dict]:
            preds = (preds + [preds[-1]] * (total_steps - len(preds)))[:total_steps]
            result = []
            for i in range(horizon):
                p = _clip(preds[offset + i]) if offset + i < len(preds) else _clip(preds[-1])
                row = {"month": i + 1, "period": _period_to_str(_advance_month(first_show_ts, i)), "profitability": p}
                if with_components and arima_p is not None and cat_p is not None:
                    row["profitability_arima"] = _clip(arima_p[offset + i]) if offset + i < len(arima_p) else None
                    row["profitability_catboost"] = _clip(cat_p[offset + i]) if offset + i < len(cat_p) else None
                result.append(row)
            _apply_seasonal_variation(result, df)
            for r in result:
                r["profitability"] = _clip(r["profitability"])
                if "profitability_arima" in r and r["profitability_arima"] is not None:
                    r["profitability_arima"] = _clip(r["profitability_arima"])
                if "profitability_catboost" in r and r["profitability_catboost"] is not None:
                    r["profitability_catboost"] = _clip(r["profitability_catboost"])
            return result

        if model_type == "arima":
            series = df.set_index("period")["profitability"]
            preds = forecast_arima(series, total_steps)
            if not preds:
                preds = [float(df["profitability"].iloc[-1])] * total_steps
            result = _build_result(preds)
            return {"model": "arima", "predictions": result, "metrics": {}}
        if model_type == "catboost":
            preds = forecast_catboost(df, total_steps, last_period)
            if not preds:
                preds = [float(df["profitability"].iloc[-1])] * total_steps
            result = _build_result(preds)
            return {"model": "catboost", "predictions": result, "metrics": {}}
        arima, cat, ensemble = forecast_ensemble(df, total_steps, last_period)
        n = total_steps
        last_val = float(df["profitability"].iloc[-1])
        arima = (arima + [arima[-1] if arima else last_val] * (n - len(arima)))[:n] if arima else [last_val] * n
        cat = (cat + [cat[-1] if cat else last_val] * (n - len(cat)))[:n] if cat else [last_val] * n
        if len(ensemble) < n:
            ensemble = (ensemble + [ensemble[-1] if ensemble else last_val] * (n - len(ensemble)))[:n]
        result = _build_result(ensemble, with_components=True, arima_p=arima, cat_p=cat)
        return {"model": "ensemble", "predictions": result, "metrics": {}}
    except Exception:
        naive = _naive_forecast(rows_list, horizon, last_period)
        _apply_forecast_periods(naive, first_show_ts, horizon)
        return {"model": "naive", "predictions": naive, "metrics": {}, "note": "Ошибка модели — выдан упрощённый прогноз."}


def _next_period(last: pd.Timestamp, offset: int) -> str:
    m = last.month + offset
    y = last.year
    while m > 12:
        m -= 12
        y += 1
    return f"{y}-{m:02d}"


def _first_forecast_period_from_today() -> pd.Timestamp:
    """Первый месяц прогноза = следующий календарный месяц от сегодня."""
    from datetime import date
    today = date.today()
    y = today.year
    m = today.month + 1
    if m > 12:
        m -= 12
        y += 1
    return pd.Timestamp(year=y, month=m, day=1)


def _period_to_str(ts: pd.Timestamp) -> str:
    return f"{ts.year}-{ts.month:02d}"


def _seasonal_adjustment_by_month(df: pd.DataFrame) -> dict[int, float]:
    """Среднее отклонение рентабельности по номеру месяца от общей средней (1–12). Для добавки сезонности к прогнозу."""
    if df.empty or "profitability" not in df.columns or "month_num" not in df.columns:
        return {}
    global_mean = df["profitability"].mean()
    by_month = df.groupby(df["period"].dt.month)["profitability"].mean()
    return {int(m): float(by_month[m] - global_mean) for m in by_month.index}


def _apply_seasonal_variation(predictions: list[dict], df: pd.DataFrame) -> None:
    """Добавляет сезонную вариацию по месяцам из истории (чтобы не было одной и той же цифры)."""
    adj = _seasonal_adjustment_by_month(df)
    if not adj:
        return
    for i, row in enumerate(predictions):
        period_str = row.get("period", "")
        try:
            month = int(period_str.split("-")[1])
            delta = adj.get(month, 0.0)
            row["profitability"] = row["profitability"] + delta * 0.85  # сезонность по истории
        except (IndexError, ValueError):
            pass
