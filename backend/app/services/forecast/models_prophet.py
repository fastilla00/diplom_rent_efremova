"""Prophet forecast for monthly profitability."""
from __future__ import annotations

import pandas as pd

from app.services.forecast.constants import MIN_PROPHET_MONTHS
from app.services.forecast.models_arima import forecast_arima


def forecast_prophet(series: pd.Series, horizon: int, last_period: pd.Timestamp) -> list[float]:
    if len(series) < MIN_PROPHET_MONTHS or horizon < 1:
        return forecast_arima(series, horizon)
    try:
        from prophet import Prophet

        idx = series.index
        df_p = pd.DataFrame({"ds": pd.to_datetime(idx), "y": series.values.astype(float)})
        m = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            seasonality_mode="multiplicative",
        )
        m.fit(df_p)
        future = m.make_future_dataframe(periods=horizon, freq="MS", include_history=False)
        fcst = m.predict(future)
        return [float(x) for x in fcst["yhat"].values]
    except Exception:
        return forecast_arima(series, horizon)
