# EcomProfit Guard — ML forecasting (facade over app.services.forecast)
from __future__ import annotations

from app.services.forecast.constants import (
    MAX_TRAIN_MONTHS,
    MIN_HISTORY_FOR_FULL,
    PROFITABILITY_DISPLAY_CLIP,
    WINSORIZE_HIGH,
    WINSORIZE_LOW,
)
from app.services.forecast.data import metric_df as _metric_df
from app.services.forecast.features import build_features
from app.services.forecast.models_arima import forecast_arima
from app.services.forecast.models_gbdt import forecast_catboost, forecast_lightgbm
from app.services.forecast.ensemble import forecast_ensemble
from app.services.forecast.naive import apply_forecast_periods as _apply_forecast_periods
from app.services.forecast.naive import naive_forecast as _naive_forecast
from app.services.forecast.periods import advance_month as _advance_month
from app.services.forecast.periods import first_forecast_period_from_today as _first_forecast_period_from_today
from app.services.forecast.periods import next_period_str as _next_period
from app.services.forecast.periods import period_to_str as _period_to_str
from app.services.forecast.run import run_forecast
from app.services.forecast.seasonal import apply_seasonal_variation as _apply_seasonal_variation
from app.services.forecast.seasonal import seasonal_adjustment_by_month as _seasonal_adjustment_by_month

__all__ = [
    "PROFITABILITY_DISPLAY_CLIP",
    "WINSORIZE_LOW",
    "WINSORIZE_HIGH",
    "MAX_TRAIN_MONTHS",
    "MIN_HISTORY_FOR_FULL",
    "_metric_df",
    "build_features",
    "forecast_arima",
    "forecast_catboost",
    "forecast_lightgbm",
    "forecast_ensemble",
    "_naive_forecast",
    "_apply_forecast_periods",
    "_advance_month",
    "_first_forecast_period_from_today",
    "_next_period",
    "_period_to_str",
    "_apply_seasonal_variation",
    "_seasonal_adjustment_by_month",
    "run_forecast",
]
