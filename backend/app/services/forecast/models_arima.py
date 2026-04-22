"""ARIMA / SARIMAX forecasts on a monthly profitability series."""
from __future__ import annotations

import warnings

import pandas as pd
from statsmodels.tools.sm_exceptions import ConvergenceWarning
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller

from app.services.forecast.constants import MIN_SARIMAX_MONTHS


def forecast_arima(series: pd.Series, horizon: int) -> list[float]:
    if len(series) < 4 or horizon < 1:
        return []
    try:
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


def forecast_sarimax(series: pd.Series, horizon: int) -> list[float]:
    """Seasonal ARIMA with m=12 when history is long enough; else delegates to ARIMA."""
    if len(series) < 4 or horizon < 1:
        return []
    s = series.dropna()
    if len(s) < MIN_SARIMAX_MONTHS:
        return forecast_arima(series, horizon)
    try:
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            warnings.simplefilter("ignore", UserWarning)
            best_aic, best_pred = None, None
            # Small seasonal grid
            candidates = [
                ((1, 1, 1), (1, 0, 1, 12)),
                ((1, 0, 1), (1, 0, 1, 12)),
                ((1, 1, 0), (1, 0, 0, 12)),
                ((0, 1, 1), (0, 0, 1, 12)),
            ]
            for order, seasonal_order in candidates:
                try:
                    model = SARIMAX(
                        s,
                        order=order,
                        seasonal_order=seasonal_order,
                        enforce_stationarity=False,
                        enforce_invertibility=False,
                    )
                    fit = model.fit(disp=False)
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
    return forecast_arima(series, horizon)


def arima_one_step_train_predict(train: pd.Series) -> float | None:
    """Fit best ARIMA on train and return one-step ahead forecast."""
    p = forecast_arima(train, 1)
    return p[0] if p else None
