# EcomProfit Guard — forecast schemas
from pydantic import BaseModel


class ForecastRequest(BaseModel):
    horizon_months: int = 6
    model_type: str = "ensemble"


class PredictionPoint(BaseModel):
    month: int
    period: str
    profitability: float | None = None
    profitability_arima: float | None = None
    profitability_catboost: float | None = None


class ForecastResponse(BaseModel):
    model: str
    predictions: list[PredictionPoint]
    metrics: dict = {}
    note: str | None = None
