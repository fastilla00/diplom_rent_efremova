# EcomProfit Guard — dashboard schemas
from decimal import Decimal
from pydantic import BaseModel


class DashboardSummary(BaseModel):
    revenue: Decimal
    costs: Decimal
    profit: Decimal
    profitability_pct: float | None
    unique_clients: int
    unique_specialists: int


class TopItem(BaseModel):
    name: str
    value: Decimal
    count: int | None = None


class DashboardOut(BaseModel):
    summary: DashboardSummary
    top_projects: list[TopItem]
    top_specialists: list[TopItem]
    by_department: list[TopItem]
    period_start: str
    period_end: str
