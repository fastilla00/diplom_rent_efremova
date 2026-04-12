# EcomProfit Guard — alert schemas
from datetime import datetime
from pydantic import BaseModel


class AlertOut(BaseModel):
    id: int
    alert_type: str
    severity: str
    title: str
    message: str | None
    recommendation: str | None
    entity_type: str | None
    entity_id: str | None
    value: float | None
    threshold: float | None
    created_at: datetime
    read_at: datetime | None

    class Config:
        from_attributes = True
