# EcomProfit Guard — analytics schemas
from decimal import Decimal
from pydantic import BaseModel


class PeriodRow(BaseModel):
    period: str
    revenue: Decimal
    costs: Decimal
    profit: Decimal
    profitability_pct: float | None
    count: int | None = None


class GroupRow(BaseModel):
    name: str
    revenue: Decimal
    costs: Decimal
    profit: Decimal
    profitability_pct: float | None
    count: int | None = None


class AnalyticsOut(BaseModel):
    by_period: list[PeriodRow]
    by_project: list[GroupRow]
    by_client: list[GroupRow]
    by_specialist: list[GroupRow]
    by_department: list[GroupRow]
