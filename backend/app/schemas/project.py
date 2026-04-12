# EcomProfit Guard — project schemas
from datetime import datetime
from pydantic import BaseModel


class ProjectIntegrationCreate(BaseModel):
    spreadsheet_url: str
    sheet_acts: str = "Акты"   # лист с ДОХОДАМИ (выручка, акты — приходящие деньги)
    sheet_costs: str = "Затраты"  # лист с РАСХОДАМИ (траты, платежи — уходящие деньги)
    sheet_specialists: str = "TL"
    sheet_metrics: str = "Метрики"


class ProjectCreate(BaseModel):
    name: str
    integration: ProjectIntegrationCreate | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    integration: ProjectIntegrationCreate | None = None


class ProjectIntegrationOut(BaseModel):
    spreadsheet_id: str
    sheet_acts: str
    sheet_costs: str
    sheet_specialists: str
    sheet_metrics: str
    last_sync_at: datetime | None

    class Config:
        from_attributes = True


class ProjectOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    integration: ProjectIntegrationOut | None = None

    class Config:
        from_attributes = True
