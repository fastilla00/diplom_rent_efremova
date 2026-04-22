from decimal import Decimal

import pandas as pd

from app.models.metric import Metric
from app.services import forecast_ml
from app.services.forecast import metrics as forecast_metrics


def _make_metric(month: int, revenue: int, costs: int) -> Metric:
    return Metric(
        project_id=1,
        year=2025,
        month=month,
        revenue=Decimal(str(revenue)),
        costs=Decimal(str(costs)),
    )


def test_build_features_creates_trend_and_calendar_columns():
    rows = [
        _make_metric(1, 1000, 900),
        _make_metric(2, 1100, 960),
        _make_metric(3, 1200, 1000),
        _make_metric(4, 1300, 1040),
        _make_metric(5, 1400, 1080),
        _make_metric(6, 1500, 1120),
    ]
    df = forecast_ml._metric_df(rows)
    features = forecast_ml.build_features(df)

    assert not features.empty
    # Ключевые ML-признаки для определения тренда и сезонности
    for col in ("lag_1", "lag_7", "rolling_3", "rolling_std_6", "trend_6", "month_num", "sin_month", "cos_month"):
        assert col in features.columns

    # Для монотонно растущей рентабельности наклон тренда должен быть неотрицательным
    assert float(features["trend_6"].iloc[-1]) >= 0


def test_mae_wape_helpers():
    import numpy as np

    yt = np.array([10.0, -5.0, 3.0])
    yp = np.array([12.0, -4.0, 0.0])
    assert forecast_metrics.mae(yt, yp) > 0
    w = forecast_metrics.wape(yt, yp)
    assert w is not None and w > 0
    assert forecast_metrics.wape(np.array([0.0, 0.0]), yp) is None


def test_naive_forecast_repeats_last_profitability():
    rows = [{"profitability": 12.5}, {"profitability": 13.0}]
    last_period = pd.Timestamp(year=2025, month=6, day=1)

    preds = forecast_ml._naive_forecast(rows, horizon=3, last_period=last_period)

    assert len(preds) == 3
    assert [p["profitability"] for p in preds] == [13.0, 13.0, 13.0]
    assert [p["period"] for p in preds] == ["2025-07", "2025-08", "2025-09"]


def test_forecast_ensemble_uses_equal_weights(monkeypatch):
    # Фиксируем выходы источников, чтобы проверить формулу ансамбля 0.5/0.5
    import app.services.forecast.ensemble as ensemble_mod

    monkeypatch.setattr(ensemble_mod, "forecast_arima", lambda series, horizon: [10.0, 20.0])
    monkeypatch.setattr(ensemble_mod, "forecast_catboost", lambda df, horizon, last_period: [30.0, 50.0])

    df = pd.DataFrame(
        {
            "period": pd.to_datetime(["2025-01-01", "2025-02-01"]),
            "profitability": [8.0, 9.0],
            "revenue": [1000.0, 1000.0],
            "costs": [920.0, 910.0],
        }
    )
    last_period = pd.Timestamp(year=2025, month=2, day=1)

    arima, cat, ensemble = ensemble_mod.forecast_ensemble(df, horizon=2, last_period=last_period)

    assert arima == [10.0, 20.0]
    assert cat == [30.0, 50.0]
    assert ensemble == [20.0, 35.0]


def test_forecast_ensemble_falls_back_to_last_value_when_models_fail(monkeypatch):
    import app.services.forecast.ensemble as ensemble_mod

    monkeypatch.setattr(ensemble_mod, "forecast_arima", lambda series, horizon: [])
    monkeypatch.setattr(ensemble_mod, "forecast_catboost", lambda df, horizon, last_period: [])

    df = pd.DataFrame(
        {
            "period": pd.to_datetime(["2025-01-01", "2025-02-01", "2025-03-01"]),
            "profitability": [8.0, 9.0, 11.0],
            "revenue": [1000.0, 1000.0, 1000.0],
            "costs": [920.0, 910.0, 890.0],
        }
    )
    last_period = pd.Timestamp(year=2025, month=3, day=1)

    arima, cat, ensemble = ensemble_mod.forecast_ensemble(df, horizon=3, last_period=last_period)

    assert arima == [11.0, 11.0, 11.0]
    assert cat == [11.0, 11.0, 11.0]
    assert ensemble == [11.0, 11.0, 11.0]
